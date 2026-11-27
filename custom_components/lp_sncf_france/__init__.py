"""LP SNCF France — French railway stations from SNCF open data (no API key)."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import async_get_integration

from . import engine
from .const import (
    CONF_HIDE_MINOR,
    CONF_HORIZON,
    CONF_ROWS,
    CONF_UIC,
    DEFAULT_HIDE_MINOR,
    DEFAULT_HORIZON,
    DEFAULT_ROWS,
    DOMAIN,
    SERVICE_GET_BOARD,
    SERVICE_REFRESH,
    SERVICE_SEARCH,
)
from .coordinator import StationCoordinator
from .hub import SncfHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type SncfConfigEntry = ConfigEntry[StationCoordinator]

KEY_HUB = "hub"
CARD_FILE = "lp-sncf-france-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILE}"


async def async_get_hub(hass: HomeAssistant) -> SncfHub:
    """Return the shared hub, starting it on first use."""
    data = hass.data.setdefault(DOMAIN, {})
    hub: SncfHub | None = data.get(KEY_HUB)
    if hub is None:
        hub = SncfHub(hass)
        await hub.async_start()
        data[KEY_HUB] = hub
    return hub


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _register_services(hass)
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and load it on every dashboard."""
    integration = await async_get_integration(hass, DOMAIN)
    path = Path(__file__).parent / "www" / CARD_FILE
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), True)])
    # the version in the URL makes browsers reload the card after each update
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")


async def async_setup_entry(hass: HomeAssistant, entry: SncfConfigEntry) -> bool:
    hub = await async_get_hub(hass)
    if not hub.ref["by_id"]:
        raise ConfigEntryNotReady("SNCF station reference not available yet")
    await hub.async_add_station(entry.data[CONF_UIC])
    coordinator = StationCoordinator(hass, entry, hub)
    await coordinator.async_config_entry_first_refresh()
    coordinator.async_follow_hub()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: SncfConfigEntry) -> None:
    await entry.runtime_data.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: SncfConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        coordinator: StationCoordinator = entry.runtime_data
        coordinator.async_unfollow_hub()
        hub: SncfHub = hass.data[DOMAIN][KEY_HUB]
        hub.remove_station(entry.data[CONF_UIC])
        others = [e for e in hass.config_entries.async_loaded_entries(DOMAIN) if e.entry_id != entry.entry_id]
        if not others:
            await hub.async_stop()
            hass.data[DOMAIN].pop(KEY_HUB, None)
    return ok


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
def _find_coordinator(hass: HomeAssistant, uic: str | None) -> StationCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_station")
    if not uic:
        return entries[0].runtime_data
    for e in entries:
        if e.data.get(CONF_UIC) == str(uic):
            return e.runtime_data
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_station",
                                 translation_placeholders={"uic": str(uic)})


def _register_services(hass: HomeAssistant) -> None:
    async def get_board(call: ServiceCall) -> ServiceResponse:
        coord = _find_coordinator(hass, call.data.get(CONF_UIC))
        opts = coord.config_entry.options
        board = await coord.hub.async_board(
            coord.uic,
            int(call.data.get(CONF_ROWS, opts.get(CONF_ROWS, DEFAULT_ROWS))),
            float(call.data.get(CONF_HORIZON, opts.get(CONF_HORIZON, DEFAULT_HORIZON))),
            bool(call.data.get(CONF_HIDE_MINOR, opts.get(CONF_HIDE_MINOR, DEFAULT_HIDE_MINOR))),
        )
        direction = call.data.get("direction", "departures")
        return {
            "uic": coord.uic,
            "station": (coord.data.station or {}).get("name") if coord.data else None,
            "direction": direction,
            "rows": board[direction],
            "realtime": coord.data.realtime if coord.data else {},
        }

    async def search(call: ServiceCall) -> ServiceResponse:
        hub = await async_get_hub(hass)
        found = await hass.async_add_executor_job(
            engine.search_stations, hub.ref["by_id"], call.data["query"], int(call.data.get("limit", 15))
        )
        return {
            "results": [
                {
                    "name": g["name"], "code": g["code"], "uic": g["uic"], "id": g["id"],
                    "assistance": g["assistance"] is not None,
                    "lifts": len(hub.lifts_for(g["id"])),
                }
                for g in found
            ]
        }

    async def refresh(call: ServiceCall) -> None:
        hub = await async_get_hub(hass)
        what = call.data.get("what", "realtime")
        if what in ("reference", "all"):
            await hub.ref_coordinator.async_refresh()
            await hub.lifts_coordinator.async_refresh()
        if what in ("timetable", "all"):
            await hub.gtfs_coordinator.async_refresh()
        await hub.rt_coordinator.async_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_GET_BOARD, get_board,
        schema=vol.Schema({
            vol.Optional(CONF_UIC): cv.string,
            vol.Optional("direction", default="departures"): vol.In(["departures", "arrivals"]),
            vol.Optional(CONF_ROWS): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            vol.Optional(CONF_HORIZON): vol.All(vol.Coerce(float), vol.Range(min=1, max=48)),
            vol.Optional(CONF_HIDE_MINOR): cv.boolean,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH, search,
        schema=vol.Schema({
            vol.Required("query"): cv.string,
            vol.Optional("limit", default=15): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
        }),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, refresh,
        schema=vol.Schema({
            vol.Optional("what", default="realtime"): vol.In(["realtime", "timetable", "reference", "all"]),
        }),
    )
