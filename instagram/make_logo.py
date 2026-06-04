"""
Erzeugt eine originalgetreue Nachbildung des Logos „AI Alpha Selection"
als transparentes PNG -> instagram/assets/logo.png.

Hinweis: Dies ist eine Reproduktion. Wenn du deine exakte Original-Datei
nutzen willst, lege sie einfach selbst unter instagram/assets/logo.png ab –
der Generator verwendet automatisch die vorhandene Datei.

Aufruf:  python3 -m instagram.make_logo
"""
import os

from PIL import Image, ImageDraw, ImageFont

from . import theme as T

OUT = T.LOGO_PATH
BLUE = (47, 107, 255, 255)
WHITE = (255, 255, 255, 255)
BAR_WHITE = (233, 237, 245, 255)

_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
_ALPHA = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Oblique.ttf"


def build(scale=2):
    W, H = 2100 * scale, 340 * scale
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ── Icon: aufsteigende Balken, der höchste in Blau, Alpha darüber ──────────
    base = 250 * scale
    x = 70 * scale
    bw = 34 * scale
    gap = 20 * scale
    heights = [70, 112, 150]
    for h in heights:
        top = base - h * scale
        d.rounded_rectangle([x, top, x + bw, base], radius=8 * scale, fill=BAR_WHITE)
        x += bw + gap
    # höchster Balken (blau)
    h4 = 196 * scale
    top4 = base - h4
    d.rounded_rectangle([x, top4, x + bw, base], radius=8 * scale, fill=BLUE)
    # Alpha über dem blauen Balken
    af = ImageFont.truetype(_ALPHA, 78 * scale)
    ab = d.textbbox((0, 0), "α", font=af)
    aw = ab[2] - ab[0]
    d.text((x + bw / 2 - aw / 2 - ab[0], top4 - 86 * scale), "α", font=af, fill=BLUE)

    # ── Wortmarke: „AI Alpha " weiß + „Selection" blau ─────────────────────────
    wf = ImageFont.truetype(_BOLD, 132 * scale)
    tx = x + bw + 54 * scale
    ty = (H - 132 * scale) // 2 - 10 * scale
    part1 = "AI Alpha "
    d.text((tx, ty), part1, font=wf, fill=WHITE)
    w1 = d.textbbox((0, 0), part1, font=wf)[2]
    d.text((tx + w1, ty), "Selection", font=wf, fill=BLUE)

    # auf Inhalt zuschneiden
    bbox = img.getbbox()
    img = img.crop(bbox)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print(f"✓ Logo gespeichert: {OUT} ({img.width}x{img.height})")


if __name__ == "__main__":
    build()
