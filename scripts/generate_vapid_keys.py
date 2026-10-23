"""Create the VAPID key pair that lets this server send browser push notifications.

    python scripts/generate_vapid_keys.py

Writes VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY to the local .env (gitignored) and prints neither
the private key nor anything secret. Then copy BOTH lines into the backend's environment on
Render (Environment tab) -- the live server reads them from there, not from your .env.

The private key is a secret: never paste it into chat, a commit or a screenshot. Existing keys are
never overwritten (a new pair silently invalidates every subscription); pass --force only if you
mean to start over.
"""
import base64
import pathlib
import sys

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid

ENV_PATH = pathlib.Path(__file__).resolve().parent.parent / ".env"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def generate_vapid_keys() -> tuple[str, str]:
    """(public key for the browser, private key for the server), both urlsafe base64 -- the
    forms the browser's pushManager.subscribe and pywebpush's webpush() accept."""
    vapid = Vapid()
    vapid.generate_keys()
    public = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    return _b64url(public), _b64url(private)


def main() -> int:
    existing = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    if "VAPID_PRIVATE_KEY=" in existing and "--force" not in sys.argv:
        print("VAPID keys already exist in .env -- not overwriting (a new pair would break every subscription).")
        return 1
    public, private = generate_vapid_keys()
    kept = [line for line in existing.splitlines() if not line.startswith(("VAPID_PUBLIC_KEY=", "VAPID_PRIVATE_KEY="))]
    kept += [f"VAPID_PUBLIC_KEY={public}", f"VAPID_PRIVATE_KEY={private}"]
    ENV_PATH.write_text("\n".join(kept) + "\n", encoding="utf-8")
    print("Wrote VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY to .env.")
    print("Next: copy both lines into the backend's environment on Render, then redeploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
