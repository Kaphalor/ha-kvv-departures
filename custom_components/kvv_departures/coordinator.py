"""DataUpdateCoordinator für KVV-Abfahrten."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TZ, Departure, KvvError, Stop, filter_departures, parse_lines
from .const import (CONF_COUNT, CONF_INTERVAL, CONF_LINES, CONF_WALK,
                    DEFAULT_COUNT, DEFAULT_INTERVAL, DOMAIN)

_LOGGER = logging.getLogger(__name__)


class KvvCoordinator(DataUpdateCoordinator[list[Departure]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client, stop: Stop) -> None:
        opts = entry.options
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN} {stop.name}", config_entry=entry,
            update_interval=timedelta(seconds=max(30, int(opts.get(CONF_INTERVAL, DEFAULT_INTERVAL)))),
        )
        self.client = client
        self.stop = stop
        self.count = int(opts.get(CONF_COUNT, DEFAULT_COUNT))
        self.lines = parse_lines(opts.get(CONF_LINES))
        self.walk = int(opts.get(CONF_WALK, 0) or 0)

    async def _async_update_data(self) -> list[Departure]:
        # Mehr abfragen, damit Linien-/Fußwegfilter genug Treffer übrig lassen
        fetch = min(60, self.count * 3 + 5) if (self.lines or self.walk) else self.count
        try:
            deps = await self.client.departures(self.stop, fetch)
        except KvvError as err:
            raise UpdateFailed(str(err)) from err
        return filter_departures(deps, self.lines, self.walk, datetime.now(TZ), self.count)
