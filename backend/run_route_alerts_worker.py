"""Render cron entrypoint for critical route alerts.

Command (repo root):
    python backend/run_route_alerts_worker.py
"""

import logging
import os
import sys

from pymongo import MongoClient

from notifications.route_alerts import CriticalRouteAlertWorker, RouteAlertService, DEFAULT_NOAA_UA


logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Debug visibility for Render cron deployments
    try:
        print("CWD:", os.getcwd())
        print("backend dir:", os.listdir("backend"))
    except Exception:
        logger.info("[route-alerts] unable to list backend dir for debug")

    mongo_url = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI")
    if not mongo_url:
        logger.error("MONGO_URL (or MONGODB_URI) is required for route alerts worker")
        return 1

    if not os.environ.get("NOAA_USER_AGENT"):
        logger.warning("NOAA_USER_AGENT not set; defaulting to %s", DEFAULT_NOAA_UA)

    db_name = os.environ.get("DB_NAME", "routecast_test")

    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client[db_name]
        logger.info("[route-alerts] Mongo connected db=%s", db_name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to connect to Mongo")
        return 1

    service = RouteAlertService(db)
    worker = CriticalRouteAlertWorker(service)

    try:
        result = worker.run_once()
        logger.info("[route-alerts] worker result %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Route alerts worker failed")
        return 1
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
