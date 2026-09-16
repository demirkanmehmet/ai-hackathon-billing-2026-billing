#!/usr/bin/env sh
# S-A1 Alarm Firtinasi — macOS / Linux / Git Bash / WSL baslatici.
#   ./run.sh          arayuzu ac
#   ./run.sh cli      boru hattini terminalde kos
#   ./run.sh test     kurulumu dogrula
# Harici bagimlilik yok; yalnizca Python 3.9+ gerekir.
set -eu

DIZIN="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

for AY in python3 python py; do
  if command -v "$AY" >/dev/null 2>&1; then
    if "$AY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
      exec "$AY" "$DIZIN/run.py" "$@"
    fi
  fi
done

echo "HATA: Python 3.9+ bulunamadi." >&2
echo "Kurulum: https://www.python.org/downloads/" >&2
exit 1
