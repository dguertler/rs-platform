"""
instagram/cinematic_reel.py — Cinematischer Reel-Renderer für AI Alpha Selection

Ersetzt den statischen Ken-Burns-Reel durch:
  1. TTS-Voiceover via edge-tts (de-DE-KillianNeural)
  2. Stock-Footage-Download von Pexels (kostenlos, kein Attributions-Zwang)
  3. Whisper-Untertitel (wortweise, gebrannt)
  4. MoviePy-Schnitt: Clips + Logo-Overlay + Rating-Overlay (Sek. 6–9)
  5. Finale H.264-MP4, 1080×1920, 30fps

Aufruf (nach expliziter Stage-2-Bestätigung):
    python3 instagram/cinematic_reel.py --ticker AMD \\
        --hook-typ wissensluecke \\
        --script out/instagram/2026-06-17_ANALYSE_AMD/reel_script.txt \\
        --output out/instagram/2026-06-17_ANALYSE_AMD/reel_cinematic.mp4

Ohne PEXELS_API_KEY: Fallback auf schwarze Clips (Voiceover + Untertitel bleiben).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CFG_PATH = Path(__file__).parent / "config" / "tech_trader.yaml"
LOGO_PATH = Path(__file__).parent / "assets" / "Logo.png"
LOGOS_DIR = Path(__file__).parent / "assets" / "logos"

# Sektor → Pexels-Keywords für stock-footage
_SECTOR_KEYWORDS = {
    "Technology":            ["semiconductor chip closeup 4k", "data center servers glowing 4k", "circuit board macro 4k"],
    "Semiconductors":        ["semiconductor wafer production 4k", "microchip glowing blue 4k", "chip factory cleanroom 4k"],
    "Software":              ["dark code screen abstract 4k", "software developer multiple screens 4k", "abstract digital network 4k"],
    "Healthcare":            ["medical laboratory research 4k", "biotech lab glowing 4k", "doctor digital screen 4k"],
    "Consumer Cyclical":     ["modern retail store 4k", "electric vehicle charging 4k", "luxury consumer products 4k"],
    "Financial Services":    ["stock market trading floor 4k", "financial data screen night 4k", "banking skyscrapers 4k"],
    "Communication Services":["fiber optic network abstract 4k", "social media data stream 4k", "5g tower night 4k"],
    "Energy":                ["oil refinery night 4k", "solar panel field aerial 4k", "energy grid abstract 4k"],
    "Industrials":           ["industrial factory automation 4k", "robotic arm factory 4k", "aerospace jet engine 4k"],
    "default":               ["abstract financial data neon 4k", "dark tech background 4k", "stock market data screen night 4k"],
}


def _ticker_footage_keywords(ticker: str) -> list[str]:
    """Gibt sektor-spezifische Pexels-Keywords für einen Ticker zurück."""
    try:
        import json
        fund_path = ROOT / "data" / "fundamentals.json"
        if fund_path.exists():
            fund = json.loads(fund_path.read_text(encoding="utf-8"))
            t = fund.get("tickers", {}).get(ticker, {})
            sector = t.get("sector", "")
            industry = t.get("industry", "")
            # Semiconductors gezielt abfangen
            if "semiconductor" in (industry or "").lower():
                return _SECTOR_KEYWORDS["Semiconductors"]
            for key in _SECTOR_KEYWORDS:
                if key.lower() in (sector or "").lower():
                    return _SECTOR_KEYWORDS[key]
    except Exception:
        pass
    return _SECTOR_KEYWORDS["default"]


def _ticker_logo(ticker: str) -> Optional[Path]:
    """Sucht das Firmenlogo in logos/ — PNG bevorzugt, JPEG akzeptiert."""
    for ext in (".png", ".PNG", ".jpeg", ".jpg", ".JPEG"):
        p = LOGOS_DIR / f"{ticker}{ext}"
        if p.exists():
            return p
    return None


def _load_cfg() -> dict:
    import yaml
    with open(CFG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Pexels-Footage ─────────────────────────────────────────────────────────────

def _pexels_download(query: str, dest: str, api_key: str, min_dur: int = 4) -> bool:
    import requests
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 10, "orientation": "portrait", "size": "large"}
    try:
        r = requests.get("https://api.pexels.com/videos/search",
                         headers=headers, params=params, timeout=15)
        r.raise_for_status()
        videos = r.json().get("videos", [])
    except Exception as exc:
        print(f"  [Pexels] Suche fehlgeschlagen für '{query}': {exc}")
        return False

    for v in videos:
        if v.get("duration", 0) < min_dur:
            continue
        files = sorted(v.get("video_files", []),
                       key=lambda f: f.get("width", 0) * f.get("height", 0),
                       reverse=True)
        for vf in files:
            if vf.get("width", 9999) <= vf.get("height", 0):  # Portrait
                url = vf["link"]
                try:
                    dl = requests.get(url, stream=True, timeout=60)
                    dl.raise_for_status()
                    with open(dest, "wb") as fp:
                        for chunk in dl.iter_content(chunk_size=1 << 16):
                            fp.write(chunk)
                    print(f"  [Pexels] ✓ '{query}' → {dest}")
                    return True
                except Exception as exc:
                    print(f"  [Pexels] Download-Fehler: {exc}")
    print(f"  [Pexels] Kein passender Clip für '{query}'")
    return False


# ── TTS: edge-tts (bevorzugt) oder espeak-ng (Fallback) ───────────────────────

async def _tts_edge_async(text: str, voice: str, dest: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(dest)


def _run_tts(text: str, voice: str, dest: str) -> None:
    """Versucht edge-tts; fällt bei SSL-Fehler auf espeak-ng zurück."""
    try:
        asyncio.run(_tts_edge_async(text, voice, dest))
        print("  [TTS] edge-tts ✓")
    except Exception as exc:
        print(f"  [TTS] edge-tts fehlgeschlagen ({exc.__class__.__name__}), "
              f"Fallback auf espeak-ng…")
        _run_tts_espeak(text, dest)


def _run_tts_espeak(text: str, dest: str) -> None:
    """Offline-TTS: MBROLA mb-de6 (natürlicher) → Fallback espeak-ng Standard."""
    wav_path = dest.replace(".mp3", ".wav")
    # Versuche zuerst MBROLA mb-de6 (klingt deutlich natürlicher)
    result = subprocess.run(
        ["espeak-ng", "-v", "mb-de6", "-s", "130", "-w", wav_path, text],
        capture_output=True,
    )
    if result.returncode != 0:
        # Fallback auf Standard-espeak-ng
        result = subprocess.run(
            ["espeak-ng", "-v", "de", "-s", "130", "-w", wav_path, text],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"espeak-ng fehlgeschlagen: {result.stderr.decode()}")
        print("  [TTS] espeak-ng de ✓")
    else:
        print("  [TTS] espeak-ng mb-de6 (MBROLA) ✓")
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-q:a", "4", dest],
        capture_output=True, check=True,
    )
    os.remove(wav_path)


# ── Whisper-Untertitel ─────────────────────────────────────────────────────────

def _whisper_srt(audio_path: str, srt_path: str) -> None:
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, language="de", word_timestamps=True)
    _write_word_srt(result, srt_path)


def _write_word_srt(result: dict, srt_path: str) -> None:
    idx = 1
    lines = []
    for seg in result.get("segments", []):
        for word_info in seg.get("words", []):
            start = word_info["start"]
            end = word_info["end"]
            word = word_info["word"].strip()
            if not word:
                continue
            lines.append(str(idx))
            lines.append(f"{_ts(start)} --> {_ts(end)}")
            lines.append(word)
            lines.append("")
            idx += 1
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ── Szenen-Parser für reel_script.txt ─────────────────────────────────────────

def _parse_scenes(script_path: str) -> list[dict]:
    """
    Extrahiert Szenen aus reel_script.txt.
    Erwartet Blöcke der Form:
        [SZENE N – H:MM–H:MM]
        Visual: [Pexels: <keywords>]
        Voiceover: "<text>"
    """
    text = Path(script_path).read_text(encoding="utf-8")
    scenes = []
    blocks = re.split(r"\[SZENE \d+", text)
    for block in blocks[1:]:
        visual_m = re.search(r"Visual:\s*\[Pexels:\s*([^\]]+)\]", block)
        vo_m = re.search(r'Voiceover:\s*[\"„"](.+?)[\""\"]', block, re.DOTALL)
        if visual_m and vo_m:
            scenes.append({
                "visual": visual_m.group(1).strip(),
                "vo": vo_m.group(1).strip().replace("\n", " "),
            })
    return scenes


# ── SRT aus Szenen-Text generieren (kein Whisper-Download nötig) ──────────────

def _build_srt_from_scenes(scenes: list[dict], audio_path: str,
                           srt_path: str) -> Optional[str]:
    """
    Baut eine SRT-Datei direkt aus dem Szenen-Voiceover-Text.
    Teilt den Text gleichmäßig auf die Audio-Dauer auf — kein Whisper-Modell nötig.
    """
    try:
        # Audio-Dauer per ffprobe ermitteln
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", audio_path],
            capture_output=True, text=True, check=True,
        )
        import json
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except Exception as exc:
        print(f"  [SRT] ffprobe fehlgeschlagen ({exc}) — ohne Untertitel")
        return None

    words_per_scene = [s["vo"].split() for s in scenes]
    total_words = sum(len(w) for w in words_per_scene)
    if total_words == 0:
        return None

    idx = 1
    lines = []
    t = 0.0
    for w_list in words_per_scene:
        if not w_list:
            continue
        scene_dur = duration * len(w_list) / total_words
        word_dur = scene_dur / len(w_list)
        for word in w_list:
            end = min(t + word_dur, duration)
            lines.append(str(idx))
            lines.append(f"{_ts(t)} --> {_ts(end)}")
            lines.append(word)
            lines.append("")
            idx += 1
            t = end

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  [SRT] {idx - 1} Wort-Untertitel generiert ✓")
    return srt_path


# ── Cinematische Prozedur-Hintergründe via ffmpeg geq-Filter ─────────────────

# Jede Szene bekommt einen anderen animierten Dunkel-Gradienten
_BG_PRESETS = [
    # hook: dunkles Lila-Blau pulsierend
    "r='15+8*sin(2*PI*T/7)':g='5+3*sin(2*PI*T/9+1)':b='45+25*sin(2*PI*T/5+2)'",
    # daten: dunkles Cyan-Teal
    "r='8+5*sin(2*PI*T/8+1)':g='25+15*sin(2*PI*T/6)':b='40+20*sin(2*PI*T/7+3)'",
    # analyse: dunkles Gold-Orange
    "r='40+20*sin(2*PI*T/6)':g='20+10*sin(2*PI*T/8+1)':b='5+3*sin(2*PI*T/10)'",
    # fazit: dunkles Grün
    "r='8+4*sin(2*PI*T/9)':g='35+18*sin(2*PI*T/7+2)':b='10+5*sin(2*PI*T/5+1)'",
    # cta: dunkles Magenta
    "r='38+18*sin(2*PI*T/6+1)':g='5+3*sin(2*PI*T/9)':b='40+20*sin(2*PI*T/7+2)'",
    # extra: dunkles Blau-Silber
    "r='12+6*sin(2*PI*T/8+2)':g='18+10*sin(2*PI*T/6+1)':b='50+22*sin(2*PI*T/5)'",
    # extra2: dunkles Rot-Dunkel
    "r='45+18*sin(2*PI*T/5)':g='8+4*sin(2*PI*T/8+2)':b='12+6*sin(2*PI*T/9+1)'",
]


def _generate_bg_cinematic(scene_idx: int, dest: str, W: int, H: int, dur: float) -> None:
    """Erzeugt einen animierten Cinematic-Hintergrund via ffmpeg geq (vollständig offline)."""
    preset = _BG_PRESETS[scene_idx % len(_BG_PRESETS)]
    # Animierter Gradient + leichtes Grain für Film-Look
    vf = (
        f"nullsrc=size={W}x{H}:rate=30,geq={preset},"
        f"noise=alls=12:allf=t+u,"
        f"vignette=PI/4"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", vf,
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        dest,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        # Fallback: einfarbiger dunkler Clip
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=0x0d0e1a:size={W}x{H}:rate=30",
            "-t", str(dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", dest,
        ], capture_output=True, check=True)


def _png_to_video(png_path: str, dest: str, W: int, H: int, dur: float) -> None:
    """Konvertiert ein PNG-Bild in ein kurzes MP4 mit leichtem Zoom-Effekt (Legacy-Fallback)."""
    zoom = "scale=8000:-1,zoompan=z='min(zoom+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30".replace("{W}", str(W)).replace("{H}", str(H))
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", png_path,
        "-vf", zoom, "-t", str(dur),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", dest,
    ]
    subprocess.run(cmd, capture_output=True, check=True)


# ── Chart-Szene (Kurschart + Kennzahlen) ──────────────────────────────────────

def _generate_chart_scene(ticker: str, score: Optional[int], verdict: str,
                          dest_png: str, W: int, H: int) -> bool:
    """Generiert ein dunkles Kurschart-PNG mit RS-Score und Kennzahlen."""
    try:
        import json, numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import FancyBboxPatch
        from datetime import datetime as dt

        # Kursdaten laden (NASDAQ-100 → S&P 500 → DAX als Fallback)
        ohlcv = None
        rs_score_val = None
        for fname in ("data/rs_full.json", "data/rs_sp500.json", "data/rs_dax.json"):
            fpath = ROOT / fname
            if not fpath.exists():
                continue
            data = json.loads(fpath.read_text(encoding="utf-8"))
            entry = next((e for e in data.get("data", [])
                          if e.get("ticker") == ticker), None)
            if entry and entry.get("ohlcv"):
                ohlcv = entry["ohlcv"]
                rs_score_val = entry.get("rs_score")
                break

        if not ohlcv:
            return False

        # Letzte 26 Wochen (~6 Monate)
        ohlcv = ohlcv[-130:]
        dates = [dt.strptime(r["d"], "%Y-%m-%d") for r in ohlcv]
        closes = [r["c"] for r in ohlcv]

        # Fundamentaldaten
        fund_path = ROOT / "data" / "fundamentals.json"
        fund = {}
        if fund_path.exists():
            all_fund = json.loads(fund_path.read_text(encoding="utf-8"))
            fund = all_fund.get("tickers", {}).get(ticker, {})

        # Dark-Theme Chart
        fig = plt.figure(figsize=(W / 150, H / 150), dpi=150)
        fig.patch.set_facecolor("#0d0e1a")
        ax = fig.add_axes([0.08, 0.30, 0.84, 0.52])
        ax.set_facecolor("#0d0e1a")

        # Kurslinie + Gradient-Fill
        color = "#00c896" if closes[-1] >= closes[0] else "#ff4d6d"
        ax.plot(dates, closes, color=color, linewidth=2.0, zorder=3)
        ax.fill_between(dates, closes, min(closes) * 0.98,
                        color=color, alpha=0.15, zorder=2)

        # Achsen
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.tick_params(colors="#888888", labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333344")
        ax.yaxis.set_tick_params(labelcolor="#888888")
        ax.set_xlim(dates[0], dates[-1])

        # Ticker + Verdict oben
        pct = (closes[-1] / closes[0] - 1) * 100
        pct_str = f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"
        fig.text(0.08, 0.89, ticker, color="#ffffff", fontsize=28, fontweight="bold",
                 transform=fig.transFigure)
        fig.text(0.08, 0.84, f"6-Monats-Performance: {pct_str}",
                 color=color, fontsize=13, transform=fig.transFigure)

        # Verdict + Score Badge
        verdict_color = {"BUY": "#00c896", "HOLD": "#f5a623", "SELL": "#ff4d6d"}.get(
            (verdict or "").upper(), "#aaaaaa")
        if verdict:
            fig.text(0.92, 0.89, verdict.upper(), color=verdict_color,
                     fontsize=22, fontweight="bold", ha="right",
                     transform=fig.transFigure)
        if score is not None:
            fig.text(0.92, 0.84, f"Score {score}/100", color="#aaaaaa",
                     fontsize=12, ha="right", transform=fig.transFigure)

        # Kennzahlen-Grid unten (4 Metriken)
        metrics = []
        pe = fund.get("trailingPE") or fund.get("forwardPE")
        if pe:
            metrics.append(("KGV", f"{pe:.1f}x"))
        rev_growth = fund.get("revenueGrowth")
        if rev_growth is not None:
            metrics.append(("Umsatzwachstum", f"{rev_growth*100:+.1f}%"))
        mkt = fund.get("marketCap")
        if mkt:
            if mkt >= 1e12:
                metrics.append(("Marktkapitalisierung", f"${mkt/1e12:.1f}B"))
            else:
                metrics.append(("Marktkapitalisierung", f"${mkt/1e9:.0f}Mrd"))
        if rs_score_val is not None:
            metrics.append(("RS-Score", f"{rs_score_val:.0f}"))

        metrics = metrics[:4]
        if metrics:
            cols = len(metrics)
            for j, (label, val) in enumerate(metrics):
                x = 0.08 + j * (0.84 / cols) + (0.84 / cols) / 2
                fig.text(x, 0.22, val, color="#ffffff", fontsize=14,
                         fontweight="bold", ha="center", transform=fig.transFigure)
                fig.text(x, 0.17, label, color="#666688", fontsize=9,
                         ha="center", transform=fig.transFigure)

        # Trennlinie
        fig.add_artist(plt.Line2D([0.05, 0.95], [0.27, 0.27],
                                  transform=fig.transFigure,
                                  color="#333344", linewidth=0.8))

        # Branding
        fig.text(0.5, 0.04, "AI Alpha Selection", color="#444466",
                 fontsize=10, ha="center", transform=fig.transFigure)

        plt.savefig(dest_png, dpi=150, bbox_inches="tight",
                    facecolor="#0d0e1a", edgecolor="none")
        plt.close(fig)
        return True
    except Exception as exc:
        print(f"  [Chart] Fehler beim Generieren ({exc})")
        return False


# ── CTA-Endszene mit Analyse-Slide-Montage ────────────────────────────────────

def _generate_cta_scene(ticker: str, carousel_dir: Optional[Path],
                        dest_png: str, W: int, H: int) -> bool:
    """CTA-Slide: 4 Analyse-Slides als Montage + 'Komplette Analyse auf meinem Profil'."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image as PILImage
        import numpy as np

        fig = plt.figure(figsize=(W / 150, H / 150), dpi=150)
        fig.patch.set_facecolor("#0d0e1a")

        # Analyse-Slides sammeln (max. 4)
        slides = []
        if carousel_dir and carousel_dir.exists():
            for f in sorted(carousel_dir.glob("*.png"))[:4]:
                try:
                    slides.append(np.array(PILImage.open(f).convert("RGB")))
                except Exception:
                    pass

        if slides:
            # 2×2 Grid der Slides (leicht geneigt für Tiefe)
            positions = [(0.05, 0.38, 0.43, 0.42), (0.52, 0.38, 0.43, 0.42),
                         (0.05, 0.08, 0.43, 0.28), (0.52, 0.08, 0.43, 0.28)]
            for idx, (img, (x, y, w, h)) in enumerate(zip(slides, positions)):
                ax = fig.add_axes([x, y, w, h])
                ax.imshow(img)
                ax.axis("off")
                for spine in ax.spines.values():
                    spine.set_visible(False)
                # Rahmen
                rect = plt.Rectangle((0, 0), 1, 1, fill=False,
                                      edgecolor="#2a2a4a", linewidth=2,
                                      transform=ax.transAxes)
                ax.add_patch(rect)

        # CTA-Text
        fig.text(0.5, 0.94, "Komplette Analyse", color="#ffffff",
                 fontsize=22, fontweight="bold", ha="center",
                 transform=fig.transFigure)
        fig.text(0.5, 0.89, "auf meinem Instagram-Profil",
                 color="#00c896", fontsize=14, ha="center",
                 transform=fig.transFigure)
        fig.text(0.5, 0.84, f"AI Alpha Selection  ·  {ticker}",
                 color="#555577", fontsize=11, ha="center",
                 transform=fig.transFigure)

        plt.savefig(dest_png, dpi=150, bbox_inches="tight",
                    facecolor="#0d0e1a", edgecolor="none")
        plt.close(fig)
        return True
    except Exception as exc:
        print(f"  [CTA] Fehler ({exc})")
        return False


# ── Rating-Overlay (dynamisch gerendert) ──────────────────────────────────────

def _make_rating_overlay(score: Optional[int], verdict: str,
                         size: tuple = (540, 180)) -> str:
    from PIL import Image, ImageDraw, ImageFont
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=24,
                            fill=(47, 107, 255, 220))
    score_txt = f"{score}/100" if score is not None else "—"
    def _pil_font(size):
        candidates = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/Library/Fonts/Arial Bold.ttf",
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    continue
        return ImageFont.load_default()
    font_big = _pil_font(56)
    font_sm  = _pil_font(28)
    draw.text((w // 2, 55), score_txt, fill="#FFFFFF", font=font_big, anchor="mm")
    draw.text((w // 2, 110), verdict, fill="#00F0FF", font=font_sm, anchor="mm")
    dest = tempfile.mktemp(suffix="_rating.png")
    img.save(dest, "PNG")
    return dest


# ── Logo-Breite ────────────────────────────────────────────────────────────────

def _logo_width(path: Path, height: int = 80) -> int:
    from PIL import Image
    img = Image.open(path)
    return int(height * img.width / img.height)


# ── Clip-Crop ──────────────────────────────────────────────────────────────────

def _crop_portrait(clip, W: int, H: int):
    import moviepy.video.fx as vfx
    cw, ch = clip.size
    scale = max(W / cw, H / ch)
    new_w, new_h = int(cw * scale), int(ch * scale)
    clip = clip.with_effects([vfx.Resize((new_w, new_h))])
    x1 = (new_w - W) // 2
    y1 = (new_h - H) // 2
    return clip.with_effects([vfx.Crop(x1=x1, y1=y1, x2=x1 + W, y2=y1 + H)])


# ── Untertitel einbrennen ──────────────────────────────────────────────────────

def _burn_subtitles(video_in: str, srt_path: str, video_out: str, cfg: dict) -> None:
    fs = cfg["subtitles"]["font_size"]
    fc = cfg["subtitles"]["font_color"].lstrip("#")
    oc = cfg["subtitles"]["outline_color"].lstrip("#")
    ow = cfg["subtitles"]["outline_width"]
    style = (f"FontSize={fs},PrimaryColour=&H{fc},OutlineColour=&H{oc},"
             f"Outline={ow},Alignment=2,MarginV=200")
    # SRT neben das Video kopieren → relativer Pfad vermeidet Windows-Laufwerksbuchstaben-Problem
    srt_local = os.path.join(os.path.dirname(video_in), "subtitles_burn.srt")
    shutil.copy2(srt_path, srt_local)
    # ffmpeg aus dem Verzeichnis des Videos ausführen → nur Dateiname nötig
    srt_name = os.path.basename(srt_local).replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y", "-i", video_in,
        "-vf", f"subtitles={srt_name}:force_style='{style}'",
        "-c:a", "copy", video_out,
    ]
    result = subprocess.run(cmd, capture_output=True, cwd=os.path.dirname(video_in))
    if result.returncode != 0:
        shutil.copy2(video_in, video_out)
        print("  [Untertitel] ffmpeg-Fehler, Video ohne Untertitel gespeichert.")
    try:
        os.remove(srt_local)
    except OSError:
        pass


# ── Haupt-Rendering ────────────────────────────────────────────────────────────

def render(
    ticker: str,
    hook_typ: str,
    script_path: str,
    output_path: str,
    score: Optional[int] = None,
    verdict: str = "",
    hype_aktie: str = "Nvidia",
) -> str:
    from moviepy import (
        VideoFileClip, ImageClip, CompositeVideoClip,
        concatenate_videoclips, AudioFileClip, ColorClip,
    )
    import moviepy.video.fx as vfx

    cfg = _load_cfg()
    api_key = os.environ.get(cfg["stock_footage"]["api_key_env"], "")
    voice = cfg["voice"]
    fps = cfg["video"]["fps"]
    scene_sec = cfg["video"]["scene_max_sec"]
    fade = cfg["video"]["crossfade_sec"]
    W, H = cfg["video"]["resolution"]
    rov_start = cfg["rating_overlay"]["start_sec"]
    rov_end = cfg["rating_overlay"]["end_sec"]

    try:
        from . import hook_generator
    except ImportError:
        import sys
        sys.path.insert(0, str(ROOT))
        from instagram import hook_generator
    hook = hook_generator.get_hook_typed(hook_typ, ticker, hype_aktie)

    # Szenen laden und Hook als Szene 1 setzen
    scenes = []
    if script_path and Path(script_path).exists():
        scenes = _parse_scenes(script_path)
    hook_scene = {"visual": hook["visual"], "vo": hook["text"]}
    if scenes:
        scenes[0] = hook_scene
    else:
        scenes = [hook_scene]

    print(f"\n[Cinematic Reel] {ticker} | Hook: {hook['typ']}")
    print(f"  Voiceover Szene 1: {hook['text'][:80]}…")
    print(f"  Szenen gesamt: {len(scenes)}\n")

    tmpdir = tempfile.mkdtemp(prefix=f"reel_{ticker}_")
    full_vo = " ".join(s["vo"] for s in scenes)
    audio_path = os.path.join(tmpdir, "voiceover.mp3")
    srt_path = os.path.join(tmpdir, "subtitles.srt")

    print("[1/5] TTS generieren…")
    _run_tts(full_vo, voice, audio_path)

    print("[2/5] Untertitel aus Voiceover-Text generieren…")
    srt_path = _build_srt_from_scenes(scenes, audio_path, srt_path)

    print("[3/5] Stock-Footage laden (Pexels → Chart-Szene → Gradient-Fallback)…")
    ticker_kw = _ticker_footage_keywords(ticker)
    fallback_kw = cfg["stock_footage"]["fallback_keywords"]

    # Chart-PNG als Szene 2 (nach dem Hook) generieren
    chart_png = os.path.join(tmpdir, "chart_scene.png")
    chart_ok = _generate_chart_scene(ticker, score, verdict or "", chart_png, W, H)
    if chart_ok:
        print(f"  [Chart] Kurschart + Kennzahlen ✓")

    # CTA-Szene ans Ende anhängen
    carousel_dir = Path(script_path).parent / "carousel" if script_path else None
    cta_png = os.path.join(tmpdir, "cta_scene.png")
    cta_ok = _generate_cta_scene(ticker, carousel_dir, cta_png, W, H)
    if cta_ok:
        scenes.append({"visual": "instagram profile swipe", "vo": ""})
        print(f"  [CTA] Endszene mit Analyse-Slides ✓")

    # Audio-Dauer ermitteln um letzten Clip richtig lang zu generieren
    try:
        import json as _json
        _probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
            capture_output=True, text=True, check=True)
        audio_dur = float(_json.loads(_probe.stdout)["format"]["duration"])
    except Exception:
        audio_dur = len(scenes) * scene_sec

    n = len(scenes)
    total_video_dur = n * scene_sec - max(0, n - 1) * fade
    # Letzten Clip so lang machen dass Video >= Audio (+ 0.3s Puffer)
    last_scene_dur = scene_sec + max(0.0, audio_dur - total_video_dur + 0.3)

    video_paths = []
    for i, scene in enumerate(scenes):
        dest = os.path.join(tmpdir, f"scene_{i:02d}.mp4")
        dur = last_scene_dur if i == n - 1 else scene_sec
        ok = False
        # Szene 2 (Index 1) → Chart-PNG
        if i == 1 and chart_ok:
            _png_to_video(chart_png, dest, W, H, dur)
            ok = True
        # Letzte Szene → CTA-PNG
        if not ok and cta_ok and i == n - 1:
            _png_to_video(cta_png, dest, W, H, dur)
            ok = True
        if not ok and api_key:
            kw = ticker_kw[i % len(ticker_kw)] if ticker_kw else scene["visual"]
            ok = _pexels_download(scene["visual"], dest, api_key, min_dur=int(dur))
            if not ok:
                ok = _pexels_download(kw, dest, api_key, min_dur=int(dur))
        if not ok:
            _generate_bg_cinematic(i, dest, W, H, dur)
            ok = True
        video_paths.append(dest if ok else None)

    print("[4/5] Clips zusammenstellen…")
    clips = []
    for i, vpath in enumerate(video_paths):
        if vpath and Path(vpath).exists():
            try:
                cl = VideoFileClip(vpath).subclipped(0, scene_sec)
                clips.append(_crop_portrait(cl, W, H))
                continue
            except Exception as exc:
                print(f"  Clip {i} fehlgeschlagen ({exc})")
        clips.append(ColorClip(size=(W, H), color=(14, 19, 32), duration=scene_sec))

    # Crossfade zwischen Clips (moviepy 2.x: with_effects)
    final_clips = [clips[0]]
    for cl in clips[1:]:
        final_clips.append(cl.with_effects([vfx.CrossFadeIn(fade)]))
    video = concatenate_videoclips(final_clips, method="compose", padding=-fade)

    audio = AudioFileClip(audio_path)
    # Audio auf Video-Dauer anpassen (sicher: nie über echte Audio-Länge hinaus)
    safe_dur = min(audio.duration - 0.05, video.duration)
    video = video.with_audio(audio.with_duration(safe_dur))

    # Logo — AI Alpha Selection Brand + Ticker-Firmenlogo (oben links)
    overlays = [video]
    if LOGO_PATH.exists():
        lw = _logo_width(LOGO_PATH, height=60)
        logo = (ImageClip(str(LOGO_PATH))
                .with_effects([vfx.Resize(height=60)])
                .with_duration(video.duration)
                .with_position((W - lw - 30, 30)))
        overlays.append(logo)
    ticker_logo_path = _ticker_logo(ticker)
    if ticker_logo_path:
        try:
            tlw = _logo_width(ticker_logo_path, height=70)
            tlogo = (ImageClip(str(ticker_logo_path))
                     .with_effects([vfx.Resize(height=70)])
                     .with_duration(video.duration)
                     .with_position((30, 30)))
            overlays.append(tlogo)
        except Exception:
            pass
    if len(overlays) > 1:
        video = CompositeVideoClip(overlays)

    # Rating-Overlay (Sek. 6–9)
    if video.duration >= rov_end and (score is not None or verdict):
        rating_png = _make_rating_overlay(score, verdict)
        rating_clip = (ImageClip(rating_png)
                       .with_start(rov_start)
                       .with_end(rov_end)
                       .with_position("center"))
        video = CompositeVideoClip([video, rating_clip])

    raw_path = os.path.join(tmpdir, "raw.mp4")
    print("[5/5] Video schreiben…")
    os.makedirs(Path(output_path).parent, exist_ok=True)
    video.write_videofile(
        raw_path, codec="libx264", fps=fps, audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "23"],
        logger=None,
    )

    if srt_path and Path(srt_path).exists():
        _burn_subtitles(raw_path, srt_path, output_path, cfg)
    else:
        shutil.copy2(raw_path, output_path)

    print(f"\n✓ Reel gespeichert: {output_path}")
    return output_path


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Cinematischer Reel-Renderer")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--hook-typ", default="",
                        choices=["verlustangst", "wissensluecke", "widerspruch", ""])
    parser.add_argument("--script", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--score", type=int, default=None)
    parser.add_argument("--verdict", default="")
    parser.add_argument("--hype-aktie", default="Nvidia")
    args = parser.parse_args()

    hook_typ = args.hook_typ or random.choice(
        ["verlustangst", "wissensluecke", "widerspruch"])

    render(
        ticker=args.ticker,
        hook_typ=hook_typ,
        script_path=args.script,
        output_path=args.output,
        score=args.score,
        verdict=args.verdict,
        hype_aktie=args.hype_aktie,
    )


if __name__ == "__main__":
    main()
