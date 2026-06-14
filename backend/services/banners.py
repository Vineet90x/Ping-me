"""Offer-banner generation for broadcasts.

The owner doesn't design anything — they provide a headline (and optional
subtext) and we render a clean, on-brand banner with the salon name. Shares the
font-loading + dark/violet style used by ``services/images.py``.
"""
import io

from PIL import Image, ImageDraw, ImageFont


def _font(size: int, bold: bool = False):
    candidates = (
        ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap so long headlines don't overflow the banner."""
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_offer_banner(salon_name: str, headline: str, subtext: str | None = None) -> bytes:
    """Render a promotional banner as PNG bytes."""
    width, height = 1000, 525
    img = Image.new("RGB", (width, height), "#0f172a")
    draw = ImageDraw.Draw(img)

    # Top accent bar with the salon name.
    draw.rectangle([0, 0, width, 96], fill="#6d28d9")
    draw.text((40, 28), salon_name, font=_font(40, bold=True), fill="#ffffff")

    # Headline (wrapped, centred vertically in the body).
    margin = 40
    max_w = width - 2 * margin
    head_font = _font(58, bold=True)
    lines = _wrap(draw, headline, head_font, max_w)
    y = 170
    for line in lines:
        draw.text((margin, y), line, font=head_font, fill="#f8fafc")
        y += 70

    if subtext:
        sub_font = _font(30)
        for line in _wrap(draw, subtext, sub_font, max_w):
            draw.text((margin, y + 10), line, font=sub_font, fill="#a78bfa")
            y += 42

    draw.text((margin, height - 50), "Powered by Ping", font=_font(20), fill="#64748b")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
