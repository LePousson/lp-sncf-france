"""Base entity for LP SNCF France."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_STATION_NAME, CONF_UIC, DOMAIN
from .coordinator import StationCoordinator


class SncfEntity(CoordinatorEntity[StationCoordinator]):
    """One station = one service device."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: StationCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        uic = entry.data[CONF_UIC]
        self._attr_unique_id = f"{uic}_{key}"
        self._attr_translation_key = key
        station = coordinator.data.station if coordinator.data else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uic)},
            name=entry.data.get(CONF_STATION_NAME) or (station or {}).get("name") or uic,
            manufacturer="SNCF Open Data",
            model=f"Gare {((station or {}).get('code') or '').upper()}".strip(),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://ressources.data.sncf.com",
        )
