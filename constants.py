"""Centralized constants for DG-LAB VRChat Controller."""

# Application
APP_VERSION = "v1.2.6"
APP_NAME = "芝士郊狼控制软件"

# Default ports
DEFAULT_WS_PORT = 9999
DEFAULT_HTTP_PORT = 8800
DEFAULT_CHATBOX_PORT = 9000

# Safety limits
SAFETY_WINDOW_SECONDS = 10.0  # 10-second window for shock accumulation
SAFETY_MAX_PER_WINDOW = 30     # max 30 seconds per window (≈3 overlapping 9s shocks)
SAFETY_MAX_TOTAL = 30          # max 30 seconds total remaining

# Intensity limits
MIN_INTENSITY = 0
MAX_INTENSITY = 200

# Timing
CLEANUP_TIMEOUT_SECONDS = 5.0

# UI
DEFAULT_WINDOW_WIDTH = 1600
DEFAULT_WINDOW_HEIGHT = 950
MIN_WINDOW_WIDTH = 1300
MIN_WINDOW_HEIGHT = 800
