#!/usr/bin/env python3
"""
One-time script to create/fix the Apple/Google review demo account.
Run from the Render shell:  python3 fix_reviewer_account.py
Requires MONGODB_URI and DB_NAME env vars (already set on Render).
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorClient

REVIEWER_EMAIL = "appreview@routecastweather.com"
REVIEWER_PASSWORD = "RouteCast2026!"
REVIEWER_NAME = "Apple App Review"
EXPIRATION = datetime(2027, 6, 30, 23, 59, 59, tzinfo=timezone.utc)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def fix():
    mongo_url = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "routecast_db")

    if not mongo_url:
        print("ERROR: MONGODB_URI / MONGO_URL not set")
        return

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=10000)
    db = client[db_name]

    hashed_pw = pwd_context.hash(REVIEWER_PASSWORD)
    now = datetime.now(timezone.utc)

    existing = await db.users.find_one({"email": REVIEWER_EMAIL})

    if existing:
        user_id = existing["user_id"]
        print(f"Found existing account: user_id={user_id}")
        print(f"  Before: email_verified={existing.get('email_verified')}, "
              f"subscription_status={existing.get('subscription_status')}, "
              f"is_premium={existing.get('is_premium')}")
    else:
        user_id = str(uuid.uuid4())
        print(f"Creating new account: user_id={user_id}")

    result = await db.users.update_one(
        {"email": REVIEWER_EMAIL},
        {"$set": {
            "user_id": user_id,
            "email": REVIEWER_EMAIL,
            "name": REVIEWER_NAME,
            "hashed_password": hashed_pw,
            "email_verified": True,
            "subscription_status": "active",
            "subscription_provider": "admin",
            "subscription_plan": "yearly",
            "subscription_expiration": EXPIRATION,
            "is_premium": True,
            "updated_at": now,
            "created_at": existing.get("created_at", now) if existing else now,
        }},
        upsert=True,
    )

    await db.subscription_logs.insert_one({
        "user_id": user_id,
        "action": "reviewer_account_setup",
        "new_status": "active",
        "new_is_premium": True,
        "subscription_expiration": EXPIRATION,
        "admin_action": True,
        "timestamp": now,
    })

    # Verify
    updated = await db.users.find_one({"email": REVIEWER_EMAIL}, {"hashed_password": 0})
    print("\n=== FINAL STATE ===")
    print(f"  email:                 {updated.get('email')}")
    print(f"  user_id:               {updated.get('user_id')}")
    print(f"  email_verified:        {updated.get('email_verified')}")
    print(f"  subscription_status:   {updated.get('subscription_status')}")
    print(f"  subscription_plan:     {updated.get('subscription_plan')}")
    print(f"  subscription_provider: {updated.get('subscription_provider')}")
    print(f"  is_premium:            {updated.get('is_premium')}")
    print(f"  subscription_expiration: {updated.get('subscription_expiration')}")
    print("\nDone. Account is ready for Apple review.")

    client.close()


if __name__ == "__main__":
    asyncio.run(fix())
