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
- [STEP]  step=<n> action=<action_str> reward=<float> done=<bool> error=<null|msg>
- [END]   success=<bool> steps=<n> reward=<float>
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
SUCCESS_THRESHOLD = 0.05


def clamp(r):
    if r is None or not isinstance(r, (int, float)) or math.isnan(r) or math.isinf(r):
        return 0.10
    return round(max(0.10, min(0.90, float(r))), 2)


def sanitize(s):
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


def parse_action(text: str) -> SREIncidentAction:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    data = json.loads(text)
    return SREIncidentAction(**data)


def build_user_message(obs) -> str:
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

    print(f"[START] task={label} env={BENCHMARK} model={MODEL_NAME}", flush=True)

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
                r = clamp(0.0)
                print(f"[STEP] step={step_num} action=llm_error reward={r:.2f} done=false error={sanitize(last_error)}", flush=True)
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
            reward = clamp(obs.reward)
            rewards.append(reward)

            err = "null" if last_error is None else sanitize(last_error)
            done = "true" if obs.done else "false"
            print(f"[STEP] step={step_num} action={sanitize(action_str)} reward={reward:.2f} done={done} error={err}", flush=True)
            last_error = None

            messages.append({"role": "assistant", "content": raw_output})
            messages.append({"role": "user", "content": build_user_message(obs)})

            if obs.done:
                break

        score = clamp(rewards[-1]) if rewards else 0.10

    except Exception:
        traceback.print_exc(file=sys.stderr)
    finally:
        success = "true" if score >= SUCCESS_THRESHOLD else "false"
        rewards_str = ",".join(f"{clamp(r):.2f}" for r in rewards) if rewards else "0.10"
        print(f"[END] success={success} steps={len(rewards)} reward={score:.2f} rewards={rewards_str}", flush=True)
        print(f"[END] score={score:.2f}", flush=True)

    return score


def main():
    for task_cfg in TASKS:
        run_episode(task_cfg)


if __name__ == "__main__":
    main()
