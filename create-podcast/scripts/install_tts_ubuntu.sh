#!/usr/bin/env bash
set -euo pipefail

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
else
  echo "Cannot determine operating system." >&2
  exit 1
fi

if [[ "${ID:-}" != "ubuntu" && "${ID_LIKE:-}" != *debian* ]]; then
  echo "This installer currently supports Ubuntu/Debian systems." >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required to install packages." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y espeak-ng

echo
echo "Installed espeak-ng."
echo "Verify with: espeak-ng --version"
echo "Then render audio with:"
echo "python3 <CODEX_SKILLS_DIR>/create-podcast/scripts/render_podcast.py <script-path> --output <audio-path>"
