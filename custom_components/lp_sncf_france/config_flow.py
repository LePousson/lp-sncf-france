"""Config flow: search a station by name, pick it, done."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import engine
from .const import (
    CONF_HIDE_MINOR,
    CONF_HORIZON,
    CONF_QUERY,
    CONF_ROWS,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_UIC,
    DEFAULT_HIDE_MINOR,
    DEFAULT_HORIZON,
    DEFAULT_ROWS,
    DOMAIN,
)


class SncfConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._found: list[dict] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        from . import async_get_hub

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                hub = await async_get_hub(self.hass)
            except Exception:  # noqa: BLE001 - surfaced as a form error
                hub = None
            if hub is None or not hub.ref["by_id"]:
                errors["base"] = "cannot_connect"
            else:
                self._found = await self.hass.async_add_executor_job(
                    engine.search_stations, hub.ref["by_id"], user_input[CONF_QUERY], 25
                )
                self._found = [g for g in self._found if g["uic"]]
                if self._found:
                    return await self.async_step_pick()
                errors[CONF_QUERY] = "no_match"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_QUERY): TextSelector()}),
            errors=errors,
        )

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            g = next(x for x in self._found if x["id"] == user_input[CONF_STATION_ID])
            uic = g["uic"][0]
            await self.async_set_unique_id(uic)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=g["name"],
                data={CONF_UIC: uic, CONF_STATION_ID: g["id"], CONF_STATION_NAME: g["name"]},
            )
        options = []
        for g in self._found:
            tags = []
            if g["code"]:
                tags.append(g["code"].upper())
            if g["assistance"]:
                tags.append("♿")
            label = g["name"] + (f"  ({' · '.join(tags)})" if tags else "")
            options.append(SelectOptionDict(value=g["id"], label=label))
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema({
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                )
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SncfOptionsFlow()


class SncfOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        o = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_ROWS, default=o.get(CONF_ROWS, DEFAULT_ROWS)): NumberSelector(
                    NumberSelectorConfig(min=1, max=40, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_HORIZON, default=o.get(CONF_HORIZON, DEFAULT_HORIZON)): NumberSelector(
                    NumberSelectorConfig(min=1, max=48, step=1, mode=NumberSelectorMode.BOX,
                                         unit_of_measurement="h")
                ),
                vol.Required(CONF_HIDE_MINOR, default=o.get(CONF_HIDE_MINOR, DEFAULT_HIDE_MINOR)): BooleanSelector(),
            }),
        )
