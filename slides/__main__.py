#!/usr/bin/env python3
import os
import shutil
import subprocess
import re
import argparse
from pathlib import Path
from datetime import datetime


# ------------------ Helpers ------------------ #

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
        path.is_file()
        and path.suffix.lower() == ".png"
        and re.match(r"^Screenshot.*", path.name) is not None
    )


def run_ocr_and_write_markdown(image_path: Path) -> None:
    """
    Run tesseract on image_path and create a .txt file with a markdown header.
    The header includes the file's modified timestamp.
    """
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


# ------------------ Commands ------------------ #

def cmd_move(args: argparse.Namespace) -> None:
    """
    Move files from ~/Desktop to ~/.slides/YYYY/MM/DD and OCR Screenshot*.png.
    """
    home = Path(os.path.expanduser("~"))
    desktop = home / "Desktop"

    # Desktop must exist; do not create it.
    if not desktop.exists():
        raise FileNotFoundError(f"Desktop directory does not exist: {desktop}")
    if not desktop.is_dir():
        raise NotADirectoryError(f"Desktop is not a directory: {desktop}")

    # Ensure .slides root exists
    slides_root = home / ".slides"
    slides_root.mkdir(parents=True, exist_ok=True)

    # Date-based destination directory
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


def cmd_refresh(args: argparse.Namespace) -> None:
    """
    Recursively walk ~/.slides and OCR any Screenshot*.png that does not yet
    have a corresponding .txt file.
    """
    home = Path(os.path.expanduser("~"))
    slides_root = home / ".slides"

    if not slides_root.exists():
        raise FileNotFoundError(f"Slides directory does not exist: {slides_root}")
    if not slides_root.is_dir():
        raise NotADirectoryError(f"Slides path is not a directory: {slides_root}")

    tesseract_available = ensure_tesseract_available()
    if not tesseract_available:
        raise RuntimeError("'tesseract' not found on PATH. Cannot process images.")

    for dirpath, dirnames, filenames in os.walk(slides_root):
        dir_path = Path(dirpath)
        for filename in filenames:
            img_path = dir_path / filename

            if not is_screenshot_png(img_path):
                continue

            txt_path = img_path.with_suffix(".txt")
            if txt_path.exists():
                # Idempotent behavior: skip already-processed images
                print(f"Skipping (already has txt): {img_path}")
                continue

            print(f"Processing image: {img_path}")
            try:
                run_ocr_and_write_markdown(img_path)
            except Exception as e:
                print(f"Failed to OCR {img_path}: {e}")


# ------------------ CLI ------------------ #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage slide screenshots and OCR text under ~/.slides"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # slides.py move
    move_parser = subparsers.add_parser(
        "move",
        help="Move files from ~/Desktop to ~/.slides/YYYY/MM/DD and OCR screenshots",
    )
    move_parser.set_defaults(func=cmd_move)

    # slides.py refresh
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Recursively OCR any Screenshot*.png in ~/.slides missing .txt",
    )
    refresh_parser.set_defaults(func=cmd_refresh)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
