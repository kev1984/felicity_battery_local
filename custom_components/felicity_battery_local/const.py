"""Constants for the Felicity Battery (Local) integration.

Protocol notes
--------------
Felicity's WiFi module (the same one used by the "Shine" app in local mode)
listens on TCP port 53970. You send it a plain ASCII command and it replies
with one or more JSON objects (sometimes concatenated back-to-back as
"...}{..." if the module also has an inverter attached).

Known commands:
    wifilocalMonitor:get dev real infor   -> live measurements (what we poll)
    wifilocalMonitor:get dev basice infor -> basic/static device info
    wifilocalMonitor:get dev set infor    -> current settings
    wifilocalMonitor:get Date             -> device date/time

This has been community-verified against a 12.5 kWh Felicity LiFePO4 battery
(same LUX-E/LPBF family as the LUX-E-48250LG03). Field availability can vary
slightly by firmware/model - unknown fields are simply skipped (entity shows
as unavailable) rather than causing an error.
"""

DOMAIN = "felicity_battery_local"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 53970
DEFAULT_SCAN_INTERVAL = 10  # seconds
SOCKET_TIMEOUT = 5  # connect timeout
READ_IDLE_TIMEOUT = 1.5  # stop reading once the device is quiet for this long

CMD_REAL_INFO = "wifilocalMonitor:get dev real infor"

# BtemList (individual temperature probes) uses 32767 (0x7FFF, max int16) as
# "no probe connected here" sentinel. BatcelList uses 65535 (0xFFFF) for the
# same purpose on unused cell-voltage slots of a second, absent pack.
TEMP_PROBE_SENTINEL = 32767
CELL_SLOT_SENTINEL = 65535

# Battery state code -> label (as observed in the field)
BATTERY_STATE_MAP = {
    320: "full",
    960: "standby",
    9152: "charging",
    5056: "discharging",
}
