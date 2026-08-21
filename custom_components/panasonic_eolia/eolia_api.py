"""API Client for Panasonic Eolia AC (v6 API with Auth0 PKCE authentication).

Uses standard library (urllib) for zero external dependencies.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from .const import (
    API_BASE_URL,
    API_CLEAN_FILTER,
    API_DEVICES,
    API_DEVICE_STATUS,
    API_MULTIPLE_DEVICES_STATUS,
    AUTH0_AUDIENCE,
    AUTH0_CLIENT_ID,
    AUTH0_DOMAIN,
    AUTH0_REDIRECT_URI,
    AUTH0_SCOPE,
    AirSwingLR,
    AirSwingUD,
    FanSpeed,
    OperationMode,
)

_LOGGER = logging.getLogger(__name__)


class EoliaError(Exception):
    """Base exception for Eolia errors."""
    pass


class EoliaAuthError(EoliaError):
    """Authentication failure."""
    pass


class EoliaResponseError(EoliaError):
    """API response error."""

    def __init__(self, status_code: int, message: str, raw_response: Any = None) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.raw_response = raw_response


class EoliaAuth:
    """Manages Auth0 OAuth2 / PKCE tokens for Panasonic Eolia."""

    def __init__(
        self,
        refresh_token: Optional[str] = None,
        access_token: Optional[str] = None,
        token_expires_at: float = 0,
    ) -> None:
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.token_expires_at = token_expires_at
        self._ssl_context = ssl.create_default_context()

    @staticmethod
    def generate_pkce_pair() -> tuple[str, str]:
        """Generate PKCE code_verifier and code_challenge (S256)."""
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return verifier, challenge

    @staticmethod
    def get_authorize_url(
        code_challenge: str,
        state: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> str:
        """Construct Auth0 authorization URL for browser login."""
        state = state or secrets.token_urlsafe(32)
        nonce = nonce or secrets.token_urlsafe(32)
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

    def _post_token(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"https://{AUTH0_DOMAIN}/oauth/token"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3a XL Build/QQ1A.200105.002)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8") if err.fp else str(err)
            raise EoliaAuthError(f"Auth request failed (HTTP {err.code}): {err_body}") from err
        except urllib.error.URLError as err:
            raise EoliaAuthError(f"Network error during auth request: {err}") from err

    def exchange_code(self, code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchange authorization code for access_token and refresh_token."""
        payload = {
            "client_id": AUTH0_CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": AUTH0_REDIRECT_URI,
        }
        data = self._post_token(payload)
        self.access_token = data.get("access_token")
        if data.get("refresh_token"):
            self.refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 86400)
        self.token_expires_at = time.time() + expires_in - 300
        return data

    def refresh_access_token(self) -> str:
        """Refresh access token using stored refresh_token."""
        if not self.refresh_token:
            raise EoliaAuthError("No refresh_token available to refresh access_token.")

        payload = {
            "client_id": AUTH0_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        data = self._post_token(payload)
        self.access_token = data.get("access_token")
        if data.get("refresh_token"):
            self.refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 86400)
        self.token_expires_at = time.time() + expires_in - 300
        _LOGGER.debug("Successfully refreshed Auth0 access token for Eolia.")
        return self.access_token

    def get_valid_access_token(self) -> str:
        """Return a valid access token, refreshing if necessary."""
        if not self.access_token or time.time() >= self.token_expires_at:
            return self.refresh_access_token()
        return self.access_token


class EoliaSession:
    """Session for interacting with Panasonic Eolia v6 Cloud API."""

    def __init__(
        self,
        auth: Optional[EoliaAuth] = None,
        refresh_token: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> None:
        if auth:
            self.auth = auth
        elif refresh_token or access_token:
            self.auth = EoliaAuth(refresh_token=refresh_token, access_token=access_token)
        else:
            raise ValueError("Either an EoliaAuth instance or tokens must be provided.")

        self._ssl_context = ssl.create_default_context()
        self._device_tokens: Dict[str, str] = {}
        self._device_cache: Dict[str, Dict[str, Any]] = {}

    def _headers(self) -> Dict[str, str]:
        token = self.auth.get_valid_access_token()
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        return {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
            "Authorization": f"Bearer {token}",
            "X-Eolia-Date": now_str,
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3a XL Build/QQ1A.200105.002)",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        retry_auth: bool = True,
    ) -> Dict[str, Any]:
        url = f"{API_BASE_URL}{endpoint}" if not endpoint.startswith("http") else endpoint
        headers = self._headers()
        data = json.dumps(json_data).encode("utf-8") if json_data is not None else None

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=30) as resp:
                resp_text = resp.read().decode("utf-8")
                return json.loads(resp_text) if resp_text else {}
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8") if err.fp else str(err)
            if err.code == 401 and retry_auth:
                _LOGGER.debug("Received 401 Unauthorized, refreshing token and retrying request...")
                self.auth.refresh_access_token()
                return self._request(method, endpoint, json_data, retry_auth=False)
            raise EoliaResponseError(err.code, f"API error on {endpoint}: {err_body}", err_body) from err
        except urllib.error.URLError as err:
            raise EoliaError(f"Network request to {endpoint} failed: {err}") from err

    def get_devices(self) -> List[Dict[str, Any]]:
        """Fetch list of all air conditioner devices."""
        data = self._request("GET", API_DEVICES)
        ac_list = data.get("ac_list", [])
        devices = []
        for ac in ac_list:
            devices.append(
                {
                    "id": ac.get("appliance_id"),
                    "name": ac.get("nickname") or ac.get("appliance_id"),
                    "model": ac.get("product_code", ""),
                    "status": ac.get("device_status"),
                    "permission": ac.get("permission_type"),
                    "raw": ac,
                }
            )
        return devices

    def get_device_status(self, appliance_id: str) -> Dict[str, Any]:
        """Fetch real-time status of a specific device."""
        endpoint = API_DEVICE_STATUS.format(appliance_id=appliance_id)
        data = self._request("GET", endpoint)

        # Cache operation_token if returned
        if "operation_token" in data:
            self._device_tokens[appliance_id] = data["operation_token"]
        self._device_cache[appliance_id] = data

        return data

    def set_device_status(
        self,
        appliance_id: str,
        power: Optional[bool] = None,
        mode: Optional[OperationMode | str] = None,
        temperature: Optional[float] = None,
        fan_speed: Optional[FanSpeed | int] = None,
        air_swing_vertical: Optional[AirSwingUD | int] = None,
        air_swing_horizontal: Optional[AirSwingLR | str] = None,
        air_flow: Optional[str] = None,
        nanoex: Optional[bool] = None,
        humidity: Optional[int] = None,
        ai_control: Optional[str] = None,
        circulation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send control commands to update device state."""
        # Refresh current device cache if not present
        if appliance_id not in self._device_cache:
            self.get_device_status(appliance_id)

        current = self._device_cache.get(appliance_id, {})
        operation_token = self._device_tokens.get(appliance_id, current.get("operation_token", ""))

        payload: Dict[str, Any] = {
            "operation_token": operation_token,
            "operation_status": current.get("operation_status", True) if power is None else power,
            "operation_mode": current.get("operation_mode", "Cooling") if mode is None else (mode.value if isinstance(mode, OperationMode) else str(mode)),
            "temperature": current.get("temperature", 25.0) if temperature is None else float(temperature),
            "wind_volume": current.get("wind_volume", 0) if fan_speed is None else (fan_speed.value if isinstance(fan_speed, FanSpeed) else int(fan_speed)),
            "wind_direction": current.get("wind_direction", 0) if air_swing_vertical is None else (air_swing_vertical.value if isinstance(air_swing_vertical, AirSwingUD) else int(air_swing_vertical)),
            "wind_direction_horizon": current.get("wind_direction_horizon", "auto") if air_swing_horizontal is None else (air_swing_horizontal.value if isinstance(air_swing_horizontal, AirSwingLR) else str(air_swing_horizontal)),
            "air_flow": current.get("air_flow", "not_set") if air_flow is None else air_flow,
            "nanoex": current.get("nanoex", False) if nanoex is None else bool(nanoex),
            "humidity": current.get("humidity", 100) if humidity is None else int(humidity),
            "ai_control": current.get("ai_control", "off") if ai_control is None else ai_control,
            "circulation": current.get("circulation", "off") if circulation is None else circulation,
            "silence_control": current.get("silence_control", False),
            "wind_shield_hit": current.get("wind_shield_hit", "not_set"),
            "airquality": current.get("airquality", False),
        }

        endpoint = API_DEVICE_STATUS.format(appliance_id=appliance_id)
        result = self._request("PUT", endpoint, json_data=payload)

        if isinstance(result, dict):
            if "operation_token" in result:
                self._device_tokens[appliance_id] = result["operation_token"]
            self._device_cache[appliance_id].update(result)

        return result

    def get_clean_filter_status(self, appliance_id: str) -> Dict[str, Any]:
        """Fetch filter clean status."""
        endpoint = API_CLEAN_FILTER.format(appliance_id=appliance_id)
        return self._request("GET", endpoint)

    def turn_off_all(self, appliance_ids: Optional[List[str]] = None) -> None:
        """Turn off all devices at once."""
        if appliance_ids is None:
            devices = self.get_devices()
            appliance_ids = [d["id"] for d in devices if "id" in d]

        payload = [{"appliance_id": aid, "operation_status": False} for aid in appliance_ids]
        self._request("PUT", API_MULTIPLE_DEVICES_STATUS, json_data={"devices": payload})
