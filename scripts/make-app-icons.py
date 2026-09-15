"""生成 StudyDash 安卓图标与启动页源图（1024 图标 + 2732 启动页）。

用法：python scripts/make-app-icons.py
产物在 frontend/assets/，再由 @capacitor/assets 生成各尺寸：
    npx @capacitor/assets generate --android
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "assets"

INDIGO_TL = (99, 102, 241)
INDIGO_TR = (79, 70, 229)
INDIGO_BL = (67, 56, 202)
INDIGO_BR = (124, 58, 237)
AMBER = (245, 158, 11)
WHITE = (255, 255, 255)
SPLASH_LIGHT = (245, 246, 251)
SPLASH_DARK = (15, 23, 42)

SIZE = 1024


def gradient(size: int) -> Image.Image:
    """四角插值的靛蓝渐变底。"""
    small = Image.new("RGB", (2, 2))
    small.putpixel((0, 0), INDIGO_TL)
    small.putpixel((1, 0), INDIGO_TR)
    small.putpixel((0, 1), INDIGO_BL)
    small.putpixel((1, 1), INDIGO_BR)
    return small.resize((size, size), Image.BICUBIC)


def draw_mark(canvas: Image.Image, scale: int, center: tuple[int, int], side: int) -> None:
    """在 canvas 上画「白色卡片 + 对勾 + 番茄圆点」标记。"""
    draw = ImageDraw.Draw(canvas)
    half = side // 2
    left, top = center[0] - half, center[1] - half
    radius = int(side * 0.22)

    # 柔和投影：单独一层模糊后叠回，避免出现生硬描边
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    offset = int(side * 0.03)
    ImageDraw.Draw(shadow).rounded_rectangle(
        [left, top + offset, left + side, top + side + offset],
        radius=radius,
        fill=(24, 20, 70, 70),
    )
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(side * 0.02)))
    # 白色卡片
    ImageDraw.Draw(canvas).rounded_rectangle(
        [left, top, left + side, top + side], radius=radius, fill=WHITE
    )

    # 对勾
    line = int(side * 0.11)
    points = [
        (left + side * 0.26, top + side * 0.54),
        (left + side * 0.44, top + side * 0.72),
        (left + side * 0.76, top + side * 0.32),
    ]
    draw.line(points, fill=INDIGO_TR, width=line, joint="curve")
    for point in (points[0], points[-1]):
        draw.ellipse(
            [point[0] - line / 2, point[1] - line / 2, point[0] + line / 2, point[1] + line / 2],
            fill=INDIGO_TR,
        )

    # 番茄圆点（右上角压在卡片外沿）
    dot_center = (int(left + side * 0.86), int(top + side * 0.14))
    dot_radius = int(side * 0.13)
    draw.ellipse(
        [
            dot_center[0] - dot_radius,
            dot_center[1] - dot_radius,
            dot_center[0] + dot_radius,
            dot_center[1] + dot_radius,
        ],
        fill=AMBER,
        outline=WHITE,
        width=int(side * 0.03),
    )


def rounded(image: Image.Image, radius_ratio: float = 0.22) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, image.size[0] - 1, image.size[1] - 1],
        radius=int(image.size[0] * radius_ratio),
        fill=255,
    )
    out = image.convert("RGBA")
    out.putalpha(mask)
    return out


def make_icon() -> Image.Image:
    scale = 4
    canvas = gradient(SIZE * scale).convert("RGBA")
    draw_mark(canvas, scale, (SIZE * scale // 2, SIZE * scale // 2), int(SIZE * scale * 0.58))
    return rounded(canvas.resize((SIZE, SIZE), Image.LANCZOS))


def make_foreground() -> Image.Image:
    """自适应图标前景：透明底，标记落在中间安全区内。"""
    scale = 4
    canvas = Image.new("RGBA", (SIZE * scale, SIZE * scale), (0, 0, 0, 0))
    draw_mark(canvas, scale, (SIZE * scale // 2, SIZE * scale // 2), int(SIZE * scale * 0.42))
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def make_background() -> Image.Image:
    return gradient(SIZE).convert("RGBA")


def make_splash(background: tuple[int, int, int]) -> Image.Image:
    canvas = Image.new("RGB", (2732, 2732), background)
    icon = make_icon().resize((760, 760), Image.LANCZOS)
    canvas.paste(icon, (2732 // 2 - 380, 2732 // 2 - 460), icon)
    return canvas


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_icon().save(OUT / "icon-only.png")
    make_foreground().save(OUT / "icon-foreground.png")
    make_background().save(OUT / "icon-background.png")
    make_splash(SPLASH_LIGHT).save(OUT / "splash.png")
    make_splash(SPLASH_DARK).save(OUT / "splash-dark.png")
    for path in sorted(OUT.glob("*.png")):
        print(f"{path.name}: {path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
