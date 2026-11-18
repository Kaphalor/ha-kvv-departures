"""Config and options flow: stop search and settings."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EfaClient, KvvError, Stop
from .const import (CONF_COUNT, CONF_INTERVAL, CONF_LINES, CONF_SOURCE,
                    CONF_STOP_GID, CONF_STOP_ID, CONF_STOP_NAME, CONF_TRIAS_REF,
                    CONF_TRIAS_URL, CONF_WALK, DEFAULT_COUNT, DEFAULT_INTERVAL,
                    DOMAIN, SOURCE_EFA, SOURCE_TRIAS)


class KvvConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._stops: list[Stop] = []

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = EfaClient(async_get_clientsession(self.hass))
                self._stops = await client.search_stops(user_input["query"])
            except KvvError:
                errors["base"] = "cannot_connect"
            else:
                if self._stops:
                    return await self.async_step_select()
                errors["base"] = "no_results"
        return self.async_show_form(
            step_id="user", errors=errors,
            data_schema=vol.Schema({vol.Required("query"): str}),
        )

    async def async_step_select(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            stop = next(s for s in self._stops if s.id == user_input["stop"])
            await self.async_set_unique_id(stop.id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=stop.name,
                data={CONF_STOP_ID: stop.id, CONF_STOP_GID: stop.gid, CONF_STOP_NAME: stop.name},
                options={CONF_SOURCE: SOURCE_EFA},
            )
        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema({vol.Required("stop"): vol.In({s.id: s.name for s in self._stops})}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return KvvOptionsFlow()


class KvvOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        o = self.config_entry.options
        if user_input is not None:
            if user_input[CONF_SOURCE] == SOURCE_TRIAS and not (
                    user_input.get(CONF_TRIAS_URL) and user_input.get(CONF_TRIAS_REF)):
                errors["base"] = "trias_missing"
            else:
                return self.async_create_entry(data=user_input)
        schema = vol.Schema({
            vol.Required(CONF_SOURCE, default=o.get(CONF_SOURCE, SOURCE_EFA)): vol.In([SOURCE_EFA, SOURCE_TRIAS]),
            vol.Optional(CONF_TRIAS_URL, default=o.get(CONF_TRIAS_URL, "")): str,
            vol.Optional(CONF_TRIAS_REF, default=o.get(CONF_TRIAS_REF, "")): str,
            vol.Required(CONF_COUNT, default=o.get(CONF_COUNT, DEFAULT_COUNT)): vol.All(int, vol.Range(min=1, max=20)),
            vol.Optional(CONF_LINES, default=o.get(CONF_LINES, "")): str,
            vol.Required(CONF_WALK, default=o.get(CONF_WALK, 0)): vol.All(int, vol.Range(min=0, max=60)),
            vol.Required(CONF_INTERVAL, default=o.get(CONF_INTERVAL, DEFAULT_INTERVAL)): vol.All(int, vol.Range(min=30, max=900)),
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
