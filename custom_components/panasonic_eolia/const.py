"""Constants for the Panasonic Eolia integration."""
from enum import Enum

DOMAIN = "panasonic_eolia"

# Auth0 Configuration
AUTH0_DOMAIN = "auth.digital.panasonic.com"
AUTH0_CLIENT_ID = "JpNCoLeXs4rPMhWmnOjbOxat7MWTZEgr"
AUTH0_AUDIENCE = "https://club.panasonic.jp/JpNCoLeXs4rPMhWmnOjbOxat7MWTZEgr/api/v1/"
AUTH0_SCOPE = "openid offline_access eolia.control"
AUTH0_REDIRECT_URI = "panasonic-eolia://auth.digital.panasonic.com/android/com.panasonic.SmartRAC/callback"


# API Endpoints
API_BASE_URL = "https://app.rac.apws.panasonic.com/eolia/v6"
API_DEVICES = "/devices"
API_DEVICE_STATUS = "/devices/{appliance_id}/status"
API_DEVICE_DETAIL = "/devices/{appliance_id}"
API_MULTIPLE_DEVICES_STATUS = "/multipledevices/status"
API_CLEAN_FILTER = "/devices/{appliance_id}/cleanfilter/status"
API_AIR_QUALITY_HISTORY = "/devices/{appliance_id}/airquality/history"
API_PRODUCT_FUNCTIONS = "/products/{product_code}/functions"

# Configuration Keys
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCESS_TOKEN = "access_token"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Operation Modes
class OperationMode(str, Enum):
    AUTO = "Auto"
    COOL = "Cooling"
    HEAT = "Heating"
    DRY = "CoolDehumidifying"
    FAN = "Blast"
    DEHUMIDIFY = "Dehumidifying"
    CLOTHES_DRYER = "ClothesDryer"
    NANOE = "Nanoe"
    STOP = "Stop"
    MOIST_COOLING = "MoistCooling"
    KEEP_HEATING = "KeepHeating"
    SMELL_CARE = "SmellCare"
    SMELL_CARE_SPOT = "SmellCareSpot"
    CLEANING = "Cleaning"
    NANOEX_CLEANING = "NanoexCleaning"


# Fan Speed / Wind Volume
class FanSpeed(int, Enum):
    AUTO = 0
    QUIET = 1
    LOW = 2
    MID = 3
    HIGH_MID = 4
    HIGH = 5


# Air Swing Vertical (Up / Down)
class AirSwingUD(int, Enum):
    AUTO = 0
    UP = 1
    UP_MID = 2
    MID = 3
    DOWN_MID = 4
    DOWN = 5


# Air Swing Horizontal (Left / Right)
class AirSwingLR(str, Enum):
    AUTO = "auto"
    FRONT = "front"
    SPOT = "spot"
    WIDE = "wide"
    TO_LEFT = "to_left"
    NEARBY_LEFT = "nearby_left"
    NEARBY_RIGHT = "nearby_right"
    TO_RIGHT = "to_right"
