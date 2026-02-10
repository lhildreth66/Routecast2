"""Inspect route monitor documents for debugging Render cron.

Usage:
    python backend/inspect_route_monitors.py

Reads Mongo connection details from MONGODB_URI, MONGO_URL, or MONGO_URI and
DB_NAME (default: routecast_test). Prints collection names, monitor count, and
a recent document (keys + full doc) from route_monitors.
"""

import os
import sys
import json
import pprint
from datetime import datetime
from typing import Optional

from pymongo import MongoClient


def get_mongo_url() -> Optional[str]:
    return os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL") or os.environ.get("MONGO_URI")


def main() -> int:
    mongo_url = get_mongo_url()
    if not mongo_url:
        print("MONGODB_URI/MONGO_URL/MONGO_URI is required", file=sys.stderr)
        return 1

    db_name = os.environ.get("DB_NAME", "routecast_test")
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client[db_name]
        print(f"Connected to Mongo db={db_name}")
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to connect to Mongo: {exc}", file=sys.stderr)
        return 1

    try:
        collections = db.list_collection_names()
        print("Collections:", collections)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to list collections: {exc}", file=sys.stderr)
        return 1

    if "route_monitors" not in collections:
        print("route_monitors collection not found")
        return 0

    try:
        count = db.route_monitors.count_documents({})
        print(f"route_monitors count: {count}")
        doc = db.route_monitors.find_one(sort=[("created_at", -1)]) or {}
        print("Most recent route_monitor keys:", sorted(list(doc.keys())))
        # Avoid printing secrets; these docs typically don't contain them.
        print("Most recent route_monitor document:")
        pprint.pprint(doc)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to inspect route_monitors: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
