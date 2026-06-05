# spectrenet/theme.py
"""SpectreNet visual identity: dark navy base, cyan accent. Modern, not retro."""

# Core palette
NAVY_DEEP = "#050d1a"     # primary background
NAVY = "#0a1628"          # panel background
NAVY_LIGHT = "#16263f"    # borders / dividers
CYAN = "#00c8ff"          # primary accent
CYAN_DIM = "#0891b2"      # secondary accent
WHITE = "#e8f1f8"         # primary text
GREY = "#7a8ba0"          # muted text

# Semantic
RISK_HIGH = "#ff4d6d"
RISK_MED = "#ffb84d"
RISK_LOW = "#4dffa3"
SUCCESS = "#4dffa3"
WARNING = "#ffb84d"
ERROR = "#ff4d6d"

# Rich style strings
STYLE_HEADER = f"bold {CYAN} on {NAVY_DEEP}"
STYLE_PROMPT = f"bold {CYAN}"
STYLE_MUTED = GREY
STYLE_WARNING = f"bold {WARNING}"

BANNER = r"""
   ____                 _           _   _      _
  / ___| _ __  ___  ___| |_ _ __ __| \ | | ___| |_
  \___ \| '_ \/ _ \/ __| __| '__/ _ \ \| |/ _ \ __|
   ___) | |_) |  __/ (__| |_| | |  __/ |\  |  __/ |_
  |____/| .__/ \___|\___|\__|_|  \___|_| \_|\___|\__|
        |_|        Always one step ahead
"""
