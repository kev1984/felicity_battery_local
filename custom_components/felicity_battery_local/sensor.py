"""Sensor platform for Felicity Battery (Local)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BATTERY_STATE_MAP, TEMP_PROBE_SENTINEL
from .coordinator import FelicityBatteryCoordinator
from .entity import device_info, get_path, iter_platform_devices


def _get_path(data: dict, path: list) -> Any:
    """Safely walk nested dict/list structures, returning None if missing."""
    return get_path(data, path)


def _scaled(path: list, scale: float, ndigits: int | None = None) -> Callable[[dict], Any]:
    def _fn(data: dict) -> Any:
        raw = _get_path(data, path)
        if raw is None:
            return None
        value = raw * scale
        return round(value, ndigits) if ndigits is not None else value

    return _fn


def _battery_state(data: dict) -> str | None:
    code = data.get("Estate")
    if code is None:
        return None
    return BATTERY_STATE_MAP.get(code, f"unknown ({code})")


def _bank_state(data: dict) -> str | None:
    code = data.get("Bstate")
    if code is None:
        return None
    return BATTERY_STATE_MAP.get(code, f"unknown ({code})")


def _power(data: dict) -> float | None:
    voltage = _get_path(data, ["Batt", 0, 0])
    current = _get_path(data, ["Batt", 1, 0])
    if voltage is None or current is None:
        return None
    return round((voltage / 1000) * (current / 10), 1)


def _cell_drift(data: dict) -> float | None:
    vmax = _get_path(data, ["BMaxMin", 0, 0])
    vmin = _get_path(data, ["BMaxMin", 0, 1])
    if vmax is None or vmin is None:
        return None
    return round((vmax - vmin) / 1000, 3)


@dataclass(frozen=True, kw_only=True)
class FelicitySensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any] = lambda data: None


SENSOR_TYPES: tuple[FelicitySensorDescription, ...] = (
    FelicitySensorDescription(
        key="soc",
        translation_key="soc",
        name="State of Charge",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        # BatsocList[0][0] is THIS unit's own SOC. Batsoc[0][0] is shared/
        # identical across every battery in a parallel stack (confirmed: it
        # equals the average of all units' BatsocList values) - exposed
        # separately below as "Stack State of Charge".
        value_fn=_scaled(["BatsocList", 0, 0], 0.01, 0),
    ),
    FelicitySensorDescription(
        key="stack_soc",
        translation_key="stack_soc",
        name="Stack State of Charge",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_scaled(["Batsoc", 0, 0], 0.01, 0),
    ),
    FelicitySensorDescription(
        key="soh",
        translation_key="soh",
        name="State of Health",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_scaled(["BatsocList", 0, 1], 0.1, 1),
    ),
    FelicitySensorDescription(
        key="voltage",
        translation_key="voltage",
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_scaled(["Batt", 0, 0], 0.001, 3),
    ),
    FelicitySensorDescription(
        key="current",
        translation_key="current",
        name="Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_scaled(["Batt", 1, 0], 0.1, 1),
    ),
    FelicitySensorDescription(
        key="power",
        translation_key="power",
        name="Battery Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_power,
    ),
    FelicitySensorDescription(
        key="temperature",
        translation_key="temperature",
        name="Controller Temperature (BMS board, likely)",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        # BTemp[0][0]: consistently reads a bit higher than the individual
        # cell probes (BtemList) - likely BMS board / MOSFET self-heating.
        # Not officially documented, inferred from observed data.
        value_fn=_scaled(["BTemp", 0, 0], 0.1, 1),
    ),
    FelicitySensorDescription(
        key="temperature_2",
        translation_key="temperature_2",
        name="Battery Temperature (cells, likely)",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        # BTemp[0][1]: matches the individual cell-probe readings (BtemList)
        # closely - likely the actual battery/cell temperature.
        value_fn=_scaled(["BTemp", 0, 1], 0.1, 1),
    ),
    FelicitySensorDescription(
        key="state",
        translation_key="state",
        name="Battery State",
        device_class=SensorDeviceClass.ENUM,
        options=list(BATTERY_STATE_MAP.values()),
        value_fn=_battery_state,
    ),
    FelicitySensorDescription(
        key="bank_state",
        translation_key="bank_state",
        name="Bank State",
        device_class=SensorDeviceClass.ENUM,
        options=list(BATTERY_STATE_MAP.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        # "Bstate": observed identical to Estate in testing so far. Exposed
        # separately in case it diverges in multi-pack/parallel setups.
        value_fn=_bank_state,
    ),
    FelicitySensorDescription(
        key="max_cell_voltage",
        translation_key="max_cell_voltage",
        name="Max Cell Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
        value_fn=_scaled(["BMaxMin", 0, 0], 0.001, 3),
    ),
    FelicitySensorDescription(
        key="min_cell_voltage",
        translation_key="min_cell_voltage",
        name="Min Cell Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
        value_fn=_scaled(["BMaxMin", 0, 1], 0.001, 3),
    ),
    FelicitySensorDescription(
        key="cell_voltage_drift",
        translation_key="cell_voltage_drift",
        name="Cell Voltage Drift",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
        value_fn=_cell_drift,
    ),
    FelicitySensorDescription(
        key="max_charge_current",
        translation_key="max_charge_current",
        name="Max Charge Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=_scaled(["LVolCur", 1, 0], 0.1, 1),
    ),
    FelicitySensorDescription(
        key="max_discharge_current",
        translation_key="max_discharge_current",
        name="Max Discharge Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=_scaled(["LVolCur", 1, 1], 0.1, 1),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    for coordinator, identifier, title, host, subentry_id in iter_platform_devices(hass, entry):
        entities: list[SensorEntity] = [
            FelicityBatterySensor(coordinator, identifier, title, host, description)
            for description in SENSOR_TYPES
        ]

        # Individual cell voltages: number of cells only known after first poll.
        cell_list = _get_path(coordinator.data or {}, ["BatcelList", 0])
        if isinstance(cell_list, list):
            for index in range(len(cell_list)):
                entities.append(
                    FelicityCellVoltageSensor(coordinator, identifier, title, host, index)
                )

        # Individual temperature probes: only create entities for slots that
        # are actually populated (not the "no probe" sentinel) on first poll.
        temp_list = _get_path(coordinator.data or {}, ["BtemList", 0])
        if isinstance(temp_list, list):
            for index, raw in enumerate(temp_list):
                if raw is not None and raw != TEMP_PROBE_SENTINEL:
                    entities.append(
                        FelicityTempProbeSensor(coordinator, identifier, title, host, index)
                    )

        async_add_entities(entities, config_subentry_id=subentry_id)


class FelicityBatterySensor(CoordinatorEntity[FelicityBatteryCoordinator], SensorEntity):
    """A single battery measurement."""

    entity_description: FelicitySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FelicityBatteryCoordinator,
        identifier: str,
        title: str,
        host: str,
        description: FelicitySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}_{description.key}"
        self._attr_device_info = device_info(identifier, title, host, coordinator.data)

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)


class FelicityCellVoltageSensor(CoordinatorEntity[FelicityBatteryCoordinator], SensorEntity):
    """Individual LiFePO4 cell voltage."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FelicityBatteryCoordinator,
        identifier: str,
        title: str,
        host: str,
        index: int,
    ) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_name = f"Cell {index + 1} Voltage"
        self._attr_unique_id = f"{identifier}_cell_{index + 1}_voltage"
        self._attr_device_info = device_info(identifier, title, host, coordinator.data)

    @property
    def native_value(self) -> float | None:
        raw = _get_path(self.coordinator.data or {}, ["BatcelList", 0, self._index])
        if raw is None:
            return None
        return round(raw / 1000, 2)


class FelicityTempProbeSensor(CoordinatorEntity[FelicityBatteryCoordinator], SensorEntity):
    """Individual temperature probe (from BtemList)."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FelicityBatteryCoordinator,
        identifier: str,
        title: str,
        host: str,
        index: int,
    ) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_name = f"Temperature Probe {index + 1}"
        self._attr_unique_id = f"{identifier}_temp_probe_{index + 1}"
        self._attr_device_info = device_info(identifier, title, host, coordinator.data)

    @property
    def native_value(self) -> float | None:
        raw = _get_path(self.coordinator.data or {}, ["BtemList", 0, self._index])
        if raw is None or raw == TEMP_PROBE_SENTINEL:
            return None
        return round(raw / 10, 1)
