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

# ── ffmpeg + espeak-ng (für moviepy, Whisper-Untertitel, TTS-Fallback) ─────────
if ! command -v ffmpeg &>/dev/null || ! command -v espeak-ng &>/dev/null; then
  sudo apt-get update -qq --allow-unauthenticated 2>/dev/null || true
  sudo apt-get install -y --quiet --fix-missing ffmpeg espeak-ng 2>/dev/null || true
fi

# ── PYTHONPATH setzen ──────────────────────────────────────────────────────────
echo "export PYTHONPATH=\"$CLAUDE_PROJECT_DIR\"" >> "$CLAUDE_ENV_FILE"

echo "[session-start] ✓ Alle Abhängigkeiten installiert."
