"""Per-station coordinator: builds the board every minute from the shared hub data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import engine
from .const import (
    BOARD_INTERVAL,
    CONF_HIDE_MINOR,
    CONF_HORIZON,
    CONF_ROWS,
    CONF_UIC,
    DEFAULT_HIDE_MINOR,
    DEFAULT_HORIZON,
    DEFAULT_ROWS,
    DOMAIN,
    TZ,
)
from .hub import SncfHub

_LOGGER = logging.getLogger(__name__)


@dataclass
class StationData:
    station: dict | None
    departures: list[dict]
    arrivals: list[dict]
    assistance: dict
    lifts: list[dict]
    station_messages: list[dict]
    realtime: dict


class StationCoordinator(DataUpdateCoordinator[StationData]):
    """Recomputes one station's board (cheap, local) every minute and on hub updates."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, hub: SncfHub) -> None:
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN} {entry.data[CONF_UIC]}",
            update_interval=BOARD_INTERVAL, config_entry=entry,
        )
        self.hub = hub
        self.uic: str = entry.data[CONF_UIC]
        self._unsubs: list = []

    @callback
    def async_follow_hub(self) -> None:
        for coord in (self.hub.rt_coordinator, self.hub.gtfs_coordinator,
                      self.hub.lifts_coordinator, self.hub.ref_coordinator):
            self._unsubs.append(coord.async_add_listener(self._hub_updated))

    @callback
    def _hub_updated(self) -> None:
        self.hass.async_create_task(self.async_request_refresh())

    @callback
    def async_unfollow_hub(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    def _opt(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, default)

    async def _async_update_data(self) -> StationData:
        station = self.hub.station_by_uic(self.uic)
        board = await self.hub.async_board(
            self.uic,
            int(self._opt(CONF_ROWS, DEFAULT_ROWS)),
            float(self._opt(CONF_HORIZON, DEFAULT_HORIZON)),
            bool(self._opt(CONF_HIDE_MINOR, DEFAULT_HIDE_MINOR)),
        )
        now = dt_util.now().astimezone(TZ)
        assist = engine.assistance_status(station["assistance"] if station else None, now)
        rt = self.hub.rt_coordinator
        return StationData(
            station=station,
            departures=board["departures"],
            arrivals=board["arrivals"],
            assistance=assist,
            lifts=self.hub.lifts_for(station["id"]) if station else [],
            station_messages=(self.hub.situations.get("stations") or {}).get(self.uic, [])[:5],
            realtime={
                "available": bool(rt.last_update_success and rt.data),
                "updated": (rt.data or {}).get("fetched"),
                "timetable_version": (self.hub.gtfs_feed or {}).get("feed_version"),
            },
        )
