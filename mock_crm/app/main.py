import asyncio
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.seed_data import CUSTOMERS, POLICIES

app = FastAPI(title="Mock CRM")


class Policy(BaseModel):
    policy_number: str
    customer_id: str
    status: str
    category: str
    coverage_limit: float
    effective_date: str
    expiry_date: str


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str


def _chaos_mode() -> str:
    return os.environ.get("CHAOS_MODE", "").lower()


async def _apply_chaos() -> None:
    mode = _chaos_mode()
    if mode == "down":
        raise HTTPException(status_code=503, detail="CRM unavailable")
    if mode == "latency":
        await asyncio.sleep(3)
    elif mode == "errors":
        raise HTTPException(status_code=500, detail="Simulated CRM error")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "chaos_mode": _chaos_mode() or "none"}


@app.get("/policies/{policy_number}", response_model=Policy)
async def get_policy(policy_number: str) -> Policy:
    await _apply_chaos()
    policy = POLICIES.get(policy_number)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return Policy(**policy)  # type: ignore[arg-type]


@app.get("/customers/{customer_id}", response_model=Customer)
async def get_customer(customer_id: str) -> Customer:
    await _apply_chaos()
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return Customer(**customer)
