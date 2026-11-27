"""Shared data hub: one set of downloads for all configured stations."""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import STORAGE_DIR, Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import engine
from .const import (
    DOMAIN,
    DS_ASSISTANCE,
    DS_LIFTS,
    DS_STATIONS,
    GTFS_INTERVAL,
    GTFS_MAX_AGE,
    GTFS_URL,
    HTTP_TIMEOUT,
    LIFTS_INTERVAL,
    ODS_BASE,
    REF_INTERVAL,
    RT_ET_URL,
    RT_INTERVAL,
    RT_SX_URL,
    SX_INTERVAL,
    TZ,
)

_LOGGER = logging.getLogger(__name__)
STORE_VERSION = 1


class SncfHub:
    """Downloads and caches every open data source, shared by all stations."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.stations: set[str] = set()
        self.cache_dir = hass.config.path(STORAGE_DIR, DOMAIN)
        self.gtfs_path = os.path.join(self.cache_dir, "gtfs.zip")
        self._ref_store: Store = Store(hass, STORE_VERSION, f"{DOMAIN}.reference")

        self.ref: dict[str, Any] = {"by_id": {}, "by_uic": {}}
        self.ref_fetched: str | None = None
        self.lifts: dict[str, list[dict]] = {}
        self.planned: dict[str, list[dict]] = {}
        self.gtfs_feed: dict = {}
        self.journeys: list[dict] = []
        self.situations: dict = {"trains": {}, "stations": {}}
        self._sx_at = 0.0

        self.ref_coordinator = DataUpdateCoordinator(
            hass, _LOGGER, name=f"{DOMAIN} reference", update_interval=REF_INTERVAL,
            update_method=self._update_reference, config_entry=None,
        )
        self.lifts_coordinator = DataUpdateCoordinator(
            hass, _LOGGER, name=f"{DOMAIN} lifts", update_interval=LIFTS_INTERVAL,
            update_method=self._update_lifts, config_entry=None,
        )
        self.gtfs_coordinator = DataUpdateCoordinator(
            hass, _LOGGER, name=f"{DOMAIN} timetable", update_interval=GTFS_INTERVAL,
            update_method=self._update_gtfs, config_entry=None,
        )
        self.rt_coordinator = DataUpdateCoordinator(
            hass, _LOGGER, name=f"{DOMAIN} realtime", update_interval=RT_INTERVAL,
            update_method=self._update_realtime, config_entry=None,
        )
        self._unsubs: list = []

    # ------------------------------------------------------------------ setup
    async def async_start(self) -> None:
        """Load the reference (cache first), then the timetable and real time."""
        cached = await self._ref_store.async_load()
        if cached:
            await self._apply_reference(cached.get("stations") or [], cached.get("assistance") or [])
            self.ref_fetched = cached.get("fetched")
        stale = True
        if self.ref_fetched:
            fetched = dt_util.parse_datetime(self.ref_fetched)
            stale = fetched is None or dt_util.now() - fetched > REF_INTERVAL
        if stale or not self.ref["by_id"]:
            await self.ref_coordinator.async_refresh()
        else:
            self.ref_coordinator.async_set_updated_data(self.ref_fetched)
        await self.lifts_coordinator.async_refresh()
        # keep coordinators polling even without entity listeners
        for coord in (self.ref_coordinator, self.lifts_coordinator, self.gtfs_coordinator, self.rt_coordinator):
            self._unsubs.append(coord.async_add_listener(lambda: None))

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    async def async_add_station(self, uic: str) -> None:
        if uic in self.stations:
            return
        self.stations.add(uic)
        await self.gtfs_coordinator.async_refresh()
        self._sx_at = 0.0
        await self.rt_coordinator.async_refresh()

    def remove_station(self, uic: str) -> None:
        self.stations.discard(uic)
        self.planned.pop(uic, None)

    # ------------------------------------------------------------- downloads
    async def _get_bytes(self, url: str) -> bytes:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        async with self.session.get(url, timeout=timeout) as resp:
            resp.raise_for_status()
            return await resp.read()

    async def _ods_export(self, dataset: str) -> list[dict]:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        async with self.session.get(f"{ODS_BASE}/{dataset}/exports/json", timeout=timeout) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        if not isinstance(data, list):
            raise UpdateFailed(f"Unexpected export format for {dataset}")
        return data

    # -------------------------------------------------------------- updates
    async def _apply_reference(self, stations: list, assistance: list) -> None:
        self.ref = await self.hass.async_add_executor_job(engine.build_reference, stations, assistance)

    async def _update_reference(self) -> str:
        try:
            stations = await self._ods_export(DS_STATIONS)
            assistance = await self._ods_export(DS_ASSISTANCE)
        except (aiohttp.ClientError, TimeoutError) as err:
            if self.ref["by_id"]:
                _LOGGER.warning("Station reference refresh failed, keeping cache: %s", err)
                return self.ref_fetched or ""
            raise UpdateFailed(f"Station reference unavailable: {err}") from err
        await self._apply_reference(stations, assistance)
        self.ref_fetched = dt_util.now().isoformat(timespec="seconds")
        await self._ref_store.async_save(
            {"fetched": self.ref_fetched, "stations": stations, "assistance": assistance}
        )
        return self.ref_fetched

    async def _update_lifts(self) -> str:
        try:
            records = await self._ods_export(DS_LIFTS)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Lift status unavailable: {err}") from err
        self.lifts = await self.hass.async_add_executor_job(engine.build_lifts, records)
        return dt_util.now().isoformat(timespec="seconds")

    def _zip_age(self) -> timedelta | None:
        try:
            return timedelta(seconds=time.time() - os.path.getmtime(self.gtfs_path))
        except OSError:
            return None

    def _write_zip(self, data: bytes) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        tmp = self.gtfs_path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, self.gtfs_path)

    async def _update_gtfs(self) -> dict:
        age = await self.hass.async_add_executor_job(self._zip_age)
        if age is None or age > GTFS_MAX_AGE:
            try:
                data = await self._get_bytes(GTFS_URL)
                await self.hass.async_add_executor_job(self._write_zip, data)
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                if age is None:
                    raise UpdateFailed(f"GTFS timetable unavailable: {err}") from err
                _LOGGER.warning("GTFS download failed, using cached timetable: %s", err)
        if not self.stations:
            return {}
        today = dt_util.now().astimezone(TZ).date()
        result = await self.hass.async_add_executor_job(
            engine.gtfs_extract, self.gtfs_path, sorted(self.stations),
            today - timedelta(days=1), today + timedelta(days=2),
        )
        self.planned = result["stations"]
        self.gtfs_feed = result["feed"]
        return {"feed": self.gtfs_feed, "built": dt_util.now().isoformat(timespec="seconds")}

    async def _update_realtime(self) -> dict:
        if not self.stations:
            return {}
        uics = sorted(self.stations)
        try:
            body = await self._get_bytes(RT_ET_URL)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Real-time feed unavailable: {err}") from err
        et = await self.hass.async_add_executor_job(engine.parse_estimated_timetable, body, uics)
        self.journeys = et["journeys"]
        if time.monotonic() - self._sx_at > SX_INTERVAL.total_seconds():
            trains: set[str] = set()
            for rows in self.planned.values():
                trains.update(r["train"] for r in rows if r["train"])
            for j in self.journeys:
                trains.update(j["trains"])
            try:
                sx_body = await self._get_bytes(RT_SX_URL)
                self.situations = await self.hass.async_add_executor_job(
                    engine.parse_situations, sx_body, trains, set(uics)
                )
                self._sx_at = time.monotonic()
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug("Disruption messages unavailable: %s", err)
        return {
            "timestamp": et["timestamp"],
            "journeys": len(self.journeys),
            "fetched": dt_util.now().isoformat(timespec="seconds"),
        }

    # -------------------------------------------------------------- queries
    def station_by_uic(self, uic: str) -> dict | None:
        gid = self.ref["by_uic"].get(str(uic))
        return self.ref["by_id"].get(gid) if gid else None

    def station_by_id(self, gid: str) -> dict | None:
        return self.ref["by_id"].get(gid)

    def lifts_for(self, gid: str) -> list[dict]:
        return self.lifts.get(gid) or []

    async def async_board(self, uic: str, rows: int, horizon: float, hide_minor: bool) -> dict:
        return await self.hass.async_add_executor_job(
            engine.build_board, uic, self.planned.get(uic) or [], self.journeys, self.situations,
            self.ref, dt_util.now().astimezone(TZ), horizon, rows, hide_minor,
        )

    def realtime_ok(self) -> bool:
        return bool(self.rt_coordinator.last_update_success and self.journeys is not None
                    and self.rt_coordinator.data)
