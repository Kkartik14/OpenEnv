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
- [END]   score=<float>

All reward and score values are strictly in (0.10, 0.90).
"""

import json
import math
import os
import re
import sys
import textwrap
import traceback

from openai import OpenAI

from sre_incident_env import SREIncidentAction, SREIncidentEnvironment

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

BENCHMARK = "sre_incident_env"
TASKS = [
    {"task": "easy", "scenario_id": "e1_auth_oom", "label": "single_service_failure"},
    {"task": "medium", "scenario_id": "m1_postgres_pool", "label": "cascading_failure"},
    {"task": "hard", "scenario_id": "h1_tls_cert_expiry", "label": "complex_failure"},
]

TEMPERATURE = 0.3
MAX_TOKENS = 512
SUCCESS_THRESHOLD = 0.5


def clamp_reward(r):
    if r is None or not isinstance(r, (int, float)) or math.isnan(r) or math.isinf(r):
        return 0.10
    return round(max(0.10, min(0.90, float(r))), 2)


def sanitize(s):
    """Remove newlines and control characters so [STEP] stays on one line."""
    return str(s).replace("\n", " ").replace("\r", "")[:200]


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
    err = "null" if error is None else sanitize(error)
    d = "true" if done else "false"
    r = clamp_reward(reward)
    print(
        f"[STEP] step={step} action={sanitize(action_str)} reward={r:.2f} "
        f"done={d} error={err}",
        flush=True,
    )


def log_end(success: bool, steps: int, rewards: list):
    s = "true" if success else "false"
    r_str = ",".join(f"{clamp_reward(r):.2f}" for r in rewards)
    print(f"[END] success={s} steps={steps} rewards={r_str}", flush=True)


def log_task_score(score: float):
    print(f"[END] score={clamp_reward(score):.2f}", flush=True)


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

    env = SREIncidentEnvironment()

    log_start(task=label, env=BENCHMARK, model=MODEL_NAME)

    rewards = []
    last_error = None
    score = 0.10

    try:
        obs = env.reset(task=task, scenario_id=scenario_id, seed=42)
        max_steps = obs.max_steps
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(obs)},
        ]

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
                r = clamp_reward(0.0)
                log_step(step_num, "llm_error", r, False, last_error)
                rewards.append(r)
                continue

            try:
                action = parse_action(raw_output)
                last_error = None
            except Exception:
                action = SREIncidentAction(
                    action_type="query_logs",
                    target_service="api-gateway",
                    params={"severity": "ERROR"},
                )
                last_error = "parse_error"

            action_str = f"{action.action_type}({action.target_service or ''})"

            obs = env.step(action)
            reward = clamp_reward(obs.reward)
            rewards.append(reward)

            log_step(step_num, action_str, reward, obs.done, last_error)
            last_error = None

            messages.append({"role": "assistant", "content": raw_output})
            messages.append({"role": "user", "content": build_user_message(obs)})

            if obs.done:
                break

        score = rewards[-1] if rewards else 0.10
        score = clamp_reward(score)

    except Exception:
        traceback.print_exc(file=sys.stderr)
    finally:
        success = score >= SUCCESS_THRESHOLD
        log_end(success=success, steps=len(rewards), rewards=rewards)
        log_task_score(score)

    return score


def main():
    for task_cfg in TASKS:
        run_episode(task_cfg)


if __name__ == "__main__":
    main()
