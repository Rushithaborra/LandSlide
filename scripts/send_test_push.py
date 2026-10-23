"""Send a clearly-labelled TEST notification to a browser that subscribed through the dashboard.

    python scripts/send_test_push.py          # the newest subscription (the one you just made)
    python scripts/send_test_push.py --all    # every subscription

Use it to check the real chain (the server's keys, the browser's push service, the notification
itself) without waiting for an actual warning. The message says it is a test and that no warning
has been raised. Needs VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY and DATABASE_URL in .env, and a network
that can reach the database. Prints nothing secret (no endpoints, keys or tokens).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AlertSubscription  # noqa: E402
from app.services import push_alerts  # noqa: E402

TEST_PAYLOAD = {
    "en": ("TEST - landslide warning (not real)", "This is a test of your alert notifications. No landslide warning has been raised."),
    "hi": ("परीक्षण - भूस्खलन चेतावनी (असली नहीं)", "यह आपकी अलर्ट सूचनाओं का परीक्षण है। कोई भूस्खलन चेतावनी जारी नहीं हुई है।"),
    "ne": ("परीक्षण - पहिरो चेतावनी (वास्तविक होइन)", "यो तपाईंको अलर्ट सूचनाको परीक्षण हो। कुनै पहिरो चेतावनी जारी गरिएको छैन।"),
}


def main() -> int:
    if not push_alerts.push_configured():
        print("VAPID keys are not set. Run scripts/generate_vapid_keys.py first.")
        return 1
    db = SessionLocal()
    try:
        query = select(AlertSubscription).where(AlertSubscription.channel == "webpush").order_by(AlertSubscription.created_at.desc())
        subs = db.execute(query).scalars().all()
        if not subs:
            print("No subscriptions found. Open Check my area on your phone and tap 'Alert me' first.")
            return 1
        if "--all" not in sys.argv:
            subs = subs[:1]
        failures = 0
        for sub in subs:
            title, body = TEST_PAYLOAD.get(sub.language, TEST_PAYLOAD["en"])
            payload = json.dumps({"title": title, "body": body, "url": settings.dashboard_url, "tag": "test-notification"}, ensure_ascii=False)
            try:
                push_alerts._send(sub, payload)
                print(f"sent a test to the subscription for '{sub.place_label}' ({sub.language}, {sub.radius_km:g} km)")
            except Exception as e:
                failures += 1
                status = getattr(getattr(e, "response", None), "status_code", None)
                print(f"FAILED for '{sub.place_label}': {type(e).__name__}{f' (HTTP {status})' if status else ''}")
        return 1 if failures else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
