# Panasonic Eolia Home Assistant Component (v2.0)

A Home Assistant custom climate integration to monitor and control Panasonic Eolia (エオリア) air conditioners via the official Panasonic v6 Cloud API with Auth0 OAuth2 / PKCE authentication.

## Features
- **Web UI Configuration (Config Flow)**: Add and configure devices directly from the Home Assistant Web UI.
- **Cloud Control**: Full support for Power, Target Temperature, Operation Modes (Auto, Cool, Heat, Dry, Fan), Fan Speeds (Auto, Quiet, Low, Mid, HighMid, High), and Vertical Swings (Auto, Up, UpMid, Mid, DownMid, Down).
- **Sensors & Attributes**: Live readings of Indoor Temperature, Outdoor Temperature, and Indoor Humidity.
- **Auth0 Security**: Official Auth0 PKCE OAuth 2.0 flow with automatic token renewal.

---

## Installation & Setup

### Method 1: Web UI Configuration (Recommended)

1. Go to **Settings** > **Devices & Services** > **Add Integration** in Home Assistant.
2. Search for **Panasonic Eolia AC**.
3. Click the provided link in the dialog to log in with your **CLUB Panasonic / Eolia** account.
4. After logging in, copy the redirected URL from your browser address bar (starting with `panasonic-eolia://...`) and paste it into the configuration box.
5. Click **Submit**. All your Eolia air conditioners will be automatically discovered and added!

---

### Method 2: CLI Token Helper & YAML Configuration

If you prefer using `configuration.yaml` or want to retrieve your `refresh_token` manually:

1. Run the token generator script:
   ```bash
   python3 custom_components/panasonic_eolia/auth_helper.py
   ```
2. Follow the prompt to log in and get your `refresh_token`.
3. Add the following to your `configuration.yaml`:
   ```yaml
   climate:
     - platform: panasonic_eolia
       refresh_token: "YOUR_REFRESH_TOKEN_HERE"
   ```
4. Restart Home Assistant.
