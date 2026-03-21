"""Image processing utilities for optimization and resizing."""
from io import BytesIO
from typing import Iterable

from PIL import Image
from django.core.files.base import ContentFile


def optimize_image(image_file, max_width=750, quality=85):
    """
    Optimize image by resizing and compressing.

    Args:
        image_file: Django ImageField file object or file path
        max_width: Maximum width in pixels (height auto-scales)
        quality: JPEG quality (1-100)

    Returns:
        Django ContentFile object with optimized image
    """
    if isinstance(image_file, str):
        img = Image.open(image_file)
    else:
        img = Image.open(image_file)

    # Convert RGBA to RGB for JPEG if needed
    if img.mode in ("RGBA", "LA", "P"):
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = rgb_img

    # Resize if needed
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

    # Save optimized image
    output = BytesIO()
    img.save(output, format="JPEG", quality=quality, optimize=True)
    output.seek(0)

    return ContentFile(output.getvalue())


def create_thumbnail(image_file, size=200, quality=85):
    """
    Create square thumbnail from image.

    Args:
        image_file: Django ImageField file object or file path
        size: Thumbnail size in pixels (width and height)
        quality: JPEG quality (1-100)

    Returns:
        Django ContentFile object with thumbnail image
    """
    if isinstance(image_file, str):
        img = Image.open(image_file)
    else:
        img = Image.open(image_file)

    # Convert RGBA to RGB for JPEG if needed
    if img.mode in ("RGBA", "LA", "P"):
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = rgb_img

    # Create square thumbnail (crop center)
    min_dimension = min(img.width, img.height)
    left = (img.width - min_dimension) // 2
    top = (img.height - min_dimension) // 2
    right = left + min_dimension
    bottom = top + min_dimension

    img = img.crop((left, top, right, bottom))
    img = img.resize((size, size), Image.Resampling.LANCZOS)

    # Save thumbnail
    output = BytesIO()
    img.save(output, format="JPEG", quality=quality, optimize=True)
    output.seek(0)

    return ContentFile(output.getvalue())


def delete_image_file(image_field):
    """Delete physical image file from storage."""
    if image_field and hasattr(image_field, "delete"):
        image_field.delete(save=False)


def cleanup_storage_prefix(
    storage,
    prefix: str,
    keep_paths: Iterable[str] | None = None,
):
    """Delete all files under prefix except explicitly kept paths."""
    keep = {path for path in (keep_paths or []) if path}
    root = prefix.rstrip("/")
    if not root:
        return 0

    deleted = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            directories, files = storage.listdir(current)
        except Exception:
            continue

        for dirname in directories:
            stack.append(f"{current}/{dirname}".rstrip("/"))

        for filename in files:
            file_path = f"{current}/{filename}".lstrip("/")
            if file_path in keep:
                continue
            try:
                storage.delete(file_path)
                deleted += 1
            except Exception:
                continue

    return deleted
