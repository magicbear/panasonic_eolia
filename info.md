# Panasonic Eolia HA component

> ⚠️ **DEPRECATED**: This integration is no longer maintained. Panasonic has changed their API and this component may not work correctly. Please consider migrating to [EchoNetLite](https://www.home-assistant.io/integrations/echonetlite/) for controlling your Panasonic air conditioners.

A home assistant custom climate component to control Panasonic Eolia airconditioners.

This component uses the python library `panasoniceolia`

https://github.com/avolmensky/python-panasonic-eolia

## Usage
Add the following configuration in `configuration.yaml`:

```yaml
climate:
  - platform: panasonic_eolia
    username: !secret user
    password: !secret password
```
