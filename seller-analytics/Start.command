#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
export SELLER_PORT="${SELLER_PORT:-8941}"
exec /usr/bin/python3 -B server.py
