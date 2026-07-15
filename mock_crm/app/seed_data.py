CUSTOMERS: dict[str, dict[str, str]] = {
    "cust-1001": {
        "customer_id": "cust-1001",
        "name": "Ava Thompson",
        "email": "ava.thompson@example.com",
    },
    "cust-1002": {
        "customer_id": "cust-1002",
        "name": "Marcus Lee",
        "email": "marcus.lee@example.com",
    },
    "cust-1003": {
        "customer_id": "cust-1003",
        "name": "Priya Nair",
        "email": "priya.nair@example.com",
    },
}

POLICIES: dict[str, dict[str, str | float]] = {
    "POL-AUTO-001": {
        "policy_number": "POL-AUTO-001",
        "customer_id": "cust-1001",
        "status": "active",
        "category": "auto",
        "coverage_limit": 25000.0,
        "effective_date": "2025-01-01",
        "expiry_date": "2026-12-31",
    },
    "POL-HOME-002": {
        "policy_number": "POL-HOME-002",
        "customer_id": "cust-1002",
        "status": "active",
        "category": "home",
        "coverage_limit": 150000.0,
        "effective_date": "2024-06-01",
        "expiry_date": "2026-06-01",
    },
    "POL-HEALTH-003": {
        "policy_number": "POL-HEALTH-003",
        "customer_id": "cust-1003",
        "status": "lapsed",
        "category": "health",
        "coverage_limit": 50000.0,
        "effective_date": "2023-01-01",
        "expiry_date": "2024-01-01",
    },
    # Active health policy so the eval dataset can include health approvals
    # (POL-HEALTH-003 stays lapsed on purpose — it powers invalid-policy cases).
    "POL-HEALTH-004": {
        "policy_number": "POL-HEALTH-004",
        "customer_id": "cust-1003",
        "status": "active",
        "category": "health",
        "coverage_limit": 50000.0,
        "effective_date": "2025-06-01",
        "expiry_date": "2027-06-01",
    },
}
