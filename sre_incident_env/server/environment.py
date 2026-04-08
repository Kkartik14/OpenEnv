"""
Core SRE Incident Response Environment.

Implements reset(), step(), and state for the OpenEnv spec.

Reward design:
  Every step returns a meaningful reward in (0.10, 0.90).
  The terminal step uses a trajectory grader that considers the full
  episode: diagnosis accuracy, remediation correctness, investigation
  quality, efficiency, and catastrophic-failure penalties.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from openenv.core.env_server import Environment

from ..models import SREIncidentAction, SREIncidentObservation, SREIncidentState
from .scenarios import ALL_SCENARIO_IDS, SCENARIOS, SERVICES, VALID_REMEDIATIONS

AVAILABLE_ACTIONS = [
    "query_logs(target_service, params={severity})",
    "check_metrics(target_service)",
    "trace_request(params={request_id})",
    "check_deployments(target_service)",
    "run_health_check(target_service)",
    "diagnose(params={root_cause, affected_service, explanation})",
    "remediate(params={action, target})",
]

TASK_NAME_TO_DIFFICULTY: Dict[str, str] = {
    "single_service_failure": "easy",
    "cascading_failure": "medium",
    "complex_failure": "hard",
    "easy": "easy",
    "medium": "medium",
    "hard": "hard",
}

# Per-step reward tiers — every action gets a score the agent can learn from
REWARD_EXCELLENT = 0.85       # investigated the right service with best tool
REWARD_GOOD = 0.65            # investigated a relevant service
REWARD_NEUTRAL = 0.45         # investigated an irrelevant but valid service
REWARD_POOR = 0.25            # wasted step (no request_id, health check on healthy svc)
REWARD_BAD = 0.15             # repeated action or invalid input
REWARD_CATASTROPHIC = 0.10    # remediated without diagnosing first


def _clamp(r: float) -> float:
    return round(max(0.10, min(0.90, r)), 2)


class SREIncidentEnvironment(
    Environment[SREIncidentAction, SREIncidentObservation, SREIncidentState]
):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._state = SREIncidentState()
        self._scenario: Optional[Dict[str, Any]] = None
        self._base_time: Optional[datetime] = None
        self._actions_taken: List[Dict[str, Any]] = []
        self._services_investigated: Set[str] = set()
        self._diagnosis: Optional[Dict[str, str]] = None
        self._remediation: Optional[Dict[str, str]] = None
        self._step_rewards: List[float] = []
        self._step_categories: List[str] = []

    # ------------------------------------------------------------------
    # OpenEnv interface
    # ------------------------------------------------------------------

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task: str = "easy",
        scenario_id: Optional[str] = None,
        **kwargs,
    ) -> SREIncidentObservation:
        if seed is not None:
            random.seed(seed)

        if scenario_id and scenario_id in ALL_SCENARIO_IDS:
            self._scenario = ALL_SCENARIO_IDS[scenario_id]
        else:
            difficulty = TASK_NAME_TO_DIFFICULTY.get(task, "easy")
            self._scenario = random.choice(SCENARIOS[difficulty])

        self._base_time = datetime.now(timezone.utc)
        self._actions_taken = []
        self._services_investigated = set()
        self._diagnosis = None
        self._remediation = None
        self._step_rewards = []
        self._step_categories = []

        self._state = SREIncidentState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            task_name=self._scenario["task_name"],
            difficulty=self._scenario["difficulty"],
            scenario_id=self._scenario["id"],
            max_steps=self._scenario["max_steps"],
            diagnosed=False,
            remediated=False,
        )

        status_text = self._format_system_status()
        alerts_text = self._format_alerts()
        initial_result = (
            f"=== INCIDENT REPORT ===\n\n"
            f"{self._scenario['description']}\n\n"
            f"{status_text}\n\n"
            f"{alerts_text}\n\n"
            f"You have {self._scenario['max_steps']} steps to investigate and resolve this incident.\n"
            f"Available actions: query_logs, check_metrics, trace_request, "
            f"check_deployments, run_health_check, diagnose, remediate"
        )

        return SREIncidentObservation(
            done=False,
            reward=None,
            system_status=self._scenario["service_states"],
            active_alerts=self._scenario["alerts"],
            action_result=initial_result,
            message="Incident assigned to you. Begin investigation.",
            step_number=0,
            max_steps=self._scenario["max_steps"],
            available_actions=AVAILABLE_ACTIONS,
            diagnosis_submitted=False,
            incident_summary=self._scenario["description"],
        )

    def step(
        self,
        action: SREIncidentAction,
        timeout_s: Optional[float] = None,
        **kwargs,
    ) -> SREIncidentObservation:
        self._state.step_count += 1
        step_num = self._state.step_count
        max_steps = self._scenario["max_steps"]

        action_key = self._action_signature(action)
        is_repeat = action_key in [
            self._action_signature_from_dict(a) for a in self._actions_taken
        ]
        self._actions_taken.append(action.model_dump())

        result_text, step_reward, message, category = self._process_action(
            action, is_repeat
        )

        done = False
        if self._remediation is not None:
            done = True
        elif step_num >= max_steps:
            done = True
            message = "Maximum steps reached. Episode ending."

        if done:
            reward = self._trajectory_grade()
        else:
            reward = _clamp(step_reward)

        self._step_rewards.append(reward)
        self._step_categories.append(category)

        return SREIncidentObservation(
            done=done,
            reward=reward,
            system_status=self._scenario["service_states"],
            active_alerts=self._scenario["alerts"],
            action_result=result_text,
            message=message,
            step_number=step_num,
            max_steps=max_steps,
            available_actions=AVAILABLE_ACTIONS,
            diagnosis_submitted=self._diagnosis is not None,
            incident_summary=self._scenario["description"],
        )

    @property
    def state(self) -> SREIncidentState:
        return self._state

    # ------------------------------------------------------------------
    # Action processing — each returns (text, reward, message, category)
    # ------------------------------------------------------------------

    def _process_action(
        self, action: SREIncidentAction, is_repeat: bool
    ) -> Tuple[str, float, str, str]:
        atype = action.action_type.lower().strip()
        handlers = {
            "query_logs": self._handle_query_logs,
            "check_metrics": self._handle_check_metrics,
            "trace_request": self._handle_trace_request,
            "check_deployments": self._handle_check_deployments,
            "run_health_check": self._handle_run_health_check,
            "diagnose": self._handle_diagnose,
            "remediate": self._handle_remediate,
        }

        handler = handlers.get(atype)
        if handler is None:
            return (
                f"Unknown action type: '{atype}'. "
                f"Valid actions: {', '.join(handlers.keys())}",
                REWARD_BAD,
                "Invalid action. Please use a valid action type.",
                "invalid",
            )

        result_text, base_reward, message, category = handler(action)

        if is_repeat and atype not in ("diagnose", "remediate"):
            base_reward = REWARD_BAD
            category = "repeat"
            message += " (repeated action — penalty)"

        return result_text, base_reward, message, category

    def _handle_query_logs(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str, str]:
        service = action.target_service
        if not service or service not in SERVICES:
            return (
                f"Service '{service}' not found. Available: {', '.join(SERVICES)}",
                REWARD_BAD,
                "Invalid service name.",
                "invalid",
            )

        self._services_investigated.add(service)
        params = action.params or {}
        severity_filter = params.get("severity", "ALL").upper()

        scenario_logs = self._scenario.get("logs", {})
        service_logs = scenario_logs.get(service, [])

        if severity_filter != "ALL":
            service_logs = [
                l for l in service_logs if l["level"] == severity_filter
            ]

        if not service_logs:
            result = (
                f"=== Logs: {service} [severity: {severity_filter}] [last 30 min] ===\n\n"
                f"No notable log entries matching filter.\n"
                f"Service appears to be operating normally.\n"
            )
        else:
            lines = []
            for entry in sorted(service_logs, key=lambda x: x["offset_min"]):
                ts = self._offset_to_timestamp(entry["offset_min"])
                lines.append(f"[{ts}] {entry['level']:5s}  {entry['message']}")
            log_block = "\n\n".join(lines)
            result = (
                f"=== Logs: {service} [severity: {severity_filter}] [last 30 min] ===\n\n"
                f"{log_block}\n\n"
                f"--- {len(service_logs)} entries shown ---"
            )

        is_relevant = service in self._scenario.get("relevant_services", set())
        if is_relevant:
            return result, REWARD_EXCELLENT, f"Queried logs from {service}.", "excellent"
        return result, REWARD_NEUTRAL, f"Queried logs from {service}.", "neutral"

    def _handle_check_metrics(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str, str]:
        service = action.target_service
        if not service or service not in SERVICES:
            return (
                f"Service '{service}' not found. Available: {', '.join(SERVICES)}",
                REWARD_BAD,
                "Invalid service name.",
                "invalid",
            )

        self._services_investigated.add(service)
        metrics = self._scenario.get("metrics", {}).get(service, {})

        if not metrics:
            result = f"=== Metrics: {service} ===\n\nNo metrics available."
        else:
            lines = [f"=== Metrics: {service} ===\n"]
            for key, value in metrics.items():
                label = key.replace("_", " ").replace("pct", "%").title()
                if value is None:
                    display = "N/A (service unreachable)"
                elif isinstance(value, float):
                    display = f"{value:.1f}"
                else:
                    display = str(value)

                flag = ""
                if "error_rate" in key and isinstance(value, (int, float)) and value > 5:
                    flag = " [HIGH]"
                elif "cpu" in key and isinstance(value, (int, float)) and value > 85:
                    flag = " [CRITICAL]"
                elif "memory" in key and "pct" in key and isinstance(value, (int, float)) and value > 90:
                    flag = " [CRITICAL]"

                lines.append(f"  {label:40s} {display}{flag}")
            result = "\n".join(lines)

        is_relevant = service in self._scenario.get("relevant_services", set())
        if is_relevant:
            return result, REWARD_GOOD, f"Checked metrics for {service}.", "good"
        return result, REWARD_NEUTRAL, f"Checked metrics for {service}.", "neutral"

    def _handle_trace_request(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str, str]:
        params = action.params or {}
        request_id = params.get("request_id", "")

        traces = self._scenario.get("traces", {})
        if not request_id:
            available = list(traces.keys())
            if available:
                return (
                    f"No request_id specified. Available trace IDs from recent errors:\n"
                    f"  {', '.join(available)}",
                    REWARD_POOR,
                    "Provide a request_id in params to trace.",
                    "poor",
                )
            return "No traces available for this incident.", REWARD_POOR, "No traces found.", "poor"

        trace_spans = traces.get(request_id)
        if not trace_spans:
            available = list(traces.keys())
            hint = f" Available: {', '.join(available)}" if available else ""
            return (
                f"Trace '{request_id}' not found.{hint}",
                REWARD_POOR,
                "Trace ID not found.",
                "poor",
            )

        lines = [f"=== Trace: {request_id} ===\n"]
        for i, span in enumerate(trace_spans, 1):
            status = span.get("status_code", "???")
            dur = span.get("duration_ms")
            dur_str = f"{dur}ms" if dur is not None else "N/A"
            lines.append(
                f"  {i}. {span['service']:25s} duration={dur_str:>8s}  "
                f"status={status}\n     {span['detail']}"
            )
        result = "\n\n".join(lines)
        return result, REWARD_EXCELLENT, f"Traced request {request_id}.", "excellent"

    def _handle_check_deployments(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str, str]:
        service = action.target_service
        if not service or service not in SERVICES:
            return (
                f"Service '{service}' not found. Available: {', '.join(SERVICES)}",
                REWARD_BAD,
                "Invalid service name.",
                "invalid",
            )

        self._services_investigated.add(service)
        deployments = self._scenario.get("deployments", {}).get(service, [])

        if not deployments:
            result = f"=== Deployments: {service} ===\n\nNo deployment history available."
        else:
            lines = [f"=== Deployments: {service} ===\n"]
            for dep in deployments:
                ago = dep["deployed_minutes_ago"]
                if ago >= 1440:
                    ago_str = f"{ago // 1440} days ago"
                elif ago >= 60:
                    ago_str = f"{ago // 60}h {ago % 60}m ago"
                else:
                    ago_str = f"{ago} min ago"
                lines.append(
                    f"  Version: {dep['version']}  |  Deployed: {ago_str}  |  "
                    f"Status: {dep['status']}\n"
                    f"    Changes: {dep['changes']}\n"
                    f"    By: {dep['deployed_by']}"
                )
            result = "\n\n".join(lines)

        is_relevant = service in self._scenario.get("relevant_services", set())
        if is_relevant:
            return result, REWARD_GOOD, f"Checked deployment history for {service}.", "good"
        return result, REWARD_NEUTRAL, f"Checked deployment history for {service}.", "neutral"

    def _handle_run_health_check(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str, str]:
        service = action.target_service
        if not service or service not in SERVICES:
            return (
                f"Service '{service}' not found. Available: {', '.join(SERVICES)}",
                REWARD_BAD,
                "Invalid service name.",
                "invalid",
            )

        self._services_investigated.add(service)
        hc = self._scenario.get("health_checks", {}).get(service, {})

        status = hc.get("status", "unknown")
        resp_time = hc.get("response_time_ms")
        msg = hc.get("message", "")
        resp_str = f"{resp_time}ms" if resp_time is not None else "TIMEOUT"

        result = (
            f"=== Health Check: {service} ===\n\n"
            f"  Status:        {status.upper()}\n"
            f"  Response Time: {resp_str}\n"
            f"  Message:       {msg}"
        )

        is_relevant = service in self._scenario.get("relevant_services", set())
        if is_relevant:
            return result, REWARD_GOOD, f"Health check for {service}: {status}.", "good"
        return result, REWARD_POOR, f"Health check for {service}: {status}.", "poor"

    def _handle_diagnose(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str, str]:
        if self._diagnosis is not None:
            return (
                "Diagnosis already submitted. You cannot change your diagnosis.\n"
                f"Current diagnosis: root_cause={self._diagnosis['root_cause']}, "
                f"affected_service={self._diagnosis['affected_service']}",
                REWARD_BAD,
                "Diagnosis already locked in.",
                "repeat",
            )

        params = action.params or {}
        root_cause = params.get("root_cause", "unknown")
        affected_service = params.get("affected_service", "unknown")
        explanation = params.get("explanation", "")

        self._diagnosis = {
            "root_cause": root_cause,
            "affected_service": affected_service,
            "explanation": explanation,
        }
        self._state.diagnosed = True

        correct_rc = self._scenario["root_cause"]
        correct_svc = self._scenario["affected_service"]
        rc_correct = root_cause == correct_rc
        svc_correct = affected_service == correct_svc

        if rc_correct and svc_correct:
            reward, cat = REWARD_EXCELLENT, "excellent"
        elif rc_correct or svc_correct:
            reward, cat = REWARD_GOOD, "good"
        else:
            reward, cat = REWARD_POOR, "poor"

        result = (
            f"=== Diagnosis Submitted ===\n\n"
            f"  Root Cause:       {root_cause}\n"
            f"  Affected Service: {affected_service}\n"
            f"  Explanation:      {explanation}\n\n"
            f"Diagnosis locked. Now apply remediation with the 'remediate' action."
        )
        return result, reward, "Diagnosis submitted. Proceed to remediation.", cat

    def _handle_remediate(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str, str]:
        params = action.params or {}
        rem_action = params.get("action", "")
        rem_target = params.get("target", "")

        if rem_action not in VALID_REMEDIATIONS:
            return (
                f"Invalid remediation action: '{rem_action}'. "
                f"Valid actions: {', '.join(VALID_REMEDIATIONS)}",
                REWARD_BAD,
                "Invalid remediation action.",
                "invalid",
            )
        if rem_target not in SERVICES:
            return (
                f"Invalid target service: '{rem_target}'. "
                f"Available: {', '.join(SERVICES)}",
                REWARD_BAD,
                "Invalid target service.",
                "invalid",
            )

        no_diagnosis = self._diagnosis is None
        if no_diagnosis:
            message = "WARNING: Remediation applied without prior diagnosis (catastrophic penalty)."
            cat = "catastrophic"
        else:
            message = "Remediation applied."
            cat = "good"

        self._remediation = {"action": rem_action, "target": rem_target}
        self._state.remediated = True

        correct = self._scenario["correct_remediation"]
        correct_action = rem_action == correct["action"] and rem_target == correct["target"]

        if correct_action and not no_diagnosis:
            reward = REWARD_EXCELLENT
            cat = "excellent"
            result = (
                f"=== Remediation Applied ===\n\n"
                f"  Action: {rem_action}\n"
                f"  Target: {rem_target}\n\n"
                f"Remediation executed successfully. Monitoring for recovery..."
            )
        elif no_diagnosis:
            reward = REWARD_CATASTROPHIC
            result = (
                f"=== Remediation Applied ===\n\n"
                f"  Action: {rem_action}\n"
                f"  Target: {rem_target}\n\n"
                f"Remediation applied WITHOUT diagnosis. This is dangerous."
            )
        else:
            reward = REWARD_POOR
            result = (
                f"=== Remediation Applied ===\n\n"
                f"  Action: {rem_action}\n"
                f"  Target: {rem_target}\n\n"
                f"Remediation executed. Awaiting results..."
            )

        return result, reward, message, cat

    # ------------------------------------------------------------------
    # Trajectory grader
    # ------------------------------------------------------------------

    def _trajectory_grade(self) -> float:
        """Non-linear trajectory grader that adjusts the final score based on
        the full episode history: diagnosis accuracy, remediation correctness,
        investigation quality, efficiency, and catastrophic penalties."""

        if not self._step_rewards:
            return _clamp(0.10)

        mean_reward = sum(self._step_rewards) / len(self._step_rewards)

        # --- Catastrophic penalty: remediated without diagnosing ---
        catastrophic_count = self._step_categories.count("catastrophic")
        difficulty = self._scenario.get("difficulty", "easy")
        catastrophic_penalty = 0.0
        if catastrophic_count > 0:
            penalty_by_diff = {"easy": -0.30, "medium": -0.40, "hard": -0.50}
            catastrophic_penalty = penalty_by_diff.get(difficulty, -0.30)

        # --- Consistency bonus: >=60% of steps are good/excellent ---
        good_steps = sum(
            1 for c in self._step_categories if c in ("excellent", "good")
        )
        consistency_ratio = good_steps / len(self._step_categories)
        consistency_bonus = 0.0
        if consistency_ratio >= 0.60:
            bonus_by_diff = {"easy": 0.05, "medium": 0.08, "hard": 0.12}
            consistency_bonus = bonus_by_diff.get(difficulty, 0.05)

        # --- Efficiency bonus: solved within expected steps ---
        expected = self._scenario.get("expected_steps", 10)
        actual = self._state.step_count
        efficiency_bonus = 0.0
        if actual <= expected:
            efficiency_bonus = 0.05
        elif actual <= expected * 1.5:
            ratio = 1.0 - (actual - expected) / (expected * 0.5)
            efficiency_bonus = 0.05 * max(ratio, 0)

        # --- Evidence bonus: investigated relevant services ---
        relevant = self._scenario.get("relevant_services", set())
        evidence_bonus = 0.0
        if relevant:
            investigated = self._services_investigated & relevant
            evidence_bonus = 0.05 * (len(investigated) / len(relevant))

        score = mean_reward + catastrophic_penalty + consistency_bonus + efficiency_bonus + evidence_bonus

        return _clamp(score)

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _format_system_status(self) -> str:
        lines = ["=== SYSTEM STATUS ===\n"]
        for svc, info in self._scenario["service_states"].items():
            status = info["status"].upper()
            lat = info.get("latency_ms")
            lat_str = f"{lat}ms" if lat is not None else "N/A"
            err = info.get("error_rate_pct", 0)
            flag = ""
            if status == "DOWN":
                flag = " <<<<<"
            elif status == "DEGRADED":
                flag = " <<<"
            lines.append(
                f"  {svc:28s} {status:10s} latency={lat_str:>8s}  "
                f"errors={err:.1f}%{flag}"
            )
        return "\n".join(lines)

    def _format_alerts(self) -> str:
        alerts = self._scenario["alerts"]
        if not alerts:
            return "=== ACTIVE ALERTS ===\n\n  No active alerts."
        lines = ["=== ACTIVE ALERTS ===\n"]
        for a in alerts:
            sev = a["severity"].upper()
            lines.append(f"  [{sev:8s}] {a['service']:28s} {a['message']}")
        return "\n".join(lines)

    def _offset_to_timestamp(self, offset_min: int) -> str:
        ts = self._base_time + timedelta(minutes=offset_min)
        return ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _action_signature(action: SREIncidentAction) -> str:
        return f"{action.action_type}|{action.target_service}|{action.params}"

    @staticmethod
    def _action_signature_from_dict(d: Dict[str, Any]) -> str:
        return f"{d.get('action_type')}|{d.get('target_service')}|{d.get('params')}"
