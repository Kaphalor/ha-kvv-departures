"""Sensors for KVV Departures."""
from __future__ import annotations

from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorStateClass)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Departure
from .const import DOMAIN
from .coordinator import KvvCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: KvvCoordinator = entry.runtime_data
    entities: list[SensorEntity] = [NextDepartureSensor(coordinator, entry.entry_id),
                                    NextDelaySensor(coordinator, entry.entry_id)]
    entities += [DepartureSensor(coordinator, entry.entry_id, i) for i in range(coordinator.count)]
    async_add_entities(entities)


class _Base(CoordinatorEntity[KvvCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: KvvCoordinator, entry_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)}, name=coordinator.stop.name,
            manufacturer="KVV", entry_type=DeviceEntryType.SERVICE,
        )

    def _first(self) -> Departure | None:
        return next((d for d in self.coordinator.data or [] if not d.cancelled), None)


class NextDepartureSensor(_Base):
    """Next departure; the `departures` attribute holds the full list."""

    _attr_translation_key = "next_departure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry_id) -> None:
        super().__init__(coordinator, entry_id, "next")

    @property
    def native_value(self):
        dep = self._first()
        return dep.actual if dep else None

    @property
    def extra_state_attributes(self):
        dep = self._first()
        attrs = {"stop": self.coordinator.stop.name,
                 "departures": [d.as_dict() for d in self.coordinator.data or []]}
        if dep:
            attrs |= {"line": dep.line, "direction": dep.direction,
                      "platform": dep.platform, "delay": dep.delay,
                      "planned": dep.planned.isoformat()}
        return attrs


class NextDelaySensor(_Base):
    _attr_translation_key = "next_delay"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id) -> None:
        super().__init__(coordinator, entry_id, "next_delay")

    @property
    def native_value(self):
        dep = self._first()
        return dep.delay if dep and dep.delay is not None else None


class DepartureSensor(_Base):
    """Single departure n (1-based), usable directly in entities cards."""

    _attr_translation_key = "departure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry_id, index: int) -> None:
        super().__init__(coordinator, entry_id, f"departure_{index + 1}")
        self._index = index
        self._attr_translation_placeholders = {"number": str(index + 1)}

    def _dep(self) -> Departure | None:
        data = self.coordinator.data or []
        return data[self._index] if self._index < len(data) else None

    @property
    def native_value(self):
        dep = self._dep()
        return dep.actual if dep else None

    @property
    def extra_state_attributes(self):
        dep = self._dep()
        if not dep:
            return {}
        return {**dep.as_dict(),
                "text": f"{dep.line} → {dep.direction}"}
