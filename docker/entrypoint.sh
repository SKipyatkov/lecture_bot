#!/bin/sh
set -eu

mkdir -p "$DATA_DIR/logs" "$DATA_DIR/cache" "$DATA_DIR/backups" "$DATA_DIR/temp"
chown -R bot:bot "$DATA_DIR"

exec setpriv --reuid=bot --regid=bot --init-groups --inh-caps=-all "$@"
