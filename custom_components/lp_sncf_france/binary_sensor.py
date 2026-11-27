"""Binary sensors: lift outage, real-time feed availability."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SncfConfigEntry
from .coordinator import StationCoordinator
from .entity import SncfEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SncfConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([LiftProblem(coordinator), RealtimeFeed(coordinator)])


class LiftProblem(SncfEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: StationCoordinator) -> None:
        super().__init__(coordinator, "lift_problem")

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        return bool(data and any(e["state"] == "ko" for e in data.lifts))


class RealtimeFeed(SncfEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: StationCoordinator) -> None:
        super().__init__(coordinator, "realtime_feed")

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        return bool(data and data.realtime.get("available"))

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        return dict(data.realtime) if data else {}
