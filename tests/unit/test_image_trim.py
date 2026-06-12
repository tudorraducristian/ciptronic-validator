import io

from PIL import Image

from web.app import _trim_solid_border


NAVY = (30, 41, 59)


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _img_with_side_bars(w=100, h=100, bar=10) -> Image.Image:
    """White image with solid NAVY vertical bars on the left and right edges."""
    im = Image.new("RGB", (w, h), (255, 255, 255))
    for x in list(range(bar)) + list(range(w - bar, w)):
        for y in range(h):
            im.putpixel((x, y), NAVY)
    # Some interior content so the image isn't blank between the bars.
    for x in range(bar + 5, w - bar - 5):
        for y in range(h // 2 - 8, h // 2 + 8):
            im.putpixel((x, y), (200, 50, 20))
    return im


def test_trim_removes_solid_side_bars():
    out = _trim_solid_border(_png(_img_with_side_bars(bar=10)))
    assert out is not None
    res = Image.open(io.BytesIO(out))
    assert res.size == (80, 100)  # 10px navy removed from each side


def test_trim_skips_image_without_uniform_frame():
    # Content touches a corner → corners differ → not a frame → untouched.
    im = Image.new("RGB", (100, 100), (255, 255, 255))
    im.putpixel((0, 0), (255, 0, 0))
    assert _trim_solid_border(_png(im)) is None


def test_trim_skips_flat_colour_image():
    im = Image.new("RGB", (50, 50), NAVY)
    assert _trim_solid_border(_png(im)) is None


def test_trim_skips_when_crop_would_be_too_aggressive():
    # Thick bars (40% per side) → trimming that much risks eating content → skip.
    out = _trim_solid_border(_png(_img_with_side_bars(w=100, h=100, bar=40)))
    assert out is None


def test_trim_returns_none_for_non_image_bytes():
    assert _trim_solid_border(b"not an image") is None
