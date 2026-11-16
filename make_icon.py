"""Zeichnet das App-Icon (icon.png, icon-128.png, icon.ico) fuer den Video Downloader.
Nur Pillow, 4x gross gezeichnet und runtergerechnet (glatte Kanten)."""
import os
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 2048  # Arbeitsgroesse, Ausgabe 1024


def lin_v(w, h, top, bottom):
    """Senkrechter Verlauf top->bottom (RGBA-Tupel)."""
    g = Image.linear_gradient("L").resize((w, h))
    a = Image.new("RGBA", (w, h), top)
    b = Image.new("RGBA", (w, h), bottom)
    return Image.composite(b, a, g)


def lin_diag(w, h, stops):
    """Diagonaler Verlauf oben-links -> unten-rechts mit mehreren Stopps."""
    g = Image.linear_gradient("L").resize((w * 2, h * 2)).rotate(45, resample=Image.BICUBIC)
    g = g.crop((w // 2, h // 2, w // 2 + w, h // 2 + h))
    out = Image.new("RGBA", (w, h), stops[0][1])
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        lo, hi = int(p0 * 255), int(p1 * 255)
        m = g.point(lambda v, lo=lo, hi=hi: 0 if v < lo else 255 if v > hi else int((v - lo) / max(1, hi - lo) * 255))
        out = Image.composite(Image.new("RGBA", (w, h), c1), out, m)
    return out


def radial(w, h, cx, cy, r, color, power=1.6):
    g = Image.radial_gradient("L").resize((int(r * 2), int(r * 2)))
    g = g.point(lambda v: int(255 * max(0.0, 1 - v / 255) ** power))
    mask = Image.new("L", (w, h), 0)
    mask.paste(g, (int(cx - r), int(cy - r)))
    layer = Image.new("RGBA", (w, h), color[:3] + (0,))
    layer.putalpha(ImageChops.multiply(mask, Image.new("L", (w, h), color[3])))
    return layer


def rr_mask(box, r):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle(box, r, fill=255)
    return m


def circle_mask(cx, cy, r):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    return m


def put(base, layer, mask=None):
    if mask is not None:
        a = ImageChops.multiply(layer.getchannel("A"), mask)
        layer = layer.copy()
        layer.putalpha(a)
    return Image.alpha_composite(base, layer)


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    m = 112
    box = (m, m, S - m, S - m)
    body = rr_mask(box, 460)

    # Schatten
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sh.putalpha(rr_mask((m, m + 40, S - m, S - m + 40), 460).filter(ImageFilter.GaussianBlur(50)).point(lambda v: v * 0.5))
    img = Image.alpha_composite(img, sh)

    # Grundflaeche + roter Schein unten + Glanz oben
    img = put(img, lin_v(S, S, (30, 30, 36, 255), (10, 10, 13, 255)), body)
    # weicher roter Schein von unten: klein gezeichnet, stark weichgezeichnet, hochgerechnet
    small = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(small).ellipse((-30, 150, 286, 360), fill=150)
    small = small.filter(ImageFilter.GaussianBlur(42)).resize((S, S), Image.BICUBIC)
    red = Image.new("RGBA", (S, S), (255, 46, 59, 0))
    red.putalpha(small)
    img = put(img, red, body)
    # Glanz oben, laeuft bis zur Mitte sanft aus
    gl = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    gl.paste(lin_v(S, S // 2, (255, 255, 255, 20), (255, 255, 255, 0)), (0, 0))
    img = put(img, gl, body)
    # feine Kante
    edge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(box, 460, outline=(255, 255, 255, 22), width=6)
    img = Image.alpha_composite(img, edge)

    # roter Kreis mit Leuchten
    cx, cy, R = S / 2, S * 0.465, 570
    glow = Image.new("RGBA", (S, S), (255, 46, 59, 0))
    glow.putalpha(circle_mask(cx, cy + 30, R).filter(ImageFilter.GaussianBlur(110)).point(lambda v: int(v * 0.75)))
    img = put(img, glow, body)
    disc = circle_mask(cx, cy, R)
    img = put(img, lin_diag(S, S, [(0.0, (255, 112, 90, 255)), (0.45, (255, 46, 59, 255)), (1.0, (178, 12, 26, 255))]), disc)
    # Glanzlicht oben im Kreis
    hl = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hl).ellipse((cx - R * 0.86, cy - R * 1.02, cx + R * 0.86, cy + R * 0.10), fill=255)
    hl = hl.filter(ImageFilter.GaussianBlur(30))
    img = put(img, lin_v(S, S, (255, 255, 255, 80), (255, 255, 255, 0)), ImageChops.multiply(hl, disc))
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((cx - R + 3, cy - R + 3, cx + R - 3, cy + R - 3), outline=(255, 255, 255, 50), width=6)
    img = Image.alpha_composite(img, ring)

    # weisser Pfeil (runde Enden) mit weichem Schatten
    def arrow(d, fill, off=0):
        w = 124
        x, y = cx, cy + off
        d.line((x, y - 300, x, y + 190), fill=fill, width=w)
        d.line((x - 218, y - 22, x, y + 196), fill=fill, width=w)
        d.line((x + 218, y - 22, x, y + 196), fill=fill, width=w)
        for px, py in ((x, y - 300), (x - 218, y - 22), (x + 218, y - 22), (x, y + 196)):
            d.ellipse((px - w / 2, py - w / 2, px + w / 2, py + w / 2), fill=fill)

    sh = Image.new("RGBA", (S, S), (90, 0, 8, 0))
    sm = Image.new("L", (S, S), 0)
    arrow(ImageDraw.Draw(sm), 255, 22)
    sh.putalpha(sm.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.55)))
    img = Image.alpha_composite(img, sh)
    am = Image.new("L", (S, S), 0)
    arrow(ImageDraw.Draw(am), 255)
    img = put(img, Image.new("RGBA", (S, S), (255, 255, 255, 255)), am)

    # Ablage-Linie
    ty, half, w = S * 0.835, 380, 88
    tm = Image.new("L", (S, S), 0)
    td = ImageDraw.Draw(tm)
    td.rounded_rectangle((cx - half, ty - w / 2, cx + half, ty + w / 2), w / 2, fill=255)
    img = put(img, Image.new("RGBA", (S, S), (255, 255, 255, 236)), tm)

    out = img.resize((1024, 1024), Image.LANCZOS)
    out.save(os.path.join(HERE, "icon.png"))
    out.resize((128, 128), Image.LANCZOS).save(os.path.join(HERE, "icon-128.png"))
    out.save(os.path.join(HERE, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ok")


if __name__ == "__main__":
    draw()
