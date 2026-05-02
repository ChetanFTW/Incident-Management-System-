#!/usr/bin/env python3
"""
Seed script — simulates a real failure cascade:
  1. RDBMS outage (P0) — 120 signals in burst
  2. MCP_HOST failure (P0) — triggered by DB being down
  3. CACHE degradation (P2) — cascades from above
  4. API latency spikes (P1)

Usage:
  # Make sure backend is running first
  python seed.py

  # Or fire against a custom URL
  BASE_URL=http://localhost:8000 python seed.py
"""
import asyncio
import httpx
import os
import json
from datetime import datetime, timezone

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
USERNAME = "seed_admin"
PASSWORD = "seed_password123"


async def get_token(client: httpx.AsyncClient) -> str:
    # Register (ignore if exists)
    await client.post(f"{BASE_URL}/auth/register", json={
        "username": USERNAME, "email": "seed@ims.local", "password": PASSWORD
    })
    r = await client.post(f"{BASE_URL}/auth/login", json={
        "username": USERNAME, "password": PASSWORD
    })
    r.raise_for_status()
    token = r.json()["access_token"]
    print(f"✅ Authenticated as {USERNAME}")
    return token


async def fire_signals(
    client: httpx.AsyncClient,
    token: str,
    component_id: str,
    component_type: str,
    severity: str,
    message: str,
    count: int,
    delay: float = 0.05,
):
    headers = {"Authorization": f"Bearer {token}"}
    print(f"\n🔥 Firing {count} signals → {component_id} [{severity}]")
    success = 0
    for i in range(count):
        payload = {
            "component_id": component_id,
            "component_type": component_type,
            "severity": severity,
            "message": f"{message} (signal {i+1}/{count})",
            "error_code": f"ERR_{component_type[:3]}_{i % 10:03d}",
            "metadata": {
                "host": f"node-{i % 5 + 1}.prod",
                "latency_ms": 5000 + (i * 100),
                "iteration": i,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            r = await client.post(f"{BASE_URL}/signals", json=payload, headers=headers)
            if r.status_code in (200, 202):
                success += 1
        except Exception as e:
            print(f"  Signal {i} failed: {e}")
        if delay:
            await asyncio.sleep(delay)
    print(f"  ✅ {success}/{count} accepted")


async def main():
    print("=" * 60)
    print("IMS Failure Cascade Simulation")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30) as client:
        # Health check
        try:
            r = await client.get(f"{BASE_URL}/health")
            print(f"\n🏥 Health: {r.json()['status']}")
        except Exception as e:
            print(f"❌ Backend not reachable: {e}")
            return

        token = await get_token(client)

        # ── Phase 1: RDBMS Outage (P0) ────────────────────────────
        print("\n📍 Phase 1: Primary database going down...")
        await asyncio.sleep(1)
        await fire_signals(
            client, token,
            component_id="POSTGRES_PRIMARY_01",
            component_type="RDBMS",
            severity="P0",
            message="Connection refused — primary DB unreachable",
            count=120,   # triggers debounce (100 in 10s → 1 work item)
            delay=0.08,
        )

        # ── Phase 2: MCP Host failure (P0) ────────────────────────
        print("\n📍 Phase 2: MCP Host failing due to DB dependency...")
        await asyncio.sleep(2)
        await fire_signals(
            client, token,
            component_id="MCP_HOST_CLUSTER_01",
            component_type="MCP_HOST",
            severity="P0",
            message="MCP host cannot reach data store — cascading from DB outage",
            count=60,
            delay=0.1,
        )

        # ── Phase 3: Cache degradation (P2) ───────────────────────
        print("\n📍 Phase 3: Cache cluster degrading...")
        await asyncio.sleep(1)
        await fire_signals(
            client, token,
            component_id="REDIS_CACHE_CLUSTER_01",
            component_type="CACHE",
            severity="P2",
            message="Cache hit rate dropped below 10% — fallback to DB causing overload",
            count=40,
            delay=0.05,
        )

        # ── Phase 4: API latency (P1) ──────────────────────────────
        print("\n📍 Phase 4: API latency spiking...")
        await asyncio.sleep(1)
        await fire_signals(
            client, token,
            component_id="API_GATEWAY_PROD",
            component_type="API",
            severity="P1",
            message="p99 latency >5000ms — downstream DB timeouts propagating",
            count=80,
            delay=0.06,
        )

        # ── Summary ────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("Simulation complete. Checking incidents...")
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.get(f"{BASE_URL}/incidents", headers=headers)
        data = r.json()
        print(f"📊 Total incidents created: {data['total']}")
        for inc in data["items"]:
            print(f"  [{inc['priority']}] {inc['component_id']:30s} {inc['status']:15s} signals={inc['signal_count']}")
        print("\n✅ Open http://localhost:3000 to see the dashboard")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
