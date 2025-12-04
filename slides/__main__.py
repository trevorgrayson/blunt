#!/usr/bin/env python3
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import re


def ensure_tesseract_available() -> bool:
    """Return True if tesseract is on PATH."""
    from shutil import which
    return which("tesseract") is not None


def unique_path(path: Path) -> Path:
    """
    If `path` exists, append a numeric suffix before the extension:
    example.png -> example_1.png, example_2.png, ...
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def is_screenshot_png(path: Path) -> bool:
    """True if the file is PNG and its name matches Screenshot.*"""
    return (
        path.suffix.lower() == ".png"
        and re.match(r"^Screenshot.*", path.name) is not None
    )


def move_desktop_files_to_slides() -> None:
    home = Path(os.path.expanduser("~"))
    desktop = home / "Desktop"

    # ---- HARD REQUIREMENT: Desktop must exist ----
    if not desktop.exists():
        raise FileNotFoundError(f"Desktop directory does not exist: {desktop}")

    # ---- Ensure .slides directory exists ----
    slides_root = home / ".slides"
    slides_root.mkdir(parents=True, exist_ok=True)

    # ---- Build date-based directory and ensure it exists ----
    now = datetime.now()
    dest_dir = slides_root / f"{now.year}" / f"{now.month:02d}" / f"{now.day:02d}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    tesseract_available = ensure_tesseract_available()
    if not tesseract_available:
        print("Warning: 'tesseract' not found on PATH. OCR will be skipped.")

    for item in desktop.iterdir():
        if item.is_dir():
            continue

        dest_path = unique_path(dest_dir / item.name)
        print(f"Moving {item} -> {dest_path}")
        shutil.move(str(item), str(dest_path))

        # OCR only for Screenshot*.png
        if tesseract_available and is_screenshot_png(dest_path):
            try:
                run_ocr_and_write_markdown(dest_path)
            except Exception as e:
                print(f"Failed to OCR {dest_path}: {e}")


def run_ocr_and_write_markdown(image_path: Path) -> None:
    """Run tesseract on image_path and create a .txt file with a markdown header."""
    mtime = datetime.fromtimestamp(image_path.stat().st_mtime)
    timestamp_str = mtime.strftime("%Y-%m-%d %H:%M:%S")

    header = f"# Slides - {timestamp_str}\n\n"

    result = subprocess.run(
        ["tesseract", str(image_path), "stdout"],
        check=True,
        text=True,
        capture_output=True,
    )

    ocr_text = result.stdout

    txt_path = image_path.with_suffix(".txt")
    print(f"Writing OCR text to {txt_path}")
    txt_path.write_text(header + ocr_text, encoding="utf-8")


def main() -> None:
    move_desktop_files_to_slides()


if __name__ == "__main__":
    main()
