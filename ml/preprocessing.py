from PIL import Image
from pathlib import Path

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}

def load_image(path: str, size=(224, 224)):
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED:
        raise ValueError(f"Unsupported image extension: {path.suffix}")
    with Image.open(path) as image:
        return image.convert("RGB").resize(size)
