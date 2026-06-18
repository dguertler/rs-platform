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

    print("[3/5] Stock-Footage laden (Pexels → Fallback auf Reel-PNGs)…")
    fallback_kw = cfg["stock_footage"]["fallback_keywords"]
    # Reel-PNGs als lokaler Fallback (immer verfügbar)
    reel_png_dir = Path(script_path).parent / "reel" if script_path else None
    reel_pngs = sorted(reel_png_dir.glob("*.png")) if (
        reel_png_dir and reel_png_dir.exists()) else []
    video_paths = []
    for i, scene in enumerate(scenes):
        dest = os.path.join(tmpdir, f"scene_{i:02d}.mp4")
        ok = False
        if api_key:
            ok = _pexels_download(scene["visual"], dest, api_key,
                                  min_dur=int(scene_sec))
            if not ok:
                ok = _pexels_download(fallback_kw[i % len(fallback_kw)],
                                      dest, api_key, min_dur=int(scene_sec))
        if not ok:
            # Cinematic Prozedur-Hintergrund (animierter Gradient, vollständig offline)
            _generate_bg_cinematic(i, dest, W, H, scene_sec)
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

    audio = AudioFileClip(audio_path).with_duration(video.duration)
    video = video.with_audio(audio)

    # Logo (oben rechts, dauerhaft)
    if LOGO_PATH.exists():
        lw = _logo_width(LOGO_PATH, height=80)
        logo = (ImageClip(str(LOGO_PATH))
                .with_effects([vfx.Resize(height=80)])
                .with_duration(video.duration)
                .with_position((W - lw - 40, 40)))
        video = CompositeVideoClip([video, logo])

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
