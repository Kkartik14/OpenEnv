# SRE Incident Response Environment

An [OpenEnv](https://github.com/meta-pytorch/OpenEnv) environment where AI agents triage production incidents in a simulated microservice architecture — reading logs, checking metrics, tracing requests, diagnosing root causes, and applying remediations.

**Live Space:** [kartikg1474-sre-incident-env.hf.space](https://kartikg1474-sre-incident-env.hf.space)

## Motivation

Site Reliability Engineering (SRE) incident response is a critical, high-stakes task performed by engineering teams worldwide. When production systems fail, engineers must rapidly:

1. Assess system health across multiple services
2. Read and correlate logs from different sources
3. Identify the root cause among cascading symptoms
4. Apply the correct remediation under time pressure

This environment models that workflow as an RL environment. An agent is paged for an incident, investigates through structured actions, and is scored on diagnostic accuracy, remediation correctness, and investigation efficiency.

## Architecture

The simulated system is an 8-service microservice architecture:

| Service | Role |
|---|---|
| `api-gateway` | Entry point, routes requests downstream |
| `auth-service` | Authentication, JWT token management |
| `user-service` | User profiles, preferences |
| `order-service` | Order processing, workflow management |
| `payment-service` | Payment processing, transactions |
| `notification-service` | Email/SMS/push notifications |
| `postgres-db` | Primary relational database |
| `redis-cache` | Caching layer |

## Action Space

The agent can take 7 types of actions, submitted as structured JSON:

| Action | Description | Example |
|---|---|---|
| `query_logs` | Fetch logs from a service, filtered by severity | `{"action_type":"query_logs","target_service":"auth-service","params":{"severity":"ERROR"}}` |
| `check_metrics` | Get CPU, memory, latency, error rate, etc. | `{"action_type":"check_metrics","target_service":"postgres-db"}` |
| `trace_request` | Follow a request ID across services | `{"action_type":"trace_request","params":{"request_id":"req-a001"}}` |
| `check_deployments` | View recent deployment history | `{"action_type":"check_deployments","target_service":"auth-service"}` |
| `run_health_check` | Ping a service for status | `{"action_type":"run_health_check","target_service":"redis-cache"}` |
| `diagnose` | Submit root cause diagnosis | `{"action_type":"diagnose","params":{"root_cause":"memory_leak","affected_service":"auth-service","explanation":"..."}}` |
| `remediate` | Apply a fix (ends episode) | `{"action_type":"remediate","params":{"action":"rollback","target":"auth-service"}}` |

**Valid root causes:** `memory_leak`, `misconfiguration`, `missing_config`, `connection_pool_exhaustion`, `performance_degradation`, `cache_eviction`, `certificate_expiry`, `dns_resolution_failure`, `race_condition`

**Valid remediations:** `restart`, `rollback`, `scale_up`, `update_config`, `flush_cache`, `failover`

## Observation Space

After each action, the agent receives:

| Field | Type | Description |
|---|---|---|
| `done` | `bool` | Whether the episode has ended |
| `reward` | `float` | Reward for this step |
| `system_status` | `dict` | Health dashboard of all 8 services |
| `active_alerts` | `list` | Currently firing alerts |
| `action_result` | `str` | Formatted text output of the action (logs, metrics, traces) |
| `message` | `str` | Feedback on the action taken |
| `step_number` | `int` | Current step |
| `max_steps` | `int` | Maximum steps allowed |
| `available_actions` | `list` | Valid action types |
| `diagnosis_submitted` | `bool` | Whether a diagnosis has been locked in |
| `incident_summary` | `str` | High-level incident description |

## Tasks (Easy → Medium → Hard)

### Task 1: Single Service Failure (Easy)
One service has an obvious failure with clear log evidence. Max 15 steps.

| Scenario | Root Cause | Service |
|---|---|---|
| `e1_auth_oom` | Memory leak after bad deployment | auth-service |
| `e2_redis_config` | Wrong port in Redis configuration | redis-cache |
| `e3_notification_envvar` | Missing SMTP_API_KEY env variable | notification-service |

### Task 2: Cascading Failure (Medium)
A root cause in one service propagates to 2-3 others. Requires correlating timestamps across services. Max 20 steps.

| Scenario | Root Cause | Origin Service |
|---|---|---|
| `m1_postgres_pool` | Database connection pool exhaustion | postgres-db |
| `m2_auth_slow_cascade` | Auth-service slow queries causing gateway timeouts | auth-service |
| `m3_redis_eviction_cascade` | Cache eviction storm overwhelming the database | redis-cache |

### Task 3: Complex Failure with Red Herrings (Hard)
Multi-factor incidents with misleading signals that must be filtered out. Max 25 steps.

| Scenario | Root Cause | Red Herring |
|---|---|---|
| `h1_tls_cert_expiry` | Expired mTLS certificate on api-gateway | Recent user-service deploy (benign) |
| `h2_dns_retry_storm` | DNS resolution failures causing payment retry storm | Notification queue backlog (normal holiday traffic) |
| `h3_race_condition_deploy` | Race condition in new order-service deployment | api-gateway memory spike (normal GC) and redis evictions (routine TTL) |

## Reward Function

The reward uses a 4-layer scoring stack (0.0–1.0):

### Layer 1: Verifier — Terminal Reward (up to 0.70)
| Check | Points |
|---|---|
| Correct root cause identified | 0.35 |
| Correct affected service identified | 0.15 |
| Correct remediation applied | 0.20 |

### Layer 2: Pass/Fail Checks — Penalties
| Violation | Penalty |
|---|---|
| Remediated without diagnosing first | -0.10 |
| Repeated exact same action | -0.01 each |

### Layer 3: Rubric — Quality Bonuses (up to 0.30)
| Criterion | Bonus |
|---|---|
| Step efficiency (completed within expected steps) | up to 0.10 |
| Evidence gathering (investigated relevant services) | up to 0.10 |
| Systematic investigation (checked ≥2 services) | 0.05 |
| No mistakes (zero penalties) | 0.05 |

### Layer 4: Per-Step Shaping Rewards
Small dense rewards (+0.01 to +0.03) for productive investigation actions, providing gradient signal throughout the trajectory.

## Baseline Performance

Using `Qwen/Qwen2.5-72B-Instruct` via the inference script:

| Task | Difficulty | Score |
|---|---|---|
| `single_service_failure` | Easy | ~0.90 |
| `cascading_failure` | Medium | ~0.70 |
| `complex_failure` | Hard | ~0.40 |

## Setup & Usage

### Install

```bash
pip install openenv-core
git clone https://github.com/Kkartik14/OpenEnv.git
cd OpenEnv
pip install -e .
```

### Run Locally

```bash
# Start the server
uvicorn sre_incident_env.server.app:app --host 0.0.0.0 --port 7860

# Or with uv
uv run server
```

### Docker

```bash
docker build -t sre-incident-env .
docker run -p 7860:7860 sre-incident-env
```

### Run Inference

```bash
export HF_TOKEN=<your-token>
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
python inference.py
```

### Validate

```bash
# Local structure
openenv validate .

# Running server
openenv validate --url http://localhost:7860
```

### Connect via Client

```python
from sre_incident_env import SREIncidentAction, SREIncidentEnvironment

env = SREIncidentEnvironment()
obs = env.reset(task="easy", scenario_id="e1_auth_oom", seed=42)
print(obs.action_result)

obs = env.step(SREIncidentAction(
    action_type="query_logs",
    target_service="auth-service",
    params={"severity": "ERROR"}
))
print(obs.action_result)
```

## OpenEnv Spec Compliance

- Typed Pydantic models inheriting from `openenv.core.env_server.{Action, Observation, State}`
- Environment inherits from `openenv.core.env_server.Environment`
- FastAPI app via `create_fastapi_app()`
- `openenv validate` passes (6/6 criteria, all 4 deployment modes)
- `openenv.yaml` metadata included
- Dockerfile deploys to HF Spaces
