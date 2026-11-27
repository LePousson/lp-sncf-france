"""Sensors: departures, arrivals, assistance, lifts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SncfConfigEntry
from .const import (
    ASSIST_CLOSED,
    ASSIST_MOBILE,
    ASSIST_NONE,
    ASSIST_OPEN,
    ASSIST_UNKNOWN,
    STATUS_CANCELLED,
    STATUS_DELAYED,
)
from .coordinator import StationCoordinator
from .engine import parse_dt
from .entity import SncfEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SncfConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([
        BoardSensor(coordinator, "departures"),
        BoardSensor(coordinator, "arrivals"),
        AssistanceSensor(coordinator),
        LiftsSensor(coordinator),
    ])


class BoardSensor(SncfEntity, SensorEntity):
    """State = expected time of the next non-cancelled train; the board is in `rows`."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _unrecorded_attributes = frozenset({"rows", "station_messages", "realtime"})

    def __init__(self, coordinator: StationCoordinator, direction: str) -> None:
        super().__init__(coordinator, direction)
        self.direction = direction
        self._attr_icon = "mdi:train-car" if direction == "departures" else "mdi:train"

    def _rows(self) -> list[dict]:
        data = self.coordinator.data
        return (data.departures if self.direction == "departures" else data.arrivals) if data else []

    @property
    def native_value(self) -> datetime | None:
        for r in self._rows():
            if r["status"] != STATUS_CANCELLED:
                return parse_dt(r["expected"])
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rows = self._rows()
        data = self.coordinator.data
        return {
            "uic": self.coordinator.uic,
            "direction": self.direction,
            "rows": rows,
            "count": len(rows),
            "delayed": sum(1 for r in rows if r["status"] == STATUS_DELAYED),
            "cancelled": sum(1 for r in rows if r["status"] == STATUS_CANCELLED),
            "station_messages": data.station_messages if data else [],
            "realtime": data.realtime if data else {},
        }


class AssistanceSensor(SncfEntity, SensorEntity):
    """PSH/PMR assistance service state right now."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [ASSIST_OPEN, ASSIST_CLOSED, ASSIST_MOBILE, ASSIST_NONE, ASSIST_UNKNOWN]
    _attr_icon = "mdi:human-wheelchair"
    _unrecorded_attributes = frozenset({"hours", "holidays", "unavailable_days"})

    def __init__(self, coordinator: StationCoordinator) -> None:
        super().__init__(coordinator, "assistance")

    @property
    def native_value(self) -> str:
        data = self.coordinator.data
        return data.assistance.get("state", ASSIST_UNKNOWN) if data else ASSIST_UNKNOWN

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if not data or not data.station:
            return {}
        a = data.station.get("assistance") or {}
        st = data.assistance
        return {
            "until": st.get("until"),
            "opens": st.get("opens"),
            "today": st.get("today"),
            "type": a.get("type"),
            "meeting_point": a.get("meeting_point"),
            "taxi_point": a.get("taxi_point"),
            "first_to_last_train": a.get("first_to_last_train"),
            "hours": a.get("hours"),
            "holidays": a.get("holidays"),
            "unavailable_days": a.get("unavailable_days"),
        }


class LiftsSensor(SncfEntity, SensorEntity):
    """Number of lifts/escalators out of order."""

    _attr_icon = "mdi:elevator-passenger"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = None
    _unrecorded_attributes = frozenset({"equipment"})

    def __init__(self, coordinator: StationCoordinator) -> None:
        super().__init__(coordinator, "lifts_out_of_order")

    @property
    def native_value(self) -> int:
        data = self.coordinator.data
        return sum(1 for e in data.lifts if e["state"] == "ko") if data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        lifts = data.lifts if data else []
        return {
            "total": len(lifts),
            "ok": sum(1 for e in lifts if e["state"] == "ok"),
            "unknown": sum(1 for e in lifts if e["state"] == "unknown"),
            "equipment": lifts,
        }
