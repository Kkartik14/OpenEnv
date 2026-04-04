"""
Inference Script — SRE Incident Response Environment
=====================================================
MANDATORY
- Before submitting, ensure the following variables are defined:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

STDOUT FORMAT
- [START] task=<task_name> env=<benchmark> model=<model_name>
- [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
- [END]   success=<true|false> steps=<n> rewards=<r1,r2,...,rn>
"""

import json
import os
import re
import sys
import textwrap

from openai import OpenAI

from sre_incident_env import SREIncidentAction, SREIncidentEnvironment

API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")

BENCHMARK = "sre_incident_env"
TASKS = [
    {"task": "easy", "scenario_id": "e1_auth_oom", "label": "single_service_failure"},
    {"task": "medium", "scenario_id": "m1_postgres_pool", "label": "cascading_failure"},
    {"task": "hard", "scenario_id": "h1_tls_cert_expiry", "label": "complex_failure"},
]

MAX_STEPS_OVERRIDE = None
TEMPERATURE = 0.3
MAX_TOKENS = 512
SUCCESS_THRESHOLD = 0.5

SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert SRE engineer responding to a production incident in a
    microservice architecture. Your goal: identify the root cause and apply
    the correct remediation.

    ## Available Services
    api-gateway, auth-service, user-service, order-service, payment-service,
    notification-service, postgres-db, redis-cache

    ## Actions — respond with ONLY a JSON object, nothing else.

    Investigation actions:
      {"action_type":"query_logs","target_service":"<svc>","params":{"severity":"ERROR|WARN|INFO|ALL"}}
      {"action_type":"check_metrics","target_service":"<svc>"}
      {"action_type":"trace_request","params":{"request_id":"<id>"}}
      {"action_type":"check_deployments","target_service":"<svc>"}
      {"action_type":"run_health_check","target_service":"<svc>"}

    Resolution actions (diagnose BEFORE remediate):
      {"action_type":"diagnose","params":{"root_cause":"<cause>","affected_service":"<svc>","explanation":"<brief>"}}
      {"action_type":"remediate","params":{"action":"restart|rollback|scale_up|update_config|flush_cache|failover","target":"<svc>"}}

    Valid root causes: memory_leak, misconfiguration, missing_config,
    connection_pool_exhaustion, performance_degradation, cache_eviction,
    certificate_expiry, dns_resolution_failure, race_condition

    ## Strategy
    1. Read the system status and alerts carefully.
    2. Query logs/metrics from suspicious services.
    3. Correlate timestamps across services to find the root cause.
    4. Submit a diagnosis, then remediate.

    Respond with ONLY a valid JSON object. No markdown, no explanation.
""")


def log_start(task: str, env: str, model: str):
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action_str: str, reward: float, done: bool, error):
    err = "null" if error is None else str(error)
    d = "true" if done else "false"
    print(
        f"[STEP] step={step} action={action_str} reward={reward:.2f} "
        f"done={d} error={err}",
        flush=True,
    )


def log_end(success: bool, steps: int, rewards: list):
    s = "true" if success else "false"
    r_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={s} steps={steps} rewards={r_str}", flush=True)


def parse_action(text: str) -> SREIncidentAction:
    """Best-effort extraction of a JSON action from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    data = json.loads(text)
    return SREIncidentAction(**data)


def build_user_message(obs) -> str:
    """Format the observation into a clear prompt for the LLM."""
    parts = [obs.action_result, ""]

    if obs.diagnosis_submitted:
        parts.append("[Your diagnosis has been submitted. Now apply remediation.]")
    else:
        parts.append(
            f"[Step {obs.step_number}/{obs.max_steps}] "
            f"Choose your next action. Respond with JSON only."
        )

    return "\n".join(parts)


def run_episode(task_cfg: dict) -> float:
    task = task_cfg["task"]
    scenario_id = task_cfg["scenario_id"]
    label = task_cfg["label"]

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env = SREIncidentEnvironment()

    log_start(task=label, env=BENCHMARK, model=MODEL_NAME)

    obs = env.reset(task=task, scenario_id=scenario_id, seed=42)
    max_steps = MAX_STEPS_OVERRIDE or obs.max_steps
    rewards = []
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(obs)},
    ]

    last_error = None
    for step_num in range(1, max_steps + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            raw_output = response.choices[0].message.content or ""
        except Exception as e:
            raw_output = ""
            last_error = str(e)
            log_step(step_num, "llm_error", 0.0, False, last_error)
            rewards.append(0.0)
            continue

        try:
            action = parse_action(raw_output)
        except Exception:
            action = SREIncidentAction(
                action_type="query_logs",
                target_service="api-gateway",
                params={"severity": "ERROR"},
            )
            last_error = f"parse_error: {raw_output[:120]}"

        action_str = (
            f"{action.action_type}("
            f"{action.target_service or ''}"
            f"{', ' + json.dumps(action.params) if action.params else ''}"
            f")"
        )

        obs = env.step(action)
        reward = obs.reward if obs.reward is not None else 0.0
        rewards.append(reward)
        last_error = None

        log_step(step_num, action_str, reward, obs.done, last_error)

        messages.append({"role": "assistant", "content": raw_output})
        messages.append({"role": "user", "content": build_user_message(obs)})

        if obs.done:
            break

    final_reward = rewards[-1] if rewards else 0.0
    success = final_reward >= SUCCESS_THRESHOLD
    log_end(success=success, steps=len(rewards), rewards=rewards)

    return final_reward


def main():
    if not API_KEY:
        print("WARNING: No API key set. Set HF_TOKEN or API_KEY.", file=sys.stderr)

    results = {}
    for task_cfg in TASKS:
        score = run_episode(task_cfg)
        results[task_cfg["label"]] = score
        print(flush=True)

    print("\n=== SUMMARY ===", flush=True)
    for label, score in results.items():
        status = "PASS" if score >= SUCCESS_THRESHOLD else "FAIL"
        print(f"  {label:30s} {score:.2f}  [{status}]", flush=True)

    avg = sum(results.values()) / len(results) if results else 0
    print(f"\n  {'Average':30s} {avg:.2f}", flush=True)


if __name__ == "__main__":
    main()
