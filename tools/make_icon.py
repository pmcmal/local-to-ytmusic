"""Generuje ikonę programu (nuta na kolorowym tle) -> assets/icon.ico i assets/icon.png.

Wymaga Pillow (tylko do generowania ikony, program go nie potrzebuje):
    pip install pillow
    python tools/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024  # rysujemy w dużej rozdzielczości, potem zmniejszamy
OUT = Path(__file__).resolve().parent.parent / "assets"
TOP = (255, 78, 80)     # koral
BOTTOM = (142, 45, 226)  # fiolet
WHITE = (255, 255, 255, 255)


def background() -> Image.Image:
    grad = Image.new("RGBA", (S, S))
    px = grad.load()
    for y in range(S):
        for x in range(S):
            t = min(1.0, (0.75 * y + 0.25 * x) / S)
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)) + (255,)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.22), fill=255)
    bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bg.paste(grad, mask=mask)
    return bg


def note_head(cx: int, cy: int) -> Image.Image:
    """Pochylona owalna główka nuty jako osobna warstwa."""
    w, h = int(S * 0.20), int(S * 0.145)
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2), fill=WHITE)
    return layer.rotate(22, center=(cx, cy), resample=Image.BICUBIC)


def music_note() -> Image.Image:
    """Dwie ósemki połączone belką."""
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    stem_w = int(S * 0.055)
    heads = [(int(S * 0.33), int(S * 0.72)), (int(S * 0.69), int(S * 0.64))]
    tops = [int(S * 0.30), int(S * 0.22)]
    stems_x = []
    for (cx, cy), top in zip(heads, tops):
        x1 = cx + int(S * 0.085)
        stems_x.append(x1)
        d.rectangle((x1 - stem_w, top, x1, cy - int(S * 0.02)), fill=WHITE)
    beam_h = int(S * 0.11)
    (xa, xb), (ta, tb) = stems_x, tops
    d.polygon([(xa - stem_w, ta), (xb, tb), (xb, tb + beam_h), (xa - stem_w, ta + beam_h)], fill=WHITE)
    for cx, cy in heads:
        layer = Image.alpha_composite(layer, note_head(cx, cy))
    return layer


def main() -> None:
    OUT.mkdir(exist_ok=True)
    icon = Image.alpha_composite(background(), music_note())
    big = icon.resize((256, 256), Image.LANCZOS)
    big.save(OUT / "icon.png")
    big.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Zapisano:", OUT / "icon.ico")


if __name__ == "__main__":
    main()
