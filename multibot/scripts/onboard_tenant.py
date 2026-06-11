"""
Automate full tenant creation via CLI (wraps create_tenant + optional API check).

Usage:
    python -m scripts.onboard_tenant \
        --slug demo2 \
        --name "Demo 2" \
        --mode autonomous \
        --channel telegram \
        --bot-token "123:ABC"
"""

import argparse
import asyncio

import httpx


def main():
    parser = argparse.ArgumentParser(description="Onboard a new tenant")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--mode", default="autonomous", choices=["autonomous", "assisted", "hybrid"])
    parser.add_argument("--channel", default="telegram", choices=["telegram", "whatsapp_official", "webchat"])
    parser.add_argument("--bot-token", default="")
    parser.add_argument("--plan-id", type=int, default=0)
    parser.add_argument("--host", default="http://localhost:8000")
    args = parser.parse_args()

    from scripts.create_tenant import create_tenant as _create
    tenant_id = asyncio.run(_create(
        slug=args.slug,
        plan_id=args.plan_id,
        name=args.name,
        mode=args.mode,
    ))

    if tenant_id == -1:
        print("Tenant already exists, skipping.")
    else:
        print(f"✓ Tenant '{args.slug}' provisioned (ID={tenant_id})")

    try:
        resp = httpx.get(f"{args.host}/health", timeout=5)
        if resp.status_code == 200:
            print(f"✓ API reachable at {args.host}")
    except Exception as e:
        print(f"⚠ API not reachable ({e}) — skipping verification")

    if args.channel == "telegram":
        print(f"Next: set webhook → {args.host}/webhook/telegram/{args.slug}")


if __name__ == "__main__":
    main()
