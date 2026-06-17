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


# ── TTS via edge-tts ───────────────────────────────────────────────────────────

async def _tts_async(text: str, voice: str, dest: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(dest)


def _run_tts(text: str, voice: str, dest: str) -> None:
    asyncio.run(_tts_async(text, voice, dest))


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
    try:
        font_big = ImageFont.truetype(
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 56)
        font_sm = ImageFont.truetype(
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 28)
    except OSError:
        font_big = font_sm = ImageFont.load_default()
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
    cw, ch = clip.size
    scale = max(W / cw, H / ch)
    clip = clip.resize(width=int(cw * scale), height=int(ch * scale))
    nw, nh = clip.size
    x1 = (nw - W) // 2
    y1 = (nh - H) // 2
    return clip.crop(x1=x1, y1=y1, x2=x1 + W, y2=y1 + H)


# ── Untertitel einbrennen ──────────────────────────────────────────────────────

def _burn_subtitles(video_in: str, srt_path: str, video_out: str, cfg: dict) -> None:
    fs = cfg["subtitles"]["font_size"]
    fc = cfg["subtitles"]["font_color"].lstrip("#")
    oc = cfg["subtitles"]["outline_color"].lstrip("#")
    ow = cfg["subtitles"]["outline_width"]
    style = (f"FontSize={fs},PrimaryColour=&H{fc},OutlineColour=&H{oc},"
             f"Outline={ow},Alignment=2,MarginV=200")
    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y", "-i", video_in,
        "-vf", f"subtitles={srt_escaped}:force_style='{style}'",
        "-c:a", "copy", video_out,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        shutil.copy2(video_in, video_out)
        print("  [Untertitel] ffmpeg-Fehler, Video ohne Untertitel gespeichert.")


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
    from moviepy.editor import (
        VideoFileClip, ImageClip, CompositeVideoClip,
        concatenate_videoclips, AudioFileClip, ColorClip,
    )

    cfg = _load_cfg()
    api_key = os.environ.get(cfg["stock_footage"]["api_key_env"], "")
    voice = cfg["voice"]
    fps = cfg["video"]["fps"]
    scene_sec = cfg["video"]["scene_max_sec"]
    fade = cfg["video"]["crossfade_sec"]
    W, H = cfg["video"]["resolution"]
    rov_start = cfg["rating_overlay"]["start_sec"]
    rov_end = cfg["rating_overlay"]["end_sec"]

    from . import hook_generator
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

    print("[2/5] Whisper-Transkription…")
    try:
        _whisper_srt(audio_path, srt_path)
    except Exception as exc:
        print(f"  Whisper fehlgeschlagen ({exc}) — ohne Untertitel")
        srt_path = None

    print("[3/5] Stock-Footage laden…")
    fallback_kw = cfg["stock_footage"]["fallback_keywords"]
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
        video_paths.append(dest if ok else None)

    print("[4/5] Clips zusammenstellen…")
    clips = []
    for i, vpath in enumerate(video_paths):
        if vpath and Path(vpath).exists():
            try:
                cl = VideoFileClip(vpath).subclip(0, scene_sec)
                clips.append(_crop_portrait(cl, W, H))
                continue
            except Exception as exc:
                print(f"  Clip {i} fehlgeschlagen ({exc})")
        clips.append(ColorClip(size=(W, H), color=(14, 19, 32), duration=scene_sec))

    final_clips = [clips[0]]
    for cl in clips[1:]:
        final_clips.append(cl.crossfadein(fade))
    video = concatenate_videoclips(final_clips, method="compose", padding=-fade)

    audio = AudioFileClip(audio_path).set_duration(video.duration)
    video = video.set_audio(audio)

    # Logo (oben rechts, dauerhaft)
    if LOGO_PATH.exists():
        lw = _logo_width(LOGO_PATH, height=80)
        logo = (ImageClip(str(LOGO_PATH))
                .resize(height=80)
                .set_duration(video.duration)
                .set_position((W - lw - 40, 40)))
        video = CompositeVideoClip([video, logo])

    # Rating-Overlay (Sek. 6–9)
    if video.duration >= rov_end and (score is not None or verdict):
        rating_png = _make_rating_overlay(score, verdict)
        rating_clip = (ImageClip(rating_png)
                       .set_start(rov_start)
                       .set_end(rov_end)
                       .set_position("center"))
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
