"""固定运行环境 profile。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceProfile:
    """描述当前唯一正式支持的设备环境。"""

    name: str
    width: int
    height: int
    device_discovery_timeout: float
    device_discovery_interval: float
    operation_retry_count: int
    operation_retry_delay: float
    attack_button_delay: float
    card_select_delay: float
    target_select_delay: float


MUMU_1920X1080 = DeviceProfile(
    name="mumu_1920x1080",
    width=1920,
    height=1080,
    device_discovery_timeout=8.0,
    device_discovery_interval=0.5,
    operation_retry_count=3,
    operation_retry_delay=0.5,
    attack_button_delay=0.5,
    card_select_delay=0.3,
    target_select_delay=0.3,
)


def resolve_device_profile(profile_name: str) -> DeviceProfile:
    """解析当前支持的设备 profile。"""
    normalized = str(profile_name).strip().lower()
    if normalized == MUMU_1920X1080.name:
        return MUMU_1920X1080
    raise ValueError(f"unsupported device profile: {profile_name}")
