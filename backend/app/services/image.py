from io import BytesIO
from PIL import Image, UnidentifiedImageError

def inspect_image(content: bytes) -> dict:
    try:
        image = Image.open(BytesIO(content))
        image.verify()
        image = Image.open(BytesIO(content))
        width, height = image.size
        if width < 64 or height < 64:
            raise ValueError("Image is too small. Please upload an image at least 64 x 64 pixels.")
        return {
            "valid": True,
            "format": image.format,
            "width": width,
            "height": height,
            "mode": image.mode
        }
    except (UnidentifiedImageError, OSError):
        raise ValueError("The uploaded file is not a valid supported image.")
