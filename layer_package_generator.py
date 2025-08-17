#!/usr/bin/env python3
"""
Layer Package Generator for Anvilizer
Creates ZIP files containing separate PNG layers for professional editing
"""

import zipfile
import json
import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image
import numpy as np

def create_layer_package(
    background_img: Image.Image,
    subject_cutout: Optional[Image.Image],
    anvil_overlay: Image.Image,
    composite_result: Image.Image,
    style_name: str,
    color_name: str,
    color_hex: str,
    base_filename: str,
    resolution: str
) -> bytes:
    """
    Create a ZIP file containing all layers as separate PNGs plus metadata.
    
    Args:
        background_img: Original cropped/resized background image
        subject_cutout: Extracted subject with transparency (None if not available)
        anvil_overlay: Anvil shape overlay with transparency
        composite_result: Final flattened result
        style_name: Style name (e.g., "Window", "Silhouette")
        color_name: Human-readable color name
        color_hex: Color hex code
        base_filename: Original filename stem
        resolution: Resolution string (e.g., "3840x2160")
    
    Returns:
        ZIP file content as bytes
    """
    
    # Create in-memory ZIP file
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        
        # Layer 1: Background (original image)
        bg_bytes = image_to_bytes(background_img, "PNG")
        zf.writestr("01_background.png", bg_bytes)
        
        # Layer 2: Subject cutout (if available)
        if subject_cutout is not None:
            subject_bytes = image_to_bytes(subject_cutout, "PNG")
            zf.writestr("02_subject_cutout.png", subject_bytes)
        
        # Layer 3: Anvil shape overlay
        anvil_bytes = image_to_bytes(anvil_overlay, "PNG")
        zf.writestr("03_anvil_shape.png", anvil_bytes)
        
        # Final composite result
        composite_bytes = image_to_bytes(composite_result, "PNG")
        zf.writestr("final_composite.png", composite_bytes)
        
        # Create metadata JSON
        metadata = create_metadata(
            style_name, color_name, color_hex, base_filename, 
            resolution, subject_cutout is not None
        )
        zf.writestr("layer_info.json", json.dumps(metadata, indent=2))
        
        # Create README file
        readme_content = create_readme(
            style_name, color_name, base_filename, resolution, subject_cutout is not None
        )
        zf.writestr("README.txt", readme_content)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def image_to_bytes(image: Image.Image, format: str) -> bytes:
    """Convert PIL Image to bytes for ZIP storage."""
    img_buffer = io.BytesIO()
    image.save(img_buffer, format=format)
    return img_buffer.getvalue()


def create_metadata(
    style_name: str, 
    color_name: str, 
    color_hex: str, 
    base_filename: str, 
    resolution: str,
    has_subject_cutout: bool
) -> Dict:
    """Create metadata JSON for the layer package."""
    
    layers = [
        {
            "name": "Background",
            "file": "01_background.png",
            "description": "Original cropped image at full resolution"
        }
    ]
    
    if has_subject_cutout:
        layers.append({
            "name": "Subject Cutout",
            "file": "02_subject_cutout.png", 
            "description": "Extracted person/object with transparency"
        })
    
    layers.append({
        "name": "Anvil Shape",
        "file": "03_anvil_shape.png",
        "description": f"SAP anvil overlay in {color_name} ({color_hex})"
    })
    
    return {
        "anvilizer_export": {
            "version": "1.0",
            "style": style_name,
            "color": {
                "name": color_name,
                "hex": color_hex
            },
            "original_filename": base_filename,
            "resolution": resolution,
            "layers": layers,
            "composite_file": "final_composite.png",
            "instructions": "Import these layers into Photoshop, GIMP, or any layer-capable editor. Each PNG maintains transparency where appropriate.",
            "created_by": "Lloyd's Anvilizer"
        }
    }


def create_readme(
    style_name: str, 
    color_name: str, 
    base_filename: str, 
    resolution: str,
    has_subject_cutout: bool
) -> str:
    """Create README.txt content for the layer package."""
    
    subject_info = """• 02_subject_cutout.png  - Extracted subject (person/object)""" if has_subject_cutout else ""
    
    return f"""ANVILIZER LAYER PACKAGE
=======================

Style: {style_name}
Color: {color_name}
Original File: {base_filename}
Resolution: {resolution}

This ZIP contains all the layers used to create your anvilized image:

FILES:
------
• 01_background.png      - Original image background
{subject_info}
• 03_anvil_shape.png     - SAP anvil overlay shape
• final_composite.png    - Final flattened result
• layer_info.json       - Technical metadata

USAGE INSTRUCTIONS:
-------------------
1. Extract all files to a folder
2. Open your image editor (Photoshop, GIMP, Figma, etc.)
3. Create a new document at {resolution}
4. Import each layer in order:
   - 01_background.png (as bottom layer)
   {"- 02_subject_cutout.png (above background)" if has_subject_cutout else ""}
   - 03_anvil_shape.png (as top layer)
5. Each PNG file maintains proper transparency
6. Edit individual layers as needed

LAYER DESCRIPTIONS:
-------------------
🔹 Background: Your original cropped image at full resolution
{"🔹 Subject Cutout: AI-extracted person/object with transparent background" if has_subject_cutout else ""}
🔹 Anvil Shape: SAP anvil in your chosen color with transparency
🔹 Final Composite: Ready-to-use flattened result

BENEFITS:
---------
✓ Full editability - modify any layer independently
✓ Universal format - works with any image editor  
✓ Transparent backgrounds preserved
✓ Original resolution maintained ({resolution})
✓ Professional workflow ready

TECHNICAL DETAILS:
------------------
Export Format: PNG with alpha channel
Color Space: sRGB
Bit Depth: 8-bit per channel
Compression: Lossless PNG

Need help? Check layer_info.json for technical metadata.

Created with Lloyd's Anvilizer
https://github.com/slurpey/anvilizer
"""


def get_layer_components_from_style(
    base_img: Image.Image,
    style_name: str, 
    color_rgb: Tuple[int, int, int],
    coords: Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]],
    opacity: float = 0.5
) -> Tuple[Image.Image, Optional[Image.Image], Image.Image]:
    """
    Extract layer components from a style processing operation.
    
    Returns:
        Tuple of (background, subject_cutout, anvil_overlay)
    """
    from app import remove_background_human, _has_rembg
    
    size = base_img.size
    
    # Background is always the base image
    background = base_img.copy()
    
    # Subject cutout (only for styles that use it)
    subject_cutout = None
    if style_name in ['Silhouette', 'Gradient Silhouette', 'Stroke']:
        if _has_rembg:
            arr = remove_background_human(np.array(base_img.convert('RGB')))
            if arr is not None:
                subject_cutout = Image.fromarray(arr).convert('RGBA')
    
    # Create anvil overlay based on style
    anvil_overlay = Image.new('RGBA', size, (0, 0, 0, 0))
    
    if style_name == 'Flat':
        # Simple filled anvil
        from PIL import ImageDraw
        draw = ImageDraw.Draw(anvil_overlay)
        alpha_val = int(max(0.0, min(1.0, opacity)) * 255)
        draw.polygon(list(coords), fill=color_rgb + (alpha_val,))
        
    elif style_name == 'Stroke':
        # Stroke outline only
        from app import draw_stroke_outline
        anvil_overlay = draw_stroke_outline(size, color_rgb, coords=coords)
        
    elif style_name in ['Gradient', 'Gradient Silhouette']:
        # Gradient fill
        from app import gradient_fill_anvil, get_gradient_stops
        color_hex = f"#{color_rgb[0]:02X}{color_rgb[1]:02X}{color_rgb[2]:02X}"
        grad_stops = get_gradient_stops(color_hex)
        anvil_overlay = gradient_fill_anvil(size, grad_stops, coords=coords)
        
    elif style_name in ['Silhouette']:
        # Semi-transparent filled anvil
        from PIL import ImageDraw
        draw = ImageDraw.Draw(anvil_overlay)
        alpha_val = int(max(0.0, min(1.0, opacity)) * 255)
        draw.polygon(list(coords), fill=color_rgb + (alpha_val,))
        
    elif style_name == 'Window':
        # For window style, the "anvil overlay" is actually a mask
        # Create a colored version showing the anvil area
        from PIL import ImageDraw
        draw = ImageDraw.Draw(anvil_overlay)
        draw.polygon(list(coords), fill=color_rgb + (128,))  # Semi-transparent for visibility
    
    return background, subject_cutout, anvil_overlay
