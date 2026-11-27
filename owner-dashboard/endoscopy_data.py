"""Read-only Endoscopy aggregate snapshot, inside the existing owner dashboard."""
import re
from datetime import datetime, timedelta, timezone

MODULE_TITLES = dict(zip((f"mod-{i}" for i in range(13)), (
    "Introduction to Colonoscopy", "Procedure Room Readiness",
    "Colonoscopy Procedure Flow", "Colon Anatomy for the GI Nurse",
    "Scope Advancement Fundamentals", "Loop Recognition",
    "Abdominal Pressure Techniques", "Patient Position Changes",
    "Screening Colonoscopy", "Colonoscopy with Biopsy",
    "Colonoscopy with Polypectomy", "Colonoscopy Hemostasis Basics",
    "Difficult Colonoscopies",
)))


def verify_roles(status, database):
    auth = status.get("authInfo", {})
    if (len(auth.get("authenticatedUsers", [])) != 1
            or auth.get("authenticatedUserRoles", []) != [{"role": "read", "db": database}]):
        raise ValueError("Dedicated database read role required")


def snapshot(db, now):
    active = {"subscription_status": "active", "subscription_expiration": {"$gt": now}}
    queries = {
        "registered": ("users", {}),
        "new_30d": ("users", {"created_at": {"$gte": now-timedelta(days=30), "$lte": now}}),
        "active": ("users", active),
        "apple": ("users", {**active, "subscription_provider": "apple"}),
        "android": ("users", {**active, "subscription_provider": "google"}),
        "monthly": ("users", {**active, "subscription_plan": "monthly"}),
        "annual": ("users", {**active, "subscription_plan": "annual"}),
        "no_expiry": ("users", {"subscription_status": "active", "subscription_expiration": None}),
        "lessons": ("lesson_progress", {"completed": True}),
        "videos": ("video_progress", {"completed": True}),
        "quizzes": ("module_progress", {}),
        "simulations": ("sim_results", {}),
        "bookmarks": ("bookmarks", {}),
    }
    for i in range(4):
        start = now - timedelta(days=7*(4-i))
        queries[f"week_{i+1}"] = ("users", {"created_at": {"$gte": start, "$lt": start+timedelta(days=7)}})
    counts = {}
    for name, (collection, query) in queries.items():
        counts[name] = db[collection].count_documents(query, maxTimeMS=3000)
    pipeline = [
        {"$match": {"completed": True, "module_id": {"$in": list(MODULE_TITLES)}}},
        {"$group": {"_id": "$module_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}}, {"$limit": 10},
    ]
    with db["lesson_progress"].aggregate(pipeline, maxTimeMS=3000) as cursor:
        rows = list(cursor)
    return {"schema": 1, "as_of": now.isoformat(), "counts": counts,
            "modules": [{"title": MODULE_TITLES[r["_id"]], "completed_lessons": r["count"]}
                        for r in rows if r["_id"] in MODULE_TITLES]}


def read_snapshot(uri, database):
    # Lazy import: other product pages never open a MongoDB connection.
    if not uri.startswith(("mongodb://", "mongodb+srv://")):
        raise ValueError("Invalid reporting connection configuration")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,63}", database) or database in {"admin", "local", "config"}:
        raise ValueError("Invalid reporting database")
    from pymongo import MongoClient, timeout
    # Explicit secure TLS and a small pool. Never reuse the app's write account.
    with MongoClient(uri, tls=True, tlsAllowInvalidCertificates=False,
                     tlsAllowInvalidHostnames=False,
                     connect=False, maxPoolSize=2, minPoolSize=0, retryReads=False,
                     serverSelectionTimeoutMS=5000, connectTimeoutMS=3000,
                     socketTimeoutMS=5000) as client:
        with timeout(12):
            verify_roles(client.admin.command("connectionStatus"), database)
            return snapshot(client[database], datetime.now(timezone.utc))
