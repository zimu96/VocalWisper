"""Icon generation helpers (microphone, idle/recording/paused)."""

from PIL import Image, ImageDraw


def make_mic_icon(size: int = 64, color: str = "white", state: str = "idle") -> Image.Image:
    """Create a simple microphone icon. state: idle|recording|paused."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    # mic body
    body_w = size // 5
    body_h = size // 2
    bx0 = cx - body_w // 2
    by0 = cy - body_h // 2 - size // 8
    bx1 = cx + body_w // 2
    by1 = by0 + body_h
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=body_w // 2, fill=color)
    # stand arc
    arc_r = size // 3
    d.arc([cx - arc_r, by1 - arc_r // 2, cx + arc_r, by1 + arc_r], start=0, end=180, fill=color, width=3)
    # stem
    d.line([cx, by1 + arc_r // 2, cx, by1 + arc_r // 2 + size // 8], fill=color, width=3)
    d.line([cx - size // 8, by1 + arc_r // 2 + size // 8, cx + size // 8, by1 + arc_r // 2 + size // 8], fill=color, width=3)

    if state == "recording":
        # red dot
        r = size // 8
        d.ellipse([size - r*2 - 2, 2, size - 2, 2 + r*2], fill="#ff3b30")
    elif state == "paused":
        # two bars
        barw = size // 10
        bh = size // 4
        x1 = cx - size // 6
        y0 = cy - bh // 2
        d.rectangle([x1, y0, x1 + barw, y0 + bh], fill=color)
        x2 = cx + size // 12
        d.rectangle([x2, y0, x2 + barw, y0 + bh], fill=color)
    return img


def pil_to_tk(img):
    from PIL import ImageTk
    return ImageTk.PhotoImage(img)
