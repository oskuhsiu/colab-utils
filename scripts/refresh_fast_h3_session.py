#!/usr/bin/env python3
"""Refresh proxy credentials for the same assigned VM; run with Colab CLI Python."""
import argparse
from datetime import datetime, timezone
import json


def refresh(name, auth="oauth2"):
    from colab_cli.auth import AuthProvider
    from colab_cli.common import state
    from colab_cli.contents import ContentsClient
    state.auth_provider = AuthProvider(auth)
    old = state.store.get(name)
    if old is None:
        raise ValueError("Existing session is required; this operation never allocates a VM")
    assignments = [a for a in state.client.list_assignments() if a.endpoint == old.endpoint]
    if len(assignments) != 1:
        raise ValueError("The original VM is no longer assigned")
    info = assignments[0].runtime_proxy_info
    current = state.store.get(name)
    if current is None or current.endpoint != old.endpoint:
        raise ValueError("Session endpoint changed during refresh")
    updated = current.model_copy(update={"token": info.token, "url": info.url})
    if ContentsClient(updated).list_dir("/content/fast-h3").get("type") != "directory":
        raise ValueError("Existing FastH3 runtime files unavailable")
    if state.store.get(name).endpoint != old.endpoint:
        raise ValueError("Session endpoint changed before cache update")
    state.store.add(updated)
    return {"session": name, "same_endpoint": True, "token_changed": current.token != info.token,
            "proxy_expires_in_seconds": info.token_expires_in_seconds,
            "at_utc": datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--auth", default="oauth2", choices=("oauth2", "adc"))
    args = parser.parse_args()
    try:
        print(json.dumps(refresh(args.session, args.auth)))
    except Exception as error:
        # HTTP exception strings may contain proxy credentials.
        print("Proxy refresh failed:", type(error).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
