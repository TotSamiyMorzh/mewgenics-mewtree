#!/usr/bin/env bash
# Linux / Steam Deck / macOS: builds the tree from the newest save, opens it in the browser and
# rebuilds it after every save in the game. Needs Python 3.10+ and nothing else.
#   ./run.sh            watch the saves (Ctrl+C to quit)
#   ./run.sh --pick     choose another account or save
#   ./run.sh --list     show what was found and where
# Steam in an unusual place: STEAM_DIR=/path/to/Steam ./run.sh
cd "$(dirname "$0")" || exit 1
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10 or newer was not found. Install it with your package manager (on Steam Deck it is already there in Desktop Mode)."
  echo "Не нашёл Python 3.10 или новее. Поставь его через пакетный менеджер."
  exit 1
fi
exec "$PY" src/build_tree.py --watch "$@"
