#!/bin/bash
# SessionStart-Hook für rs-platform (Claude Code Web)
# Installiert alle Python-Abhängigkeiten und ffmpeg automatisch.
# Nur in Remote-Sessions ausführen (lokal nicht nötig).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# ── Python-Abhängigkeiten ──────────────────────────────────────────────────────
pip install --quiet \
  -r "$CLAUDE_PROJECT_DIR/requirements.txt" \
  -r "$CLAUDE_PROJECT_DIR/instagram/requirements.txt"

# ── ffmpeg (für moviepy + Whisper-Untertitel) ──────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
  sudo apt --fix-broken install -y --quiet
  sudo apt-get install -y --quiet ffmpeg
fi

# ── PYTHONPATH setzen ──────────────────────────────────────────────────────────
echo "export PYTHONPATH=\"$CLAUDE_PROJECT_DIR\"" >> "$CLAUDE_ENV_FILE"

echo "[session-start] ✓ Alle Abhängigkeiten installiert."
