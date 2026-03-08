from pathlib import Path
from PIL import Image
import io
from src.classes.models import CBItem, Representation
from . import config


def generate(item: CBItem) -> tuple[str, bool]:
    # Ensure data is loaded for all representations
    for rep in item.types:
        if not rep.cached and rep.path:
            try:
                rep.data = Path(rep.path).read_bytes()
                rep.cached = True
            except Exception as e:
                print(f"Error loading {rep.path}: {e}")
                continue

    # Preferred image types in order
    preferred_images = ['image/jpeg', 'image/jpg', 'image/png', 'image/tiff', 'image/bmp']
    
    # Find the best image representation
    image_rep = None
    for mime in preferred_images:
        for rep in item.types:
            if rep.mime_type == mime and rep.data:
                image_rep = rep
                break
        if image_rep:
            break
    
    if image_rep:
        # Process the image
        try:
            img = Image.open(io.BytesIO(image_rep.data))
            # Calculate new size to approximately 20700 pixels (192*108 ≈ 20736)
            target_pixels = 20700
            w, h = img.size
            current_pixels = w * h
            if current_pixels > target_pixels:
                scale = (target_pixels / current_pixels) ** 0.5
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
            
            # Save preview.jpg in the same directory
            dir_path = Path(config.CACHE_DIRECTORY) / f"blobs/{item.hash}"
            dir_path.mkdir(parents=True, exist_ok=True)
            preview_path = dir_path / 'preview.jpg'
            img.convert('RGB').save(preview_path, 'JPEG')
            return str(preview_path), True
        except Exception as e:
            print(f"Error processing image: {e}")
            # Fall through to text
    
    # No suitable image, try text/plain
    for rep in item.types:
        if rep.mime_type == 'text/plain' and rep.data:
            try:
                text = rep.data.decode('utf-8', errors='ignore')
                return text, False
            except Exception as e:
                print(f"Error decoding text: {e}")
    
    # No suitable representation
    return f"Unfiltered: {item.primary_type}", False