import argparse
from pathlib import Path
from typing import Tuple
from PIL import Image


def create_devto_cover(
    input_path: Path,
    output_path: Path,
    target_size: Tuple[int, int] = (1000, 420),
    bg_color: Tuple[int, int, int] = (0, 0, 0),
) -> None:
    """
    Resizes an image to fit the dev.to cover image dimensions, padding with a background color.

    :param input_path: Path to the input image.
    :param output_path: Path to save the output image.
    :param target_size: Target dimensions (width, height) - dev.to recommendation is 1000x420.
    :param bg_color: Background color (R, G, B) - Default is black.
    """

    if not input_path.exists():
        print(f"Error: File '{input_path}' not found.")
        return

    try:
        with Image.open(input_path) as original_img:
            # Create the target canvas (filled with background color)
            canvas = Image.new("RGB", target_size, bg_color)
            target_w, target_h = target_size

            # Original image size
            orig_w, orig_h = original_img.size

            # Calculate resize ratio (fit within target)
            ratio = min(target_w / orig_w, target_h / orig_h)
            new_size = (int(orig_w * ratio), int(orig_h * ratio))

            # Resize the image (LANCZOS is a high-quality resampling filter)
            resized_img = original_img.resize(new_size, Image.Resampling.LANCZOS)

            # Calculate coordinates to center the image
            paste_x = (target_w - new_size[0]) // 2
            paste_y = (target_h - new_size[1]) // 2

            # Paste onto the canvas
            canvas.paste(resized_img, (paste_x, paste_y))

            # Save
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(output_path, "PNG")
            print(f"Success: Created '{output_path}'. Size: {target_size}")

    except Exception as e:
        print(f"Error processing image: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a cover image for dev.to.")
    parser.add_argument("input", type=Path, help="Path to the input image")
    parser.add_argument("output", type=Path, help="Path to the output image")
    parser.add_argument(
        "--bg", nargs=3, type=int, default=[0, 0, 0], help="Background color (R G B)"
    )

    args = parser.parse_args()

    create_devto_cover(args.input, args.output, bg_color=tuple(args.bg))
