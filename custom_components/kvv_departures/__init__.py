"""KVV Departures - native Home Assistant integration."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import EfaClient, Stop, TriasClient
from .const import (CARD_FILE, CARD_URL, CONF_SOURCE, CONF_STOP_GID, CONF_STOP_ID,
                    CONF_STOP_NAME, CONF_TRIAS_REF, CONF_TRIAS_URL, DOMAIN,
                    SOURCE_TRIAS, VERSION)
from .coordinator import KvvCoordinator

PLATFORMS = ["sensor"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type KvvConfigEntry = ConfigEntry[KvvCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the departure board card and load it in every dashboard."""
    card = Path(__file__).parent / "frontend" / CARD_FILE
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card), cache_headers=False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    return True


def build_client(hass: HomeAssistant, options: dict):
    session = async_get_clientsession(hass)
    if options.get(CONF_SOURCE) == SOURCE_TRIAS:
        return TriasClient(session, options[CONF_TRIAS_URL], options[CONF_TRIAS_REF])
    return EfaClient(session)


async def async_setup_entry(hass: HomeAssistant, entry: KvvConfigEntry) -> bool:
    stop = Stop(entry.data[CONF_STOP_ID], entry.data.get(CONF_STOP_GID, ""),
                entry.data[CONF_STOP_NAME])
    coordinator = KvvCoordinator(hass, entry, build_client(hass, entry.options), stop)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: KvvConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: KvvConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
