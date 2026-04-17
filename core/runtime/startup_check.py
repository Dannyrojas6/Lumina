"""启动前环境与资源自检。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.device.profile import DeviceProfile
from core.shared import BattleConfig, ResourceCatalog


def validate_runtime_prerequisites(
    config: BattleConfig,
    resources: ResourceCatalog,
    profile: DeviceProfile,
    *,
    device_resolution: tuple[int, int],
) -> None:
    """启动前校验固定环境和关键资源。"""
    _validate_required_templates(resources)
    _validate_device_resolution(profile, device_resolution)
    if config.support.servant.strip():
        validate_support_servant_resources(resources, config.support.servant)
    if config.battle_mode == "main" and config.smart_battle.enabled:
        for slot in config.smart_battle.frontline:
            resources.load_servant_manifest(slot.servant)


def validate_support_servant_resources(
    resources: ResourceCatalog,
    servant_name: str,
) -> None:
    """校验助战链依赖的本地资源是否齐全。"""
    manifest = resources.load_servant_manifest(servant_name)
    _require_exists(
        Path(resources.servant_manifest_path(servant_name)),
        f"{servant_name} manifest",
    )
    source_dir = Path(resources.support_source_dir(servant_name, manifest))
    _require_directory_with_pngs(source_dir, f"{servant_name} atlas/faces")
    _require_exists(
        Path(resources.support_reference_bank_path(servant_name, manifest)),
        f"{servant_name} reference_bank",
    )
    _require_exists(
        Path(resources.support_reference_meta_path(servant_name, manifest)),
        f"{servant_name} reference_meta",
    )


def _validate_required_templates(resources: ResourceCatalog) -> None:
    templates: list[str] = []
    for template_entry in resources.state_templates.values():
        if isinstance(template_entry, tuple):
            templates.extend(template_entry)
        else:
            templates.append(template_entry)
    templates.extend(
        [
            resources.template("next.png"),
            resources.template("continue_battle.png"),
            resources.template("close.png"),
            resources.template("ap_recovery.png", category="ap"),
            resources.template("bronzed_cobalt_fruit.png", category="ap"),
            resources.template("confirm.png", category="ap"),
            resources.support_class_template("all"),
            resources.support_class_template("berserker"),
        ]
    )
    for template in templates:
        _require_exists(Path(template), f"template {template}")


def _validate_device_resolution(
    profile: DeviceProfile,
    device_resolution: tuple[int, int],
) -> None:
    width, height = device_resolution
    if (width, height) != (profile.width, profile.height):
        raise RuntimeError(
            "device resolution does not match configured profile "
            f"{profile.name}: expected {profile.width}x{profile.height}, got {width}x{height}"
        )


def _require_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required {label}: {path}")


def _require_directory_with_pngs(path: Path, label: str) -> None:
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"missing required {label}: {path}")
    if not any(item.is_file() for item in path.rglob("*.png")):
        raise FileNotFoundError(f"missing required {label} png files: {path}")
