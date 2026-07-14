"""Timezone helper — Asia/Ho_Chi_Minh with UTC fallback if zoneinfo unavailable.
Single source of truth for tz setup (was copy-pasted in generate_card.py,
generate_weekly.py, generate_monthly.py — see H3)."""
from datetime import datetime, timezone

try:
    import zoneinfo
    VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
except ImportError:
    VN_TZ = timezone.utc


def now_vn() -> datetime:
    """Current datetime in VN_TZ (or UTC fallback if zoneinfo unavailable)."""
    return datetime.now(VN_TZ)
