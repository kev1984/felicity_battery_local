"""Binary sensor platform for Felicity Battery (Local) - fault/warning flags."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FelicityBatteryCoordinator
from .entity import device_info, iter_platform_devices


@dataclass(frozen=True, kw_only=True)
class FelicityBinarySensorDescription(BinarySensorEntityDescription):
    json_key: str = ""


BINARY_SENSOR_TYPES: tuple[FelicityBinarySensorDescription, ...] = (
    FelicityBinarySensorDescription(
        key="fault",
        translation_key="fault",
        name="Fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        json_key="Bfault",
    ),
    FelicityBinarySensorDescription(
        key="warning",
        translation_key="warning",
        name="Warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        json_key="Bwarn",
    ),
    FelicityBinarySensorDescription(
        key="bank_fault",
        translation_key="bank_fault",
        name="Bank Fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        # "BBfault" - exact scope not documented (possibly a parallel-bank /
        # secondary-controller fault code, as opposed to Bfault for this unit).
        json_key="BBfault",
    ),
    FelicityBinarySensorDescription(
        key="bank_warning",
        translation_key="bank_warning",
        name="Bank Warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        json_key="BBwarn",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    for coordinator, identifier, title, host, subentry_id in iter_platform_devices(hass, entry):
        entities = [
            FelicityFaultBinarySensor(coordinator, identifier, title, host, description)
            for description in BINARY_SENSOR_TYPES
        ]
        async_add_entities(entities, config_subentry_id=subentry_id)


class FelicityFaultBinarySensor(
    CoordinatorEntity[FelicityBatteryCoordinator], BinarySensorEntity
):
    """A fault/warning flag, on whenever the reported code is non-zero."""

    entity_description: FelicityBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FelicityBatteryCoordinator,
        identifier: str,
        title: str,
        host: str,
        description: FelicityBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}_{description.key}"
        self._attr_device_info = device_info(identifier, title, host, coordinator.data)

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        code = self.coordinator.data.get(self.entity_description.json_key)
        if code is None:
            return None
        return code != 0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self.coordinator.data:
            return None
        code = self.coordinator.data.get(self.entity_description.json_key)
        if code is None:
            return None
        return {"code": code}
