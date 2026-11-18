#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
bashio::log.info "Starte KVV Abfahrten ..."
exec python3 -u /app/server.py
