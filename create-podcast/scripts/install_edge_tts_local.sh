#!/usr/bin/env bash
set -euo pipefail

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$SKILL_ROOT/.venv"

python3 -m venv "$VENV_PATH"
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install edge-tts imageio-ffmpeg

echo
echo "Installed local edge-tts environment at: $VENV_PATH"
echo "edge-tts binary: $VENV_PATH/bin/edge-tts"
echo "The renderer will now auto-detect and prefer edge-tts over espeak-ng."
