"""
Core SRE Incident Response Environment.

Implements reset(), step(), and state for the OpenEnv spec.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

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


class SREIncidentEnvironment:
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._state = SREIncidentState()
        self._scenario: Optional[Dict[str, Any]] = None
        self._base_time: Optional[datetime] = None
        self._actions_taken: List[Dict[str, Any]] = []
        self._services_investigated: Set[str] = set()
        self._diagnosis: Optional[Dict[str, str]] = None
        self._remediation: Optional[Dict[str, str]] = None
        self._penalties: float = 0.0
        self._step_rewards: List[float] = []

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
            difficulty = task if task in SCENARIOS else "easy"
            self._scenario = random.choice(SCENARIOS[difficulty])

        self._base_time = datetime.now(timezone.utc)
        self._actions_taken = []
        self._services_investigated = set()
        self._diagnosis = None
        self._remediation = None
        self._penalties = 0.0
        self._step_rewards = []

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
        is_repeat = action_key in [self._action_signature_from_dict(a) for a in self._actions_taken]
        self._actions_taken.append(action.model_dump())

        result_text, step_reward, message = self._process_action(action, is_repeat)

        done = False
        if self._remediation is not None:
            done = True
        elif step_num >= max_steps:
            done = True
            message = "Maximum steps reached. Episode ending."

        if done:
            terminal_reward = self._calculate_terminal_reward()
            self._step_rewards.append(terminal_reward)
            reward = terminal_reward
        else:
            self._step_rewards.append(step_reward)
            reward = step_reward

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
    # Action processing
    # ------------------------------------------------------------------

    def _process_action(
        self, action: SREIncidentAction, is_repeat: bool
    ) -> Tuple[str, float, str]:
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
                0.0,
                "Invalid action. Please use a valid action type.",
            )

        result_text, base_reward, message = handler(action)

        if is_repeat and atype not in ("diagnose", "remediate"):
            self._penalties -= 0.01
            base_reward = max(base_reward - 0.01, -0.01)
            message += " (repeated action — small penalty)"

        return result_text, base_reward, message

    def _handle_query_logs(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str]:
        service = action.target_service
        if not service or service not in SERVICES:
            return (
                f"Service '{service}' not found. Available: {', '.join(SERVICES)}",
                0.0,
                "Invalid service name.",
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
        reward = 0.02 if is_relevant else 0.0
        return result, reward, f"Queried logs from {service}."

    def _handle_check_metrics(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str]:
        service = action.target_service
        if not service or service not in SERVICES:
            return (
                f"Service '{service}' not found. Available: {', '.join(SERVICES)}",
                0.0,
                "Invalid service name.",
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
        reward = 0.02 if is_relevant else 0.0
        return result, reward, f"Checked metrics for {service}."

    def _handle_trace_request(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str]:
        params = action.params or {}
        request_id = params.get("request_id", "")

        traces = self._scenario.get("traces", {})
        if not request_id:
            available = list(traces.keys())
            if available:
                return (
                    f"No request_id specified. Available trace IDs from recent errors:\n"
                    f"  {', '.join(available)}",
                    0.0,
                    "Provide a request_id in params to trace.",
                )
            return "No traces available for this incident.", 0.0, "No traces found."

        trace_spans = traces.get(request_id)
        if not trace_spans:
            available = list(traces.keys())
            hint = f" Available: {', '.join(available)}" if available else ""
            return (
                f"Trace '{request_id}' not found.{hint}",
                0.0,
                "Trace ID not found.",
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
        return result, 0.03, f"Traced request {request_id}."

    def _handle_check_deployments(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str]:
        service = action.target_service
        if not service or service not in SERVICES:
            return (
                f"Service '{service}' not found. Available: {', '.join(SERVICES)}",
                0.0,
                "Invalid service name.",
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
        reward = 0.01 if is_relevant else 0.0
        return result, reward, f"Checked deployment history for {service}."

    def _handle_run_health_check(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str]:
        service = action.target_service
        if not service or service not in SERVICES:
            return (
                f"Service '{service}' not found. Available: {', '.join(SERVICES)}",
                0.0,
                "Invalid service name.",
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
        reward = 0.01 if is_relevant else 0.0
        return result, reward, f"Health check for {service}: {status}."

    def _handle_diagnose(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str]:
        if self._diagnosis is not None:
            return (
                "Diagnosis already submitted. You cannot change your diagnosis.\n"
                f"Current diagnosis: root_cause={self._diagnosis['root_cause']}, "
                f"affected_service={self._diagnosis['affected_service']}",
                0.0,
                "Diagnosis already locked in.",
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

        result = (
            f"=== Diagnosis Submitted ===\n\n"
            f"  Root Cause:       {root_cause}\n"
            f"  Affected Service: {affected_service}\n"
            f"  Explanation:      {explanation}\n\n"
            f"Diagnosis locked. Now apply remediation with the 'remediate' action."
        )
        return result, 0.0, "Diagnosis submitted. Proceed to remediation."

    def _handle_remediate(
        self, action: SREIncidentAction
    ) -> Tuple[str, float, str]:
        params = action.params or {}
        rem_action = params.get("action", "")
        rem_target = params.get("target", "")

        if rem_action not in VALID_REMEDIATIONS:
            return (
                f"Invalid remediation action: '{rem_action}'. "
                f"Valid actions: {', '.join(VALID_REMEDIATIONS)}",
                0.0,
                "Invalid remediation action.",
            )
        if rem_target not in SERVICES:
            return (
                f"Invalid target service: '{rem_target}'. "
                f"Available: {', '.join(SERVICES)}",
                0.0,
                "Invalid target service.",
            )

        if self._diagnosis is None:
            self._penalties -= 0.10
            message = "WARNING: Remediation applied without prior diagnosis (penalty applied)."
        else:
            message = "Remediation applied."

        self._remediation = {"action": rem_action, "target": rem_target}
        self._state.remediated = True

        correct = self._scenario["correct_remediation"]
        if rem_action == correct["action"] and rem_target == correct["target"]:
            result = (
                f"=== Remediation Applied ===\n\n"
                f"  Action: {rem_action}\n"
                f"  Target: {rem_target}\n\n"
                f"Remediation executed successfully. Monitoring for recovery..."
            )
        else:
            result = (
                f"=== Remediation Applied ===\n\n"
                f"  Action: {rem_action}\n"
                f"  Target: {rem_target}\n\n"
                f"Remediation executed. Awaiting results..."
            )

        return result, 0.0, message

    # ------------------------------------------------------------------
    # Reward calculation
    # ------------------------------------------------------------------

    def _calculate_terminal_reward(self) -> float:
        reward = 0.0

        if self._diagnosis:
            if self._diagnosis["root_cause"] == self._scenario["root_cause"]:
                reward += 0.35
            if self._diagnosis["affected_service"] == self._scenario["affected_service"]:
                reward += 0.15

        if self._remediation:
            correct = self._scenario["correct_remediation"]
            if (
                self._remediation["action"] == correct["action"]
                and self._remediation["target"] == correct["target"]
            ):
                reward += 0.20

        reward += self._penalties

        expected = self._scenario.get("expected_steps", 10)
        actual = self._state.step_count
        if actual <= expected:
            reward += 0.10
        elif actual <= expected * 1.5:
            ratio = 1.0 - (actual - expected) / (expected * 0.5)
            reward += 0.10 * max(ratio, 0)

        relevant = self._scenario.get("relevant_services", set())
        if relevant:
            investigated_relevant = self._services_investigated & relevant
            evidence_ratio = len(investigated_relevant) / len(relevant)
            reward += 0.10 * evidence_ratio

        if len(self._services_investigated) >= 2:
            reward += 0.05

        if self._penalties == 0:
            reward += 0.05

        return round(max(0.0, min(1.0, reward)), 2)

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
