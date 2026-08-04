from __future__ import annotations

from pathlib import Path
import argparse
import math

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser(description="Build contact sheets from generated annotation overlays.")
    parser.add_argument("--overlays", type=Path, default=Path("outputs/annotation_qa/overlays"))
    parser.add_argument("--output", type=Path, default=Path("outputs/annotation_qa/contact_sheets"))
    parser.add_argument("--per-sheet", type=int, default=12)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    files = sorted(args.overlays.glob("*.jpg"))
    thumb_w, thumb_h, label_h, columns = 420, 560, 34, 4
    rows = math.ceil(args.per_sheet / columns)
    for sheet_index, offset in enumerate(range(0, len(files), args.per_sheet), start=1):
        canvas = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + label_h)), "#101820")
        draw = ImageDraw.Draw(canvas)
        for local_index, path in enumerate(files[offset : offset + args.per_sheet]):
            with Image.open(path) as source:
                source = source.convert("RGB")
                source.thumbnail((thumb_w, thumb_h))
                x = (local_index % columns) * thumb_w + (thumb_w - source.width) // 2
                y = (local_index // columns) * (thumb_h + label_h) + (thumb_h - source.height) // 2
                canvas.paste(source, (x, y))
            label_y = (local_index // columns) * (thumb_h + label_h) + thumb_h + 7
            draw.text(((local_index % columns) * thumb_w + 8, label_y), path.stem, fill="white", font=ImageFont.load_default())
        canvas.save(args.output / f"contact_sheet_{sheet_index:02d}.jpg", quality=90)
    print(f"created {math.ceil(len(files) / args.per_sheet)} contact sheets from {len(files)} overlays")


if __name__ == "__main__":
    main()
