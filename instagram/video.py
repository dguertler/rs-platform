"""
Einfaches Reel-Video (MP4 9:16) aus den fertigen Slide-Frames.

Kein cineastisches KI-Reel (B-Roll/Voiceover) — das entsteht extern aus
`reel_script.txt`. Dies hier ist die schnelle, sofort postbare Variante:
sanfter Ken-Burns-Zoom je Frame + kurze Crossfades. Nutzt imageio-ffmpeg
(statische ffmpeg-Binary, via pip installierbar).
"""
import numpy as np
from PIL import Image


def _kenburns(img, n, zoom=1.07):
    """n RGB-Frames mit langsamem Hineinzoomen."""
    W, H = img.size
    out = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        s = 1.0 + (zoom - 1.0) * t
        cw, ch = int(W / s), int(H / s)
        x, y = (W - cw) // 2, (H - ch) // 2
        crop = img.crop((x, y, x + cw, y + ch)).resize((W, H), Image.LANCZOS)
        out.append(np.asarray(crop.convert("RGB")))
    return out


def build_reel_video(frame_paths, out_path, fps=30, sec=3.2, fade=0.45):
    """Baut ein MP4 aus den Frame-PNGs. Gibt out_path zurück (oder wirft)."""
    import imageio.v2 as imageio

    imgs = [Image.open(p).convert("RGB") for p in frame_paths]
    n = max(2, int(fps * sec))
    nf = int(fps * fade)
    clips = [_kenburns(im, n) for im in imgs]

    seq = []
    for i, clip in enumerate(clips):
        if i > 0 and nf > 0 and len(seq) >= nf:
            tail = seq[-nf:]
            head = clip[:nf]
            for k in range(nf):
                al = (k + 1) / (nf + 1)
                seq[-nf + k] = (tail[k] * (1 - al) + head[k] * al).astype("uint8")
            seq += clip[nf:]
        else:
            seq += clip

    writer = imageio.get_writer(
        out_path, fps=fps, codec="libx264", pixelformat="yuv420p",
        macro_block_size=8, ffmpeg_log_level="error")
    try:
        for f in seq:
            writer.append_data(f)
    finally:
        writer.close()
    return out_path
