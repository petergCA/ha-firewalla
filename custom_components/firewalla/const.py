"""Constants for the Firewalla integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "firewalla"

# ---- Config entry keys ----------------------------------------------------
CONF_MSP_DOMAIN = "msp_domain"
CONF_TOKEN = "token"
CONF_BOX_GID = "box_gid"
CONF_BOX_NAME = "box_name"

# ---- Options flow keys ----------------------------------------------------
CONF_SCAN_INTERVAL = "scan_interval"
CONF_HIERARCHICAL = "hierarchical_devices"

# ---- Defaults -------------------------------------------------------------
DEFAULT_SCAN_INTERVAL = 300  # seconds
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 900
DEFAULT_HIERARCHICAL = True

# Delay after a write before we ask the coordinator to refresh, giving the
# MSP API time to reflect the change in its GET endpoints.
POST_WRITE_REFRESH_DELAY = 2.0

# ---- Managed rule tagging ------------------------------------------------
# Every rule this integration creates for device/group pause gets a notes
# field starting with this prefix so we can discover them on startup.
MANAGED_RULE_PREFIX = "[HA-PAUSE]"


def managed_rule_note(target_kind: str, target_name: str) -> str:
    """Build a notes string for a managed pause rule.

    Example: ``[HA-PAUSE] device=My iPhone``
    """
    return f"{MANAGED_RULE_PREFIX} {target_kind}={target_name}"


# ---- Services -------------------------------------------------------------
SERVICE_PAUSE_DEVICE = "pause_device"
SERVICE_PAUSE_GROUP = "pause_group"

ATTR_DURATION = "duration"

# Default pause duration used by service calls that don't specify one.
DEFAULT_PAUSE_DURATION = timedelta(minutes=30)

# ---- Platforms ------------------------------------------------------------
PLATFORMS = ["binary_sensor", "device_tracker", "sensor", "switch"]
