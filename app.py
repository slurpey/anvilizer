"""
Flask application implementing the SAP Anvil Tool.

This web application lets a user upload an image, crop it to a fixed
aspect ratio via a browser‑side Cropper.js component, and then
generates a set of brand‑compliant anvil overlays in various styles
(flat, stroke, gradient, window, silhouette).  The processed
previews are shown in a grid with one‑click downloads for the full
resolution assets.  The server performs high-quality upscaling via
Pillow when the cropped image is smaller than the target size.

Running
-------
Place this file at the root of your project and ensure that the
`templates` and `static` directories are present.  Then run:

    python app.py

Your default browser will open at http://127.0.0.1:5000/ where you
can interact with the tool.  No internet connection is required once
the dependencies are installed.

Dependencies
------------
The following Python packages must be installed for full
functionality:

* flask – web server.
* pillow – image handling and upscaling.
* numpy – numerical operations.
* cairosvg – converting the SVG anvil to a PNG mask.
* rembg – subject extraction for the silhouette style.

The code gracefully degrades if rembg is unavailable.

"""

import base64
import io
import os
import uuid
import gc
from pathlib import Path
import json
from typing import Dict, Tuple, List, Optional, Any

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import zipfile
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import numpy as np  # type: ignore

# --- Configuration for Local Execution ---
# Maximum pixels for square images to manage memory usage locally.
# 1920x1920 = 3,686,400 pixels. 1440x1440 = 2,073,600 pixels.
# 1080x1080 = 1,166,400 pixels.
MAX_SQUARE_PIXELS = 2_100_000  # ~1440x1440, balances quality and memory

# --- End Configuration ---

try:
    from rembg import remove, new_session  # type: ignore
    _has_rembg = True
except Exception as e:
    # rembg is optional.  Silhouette style will be disabled if absent.
    print(f"Warning: rembg not available: {e}")
    remove = None  # type: ignore
    new_session = None  # type: ignore
    _has_rembg = False


# Initialise Flask app
app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / 'generated'
OUTPUT_DIR.mkdir(exist_ok=True)

# Colour palette according to SAP specification (or your new one)
COLOR_PALETTE: Dict[str, str] = {
    # --- Original Palette ---
    # 'Blue 7': '#0070F2',
    # 'Blue 5': '#0A6ED1',
    # 'Blue 3': '#2D9CDB',
    # 'Gray 7': '#32363A',
    # 'Gray 5': '#6A6D70',
    # 'Gray 3': '#9FA3A6',
    # 'White': '#FFFFFF',
    # 'Green 5': '#3FA535',
    # 'Yellow 5': '#F2C94C',
    # 'Red 5': '#EB5757',
    # 'Orange 5': '#F2994A',
    # 'Teal 5': '#56CC9D',
    # 'Purple 5': '#BB6BD9',

    # --- New Palette (as per your detailed prompt) ---
    # Row 1
    'White': '#FFFFFF',
    'Black': '#000000',
    'Light Gray': '#EDEFF0',
    'Light Blue 1': '#D1EFFF',
    'Light Blue 2': '#AEDBFF',
    'Light Blue 3': '#7FC7FF',
    'Light Blue 4': '#4EAEFF',
    'Blue 1': '#1E90FF',
    'Blue 2': '#0070F2', # Default

    # Row 2
    'Dark Blue': '#0057B8',
    'Navy': '#00418A',
    'Deep Blue': '#002C5C',
    'Teal 1': '#7AD0C9',
    'Teal 2': '#2FA7A0',
    'Teal 3': '#0D7F7B',
    'Light Green': '#8FD99B',
    'Green 1': '#44B87B',
    'Green 2': '#2B7C46',

    # Row 3
    'Cream': '#FFF2CC',
    'Yellow': '#FFD97A',
    'Orange 1': '#FFB300',
    'Orange 2': '#E37D00',
    'Brown': '#8A4B00',
    'Red 1': '#7A0613',
    'Red 2': '#AA0843',
    'Pink 1': '#D66D9E',
    'Pink 2': '#B94D85',
}


def remove_background_human(image_array):
    """Remove background using a model optimized for human subjects.

    Args:
        image_array: numpy array of the image (RGB format)

    Returns:
        numpy array with background removed, or None if extraction fails
    """
    if not _has_rembg or remove is None or new_session is None:
        return None

    models_to_try = ['u2net_human_seg', 'silueta']
    for model_name in models_to_try:
        try:
            session = new_session(model_name)
            result = remove(image_array, session=session)
            print(f"Background removal successful using model: {model_name}")
            return result
        except Exception as e:
            print(f"Background removal failed with model {model_name}: {e}")
            continue

    # Final fallback to default model
    try:
        result = remove(image_array)
        print("Background removal successful using default model.")
        return result
    except Exception as e3:
        print(f"All background removal methods failed: {e3}")
        return None


def get_gradient_stops(base_hex: str) -> List[str]:
    """Generate four gradient stops from a base hex colour.

    The stops range from a light tint (towards white) to the original colour.

    Args:
        base_hex: Hex string starting with '#'.

    Returns:
        List of four hex colours from lightest to darkest.
    """
    base_hex = base_hex.lstrip('#')
    br = int(base_hex[0:2], 16)
    bg = int(base_hex[2:4], 16)
    bb = int(base_hex[4:6], 16)
    # Factors for mixing with white (1.0 yields white, 0.0 yields original)
    factors = [0.75, 0.5, 0.25, 0.0]
    stops: List[str] = []
    for f in factors:
        r = int(br + (255 - br) * f)
        g = int(bg + (255 - bg) * f)
        b = int(bb + (255 - bb) * f)
        stops.append(f"#{r:02X}{g:02X}{b:02X}")
    return stops


def decode_image(data_url: str) -> Image.Image:
    """Decode a base64 encoded image from a data URL."""
    header, encoded = data_url.split(',', 1)
    img_data = base64.b64decode(encoded)
    return Image.open(io.BytesIO(img_data)).convert('RGBA')


def upscale_image_if_needed(img: Image.Image, ratio: str) -> Image.Image:
    """Upscale the image using high-quality Pillow resizing if it's smaller than the target size.

    Memory-optimized version with conservative upscaling limits.

    Args:
        img: Cropped PIL Image in RGBA mode.
        ratio: Either '16:9' or '1:1'.

    Returns:
        Upscaled PIL Image.
    """
    # Conservative target sizes to manage memory usage
    if ratio == '16:9':
        target_w, target_h = 1920, 1080
        max_w, max_h = 1920, 1080  # Cap at Full HD
    else:  # 1:1
        target_w, target_h = 1080, 1080  # Reduced from 1920x1920
        max_w, max_h = 1080, 1080  # Cap at 1080x1080 for squares

    w, h = img.size
    print(f"Original image size: {w}x{h}, Target: {target_w}x{target_h}")

    # Only upscale if image is significantly smaller (less than 75% of target)
    min_threshold_w = int(target_w * 0.75)
    min_threshold_h = int(target_h * 0.75)
    
    if w >= min_threshold_w and h >= min_threshold_h:
        print("Image size adequate, no upscaling needed")
        return img

    # Calculate conservative scaling factor
    scale_w = min(target_w / w, max_w / w)
    scale_h = min(target_h / h, max_h / h)
    scale = min(scale_w, scale_h, 2.0)  # Cap scaling at 2x to prevent excessive memory usage

    # Only proceed if scaling is reasonable
    if scale <= 1.0:
        return img

    print(f"Upscaling by factor {scale:.2f}")
    new_size = (int(w * scale), int(h * scale))
    
    # Use more memory-efficient resampling for large images
    if w * h > 1000000:  # > 1MP
        resampling = Image.BILINEAR  # Less memory intensive
    else:
        resampling = Image.LANCZOS   # High quality for smaller images
    
    return img.resize(new_size, resampling)


def compute_anvil_dimensions(canvas_w: int, canvas_h: int) -> Tuple[int, int]:
    """Compute anvil dimensions (width, height) to fit within 80 % of the
    canvas size while maintaining a 2:1 width:height ratio."""
    max_h = int(canvas_h * 0.8)
    max_w = int(canvas_w * 0.8)
    # Try to fit by height first
    h_based = max_h
    w_based = h_based * 2
    if w_based <= canvas_w:
        return w_based, h_based
    # Otherwise, fit by width
    w_based = max_w
    h_based = w_based // 2
    if h_based > max_h:
        h_based = max_h
        w_based = h_based * 2
    return w_based, h_based


def compute_anvil_coords(canvas_size: Tuple[int, int], scale: float, offset_x: float, offset_y: float) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
    """Compute the coordinates of the anvil's four vertices.

    Args:
        canvas_size: (width, height) of the canvas.
        scale: Relative size of the anvil compared to the canvas width (0..1).  The
            anvil maintains a 2:1 width:height ratio.
        offset_x: Horizontal offset in the range [-1, 1].  0 centres the anvil.
        offset_y: Vertical offset in the range [-1, 1].  0 centres the anvil.

    Returns:
        A tuple of four (x, y) coordinates: p1 (top‑left), p2 (top‑right), p3 (bottom‑mid), p4 (bottom‑left).
    """
    w, h = canvas_size
    # Clamp inputs
    scale = max(0.0, min(scale, 1.0))
    offset_x = max(-1.0, min(offset_x, 1.0))
    offset_y = max(-1.0, min(offset_y, 1.0))
    # Width and height of anvil maintaining 2:1 ratio
    anvil_w = w * scale
    anvil_h = anvil_w / 2.0
    # Maximum translation available once centered
    max_dx = (w - anvil_w) / 2.0
    max_dy = (h - anvil_h) / 2.0
    # Position of top‑left corner
    left = (w - anvil_w) / 2.0 + offset_x * max_dx
    top = (h - anvil_h) / 2.0 + offset_y * max_dy
    # Points
    p1 = (int(left), int(top))
    p2 = (int(left + anvil_w), int(top))
    p3 = (int(left + anvil_w / 2.0), int(top + anvil_h))
    p4 = (int(left), int(top + anvil_h))
    return p1, p2, p3, p4


def create_anvil_mask(size: Tuple[int, int], invert: bool = False, coords: Optional[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]] = None) -> Image.Image:
    """Create a binary mask of the anvil shape.

    Args:
        size: (width, height) of the canvas.
        invert: When `True, invert the mask so that the anvil area is
            transparent and the surrounding area is opaque.
        coords: Optional precomputed coordinates of the anvil vertices.  If
            provided, these are used instead of computing default dimensions.

    Returns:
        A single‑channel (L mode) PIL Image representing the mask.
    """
    w, h = size
    # When invert is False, the mask will be 0 in the anvil area and 255 outside.
    # When invert is True, the mask will be 255 in the anvil area and 0 outside.
    if invert:
        mask = Image.new('L', (w, h), 0)
    else:
        mask = Image.new('L', (w, h), 255)
    draw = ImageDraw.Draw(mask)
    if coords is None:
        anvil_w, anvil_h = compute_anvil_dimensions(w, h)
        off_x = (w - anvil_w) // 2
        off_y = (h - anvil_h) // 2
        p1 = (off_x, off_y)
        p2 = (off_x + anvil_w, off_y)
        p3 = (off_x + anvil_w // 2, off_y + anvil_h)
        p4 = (off_x, off_y + anvil_h)
    else:
        p1, p2, p3, p4 = coords
    if invert:
        # Fill the anvil area with 255 on an initially 0 mask
        draw.polygon([p1, p2, p3, p4], fill=255)
    else:
        # Draw the anvil area with 0 on an initially 255 mask
        draw.polygon([p1, p2, p3, p4], fill=0)
    return mask


def draw_stroke_outline(size: Tuple[int, int], stroke_colour: Tuple[int, int, int], coords: Optional[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]] = None) -> Image.Image:
    """Draw only the outline of the anvil on a transparent background.

    Args:
        size: Canvas size (width, height).
        stroke_colour: RGB tuple for the outline.
        coords: Optional explicit anvil coordinates.  When provided, these
            override the default centred anvil.

    Returns:
        A transparent RGBA image with the outline drawn.
    """
    w, h = size
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if coords is None:
        anvil_w, anvil_h = compute_anvil_dimensions(w, h)
        off_x = (w - anvil_w) // 2
        off_y = (h - anvil_h) // 2
        p1 = (off_x, off_y)
        p2 = (off_x + anvil_w, off_y)
        p3 = (off_x + anvil_w // 2, off_y + anvil_h)
        p4 = (off_x, off_y + anvil_h)
    else:
        p1, p2, p3, p4 = coords
        anvil_w = p2[0] - p1[0]
        anvil_h = p4[1] - p1[1]
    # Stroke thickness scaled relative to a 400×200 reference
    ref_width = 400
    stroke_thickness = int(max(anvil_w / ref_width, anvil_h / (ref_width / 2)) * 16)
    if stroke_thickness < 1:
        stroke_thickness = 1
    # Use polygon with outline to draw a continuous shape with crisp edges
    draw.polygon([p1, p2, p3, p4], outline=stroke_colour + (255,), fill=None, width=stroke_thickness)
    return img


def gradient_fill_anvil(size: Tuple[int, int], colours: List[str], coords: Optional[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]] = None) -> Image.Image:
    """Create a step gradient overlay within the anvil shape.

    Draws nested anvil shapes decreasing to 75 %, 50 % and 25 % of the
    base size, aligned to the bottom‑right corner.  Colours are used
    from lightest to darkest.  The returned image is an RGBA overlay
    where the shape areas are opaque and outside the anvil is
    transparent.  This overlay can be composited onto an underlying
    photograph to achieve the gradient style.
    """
    w, h = size
    # Determine base anvil coordinates
    if coords is None:
        base_w, base_h = compute_anvil_dimensions(w, h)
        off_x = (w - base_w) // 2
        off_y = (h - base_h) // 2
        base_coords = (off_x, off_y, base_w, base_h)
    else:
        # coords: p1, p2, p3, p4
        p1, p2, p3, p4 = coords
        base_w = p2[0] - p1[0]
        base_h = p4[1] - p1[1]
        off_x = p1[0]
        off_y = p1[1]
        base_coords = (off_x, off_y, base_w, base_h)
    # Transparent canvas
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Full shape (100%) at index 0, then 75%, 50%, 25%
    scales = [1.0, 0.75, 0.5, 0.25]
    for idx, scale in enumerate(scales):
        shape_w = base_w * scale
        shape_h = base_h * scale
        # Align bottom‑right and diagonal: bottom‑mid of shape aligns with bottom‑mid of base,
        # and the diagonal edge of the smaller shape lies on the diagonal of the base.  The
        # horizontal position centres the shape relative to the base.
        px = off_x + (base_w / 2.0 - shape_w / 2.0)
        py = off_y + (base_h - shape_h)
        p1_s = (int(px), int(py))
        p2_s = (int(px + shape_w), int(py))
        p3_s = (int(px + shape_w / 2.0), int(py + shape_h))
        p4_s = (int(px), int(py + shape_h))
        colour = colours[min(idx, len(colours) - 1)]
        rgb = tuple(int(colour[i:i+2], 16) for i in (1, 3, 5))
        draw.polygon([p1_s, p2_s, p3_s, p4_s], fill=rgb + (255,))
    # Mask overlay to the base anvil area
    base_mask = create_anvil_mask(size, invert=True, coords=coords)
    masked_overlay = Image.composite(overlay, Image.new('RGBA', (w, h), (0, 0, 0, 0)), base_mask)
    return masked_overlay


def apply_window_style(img: Image.Image, size: Tuple[int, int], bg_colour: Tuple[int, int, int], coords: Optional[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]] = None) -> Image.Image:
    """Apply the window style: show the image only inside the anvil shape and
    fill the remaining area with the chosen background colour.

    Args:
        img: Upscaled PIL Image (RGBA).
        size: Size of the final canvas (width, height).
        bg_colour: RGB tuple for outside area.
        coords: Optional explicit anvil coordinates.

    Returns:
        A PIL Image with the window style applied.
    """
    w, h = size
    # Resize image to fit exactly into the canvas
    img_resized = img.resize((w, h), Image.LANCZOS)
    # Create mask: inside shape = 255, outside = 0
    mask = create_anvil_mask(size, invert=True, coords=coords)
    # Create background image filled with bg_colour
    bg = Image.new('RGBA', (w, h), bg_colour + (255,))
    # Composite the image and background using mask
    out = Image.composite(img_resized, bg, mask)
    return out


def apply_silhouette_style(img: Image.Image, size: Tuple[int, int], fill_colour: Tuple[int, int, int], opacity: float, coords: Optional[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]] = None) -> Image.Image:
    """Apply the silhouette style.

    The silhouette style overlays a semi‑transparent anvil filled with
    `fill_colour on top of the photograph and places the subject
    cut‑out on top in its original position.  No scaling or recentring
    is applied to the subject; it retains the same dimensions as the
    cropped input.  The opacity controls the alpha of the anvil fill.

    Args:
        img: Upscaled PIL Image (RGBA) that has been resized to the
            final canvas dimensions.
        size: (width, height) of the output canvas.
        fill_colour: RGB tuple for the anvil fill.
        opacity: Float between 0 and 1 specifying the opacity of the
            coloured anvil overlay.

    Returns:
        A PIL Image with the silhouette style applied.
    """
    # Ensure the base image fits the canvas
    base = img.resize(size, Image.LANCZOS).convert('RGBA')
    w, h = size
    # Create semi‑transparent anvil overlay
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if coords is None:
        # Default centred coords
        anvil_w, anvil_h = compute_anvil_dimensions(w, h)
        off_x = (w - anvil_w) // 2
        off_y = (h - anvil_h) // 2
        p1 = (off_x, off_y)
        p2 = (off_x + anvil_w, off_y)
        p3 = (off_x + anvil_w // 2, off_y + anvil_h)
        p4 = (off_x, off_y + anvil_h)
    else:
        p1, p2, p3, p4 = coords
    alpha_val = int(max(0.0, min(1.0, opacity)) * 255)
    draw.polygon([p1, p2, p3, p4], fill=fill_colour + (alpha_val,))
    # Composite coloured anvil over base
    composite = base.copy()
    composite.alpha_composite(overlay)
    # Extract subject via rembg if available
    subject_img: Optional[Image.Image]
    if _has_rembg:
        arr = remove_background_human(np.array(base.convert('RGB')))
        if arr is not None:
            subject_img = Image.fromarray(arr).convert('RGBA')
        else:
            subject_img = None
    else:
        subject_img = None
    # If extraction fails, use the original image alpha channel as the subject
    if subject_img is None:
        subject_img = base.copy()
    # Overlay subject cut‑out in the same position (no scaling or recentering)
    composite.alpha_composite(subject_img)
    return composite


def generate_styles_sequential(cropped_img: Image.Image, ratio: str, chosen_colour_hex: str, uid: str, opacity: float = 0.5, anvil_scale: float = 0.7, anvil_offset_x: float = 0.0, anvil_offset_y: float = 0.0) -> Dict[str, str]:
    """Generate all required styles sequentially with disk buffering to minimize memory usage.

    This version generates one style at a time, saves it to disk, and clears memory before
    proceeding to the next style. This dramatically reduces peak memory usage.

    Returns a dictionary mapping style names to file paths.
    """
    # Create session directory
    session_dir = OUTPUT_DIR / uid
    session_dir.mkdir(exist_ok=True)
    
    # Ensure we have RGBA
    img = cropped_img.convert('RGBA')
    print(f"Starting sequential processing for {img.size} image")
    
    # Upscale if needed
    upscaled = upscale_image_if_needed(img, ratio)
    
    # Use conservative target sizes
    if ratio == '16:9':
        target_w, target_h = 1920, 1080
    else:  # 1:1
        target_w, target_h = 1080, 1080

    orig_w, orig_h = upscaled.size
    if orig_w >= target_w and orig_h >= target_h:
        size = (orig_w, orig_h)
        img_resized = upscaled.resize(size, Image.LANCZOS) if upscaled.size != size else upscaled
    else:
        size = (target_w, target_h)
        img_resized = upscaled.resize(size, Image.LANCZOS)
    
    # Save base image to disk and clear from memory
    base_path = session_dir / 'base_temp.png'
    img_resized.save(base_path, format='PNG')
    del img, cropped_img, upscaled, img_resized
    gc.collect()
    print("Base image saved to disk, memory cleared")
    
    # Convert chosen colour hex to RGB tuple
    hex_colour = chosen_colour_hex.lstrip('#')
    fill_colour = tuple(int(hex_colour[i:i+2], 16) for i in (0, 2, 4))
    
    # Compute anvil coordinates
    coords = compute_anvil_coords(size, anvil_scale, anvil_offset_x, anvil_offset_y)
    
    # Extract subject cutout ONCE and save to disk
    subject_cutout_path = session_dir / 'subject_temp.png'
    if _has_rembg:
        print("Extracting subject using rembg...")
        # Load base image temporarily for rembg
        base_img = Image.open(base_path).convert('RGB')
        arr = remove_background_human(np.array(base_img))
        if arr is not None:
            subject_cutout = Image.fromarray(arr).convert('RGBA')
            subject_cutout.save(subject_cutout_path, format='PNG')
            print("Subject extraction successful, saved to disk")
        else:
            print("Subject extraction failed, using fallback")
            base_img.convert('RGBA').save(subject_cutout_path, format='PNG')
        del base_img, subject_cutout
        gc.collect()
    else:
        # Fallback: use base image as subject
        base_img = Image.open(base_path).convert('RGBA')
        base_img.save(subject_cutout_path, format='PNG')
        del base_img
        gc.collect()
    
    print("Subject cutout saved, starting sequential style generation...")
    
    # Generate styles sequentially
    style_paths = {}
    
    # Style 1: Flat
    print("Generating Flat style...")
    base_img = Image.open(base_path).convert('RGBA')
    flat_overlay = Image.new('RGBA', size, (0, 0, 0, 0))
    draw_flat = ImageDraw.Draw(flat_overlay)
    flat_alpha = int(max(0.0, min(1.0, opacity)) * 255)
    draw_flat.polygon(list(coords), fill=fill_colour + (flat_alpha,))
    base_img.alpha_composite(flat_overlay)
    flat_path = session_dir / 'Flat.png'
    base_img.save(flat_path, format='PNG')
    style_paths['Flat'] = str(flat_path)
    del base_img, flat_overlay
    gc.collect()
    
    # Style 2: Stroke
    print("Generating Stroke style...")
    base_img = Image.open(base_path).convert('RGBA')
    subject_img = Image.open(subject_cutout_path).convert('RGBA')
    stroke_layer = draw_stroke_outline(size, fill_colour, coords=coords)
    base_img.alpha_composite(stroke_layer)
    base_img.alpha_composite(subject_img)
    stroke_path = session_dir / 'Stroke.png'
    base_img.save(stroke_path, format='PNG')
    style_paths['Stroke'] = str(stroke_path)
    del base_img, subject_img, stroke_layer
    gc.collect()
    
    # Style 3: Gradient
    print("Generating Gradient style...")
    base_img = Image.open(base_path).convert('RGBA')
    grad_stops = get_gradient_stops(chosen_colour_hex)
    gradient_overlay = gradient_fill_anvil(size, grad_stops, coords=coords)
    base_img.alpha_composite(gradient_overlay)
    gradient_path = session_dir / 'Gradient.png'
    base_img.save(gradient_path, format='PNG')
    style_paths['Gradient'] = str(gradient_path)
    del base_img, gradient_overlay
    gc.collect()
    
    # Style 4: Window
    print("Generating Window style...")
    # For window style, we need the upscaled image, so reload and process
    base_img = Image.open(base_path).convert('RGBA')
    window_img = apply_window_style(base_img, size, fill_colour, coords=coords)
    window_path = session_dir / 'Window.png'
    window_img.save(window_path, format='PNG')
    style_paths['Window'] = str(window_path)
    del base_img, window_img
    gc.collect()
    
    # Style 5: Silhouette
    print("Generating Silhouette style...")
    base_img = Image.open(base_path).convert('RGBA')
    subject_img = Image.open(subject_cutout_path).convert('RGBA')
    overlay = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alpha_val = int(max(0.0, min(1.0, opacity)) * 255)
    draw.polygon(list(coords), fill=fill_colour + (alpha_val,))
    base_img.alpha_composite(overlay)
    base_img.alpha_composite(subject_img)
    silhouette_path = session_dir / 'Silhouette.png'
    base_img.save(silhouette_path, format='PNG')
    style_paths['Silhouette'] = str(silhouette_path)
    del base_img, subject_img, overlay
    gc.collect()
    
    # Style 6: Gradient Silhouette
    print("Generating Gradient Silhouette style...")
    base_img = Image.open(base_path).convert('RGBA')
    subject_img = Image.open(subject_cutout_path).convert('RGBA')
    grad_sil_overlay = gradient_fill_anvil(size, grad_stops, coords=coords)
    base_img.alpha_composite(grad_sil_overlay)
    base_img.alpha_composite(subject_img)
    grad_sil_path = session_dir / 'Gradient Silhouette.png'
    base_img.save(grad_sil_path, format='PNG')
    style_paths['Gradient Silhouette'] = str(grad_sil_path)
    del base_img, subject_img, grad_sil_overlay
    gc.collect()
    
    # Clean up temporary files
    try:
        base_path.unlink()
        subject_cutout_path.unlink()
    except Exception as e:
        print(f"Warning: Could not clean up temp files: {e}")
    
    print("Sequential style generation completed successfully")
    return style_paths


def save_images(images: Dict[str, Image.Image], uid: str, orig_filename: str, colour_hex: str) -> Dict[str, str]:
    """Save images to disk and return a mapping from style to file path.

    Images are stored within a session directory named by `uid.  Each
    style is saved as `<style>.png (e.g. Flat.png) regardless of
    the original filename or colour selection.  This simplifies the
    download route.  A `meta.json file is also created to record the
    `base_name (stem of the original filename) and a slugified colour
    name derived from the SAP palette.  These values are used later to
    construct friendly download names and zip entries.

    Args:
        images: Mapping of style name to PIL Image.
        uid: Unique session identifier.
        orig_filename: Name of the original uploaded file.
        colour_hex: Hex code of the selected colour.

    Returns:
        Mapping from style name to file path.
    """
    session_dir = OUTPUT_DIR / uid
    session_dir.mkdir(exist_ok=True)
    # Derive a human‑friendly colour slug based on the palette.  If no
    # matching name exists, use 'Custom'.  Spaces are removed to form
    # the slug.  This slug is stored in meta.json for later use in
    # download file names and zip entries.
    colour_name: Optional[str] = None
    for name, hex_val in COLOR_PALETTE.items():
        if hex_val.lower() == colour_hex.lower():
            colour_name = name
            break
    if colour_name is None:
        colour_name = 'Custom'
    colour_slug = colour_name.replace(' ', '')
    base_name = Path(orig_filename).stem or 'image'
    # Write session metadata
    meta = {
        'base_name': base_name,
        'colour_slug': colour_slug
    }
    with open(session_dir / 'meta.json', 'w', encoding='utf-8') as f:
        json.dump(meta, f)
    paths: Dict[str, str] = {}
    # Save each style with a simple name (<Style>.png).  Preserve
    # capitalisation for clarity.  The download route will map these
    # simple filenames to friendly names using meta.json.
    for style, img in images.items():
        filename = f"{style}.png"
        file_path = session_dir / filename
        img.convert('RGBA').save(file_path, format='PNG')
        paths[style] = str(file_path)
    return paths


@app.route('/')
def index() -> Any:
    """Serve the main page."""
    # Pass the default color explicitly if needed by the template
    default_color = COLOR_PALETTE.get('Blue 2', '#0070F2') # Fallback to original default if new palette key missing
    return render_template('index.html', colours=COLOR_PALETTE, default_color=default_color)


@app.route('/process', methods=['POST'])
def process() -> Any:
    """Handle the cropped image and generate previews.

    Expects JSON with keys:
        * imageData: Data URL of the cropped image.
        * ratio: '16:9' or '1:1'.
        * colour: Colour hex string.

    Returns:
        JSON containing preview data and download identifiers.
    """
    data = request.get_json(force=True)
    image_data = data.get('imageData')
    ratio = data.get('ratio', '16:9')
    colour = data.get('colour', COLOR_PALETTE.get('Blue 2', '#0070F2')) # Default to new palette default
    # Opacity for silhouette style (0..1)
    opacity = data.get('opacity', 0.5)
    # Original filename
    orig_filename = data.get('filename', 'image')
    # Anvil customisation parameters
    anvil_scale = data.get('anvilScale', 0.7)
    anvil_offset_x = data.get('anvilOffsetX', 0.0)
    anvil_offset_y = data.get('anvilOffsetY', 0.0)
    if not image_data:
        return jsonify({'error': 'No image data provided'}), 400
    try:
        cropped_img = decode_image(image_data)
    except Exception as e:
        print(f"Error decoding image: {e}")
        return jsonify({'error': 'Failed to decode image data'}), 400
    # Generate styles
    try:
        opacity_val = float(opacity)
    except Exception:
        opacity_val = 0.5
    opacity_val = max(0.0, min(1.0, opacity_val))
    # Parse anvil customisation values
    try:
        scale_val = float(anvil_scale)
    except Exception:
        scale_val = 0.7
    try:
        offset_x_val = float(anvil_offset_x)
    except Exception:
        offset_x_val = 0.0
    try:
        offset_y_val = float(anvil_offset_y)
    except Exception:
        offset_y_val = 0.0
    # Clamp values
    scale_val = max(0.2, min(scale_val, 1.0))
    offset_x_val = max(-1.0, min(offset_x_val, 1.0))
    offset_y_val = max(-1.0, min(offset_y_val, 1.0))
    print(f"Processing image: Ratio={ratio}, Color={colour}, Scale={scale_val}, OffsetX={offset_x_val}, OffsetY={offset_y_val}")
    
    try:
        # Generate unique ID for this session
        uid = uuid.uuid4().hex
        
        # Use sequential generation to minimize memory usage
        style_paths = generate_styles_sequential(
            cropped_img, ratio, colour, uid, opacity=opacity_val,
            anvil_scale=scale_val, anvil_offset_x=offset_x_val, anvil_offset_y=offset_y_val
        )
        
        # Save metadata for downloads
        session_dir = OUTPUT_DIR / uid
        colour_name: Optional[str] = None
        for name, hex_val in COLOR_PALETTE.items():
            if hex_val.lower() == colour.lower():
                colour_name = name
                break
        if colour_name is None:
            colour_name = 'Custom'
        colour_slug = colour_name.replace(' ', '')
        base_name = Path(orig_filename).stem or 'image'
        
        meta = {
            'base_name': base_name,
            'colour_slug': colour_slug
        }
        with open(session_dir / 'meta.json', 'w', encoding='utf-8') as f:
            json.dump(meta, f)
        
        # Create previews from saved files (memory-efficient)
        previews = {}
        for style, file_path in style_paths.items():
            # Load image temporarily for preview
            img = Image.open(file_path).convert('RGBA')
            img.thumbnail((400, 1400))  # Smaller previews to save memory
            buffered = io.BytesIO()
            img.save(buffered, format='PNG')
            preview_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            previews[style] = preview_b64
            
            # Clean up immediately
            del img, buffered
            gc.collect()
        
        # Final cleanup
        del cropped_img
        gc.collect()
        
        print("Sequential image processing completed successfully")
        return jsonify({'uid': uid, 'previews': previews})
        
    except Exception as e:
        print(f"Error during image processing: {e}")
        # Clean up on error
        gc.collect()
        return jsonify({'error': f'Image processing failed: {str(e)}. Try with a smaller image.'}), 500


@app.route('/download/<uid>/<style_name>')
def download(uid: str, style_name: str) -> Any:
    """Serve the requested high‑resolution image as an attachment."""
    session_dir = OUTPUT_DIR / uid
    file_path = session_dir / f"{style_name}.png"
    if not file_path.exists():
        return "Not found", 404
    # Load metadata to construct a friendly filename
    meta_path = session_dir / 'meta.json'
    download_name = f"{style_name}.png"
    if meta_path.exists():
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
            base_name = meta_data.get('base_name', 'image')
            colour_slug = meta_data.get('colour_slug', '')
            # Compose new download name including style and colour slug
            download_name = f"{base_name}_{style_name.lower()}"
            if colour_slug:
                download_name += f"_{colour_slug}"
            download_name += ".png"
        except Exception as e:
            print(f"Error reading meta.json for download: {e}")
            # On error fall back to default
            download_name = f"{style_name}.png"
    return send_file(str(file_path), mimetype='image/png', as_attachment=True,
                     download_name=download_name)


@app.route('/download_all/<uid>')
def download_all(uid: str) -> Any:
    """Serve a zip file containing all generated images for the given UID."""
    session_dir = OUTPUT_DIR / uid
    if not session_dir.exists():
        return "Not found", 404
    # Create a zip archive on the fly
    zip_path = session_dir / 'anvil_assets.zip'
    # Load metadata for naming; fallback values if missing
    base_name = 'image'
    colour_slug = ''
    meta_path = session_dir / 'meta.json'
    if meta_path.exists():
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
            base_name = meta_data.get('base_name', base_name)
            colour_slug = meta_data.get('colour_slug', colour_slug)
        except Exception as e:
            print(f"Error reading meta.json for zip: {e}")
            pass
    # Always rebuild the zip to ensure it contains the latest images
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for file in session_dir.iterdir():
            if file.suffix.lower() == '.png':
                style_name = file.stem  # e.g. 'Flat'
                arc_name = f"{base_name}_{style_name.lower()}"
                if colour_slug:
                    arc_name += f"_{colour_slug}"
                arc_name += ".png"
                zf.write(file, arcname=arc_name)
    return send_file(str(zip_path), mimetype='application/zip', as_attachment=True,
                     download_name='anvil_assets.zip')


def cleanup_old_sessions(max_sessions: int = 20) -> None:
    """Remove old session directories to avoid cluttering disk."""
    try:
        sessions = sorted((d for d in OUTPUT_DIR.iterdir() if d.is_dir()),
                          key=lambda d: d.stat().st_mtime, reverse=True)
        for old in sessions[max_sessions:]:
            import shutil
            shutil.rmtree(old, ignore_errors=True)
            print(f"Cleaned up old session: {old}")
    except Exception as e:
        print(f"Error during session cleanup: {e}")


if __name__ == '__main__':
    # Clean up old sessions on startup
    cleanup_old_sessions()

    # Get port from environment variable for Cloud Foundry deployment
    import os
    port = int(os.environ.get('PORT', 5000))
    
    # Start the server - bind to all interfaces for Cloud Foundry
    app.run(host='0.0.0.0', port=port, debug=False)

# --- Removed Anvil Server Code ---
# The code below seems to be for Anvil Uplink integration, not the main Flask app.
# It's commented out to prevent conflicts or errors during local execution.
#
# from anvil.server import connect, callable, wait_forever
# # Get your Uplink key from Anvil: App -> Publish -> Uplink Keys
# connect("client_ZE2DGNINFHVVTD5PFMSITCJC-GSCAMTS7SZRVLCOH")
# @callable
# def apply_style(image_bytes: bytes) -> bytes:
#     # Do your existing processing here, return processed image bytes (e.g., PNG)
#     # Example skeleton:
#     # from PIL import Image, ImageOps
#     # import io
#     # im = Image.open(io.BytesIO(image_bytes))
#     # im = ImageOps.grayscale(im)
#     # out = io.BytesIO()
#     # im.save(out, format="PNG")
#     # return out.getvalue()
#     ...
# wait_forever()
