"""
All incident scenarios for the SRE Incident Response Environment.

9 scenarios total: 3 easy, 3 medium, 3 hard.
Each scenario is a self-contained snapshot of a broken production system
with pre-generated logs, metrics, traces, deployments, and ground truth.
"""

SERVICES = [
    "api-gateway",
    "auth-service",
    "user-service",
    "order-service",
    "payment-service",
    "notification-service",
    "postgres-db",
    "redis-cache",
]

VALID_REMEDIATIONS = [
    "restart",
    "rollback",
    "scale_up",
    "update_config",
    "flush_cache",
    "failover",
]

VALID_ROOT_CAUSES = [
    "memory_leak",
    "misconfiguration",
    "missing_config",
    "connection_pool_exhaustion",
    "performance_degradation",
    "cache_eviction",
    "certificate_expiry",
    "dns_resolution_failure",
    "race_condition",
]


def _healthy_service(latency=45, cpu=22, memory=35):
    return {
        "status": "up",
        "latency_ms": latency,
        "error_rate_pct": 0.1,
        "cpu_pct": cpu,
        "memory_pct": memory,
    }


def _base_service_states():
    return {
        "api-gateway": _healthy_service(latency=42, cpu=25, memory=38),
        "auth-service": _healthy_service(latency=30, cpu=18, memory=40),
        "user-service": _healthy_service(latency=35, cpu=20, memory=42),
        "order-service": _healthy_service(latency=48, cpu=28, memory=45),
        "payment-service": _healthy_service(latency=55, cpu=22, memory=38),
        "notification-service": _healthy_service(latency=40, cpu=15, memory=30),
        "postgres-db": _healthy_service(latency=8, cpu=30, memory=55),
        "redis-cache": _healthy_service(latency=2, cpu=12, memory=60),
    }


def _base_healthy_checks():
    return {s: {"status": "healthy", "response_time_ms": 25, "message": "OK"} for s in SERVICES}


def _stable_deploy(service, version, days_ago):
    return {
        "version": version,
        "deployed_minutes_ago": days_ago * 1440,
        "status": "stable",
        "changes": "Routine maintenance update",
        "deployed_by": "ci-pipeline",
    }


def _base_deployments():
    return {
        "api-gateway": [_stable_deploy("api-gateway", "v1.8.0", 7)],
        "auth-service": [_stable_deploy("auth-service", "v2.3.0", 14)],
        "user-service": [_stable_deploy("user-service", "v3.0.2", 10)],
        "order-service": [_stable_deploy("order-service", "v3.0.5", 12)],
        "payment-service": [_stable_deploy("payment-service", "v2.1.0", 21)],
        "notification-service": [_stable_deploy("notification-service", "v1.5.0", 18)],
        "postgres-db": [_stable_deploy("postgres-db", "v15.4", 60)],
        "redis-cache": [_stable_deploy("redis-cache", "v7.2.1", 45)],
    }


def _base_metrics():
    return {
        "api-gateway": {
            "cpu_pct": 25, "memory_pct": 38, "memory_used_mb": 780, "memory_limit_mb": 2048,
            "request_latency_p50_ms": 42, "request_latency_p99_ms": 180,
            "error_rate_pct": 0.1, "requests_per_sec": 1250, "active_connections": 340,
        },
        "auth-service": {
            "cpu_pct": 18, "memory_pct": 40, "memory_used_mb": 820, "memory_limit_mb": 2048,
            "request_latency_p50_ms": 30, "request_latency_p99_ms": 95,
            "error_rate_pct": 0.05, "requests_per_sec": 800, "active_connections": 120,
        },
        "user-service": {
            "cpu_pct": 20, "memory_pct": 42, "memory_used_mb": 860, "memory_limit_mb": 2048,
            "request_latency_p50_ms": 35, "request_latency_p99_ms": 110,
            "error_rate_pct": 0.08, "requests_per_sec": 600, "active_connections": 95,
        },
        "order-service": {
            "cpu_pct": 28, "memory_pct": 45, "memory_used_mb": 920, "memory_limit_mb": 2048,
            "request_latency_p50_ms": 48, "request_latency_p99_ms": 210,
            "error_rate_pct": 0.12, "requests_per_sec": 450, "active_connections": 85,
        },
        "payment-service": {
            "cpu_pct": 22, "memory_pct": 38, "memory_used_mb": 780, "memory_limit_mb": 2048,
            "request_latency_p50_ms": 55, "request_latency_p99_ms": 250,
            "error_rate_pct": 0.1, "requests_per_sec": 200, "active_connections": 60,
        },
        "notification-service": {
            "cpu_pct": 15, "memory_pct": 30, "memory_used_mb": 615, "memory_limit_mb": 2048,
            "request_latency_p50_ms": 40, "request_latency_p99_ms": 150,
            "error_rate_pct": 0.05, "requests_per_sec": 300, "active_connections": 45,
        },
        "postgres-db": {
            "cpu_pct": 30, "memory_pct": 55, "memory_used_mb": 4500, "memory_limit_mb": 8192,
            "query_latency_p50_ms": 8, "query_latency_p99_ms": 45,
            "active_connections": 85, "max_connections": 200, "replication_lag_ms": 2,
        },
        "redis-cache": {
            "cpu_pct": 12, "memory_pct": 60, "memory_used_mb": 1230, "memory_limit_mb": 2048,
            "ops_per_sec": 15000, "hit_rate_pct": 94.5, "eviction_rate": 0,
            "connected_clients": 48, "keyspace_size": 245000,
        },
    }


# ---------------------------------------------------------------------------
# EASY SCENARIOS
# ---------------------------------------------------------------------------

E1_AUTH_OOM = {
    "id": "e1_auth_oom",
    "task_name": "single_service_failure",
    "difficulty": "easy",
    "description": (
        "PagerDuty alert: auth-service is DOWN. API gateway reporting elevated "
        "error rates on authenticated endpoints. Multiple 503 responses observed."
    ),
    "root_cause": "memory_leak",
    "root_cause_description": (
        "Memory leak in auth-service v2.3.1 caused by unbounded token cache "
        "introduced in the latest deployment."
    ),
    "affected_service": "auth-service",
    "correct_remediation": {"action": "rollback", "target": "auth-service"},
    "service_states": {
        **_base_service_states(),
        "auth-service": {"status": "down", "latency_ms": None, "error_rate_pct": 100.0, "cpu_pct": 0, "memory_pct": 98},
        "api-gateway": {"status": "degraded", "latency_ms": 2500, "error_rate_pct": 15.2, "cpu_pct": 45, "memory_pct": 55},
    },
    "alerts": [
        {"service": "auth-service", "severity": "critical", "message": "Health check failing for 10 minutes"},
        {"service": "auth-service", "severity": "critical", "message": "Memory usage at 98% — above threshold"},
        {"service": "api-gateway", "severity": "warning", "message": "Error rate elevated to 15.2%"},
    ],
    "logs": {
        "auth-service": [
            {"offset_min": -30, "level": "WARN", "message": "Memory usage at 75%, heap growing steadily"},
            {"offset_min": -25, "level": "WARN", "message": "GC pause 450ms, old generation at 85%"},
            {"offset_min": -20, "level": "ERROR", "message": "Memory usage critical at 92%, approaching container limit"},
            {"offset_min": -15, "level": "FATAL", "message": (
                "OutOfMemoryError: Java heap space\n"
                "  at com.auth.cache.TokenCache.put(TokenCache.java:87)\n"
                "  at com.auth.service.TokenService.generateToken(TokenService.java:142)\n"
                "  at com.auth.controller.AuthController.authenticate(AuthController.java:63)"
            )},
            {"offset_min": -10, "level": "FATAL", "message": "Process killed by OOM killer (cgroup memory limit 2048MB exceeded)"},
            {"offset_min": -8, "level": "INFO", "message": "Service restarting... attempt 1/5"},
            {"offset_min": -5, "level": "FATAL", "message": "OutOfMemoryError: Java heap space — crash within 30s of restart"},
            {"offset_min": -3, "level": "INFO", "message": "Service restarting... attempt 3/5"},
            {"offset_min": -1, "level": "FATAL", "message": "OutOfMemoryError: entering crash loop, backing off"},
        ],
        "api-gateway": [
            {"offset_min": -15, "level": "WARN", "message": "Upstream auth-service response time exceeded 5000ms"},
            {"offset_min": -10, "level": "ERROR", "message": "Circuit breaker OPEN for auth-service after 5 consecutive failures"},
            {"offset_min": -5, "level": "ERROR", "message": "Returning 503 for POST /api/orders — auth-service unavailable"},
            {"offset_min": -2, "level": "ERROR", "message": "Returning 503 for GET /api/user/profile — auth-service unavailable"},
        ],
    },
    "metrics": {
        **_base_metrics(),
        "auth-service": {
            "cpu_pct": 0, "memory_pct": 98, "memory_used_mb": 2010, "memory_limit_mb": 2048,
            "heap_used_mb": 1940, "heap_max_mb": 2000, "gc_pause_p99_ms": 450,
            "request_latency_p50_ms": None, "request_latency_p99_ms": None,
            "error_rate_pct": 100.0, "active_connections": 0,
            "restarts_last_hour": 5, "uptime_seconds": 45,
        },
        "api-gateway": {
            **_base_metrics()["api-gateway"],
            "error_rate_pct": 15.2, "request_latency_p50_ms": 2500, "request_latency_p99_ms": 5100,
        },
    },
    "deployments": {
        **_base_deployments(),
        "auth-service": [
            {
                "version": "v2.3.1", "deployed_minutes_ago": 35, "status": "active",
                "changes": "Added token caching layer for improved authentication performance",
                "deployed_by": "ci-pipeline",
            },
            _stable_deploy("auth-service", "v2.3.0", 14),
        ],
    },
    "traces": {
        "req-a001": [
            {"service": "api-gateway", "duration_ms": 5001, "status_code": 504,
             "detail": "POST /api/auth/validate → auth-service (TIMEOUT after 5000ms)"},
            {"service": "auth-service", "duration_ms": None, "status_code": None,
             "detail": "No response — service unreachable"},
        ],
    },
    "health_checks": {
        **_base_healthy_checks(),
        "auth-service": {"status": "unhealthy", "response_time_ms": None, "message": "Connection refused — service in crash loop"},
        "api-gateway": {"status": "degraded", "response_time_ms": 2800, "message": "Responding but upstream errors detected"},
    },
    "relevant_services": {"auth-service"},
    "max_steps": 15,
    "expected_steps": 4,
}


E2_REDIS_CONFIG = {
    "id": "e2_redis_config",
    "task_name": "single_service_failure",
    "difficulty": "easy",
    "description": (
        "PagerDuty alert: redis-cache connection refused. user-service reporting "
        "100% cache miss rate and elevated latency."
    ),
    "root_cause": "misconfiguration",
    "root_cause_description": (
        "Redis configuration changed bind port from 6379 to 6380 during "
        "a maintenance window, causing all client connections to fail."
    ),
    "affected_service": "redis-cache",
    "correct_remediation": {"action": "update_config", "target": "redis-cache"},
    "service_states": {
        **_base_service_states(),
        "redis-cache": {"status": "down", "latency_ms": None, "error_rate_pct": 100.0, "cpu_pct": 5, "memory_pct": 10},
        "user-service": {"status": "degraded", "latency_ms": 450, "error_rate_pct": 2.5, "cpu_pct": 35, "memory_pct": 48},
    },
    "alerts": [
        {"service": "redis-cache", "severity": "critical", "message": "Connection refused on port 6380"},
        {"service": "user-service", "severity": "warning", "message": "Cache miss rate at 100%, latency elevated to 450ms"},
    ],
    "logs": {
        "redis-cache": [
            {"offset_min": -20, "level": "INFO", "message": "Configuration reload triggered by deploy-bot"},
            {"offset_min": -20, "level": "WARN", "message": "Bind port changed: 6379 → 6380"},
            {"offset_min": -19, "level": "INFO", "message": "Redis server restarting with new configuration"},
            {"offset_min": -19, "level": "INFO", "message": "Redis server listening on port 6380"},
            {"offset_min": -18, "level": "ERROR", "message": "Rejected connection from user-service:  expected port 6379, server on 6380"},
            {"offset_min": -15, "level": "ERROR", "message": "0 active client connections — all connection attempts failing"},
        ],
        "user-service": [
            {"offset_min": -18, "level": "WARN", "message": "Redis connection failed: Connection refused on redis-cache:6379"},
            {"offset_min": -17, "level": "WARN", "message": "Falling back to direct database queries for all cache-eligible requests"},
            {"offset_min": -10, "level": "WARN", "message": "Cache miss rate 100%, response latency increased to 450ms (normal: 35ms)"},
            {"offset_min": -5, "level": "WARN", "message": "postgres-db query volume increased 3x due to cache bypass"},
        ],
    },
    "metrics": {
        **_base_metrics(),
        "redis-cache": {
            "cpu_pct": 5, "memory_pct": 10, "memory_used_mb": 50, "memory_limit_mb": 2048,
            "ops_per_sec": 0, "hit_rate_pct": 0, "eviction_rate": 0,
            "connected_clients": 0, "keyspace_size": 245000,
        },
        "user-service": {
            **_base_metrics()["user-service"],
            "request_latency_p50_ms": 450, "request_latency_p99_ms": 1200, "error_rate_pct": 2.5,
        },
    },
    "deployments": _base_deployments(),
    "traces": {
        "req-b001": [
            {"service": "api-gateway", "duration_ms": 460, "status_code": 200,
             "detail": "GET /api/user/profile → user-service (slow but OK)"},
            {"service": "user-service", "duration_ms": 445, "status_code": 200,
             "detail": "Cache MISS → direct DB query (redis-cache:6379 connection refused)"},
        ],
    },
    "health_checks": {
        **_base_healthy_checks(),
        "redis-cache": {"status": "unhealthy", "response_time_ms": None, "message": "Connection refused on port 6379 (server listening on 6380)"},
        "user-service": {"status": "degraded", "response_time_ms": 460, "message": "Responding but cache unavailable, elevated latency"},
    },
    "relevant_services": {"redis-cache"},
    "max_steps": 15,
    "expected_steps": 4,
}


E3_NOTIFICATION_ENVVAR = {
    "id": "e3_notification_envvar",
    "task_name": "single_service_failure",
    "difficulty": "easy",
    "description": (
        "PagerDuty alert: notification-service in crash loop. "
        "8 restarts in the last 10 minutes. No notifications being delivered."
    ),
    "root_cause": "missing_config",
    "root_cause_description": (
        "Required environment variable SMTP_API_KEY was removed during a "
        "secrets rotation and not re-added, causing notification-service to "
        "fail on startup."
    ),
    "affected_service": "notification-service",
    "correct_remediation": {"action": "update_config", "target": "notification-service"},
    "service_states": {
        **_base_service_states(),
        "notification-service": {"status": "down", "latency_ms": None, "error_rate_pct": 100.0, "cpu_pct": 2, "memory_pct": 8},
    },
    "alerts": [
        {"service": "notification-service", "severity": "critical", "message": "CrashLoopBackOff — 8 restarts in 10 minutes"},
        {"service": "notification-service", "severity": "critical", "message": "Notification delivery queue growing, 0 messages processed"},
    ],
    "logs": {
        "notification-service": [
            {"offset_min": -10, "level": "INFO", "message": "Starting notification-service v1.5.0..."},
            {"offset_min": -10, "level": "FATAL", "message": (
                "ConfigurationError: Missing required environment variable SMTP_API_KEY\n"
                "  at config.validate_required_vars(config.py:23)\n"
                "  at app.startup(app.py:15)"
            )},
            {"offset_min": -9, "level": "INFO", "message": "Container restarting... attempt 2/10"},
            {"offset_min": -9, "level": "FATAL", "message": "ConfigurationError: Missing required environment variable SMTP_API_KEY"},
            {"offset_min": -7, "level": "INFO", "message": "Container restarting... attempt 4/10"},
            {"offset_min": -7, "level": "FATAL", "message": "ConfigurationError: Missing required environment variable SMTP_API_KEY"},
            {"offset_min": -5, "level": "INFO", "message": "Container restarting... attempt 6/10 (backoff: 30s)"},
            {"offset_min": -5, "level": "FATAL", "message": "ConfigurationError: Missing required environment variable SMTP_API_KEY"},
            {"offset_min": -2, "level": "INFO", "message": "Container restarting... attempt 8/10 (backoff: 60s)"},
            {"offset_min": -2, "level": "FATAL", "message": "ConfigurationError: Missing required environment variable SMTP_API_KEY"},
        ],
    },
    "metrics": {
        **_base_metrics(),
        "notification-service": {
            "cpu_pct": 2, "memory_pct": 8, "memory_used_mb": 50, "memory_limit_mb": 2048,
            "request_latency_p50_ms": None, "request_latency_p99_ms": None,
            "error_rate_pct": 100.0, "requests_per_sec": 0, "active_connections": 0,
            "restarts_last_hour": 8, "uptime_seconds": 12,
            "queue_depth": 1547, "messages_processed_last_hour": 0,
        },
    },
    "deployments": _base_deployments(),
    "traces": {},
    "health_checks": {
        **_base_healthy_checks(),
        "notification-service": {"status": "unhealthy", "response_time_ms": None, "message": "CrashLoopBackOff — process exits before health check"},
    },
    "relevant_services": {"notification-service"},
    "max_steps": 15,
    "expected_steps": 3,
}


# ---------------------------------------------------------------------------
# MEDIUM SCENARIOS
# ---------------------------------------------------------------------------

M1_POSTGRES_POOL = {
    "id": "m1_postgres_pool",
    "task_name": "cascading_failure",
    "difficulty": "medium",
    "description": (
        "PagerDuty alert: order-service and payment-service both reporting high "
        "error rates. Multiple services degraded simultaneously. "
        "Customer-facing order placement is failing."
    ),
    "root_cause": "connection_pool_exhaustion",
    "root_cause_description": (
        "postgres-db connection pool hit the 200-connection max. Long-running "
        "analytical queries from a batch job consumed connections, starving "
        "order-service and payment-service."
    ),
    "affected_service": "postgres-db",
    "correct_remediation": {"action": "scale_up", "target": "postgres-db"},
    "service_states": {
        **_base_service_states(),
        "postgres-db": {"status": "degraded", "latency_ms": 8200, "error_rate_pct": 40.0, "cpu_pct": 85, "memory_pct": 72},
        "order-service": {"status": "degraded", "latency_ms": 8500, "error_rate_pct": 35.0, "cpu_pct": 35, "memory_pct": 40},
        "payment-service": {"status": "degraded", "latency_ms": 8100, "error_rate_pct": 28.0, "cpu_pct": 30, "memory_pct": 38},
    },
    "alerts": [
        {"service": "order-service", "severity": "critical", "message": "Error rate at 35% — above 5% threshold"},
        {"service": "payment-service", "severity": "critical", "message": "Error rate at 28% — above 5% threshold"},
        {"service": "postgres-db", "severity": "warning", "message": "Connection pool at 95% capacity (190/200)"},
    ],
    "logs": {
        "postgres-db": [
            {"offset_min": -25, "level": "INFO", "message": "Batch analytics job started — running 12 long-duration queries"},
            {"offset_min": -20, "level": "WARN", "message": "Connection pool usage at 80% (160/200)"},
            {"offset_min": -15, "level": "WARN", "message": "Connection pool usage at 90% (180/200) — approaching limit"},
            {"offset_min": -10, "level": "ERROR", "message": "Connection pool EXHAUSTED (200/200) — rejecting new connections"},
            {"offset_min": -8, "level": "ERROR", "message": "47 connection requests queued, avg wait time 8.2s"},
            {"offset_min": -5, "level": "ERROR", "message": "Connection timeout: order-service request waited 10s with no available connection"},
            {"offset_min": -3, "level": "ERROR", "message": "Connection timeout: payment-service request waited 10s with no available connection"},
            {"offset_min": -1, "level": "WARN", "message": "12 long-running queries still active (avg duration: 25 min)"},
        ],
        "order-service": [
            {"offset_min": -8, "level": "ERROR", "message": "Database connection timeout after 10000ms"},
            {"offset_min": -6, "level": "ERROR", "message": "Failed to process order #45231: java.sql.SQLTransientConnectionException: connection pool exhausted"},
            {"offset_min": -4, "level": "ERROR", "message": "Failed to process order #45232: connection pool exhausted"},
            {"offset_min": -3, "level": "ERROR", "message": "Returning 500 for POST /api/orders — database unavailable"},
            {"offset_min": -1, "level": "WARN", "message": "Order processing queue backlog: 89 pending orders"},
        ],
        "payment-service": [
            {"offset_min": -7, "level": "ERROR", "message": "Transaction failed: unable to acquire database connection within 10s"},
            {"offset_min": -5, "level": "ERROR", "message": "Payment processing halted — database connection timeout"},
            {"offset_min": -4, "level": "ERROR", "message": "Failed to record payment for order #45228: connection pool exhausted"},
            {"offset_min": -2, "level": "WARN", "message": "Retry queue growing: 34 pending payment transactions"},
        ],
    },
    "metrics": {
        **_base_metrics(),
        "postgres-db": {
            "cpu_pct": 85, "memory_pct": 72, "memory_used_mb": 5900, "memory_limit_mb": 8192,
            "query_latency_p50_ms": 8200, "query_latency_p99_ms": 15000,
            "active_connections": 200, "max_connections": 200, "replication_lag_ms": 45,
            "long_running_queries": 12, "blocked_queries": 47,
        },
        "order-service": {
            **_base_metrics()["order-service"],
            "error_rate_pct": 35.0, "request_latency_p50_ms": 8500, "request_latency_p99_ms": 12000,
        },
        "payment-service": {
            **_base_metrics()["payment-service"],
            "error_rate_pct": 28.0, "request_latency_p50_ms": 8100, "request_latency_p99_ms": 11500,
        },
    },
    "deployments": _base_deployments(),
    "traces": {
        "req-c001": [
            {"service": "api-gateway", "duration_ms": 10050, "status_code": 500,
             "detail": "POST /api/orders → order-service (TIMEOUT)"},
            {"service": "order-service", "duration_ms": 10020, "status_code": 500,
             "detail": "INSERT INTO orders → postgres-db (connection pool exhausted, waited 10s)"},
            {"service": "postgres-db", "duration_ms": None, "status_code": None,
             "detail": "Connection rejected — pool at 200/200"},
        ],
        "req-c002": [
            {"service": "api-gateway", "duration_ms": 10080, "status_code": 500,
             "detail": "POST /api/payments/charge → payment-service (TIMEOUT)"},
            {"service": "payment-service", "duration_ms": 10040, "status_code": 500,
             "detail": "UPDATE transactions → postgres-db (connection pool exhausted)"},
        ],
    },
    "health_checks": {
        **_base_healthy_checks(),
        "postgres-db": {"status": "degraded", "response_time_ms": 8500, "message": "Responding but connection pool saturated (200/200)"},
        "order-service": {"status": "degraded", "response_time_ms": 8600, "message": "Responding but high error rate (35%)"},
        "payment-service": {"status": "degraded", "response_time_ms": 8200, "message": "Responding but high error rate (28%)"},
    },
    "relevant_services": {"postgres-db", "order-service", "payment-service"},
    "max_steps": 20,
    "expected_steps": 6,
}


M2_AUTH_SLOW_CASCADE = {
    "id": "m2_auth_slow_cascade",
    "task_name": "cascading_failure",
    "difficulty": "medium",
    "description": (
        "PagerDuty alert: api-gateway reporting high latency and error rates. "
        "Multiple downstream services showing 503 errors. "
        "Users reporting slow page loads and timeouts."
    ),
    "root_cause": "performance_degradation",
    "root_cause_description": (
        "auth-service response time spiked to 4500ms due to an unoptimized "
        "database query in the token validation path, causing api-gateway "
        "timeouts that cascaded to all downstream services."
    ),
    "affected_service": "auth-service",
    "correct_remediation": {"action": "scale_up", "target": "auth-service"},
    "service_states": {
        **_base_service_states(),
        "auth-service": {"status": "degraded", "latency_ms": 4500, "error_rate_pct": 5.0, "cpu_pct": 92, "memory_pct": 70},
        "api-gateway": {"status": "degraded", "latency_ms": 5200, "error_rate_pct": 22.0, "cpu_pct": 60, "memory_pct": 55},
        "order-service": {"status": "degraded", "latency_ms": 5800, "error_rate_pct": 20.0, "cpu_pct": 32, "memory_pct": 44},
        "user-service": {"status": "degraded", "latency_ms": 5500, "error_rate_pct": 18.0, "cpu_pct": 28, "memory_pct": 43},
        "payment-service": {"status": "degraded", "latency_ms": 5600, "error_rate_pct": 15.0, "cpu_pct": 25, "memory_pct": 40},
    },
    "alerts": [
        {"service": "api-gateway", "severity": "critical", "message": "Error rate at 22% — above 5% threshold"},
        {"service": "order-service", "severity": "critical", "message": "Error rate at 20%"},
        {"service": "user-service", "severity": "warning", "message": "Error rate at 18%"},
        {"service": "payment-service", "severity": "warning", "message": "Error rate at 15%"},
        {"service": "auth-service", "severity": "warning", "message": "Response latency p99 at 4500ms"},
    ],
    "logs": {
        "auth-service": [
            {"offset_min": -22, "level": "WARN", "message": "Slow query detected: SELECT * FROM tokens WHERE ... — 2100ms (threshold: 500ms)"},
            {"offset_min": -18, "level": "WARN", "message": "Token validation latency p99 rising: 1200ms → 3200ms"},
            {"offset_min": -15, "level": "ERROR", "message": "Thread pool saturation: 48/50 threads busy, 12 requests queued"},
            {"offset_min": -12, "level": "WARN", "message": "CPU at 92%, request processing backlog growing"},
            {"offset_min": -10, "level": "ERROR", "message": "Response time exceeding SLA: avg 4500ms (SLA: 200ms)"},
            {"offset_min": -5, "level": "WARN", "message": "Request queue depth: 35 pending, est. wait time 8s"},
        ],
        "api-gateway": [
            {"offset_min": -15, "level": "WARN", "message": "auth-service response time: 3200ms (threshold: 2000ms)"},
            {"offset_min": -12, "level": "ERROR", "message": "Timeout waiting for auth-service: 5000ms exceeded"},
            {"offset_min": -10, "level": "ERROR", "message": "Circuit breaker HALF-OPEN for auth-service — 60% failure rate"},
            {"offset_min": -8, "level": "ERROR", "message": "Cascading 503s: requests to order-service, user-service, payment-service failing due to auth timeout"},
            {"offset_min": -3, "level": "ERROR", "message": "22% of all requests returning 503"},
        ],
        "order-service": [
            {"offset_min": -10, "level": "ERROR", "message": "Upstream timeout: auth validation took >5000ms"},
            {"offset_min": -5, "level": "ERROR", "message": "Returning 503 for POST /api/orders — auth gateway timeout"},
        ],
        "user-service": [
            {"offset_min": -10, "level": "ERROR", "message": "Request rejected by api-gateway: auth-service timeout"},
            {"offset_min": -5, "level": "ERROR", "message": "Returning 503 for GET /api/user/profile"},
        ],
    },
    "metrics": {
        **_base_metrics(),
        "auth-service": {
            "cpu_pct": 92, "memory_pct": 70, "memory_used_mb": 1435, "memory_limit_mb": 2048,
            "request_latency_p50_ms": 3800, "request_latency_p99_ms": 4500,
            "error_rate_pct": 5.0, "requests_per_sec": 180, "active_connections": 48,
            "thread_pool_active": 48, "thread_pool_max": 50, "request_queue_depth": 35,
        },
        "api-gateway": {
            **_base_metrics()["api-gateway"],
            "error_rate_pct": 22.0, "request_latency_p50_ms": 5200, "request_latency_p99_ms": 8000,
        },
        "order-service": {
            **_base_metrics()["order-service"],
            "error_rate_pct": 20.0, "request_latency_p50_ms": 5800,
        },
        "user-service": {
            **_base_metrics()["user-service"],
            "error_rate_pct": 18.0, "request_latency_p50_ms": 5500,
        },
        "payment-service": {
            **_base_metrics()["payment-service"],
            "error_rate_pct": 15.0, "request_latency_p50_ms": 5600,
        },
    },
    "deployments": _base_deployments(),
    "traces": {
        "req-d001": [
            {"service": "api-gateway", "duration_ms": 5020, "status_code": 503,
             "detail": "POST /api/orders → auth-service (TIMEOUT at auth validation step)"},
            {"service": "auth-service", "duration_ms": 4850, "status_code": 200,
             "detail": "Token validation completed but took 4850ms (slow DB query)"},
        ],
    },
    "health_checks": {
        **_base_healthy_checks(),
        "auth-service": {"status": "degraded", "response_time_ms": 4200, "message": "Responding but extremely slow (4200ms)"},
        "api-gateway": {"status": "degraded", "response_time_ms": 5100, "message": "Responding but high error rate"},
        "order-service": {"status": "degraded", "response_time_ms": 5500, "message": "Responding but upstream auth failures"},
        "user-service": {"status": "degraded", "response_time_ms": 5200, "message": "Responding but upstream auth failures"},
        "payment-service": {"status": "degraded", "response_time_ms": 5400, "message": "Responding but upstream auth failures"},
    },
    "relevant_services": {"auth-service", "api-gateway"},
    "max_steps": 20,
    "expected_steps": 7,
}


M3_REDIS_EVICTION_CASCADE = {
    "id": "m3_redis_eviction_cascade",
    "task_name": "cascading_failure",
    "difficulty": "medium",
    "description": (
        "PagerDuty alert: user-service latency elevated. postgres-db CPU high. "
        "Cache hit rate has dropped significantly. Multiple performance warnings."
    ),
    "root_cause": "cache_eviction",
    "root_cause_description": (
        "redis-cache memory limit hit after a traffic surge caused the eviction "
        "policy to aggressively remove keys. user-service cache miss rate went "
        "to 85%, overwhelming postgres-db with direct queries."
    ),
    "affected_service": "redis-cache",
    "correct_remediation": {"action": "scale_up", "target": "redis-cache"},
    "service_states": {
        **_base_service_states(),
        "redis-cache": {"status": "degraded", "latency_ms": 3, "error_rate_pct": 0, "cpu_pct": 45, "memory_pct": 99},
        "user-service": {"status": "degraded", "latency_ms": 520, "error_rate_pct": 3.0, "cpu_pct": 55, "memory_pct": 50},
        "postgres-db": {"status": "degraded", "latency_ms": 350, "error_rate_pct": 5.0, "cpu_pct": 94, "memory_pct": 78},
    },
    "alerts": [
        {"service": "user-service", "severity": "warning", "message": "Latency p99 at 520ms — above 200ms threshold"},
        {"service": "postgres-db", "severity": "warning", "message": "CPU at 94%"},
        {"service": "redis-cache", "severity": "warning", "message": "Memory at 99%, eviction rate elevated"},
    ],
    "logs": {
        "redis-cache": [
            {"offset_min": -30, "level": "WARN", "message": "Memory usage at 90% (1843MB/2048MB), eviction policy active"},
            {"offset_min": -25, "level": "WARN", "message": "Evicting 1200 keys/sec — allkeys-lru policy triggered"},
            {"offset_min": -20, "level": "ERROR", "message": "Memory at 99% (2028MB/2048MB), aggressive eviction in progress"},
            {"offset_min": -15, "level": "WARN", "message": "Hit rate dropped: 94% → 45% — massive key eviction ongoing"},
            {"offset_min": -10, "level": "WARN", "message": "Hit rate at 15%, 85% of requests result in cache miss"},
            {"offset_min": -5, "level": "WARN", "message": "Eviction stabilized but hit rate remains at 15%"},
        ],
        "user-service": [
            {"offset_min": -20, "level": "WARN", "message": "Cache miss rate rising: 6% → 45%"},
            {"offset_min": -15, "level": "WARN", "message": "Cache miss rate at 85%, falling back to postgres for most reads"},
            {"offset_min": -10, "level": "WARN", "message": "Response latency elevated: 35ms → 520ms due to DB fallback"},
            {"offset_min": -5, "level": "ERROR", "message": "Some requests timing out — postgres query latency at 350ms"},
        ],
        "postgres-db": [
            {"offset_min": -15, "level": "WARN", "message": "Query volume spike: 450 qps → 2800 qps (cache bypass traffic)"},
            {"offset_min": -10, "level": "WARN", "message": "CPU at 94%, query queue forming"},
            {"offset_min": -8, "level": "ERROR", "message": "Slow queries detected: 23 queries exceeding 500ms"},
            {"offset_min": -5, "level": "WARN", "message": "Connection pool at 75% (150/200) — rising"},
        ],
    },
    "metrics": {
        **_base_metrics(),
        "redis-cache": {
            "cpu_pct": 45, "memory_pct": 99, "memory_used_mb": 2028, "memory_limit_mb": 2048,
            "ops_per_sec": 14000, "hit_rate_pct": 15.0, "eviction_rate": 1200,
            "connected_clients": 48, "keyspace_size": 85000,
        },
        "user-service": {
            **_base_metrics()["user-service"],
            "request_latency_p50_ms": 520, "request_latency_p99_ms": 1800, "error_rate_pct": 3.0,
        },
        "postgres-db": {
            **_base_metrics()["postgres-db"],
            "cpu_pct": 94, "memory_pct": 78, "query_latency_p50_ms": 350, "query_latency_p99_ms": 900,
            "active_connections": 150, "queries_per_sec": 2800,
        },
    },
    "deployments": _base_deployments(),
    "traces": {
        "req-e001": [
            {"service": "api-gateway", "duration_ms": 540, "status_code": 200,
             "detail": "GET /api/user/profile → user-service (slow)"},
            {"service": "user-service", "duration_ms": 520, "status_code": 200,
             "detail": "Cache MISS on user:12345 → postgres-db direct query (350ms)"},
            {"service": "redis-cache", "duration_ms": 1, "status_code": None,
             "detail": "GET user:12345 → MISS (key evicted)"},
            {"service": "postgres-db", "duration_ms": 350, "status_code": 200,
             "detail": "SELECT * FROM users WHERE id=12345 (normally served from cache)"},
        ],
    },
    "health_checks": {
        **_base_healthy_checks(),
        "redis-cache": {"status": "degraded", "response_time_ms": 3, "message": "Responding but memory at 99%, high eviction rate"},
        "user-service": {"status": "degraded", "response_time_ms": 530, "message": "Responding but elevated latency (cache bypass)"},
        "postgres-db": {"status": "degraded", "response_time_ms": 360, "message": "Responding but CPU at 94%, elevated query latency"},
    },
    "relevant_services": {"redis-cache", "user-service", "postgres-db"},
    "max_steps": 20,
    "expected_steps": 7,
}


# ---------------------------------------------------------------------------
# HARD SCENARIOS
# ---------------------------------------------------------------------------

H1_TLS_CERT_EXPIRY = {
    "id": "h1_tls_cert_expiry",
    "task_name": "complex_failure",
    "difficulty": "hard",
    "description": (
        "PagerDuty alert: intermittent 503 errors across multiple services. "
        "Pattern is inconsistent — some requests succeed, others fail. "
        "user-service was deployed 2 hours ago. Situation is confusing."
    ),
    "root_cause": "certificate_expiry",
    "root_cause_description": (
        "Internal mTLS certificate used by api-gateway for service mesh "
        "communication expired 45 minutes ago. Only affects requests routed "
        "through the mesh — direct pod-to-pod calls still work, creating "
        "an intermittent failure pattern."
    ),
    "affected_service": "api-gateway",
    "correct_remediation": {"action": "update_config", "target": "api-gateway"},
    "service_states": {
        **_base_service_states(),
        "api-gateway": {"status": "degraded", "latency_ms": 180, "error_rate_pct": 35.0, "cpu_pct": 30, "memory_pct": 40},
        "auth-service": {"status": "degraded", "latency_ms": 55, "error_rate_pct": 12.0, "cpu_pct": 20, "memory_pct": 42},
        "order-service": {"status": "degraded", "latency_ms": 80, "error_rate_pct": 18.0, "cpu_pct": 30, "memory_pct": 46},
        "user-service": {"status": "degraded", "latency_ms": 60, "error_rate_pct": 10.0, "cpu_pct": 22, "memory_pct": 44},
    },
    "alerts": [
        {"service": "api-gateway", "severity": "critical", "message": "Error rate at 35% — intermittent 503 responses"},
        {"service": "order-service", "severity": "warning", "message": "Error rate at 18%"},
        {"service": "auth-service", "severity": "warning", "message": "Error rate at 12%"},
        {"service": "user-service", "severity": "warning", "message": "Error rate at 10% (recently deployed)"},
    ],
    "logs": {
        "api-gateway": [
            {"offset_min": -45, "level": "WARN", "message": "TLS handshake failed with auth-service: certificate has expired (NotAfter: 45 min ago)"},
            {"offset_min": -44, "level": "WARN", "message": "mTLS certificate /etc/certs/mesh-client.pem expired at 2026-04-04T01:15:00Z"},
            {"offset_min": -40, "level": "ERROR", "message": "TLS handshake error on service mesh route: x509: certificate has expired or is not yet valid"},
            {"offset_min": -35, "level": "ERROR", "message": "503 on mesh-routed request to order-service — TLS failure"},
            {"offset_min": -30, "level": "INFO", "message": "Direct pod-to-pod request to order-service succeeded (bypassing mesh)"},
            {"offset_min": -20, "level": "ERROR", "message": "Intermittent pattern: mesh-routed=FAIL, direct=OK for same endpoint"},
            {"offset_min": -10, "level": "ERROR", "message": "35% of requests failing — all failures are mesh-routed TLS errors"},
            {"offset_min": -5, "level": "WARN", "message": "Certificate file: /etc/certs/mesh-client.pem — expired 45 min ago, renewal not triggered"},
        ],
        "auth-service": [
            {"offset_min": -40, "level": "WARN", "message": "Incoming request rejected: TLS client certificate invalid"},
            {"offset_min": -20, "level": "WARN", "message": "12% of incoming connections failing TLS handshake"},
        ],
        "order-service": [
            {"offset_min": -35, "level": "WARN", "message": "Sporadic connection resets from api-gateway"},
            {"offset_min": -15, "level": "ERROR", "message": "18% of requests from api-gateway failing at TLS layer"},
        ],
        "user-service": [
            {"offset_min": -120, "level": "INFO", "message": "Deployment v3.0.3 completed successfully — all health checks passing"},
            {"offset_min": -115, "level": "INFO", "message": "v3.0.3 changelog: Updated user avatar upload compression algorithm"},
            {"offset_min": -45, "level": "WARN", "message": "Some incoming requests failing with TLS handshake errors"},
            {"offset_min": -20, "level": "WARN", "message": "10% error rate — correlates with api-gateway mesh route failures"},
        ],
    },
    "metrics": {
        **_base_metrics(),
        "api-gateway": {
            **_base_metrics()["api-gateway"],
            "error_rate_pct": 35.0, "tls_handshake_failures_per_sec": 42,
            "mesh_routed_error_rate_pct": 95.0, "direct_route_error_rate_pct": 0.1,
        },
        "auth-service": {**_base_metrics()["auth-service"], "error_rate_pct": 12.0},
        "order-service": {**_base_metrics()["order-service"], "error_rate_pct": 18.0},
        "user-service": {**_base_metrics()["user-service"], "error_rate_pct": 10.0},
    },
    "deployments": {
        **_base_deployments(),
        "user-service": [
            {
                "version": "v3.0.3", "deployed_minutes_ago": 120, "status": "active",
                "changes": "Updated user avatar upload compression algorithm",
                "deployed_by": "ci-pipeline",
            },
            _stable_deploy("user-service", "v3.0.2", 10),
        ],
    },
    "traces": {
        "req-f001": [
            {"service": "api-gateway", "duration_ms": 5, "status_code": 503,
             "detail": "POST /api/orders → order-service (TLS handshake failed: certificate expired)"},
        ],
        "req-f002": [
            {"service": "api-gateway", "duration_ms": 85, "status_code": 200,
             "detail": "POST /api/orders → order-service (direct route, bypassed mesh — SUCCESS)"},
            {"service": "order-service", "duration_ms": 48, "status_code": 200,
             "detail": "Order processed normally via direct connection"},
        ],
    },
    "health_checks": {
        **_base_healthy_checks(),
        "api-gateway": {"status": "degraded", "response_time_ms": 45, "message": "Health endpoint OK but 35% of traffic failing (mesh TLS errors)"},
    },
    "relevant_services": {"api-gateway"},
    "max_steps": 25,
    "expected_steps": 9,
}


H2_DNS_RETRY_STORM = {
    "id": "h2_dns_retry_storm",
    "task_name": "complex_failure",
    "difficulty": "hard",
    "description": (
        "PagerDuty alert: payment-service experiencing intermittent failures. "
        "notification-service queue is backing up. Multiple services showing "
        "elevated latency. Customer complaints about failed checkouts."
    ),
    "root_cause": "dns_resolution_failure",
    "root_cause_description": (
        "Internal DNS resolver is intermittently timing out, causing "
        "payment-service to fail resolving the payment gateway's hostname. "
        "Failed requests trigger retries, amplifying into a retry storm. "
        "notification-service queue growth is unrelated (normal holiday traffic)."
    ),
    "affected_service": "payment-service",
    "correct_remediation": {"action": "restart", "target": "payment-service"},
    "service_states": {
        **_base_service_states(),
        "payment-service": {"status": "degraded", "latency_ms": 3200, "error_rate_pct": 42.0, "cpu_pct": 78, "memory_pct": 65},
        "notification-service": {"status": "degraded", "latency_ms": 180, "error_rate_pct": 0.5, "cpu_pct": 55, "memory_pct": 72},
        "api-gateway": {"status": "degraded", "latency_ms": 800, "error_rate_pct": 12.0, "cpu_pct": 35, "memory_pct": 42},
    },
    "alerts": [
        {"service": "payment-service", "severity": "critical", "message": "Error rate at 42% — checkout flow impacted"},
        {"service": "notification-service", "severity": "warning", "message": "Queue depth at 4500 messages — processing backlog"},
        {"service": "api-gateway", "severity": "warning", "message": "Error rate at 12% — payment endpoints failing"},
    ],
    "logs": {
        "payment-service": [
            {"offset_min": -25, "level": "WARN", "message": "DNS resolution for payments.stripe-gateway.internal took 2800ms (threshold: 500ms)"},
            {"offset_min": -22, "level": "ERROR", "message": "DNS resolution timeout: payments.stripe-gateway.internal SERVFAIL after 5000ms"},
            {"offset_min": -20, "level": "ERROR", "message": "Payment request failed: unable to resolve gateway hostname — retrying (attempt 1/3)"},
            {"offset_min": -18, "level": "ERROR", "message": "DNS resolution timeout on retry — SERVFAIL for payments.stripe-gateway.internal"},
            {"offset_min": -15, "level": "ERROR", "message": "Retry storm detected: 340 concurrent retry threads (normal: 15)"},
            {"offset_min": -12, "level": "WARN", "message": "Thread pool near saturation: 95/100 threads active (retries consuming threads)"},
            {"offset_min": -10, "level": "ERROR", "message": "42% of payment requests failing — all failures trace to DNS timeout"},
            {"offset_min": -5, "level": "ERROR", "message": "Stale DNS cache entries being used for some requests (intermittent success pattern)"},
            {"offset_min": -2, "level": "WARN", "message": "Retry backoff escalating: max retry delay 30s, queue depth 89"},
        ],
        "notification-service": [
            {"offset_min": -60, "level": "INFO", "message": "Traffic spike detected: holiday promotion campaign started"},
            {"offset_min": -45, "level": "INFO", "message": "Notification volume 3x normal — processing within capacity"},
            {"offset_min": -30, "level": "WARN", "message": "Queue depth growing: 2000 messages (processing rate matches but inflow increased)"},
            {"offset_min": -15, "level": "WARN", "message": "Queue depth at 4500 — high but within normal range for holiday traffic"},
            {"offset_min": -5, "level": "INFO", "message": "Processing rate: 150 msg/sec, all deliveries succeeding"},
        ],
        "api-gateway": [
            {"offset_min": -15, "level": "WARN", "message": "payment-service latency elevated: 3200ms"},
            {"offset_min": -10, "level": "ERROR", "message": "12% error rate — all failures on /api/payments/* endpoints"},
        ],
    },
    "metrics": {
        **_base_metrics(),
        "payment-service": {
            "cpu_pct": 78, "memory_pct": 65, "memory_used_mb": 1330, "memory_limit_mb": 2048,
            "request_latency_p50_ms": 3200, "request_latency_p99_ms": 8000,
            "error_rate_pct": 42.0, "requests_per_sec": 200, "active_connections": 95,
            "retry_queue_depth": 89, "dns_resolution_failures_per_min": 120,
            "thread_pool_active": 95, "thread_pool_max": 100,
        },
        "notification-service": {
            **_base_metrics()["notification-service"],
            "queue_depth": 4500, "messages_processed_per_sec": 150,
            "delivery_success_rate_pct": 99.5, "cpu_pct": 55, "memory_pct": 72,
        },
        "api-gateway": {
            **_base_metrics()["api-gateway"],
            "error_rate_pct": 12.0, "request_latency_p50_ms": 800,
        },
    },
    "deployments": _base_deployments(),
    "traces": {
        "req-g001": [
            {"service": "api-gateway", "duration_ms": 5020, "status_code": 500,
             "detail": "POST /api/payments/charge → payment-service (TIMEOUT)"},
            {"service": "payment-service", "duration_ms": 5010, "status_code": 500,
             "detail": "DNS resolution for payments.stripe-gateway.internal FAILED (SERVFAIL) → 3 retries exhausted"},
        ],
        "req-g002": [
            {"service": "api-gateway", "duration_ms": 320, "status_code": 200,
             "detail": "POST /api/payments/charge → payment-service (OK — used cached DNS)"},
            {"service": "payment-service", "duration_ms": 280, "status_code": 200,
             "detail": "DNS resolved from cache → payment processed normally"},
        ],
    },
    "health_checks": {
        **_base_healthy_checks(),
        "payment-service": {"status": "degraded", "response_time_ms": 3500, "message": "Responding but 42% error rate (DNS resolution failures)"},
        "notification-service": {"status": "degraded", "response_time_ms": 190, "message": "Responding, queue backlog present but processing normally"},
        "api-gateway": {"status": "degraded", "response_time_ms": 820, "message": "Responding but payment endpoints failing"},
    },
    "relevant_services": {"payment-service"},
    "max_steps": 25,
    "expected_steps": 9,
}


H3_RACE_CONDITION_DEPLOY = {
    "id": "h3_race_condition_deploy",
    "task_name": "complex_failure",
    "difficulty": "hard",
    "description": (
        "PagerDuty alert: intermittent 500 errors from order-service. "
        "api-gateway showing memory usage spike. redis-cache reporting "
        "elevated eviction rate. Unclear which system is the root cause."
    ),
    "root_cause": "race_condition",
    "root_cause_description": (
        "order-service v3.1.0 deployed 45 minutes ago introduced a race "
        "condition in the concurrent order processing path. Under load, "
        "two threads modify the same order state simultaneously, causing "
        "intermittent NullPointerException. api-gateway memory spike is just "
        "normal GC pressure. redis-cache evictions are routine background noise."
    ),
    "affected_service": "order-service",
    "correct_remediation": {"action": "rollback", "target": "order-service"},
    "service_states": {
        **_base_service_states(),
        "order-service": {"status": "degraded", "latency_ms": 120, "error_rate_pct": 22.0, "cpu_pct": 65, "memory_pct": 58},
        "api-gateway": {"status": "degraded", "latency_ms": 55, "error_rate_pct": 8.0, "cpu_pct": 40, "memory_pct": 78},
        "redis-cache": {"status": "degraded", "latency_ms": 3, "error_rate_pct": 0, "cpu_pct": 18, "memory_pct": 88},
    },
    "alerts": [
        {"service": "order-service", "severity": "critical", "message": "Error rate at 22% — intermittent 500 errors"},
        {"service": "api-gateway", "severity": "warning", "message": "Memory usage at 78% — above 70% threshold"},
        {"service": "redis-cache", "severity": "warning", "message": "Eviction rate elevated — 50 keys/sec"},
    ],
    "logs": {
        "order-service": [
            {"offset_min": -42, "level": "INFO", "message": "Deployment v3.1.0 activated — new concurrent order processing pipeline enabled"},
            {"offset_min": -35, "level": "ERROR", "message": (
                "NullPointerException in OrderProcessor.processAsync()\n"
                "  at com.orders.processor.OrderProcessor.processAsync(OrderProcessor.java:189)\n"
                "  at com.orders.handler.OrderHandler.handleConcurrent(OrderHandler.java:67)\n"
                "Cause: order.getPaymentInfo() returned null — concurrent modification detected"
            )},
            {"offset_min": -28, "level": "ERROR", "message": (
                "ConcurrentModificationException: Order #78432 state modified by two threads simultaneously\n"
                "  Thread-42: setState(PAYMENT_PENDING) at T+0ms\n"
                "  Thread-47: setState(VALIDATING) at T+2ms"
            )},
            {"offset_min": -20, "level": "ERROR", "message": "NullPointerException in OrderProcessor.processAsync() — same pattern, order #78455"},
            {"offset_min": -15, "level": "WARN", "message": "Error rate 22% — failures correlate with concurrent request spikes (>50 rps)"},
            {"offset_min": -10, "level": "ERROR", "message": "Order #78461 failed: race condition between validation and payment threads"},
            {"offset_min": -5, "level": "WARN", "message": "Pattern: errors only occur under concurrent load >50 rps, single-threaded requests always succeed"},
        ],
        "api-gateway": [
            {"offset_min": -30, "level": "INFO", "message": "JVM GC: G1 old-gen collection freed 450MB in 120ms"},
            {"offset_min": -20, "level": "INFO", "message": "Memory usage 78% after GC — within normal post-GC range"},
            {"offset_min": -15, "level": "INFO", "message": "JVM GC: G1 young-gen pause 35ms — routine"},
            {"offset_min": -10, "level": "WARN", "message": "8% error rate due to order-service upstream failures"},
        ],
        "redis-cache": [
            {"offset_min": -60, "level": "INFO", "message": "Routine TTL expiration: 50 keys/sec (normal background cleanup)"},
            {"offset_min": -30, "level": "INFO", "message": "Eviction rate: 50 keys/sec — within normal TTL-based expiry range"},
            {"offset_min": -10, "level": "INFO", "message": "Memory at 88%, eviction rate stable at 50 keys/sec — all TTL-based, no LRU eviction"},
        ],
    },
    "metrics": {
        **_base_metrics(),
        "order-service": {
            "cpu_pct": 65, "memory_pct": 58, "memory_used_mb": 1190, "memory_limit_mb": 2048,
            "request_latency_p50_ms": 120, "request_latency_p99_ms": 850,
            "error_rate_pct": 22.0, "requests_per_sec": 450, "active_connections": 85,
            "concurrent_request_errors": 99, "single_thread_errors": 0,
        },
        "api-gateway": {
            **_base_metrics()["api-gateway"],
            "memory_pct": 78, "memory_used_mb": 1600, "gc_pause_last_ms": 120,
            "gc_collections_last_hour": 8, "error_rate_pct": 8.0,
        },
        "redis-cache": {
            **_base_metrics()["redis-cache"],
            "memory_pct": 88, "eviction_rate": 50, "eviction_type": "TTL-based",
            "hit_rate_pct": 93.2,
        },
    },
    "deployments": {
        **_base_deployments(),
        "order-service": [
            {
                "version": "v3.1.0", "deployed_minutes_ago": 45, "status": "active",
                "changes": "Refactored order processing to use concurrent pipeline for improved throughput",
                "deployed_by": "ci-pipeline",
            },
            _stable_deploy("order-service", "v3.0.5", 12),
        ],
    },
    "traces": {
        "req-h001": [
            {"service": "api-gateway", "duration_ms": 130, "status_code": 500,
             "detail": "POST /api/orders → order-service (500 Internal Server Error)"},
            {"service": "order-service", "duration_ms": 115, "status_code": 500,
             "detail": "NullPointerException — concurrent modification of order state (2 threads)"},
        ],
        "req-h002": [
            {"service": "api-gateway", "duration_ms": 62, "status_code": 200,
             "detail": "POST /api/orders → order-service (success — low concurrency window)"},
            {"service": "order-service", "duration_ms": 48, "status_code": 200,
             "detail": "Order processed successfully — single-threaded execution path"},
        ],
    },
    "health_checks": {
        **_base_healthy_checks(),
        "order-service": {"status": "degraded", "response_time_ms": 125, "message": "Responding but 22% error rate under concurrent load"},
        "api-gateway": {"status": "healthy", "response_time_ms": 42, "message": "OK (memory 78% is post-GC normal)"},
        "redis-cache": {"status": "healthy", "response_time_ms": 2, "message": "OK (eviction rate is TTL-based, not pressure-based)"},
    },
    "relevant_services": {"order-service"},
    "max_steps": 25,
    "expected_steps": 10,
}


# ---------------------------------------------------------------------------
# Combined registry
# ---------------------------------------------------------------------------

SCENARIOS = {
    "easy": [E1_AUTH_OOM, E2_REDIS_CONFIG, E3_NOTIFICATION_ENVVAR],
    "medium": [M1_POSTGRES_POOL, M2_AUTH_SLOW_CASCADE, M3_REDIS_EVICTION_CASCADE],
    "hard": [H1_TLS_CERT_EXPIRY, H2_DNS_RETRY_STORM, H3_RACE_CONDITION_DEPLOY],
}

ALL_SCENARIO_IDS = {
    s["id"]: s
    for difficulty_list in SCENARIOS.values()
    for s in difficulty_list
}
