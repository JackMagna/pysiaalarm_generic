"""Costanti per pySIAAlarm integration."""

DOMAIN = "pysiaalarm"

# Configuration keys
CONF_ACCOUNT_ID = "account_id"
CONF_ENCRYPTION_KEY = "encryption_key"
CONF_ZONES = "zones"
CONF_PING_INTERVAL = "ping_interval"

# Default values
DEFAULT_NAME = "SIA Alarm Panel"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7777
DEFAULT_PING_INTERVAL = 30

# Service names
SERVICE_SEND_MESSAGE = "send_message"
