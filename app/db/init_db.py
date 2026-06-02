"""
Database initialization and data seeding.

- Creates all tables via SQLAlchemy metadata
- Seeds the Brigade Road store (STORE_BLR_002)
- Loads POS transactions from Brigade_Bangalore CSV
  (aggregates multi-item orders by invoice_number)

Can be run standalone: python -m app.db.init_db
"""

import csv
import os
import asyncio
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy import select

from app.db.session import init_db, close_db, get_session_factory
from app.models.db import Store, PosTransaction


# Map CSV store_id (ST1008) to API store_id (STORE_BLR_002)
STORE_ID_MAP = {
    "ST1008": "STORE_BLR_002",
}

# IST offset for timestamp conversion
IST_OFFSET = timedelta(hours=5, minutes=30)


async def seed_store(session):
    """Insert the Brigade Road Bangalore store if not already present."""
    result = await session.execute(
        select(Store).where(Store.store_id == "STORE_BLR_002")
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        store = Store(
            store_id="STORE_BLR_002",
            store_name="Brigade Road Bangalore",
            city="Bangalore",
            open_time=datetime.strptime("10:00", "%H:%M").time(),
            close_time=datetime.strptime("22:00", "%H:%M").time(),
            timezone="Asia/Kolkata",
            layout_json={
                "zones": ["SKINCARE", "MAKEUP", "BATH_BODY", "BILLING"],
                "cameras": {
                    "CAM_ENTRY_01": {"type": "entry_exit"},
                    "CAM_FLOOR_01": {"type": "main_floor", "zones": ["SKINCARE", "MAKEUP", "BATH_BODY"]},
                    "CAM_BILLING_01": {"type": "billing", "zones": ["BILLING"]},
                },
            },
        )
        session.add(store)
        await session.commit()
        print("[init_db] [OK] Seeded store STORE_BLR_002 (Brigade Road Bangalore)")
    else:
        print("[init_db] Store STORE_BLR_002 already exists, skipping.")


async def seed_pos_transactions(session, csv_path: str = None):
    """
    Load POS transactions from the Brigade Road CSV.

    The real CSV has multiple rows per invoice (one per item).
    We aggregate by invoice_number to get one transaction per invoice,
    summing total_amount as basket_value_inr.
    Maps ST1008 → STORE_BLR_002.
    Anonymises customer_number (PII requirement).
    """
    if csv_path is None:
        possible_paths = [
            os.path.join("data", "Brigade_Bangalore_10_April_26.csv"),
            os.path.join("/app", "data", "Brigade_Bangalore_10_April_26.csv"),
            os.path.join("data", "Brigade_Bangalore_10_April_26 (1)bc6219c.csv"),
        ]
        for p in possible_paths:
            if os.path.exists(p):
                csv_path = p
                break

    if csv_path is None or not os.path.exists(csv_path):
        print("[init_db] [WARN] POS CSV not found, skipping POS seeding.")
        return

    # Check if already seeded
    result = await session.execute(select(PosTransaction).limit(1))
    if result.scalar_one_or_none() is not None:
        print("[init_db] POS transactions already seeded, skipping.")
        return

    # Aggregate by invoice_number (multi-item orders)
    invoices = defaultdict(lambda: {
        "store_id": None,
        "timestamp": None,
        "basket_value": 0.0,
    })

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            invoice = row.get("invoice_number", "").strip()
            if not invoice:
                continue

            # Map store_id
            csv_store = row.get("store_id", "").strip()
            store_id = STORE_ID_MAP.get(csv_store, csv_store)

            # Parse timestamp (only from first row of each invoice)
            if invoices[invoice]["timestamp"] is None:
                order_date = row.get("order_date", "").strip()
                order_time = row.get("order_time", "").strip()
                try:
                    ts_str = f"{order_date} {order_time}"
                    ts = datetime.strptime(ts_str, "%d-%m-%Y %H:%M:%S")
                    # Store as IST-aware timestamp
                    ts_utc = ts.replace(tzinfo=timezone(IST_OFFSET))
                    invoices[invoice]["timestamp"] = ts_utc
                except (ValueError, KeyError):
                    continue

            invoices[invoice]["store_id"] = store_id

            # Sum total_amount across items in the same invoice
            try:
                amount = float(row.get("total_amount", "0") or "0")
                invoices[invoice]["basket_value"] += amount
            except ValueError:
                pass

    # Insert aggregated transactions
    inserted = 0
    for invoice_num, data in invoices.items():
        if data["timestamp"] is None or data["store_id"] is None:
            continue

        pos = PosTransaction(
            transaction_id=invoice_num,
            store_id=data["store_id"],
            timestamp=data["timestamp"],
            basket_value_inr=round(data["basket_value"], 2),
        )
        session.add(pos)
        inserted += 1

    await session.commit()
    print(f"[init_db] [OK] Seeded {inserted} POS transactions from {csv_path}")


async def run_init():
    """Full initialization: tables + seed data."""
    await init_db()
    print("[init_db] [OK] Database tables created.")

    factory = get_session_factory()
    async with factory() as session:
        await seed_store(session)
        await seed_pos_transactions(session)

    print("[init_db] [OK] Database initialization complete.")


# Allow running standalone: python -m app.db.init_db
if __name__ == "__main__":
    asyncio.run(run_init())
