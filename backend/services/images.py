"""Booking-confirmation image generation using Pillow."""
import io

from PIL import Image, ImageDraw, ImageFont


def _font(size: int, bold: bool = False):
    """Best-effort load of a TrueType font, falling back to Pillow's default."""
    candidates = (
        ["arialbd.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "DejaVuSans.ttf"]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def generate_booking_image(
    salon_name: str,
    customer_name: str,
    service_name: str,
    staff_name: str,
    date_str: str,
    time_str: str,
) -> bytes:
    """Render a shareable booking-confirmation card as PNG bytes."""
    width, height = 800, 500
    img = Image.new("RGB", (width, height), "#0f172a")
    draw = ImageDraw.Draw(img)

    # Accent banner
    draw.rectangle([0, 0, width, 110], fill="#6d28d9")
    draw.text((40, 30), salon_name, font=_font(40, bold=True), fill="#ffffff")

    draw.text((40, 140), "Booking Confirmed", font=_font(34, bold=True), fill="#a78bfa")
    draw.text((40, 195), f"Hi {customer_name}!", font=_font(24), fill="#e2e8f0")

    rows = [
        ("Service", service_name),
        ("Stylist", staff_name),
        ("Date", date_str),
        ("Time", time_str),
    ]
    y = 260
    label_font = _font(22)
    value_font = _font(24, bold=True)
    for label, value in rows:
        draw.text((40, y), f"{label}:", font=label_font, fill="#94a3b8")
        draw.text((220, y), str(value), font=value_font, fill="#f8fafc")
        y += 48

    draw.text((40, height - 50), "Powered by Ping", font=_font(18), fill="#64748b")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
