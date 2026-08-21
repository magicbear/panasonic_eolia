#!/usr/bin/env python3
"""Panasonic Eolia Auth0 PKCE Helper Script.

Run this script to easily generate the authorization URL, log in via your browser,
and retrieve your `refresh_token` to configure Home Assistant.

Uses standard Python libraries (no pip dependencies required).

Usage:
    python3 auth_helper.py
"""

import base64
import hashlib
import json
import secrets
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

AUTH0_DOMAIN = "auth.digital.panasonic.com"
AUTH0_CLIENT_ID = "JpNCoLeXs4rPMhWmnOjbOxat7MWTZEgr"
AUTH0_AUDIENCE = "https://club.panasonic.jp/JpNCoLeXs4rPMhWmnOjbOxat7MWTZEgr/api/v1/"
AUTH0_SCOPE = "openid offline_access eolia.control"
AUTH0_REDIRECT_URI = "panasonic-eolia://auth.digital.panasonic.com/android/com.panasonic.SmartRAC/callback"


def generate_pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def get_authorize_url(code_challenge: str, state: str, nonce: str) -> str:
    params = {
        "client_id": AUTH0_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": AUTH0_REDIRECT_URI,
        "scope": AUTH0_SCOPE,
        "audience": AUTH0_AUDIENCE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "nonce": nonce,
    }
    query = urllib.parse.urlencode(params)
    return f"https://{AUTH0_DOMAIN}/authorize?{query}"


def exchange_code(code: str, code_verifier: str) -> dict:
    url = f"https://{AUTH0_DOMAIN}/oauth/token"
    payload = {
        "client_id": AUTH0_CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": AUTH0_REDIRECT_URI,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json;charset=UTF-8"},
        method="POST",
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=context, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        err_msg = err.read().decode("utf-8") if err.fp else str(err)
        raise Exception(f"Token exchange failed (HTTP {err.code}): {err_msg}") from err
    except urllib.error.URLError as err:
        raise Exception(f"Network connection failed: {err}") from err


def main():
    print("=" * 65)
    print("  Panasonic Eolia (エオリア) Auth0 Token Generator")
    print("=" * 65)

    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    auth_url = get_authorize_url(challenge, state, nonce)

    print("\n1. Please copy the following URL and open it in your browser:\n")
    print(auth_url)
    print("\n2. Log in with your CLUB Panasonic / Eolia account.")
    print("3. After login, your browser will try to redirect to a 'panasonic-eolia://...' address.")
    print("   If the page fails to open or shows 'Unable to connect', that's normal!")
    print("   Just copy the FULL URL from the browser's address bar.\n")

    callback_url = input("Paste the redirected URL here: ").strip()

    parsed = urllib.parse.urlparse(callback_url)
    params = urllib.parse.parse_qs(parsed.query)

    code = params.get("code", [None])[0]
    if not code:
        # Check fragment if query is empty
        if parsed.fragment:
            params = urllib.parse.parse_qs(parsed.fragment)
            code = params.get("code", [None])[0]

    if not code:
        print("\n[ERROR] Failed to extract 'code' parameter from the provided URL.")
        print(f"URL received: {callback_url}")
        sys.exit(1)

    print("\nExchanging authorization code for tokens...")
    try:
        token_data = exchange_code(code, verifier)
    except Exception as err:
        print(f"\n[ERROR] {err}")
        sys.exit(1)

    refresh_token = token_data.get("refresh_token")
    access_token = token_data.get("access_token")

    print("\n" + "=" * 65)
    print("  SUCCESS! Obtained Panasonic Eolia Tokens")
    print("=" * 65)
    if refresh_token:
        print(f"\nYour refresh_token:\n\n{refresh_token}\n")
        print("Configure this in your Home Assistant configuration.yaml:")
        print("-" * 50)
        print("climate:")
        print("  - platform: panasonic_eolia")
        print(f"    refresh_token: \"{refresh_token}\"")
        print("-" * 50)
    else:
        print(f"\nAccess token: {access_token}")

    print("\nDone!")


if __name__ == "__main__":
    main()
