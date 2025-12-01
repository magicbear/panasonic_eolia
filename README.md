# Panasonic Eolia HA component

> ⚠️ **DEPRECATED**: This integration is no longer maintained. Panasonic has changed their API and this component may not work correctly. Please consider migrating to [EchoNetLite](https://www.home-assistant.io/integrations/echonetlite/) for controlling your Panasonic air conditioners.

A home assistant custom climate component to control Panasonic eolia airconditioners.

Credit to djbulsink and lostfields as a lot of their code was modified for the Panasonic Eolia

This component uses the python library `panasoniceolia`

https://github.com/avolmensky/python-panasonic-eolia

## Usage
- Copy `__init__.py`, `climate.py`, and `manifest.json` to the `custom_components/panasonic_eolia/` folder. As an alternative, you can also install the component via the [Home Assistant Community Store (HACS)](https://hacs.xyz/) by adding it manually.
- Add the following configuration in `configuration.yaml`:

```yaml
climate:
  - platform: panasonic_eolia
    username: !secret user
    password: !secret password
```
