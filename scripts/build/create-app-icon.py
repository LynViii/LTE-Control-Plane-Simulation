from pathlib import Path

from PIL import Image


root = Path(__file__).resolve().parents[2]
source = root / "packaging" / "app-icon-source.png"
target = root / "packaging" / "app-icon.ico"
output_png = root / "packaging" / "app-icon.png"

image = Image.open(source).convert("RGBA")
pixels = image.load()
width, height = image.size
# The user-provided artwork is a rounded green square on a black canvas.
# Convert the near-black background to full transparency first, then crop to
# the visible icon so Windows does not show a dark border around the glyph.
for y in range(height):
    for x in range(width):
        r, g, b, a = pixels[x, y]
        if a and r <= 16 and g <= 16 and b <= 16:
            pixels[x, y] = (0, 0, 0, 0)

bbox = image.getbbox()
if bbox:
    image = image.crop(bbox)

# Add a small transparent breathing room so the rounded square does not clip
# at small ICO sizes, while still filling the icon much tighter than before.
master = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
content = image.copy()
content.thumbnail((476, 476), Image.Resampling.LANCZOS)
offx = (512 - content.width) // 2
offy = (512 - content.height) // 2
master.paste(content, (offx, offy), content)
master.save(output_png)
master.save(target, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(target)
