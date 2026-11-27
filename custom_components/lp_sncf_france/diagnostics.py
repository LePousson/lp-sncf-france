"""Diagnostics for LP SNCF France."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import SncfConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SncfConfigEntry) -> dict[str, Any]:
    coord = entry.runtime_data
    hub = coord.hub
    data = coord.data
    return {
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "hub": {
            "stations": sorted(hub.stations),
            "reference_stations": len(hub.ref["by_id"]),
            "reference_fetched": hub.ref_fetched,
            "lift_stations": len(hub.lifts),
            "gtfs_feed": hub.gtfs_feed,
            "planned_calls": {u: len(r) for u, r in hub.planned.items()},
            "realtime_journeys": len(hub.journeys),
            "realtime": hub.rt_coordinator.data,
            "realtime_ok": hub.rt_coordinator.last_update_success,
        },
        "board": {
            "departures": data.departures[:5] if data else [],
            "arrivals": data.arrivals[:5] if data else [],
            "assistance": data.assistance if data else None,
        },
    }
