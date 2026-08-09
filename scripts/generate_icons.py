from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets"
BACKGROUND = "#e5e5f2"
INK = "#171816"
LIME = "#dff1ad"
WHITE = "#ffffff"
CORAL = "#f58b7c"


def create_icon(size: int = 1024) -> Image.Image:
    image = Image.new("RGBA", (size, size), BACKGROUND)
    draw = ImageDraw.Draw(image)
    scale = size / 1024

    def box(values: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        left, top, right, bottom = values
        return (
            round(left * scale),
            round(top * scale),
            round(right * scale),
            round(bottom * scale),
        )

    draw.rounded_rectangle(box((174, 174, 850, 850)), radius=round(182 * scale), fill=INK)
    draw.ellipse(box((300, 420, 484, 604)), fill=LIME)
    draw.rectangle(box((520, 344, 594, 680)), fill=WHITE)
    draw.rectangle(box((642, 410, 716, 680)), fill=WHITE)
    draw.ellipse(box((642, 307, 716, 381)), fill=CORAL)
    return image


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    icon = create_icon()
    icon.save(ASSET_DIR / "app-icon.png")
    icon.save(
        ASSET_DIR / "app-icon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)],
    )
    icon.save(
        ASSET_DIR / "app-icon.icns",
        append_images=[icon.resize((size, size)) for size in (16, 32, 64, 128, 256, 512)],
    )


if __name__ == "__main__":
    main()
