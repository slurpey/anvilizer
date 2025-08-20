"""
Flask application implementing the SAP Anvil Tool.

This web application lets a user upload an image, crop it to a fixed
aspect ratio via a custom browser-side crop interface, and then
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
import threading
import time
from collections import deque
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

# --- Queue System ---
class ProcessingJob:
    def __init__(self, job_id, route, params):
        self.job_id = job_id
        self.route = route  # 'preview' or 'highres'
        self.params = params
        self.status = "queued"
        self.result = None

queue_lock = threading.Lock()
processing_queue = deque()  # List of ProcessingJob objects
active_job_id = None  # Currently running job

# Global lock dictionary for per-session concurrency control
session_locks = {}  # uid: threading.Lock

def add_job_to_queue(route, params):
    job_id = uuid.uuid4().hex
    job = ProcessingJob(job_id, route, params)
    with queue_lock:
        processing_queue.append(job)
    return job_id

def get_job_position(job_id):
    with queue_lock:
        for idx, job in enumerate(processing_queue):
            if job.job_id == job_id:
                return idx + (1 if active_job_id != job_id else 0)
    return -1

def set_active_job(job_id):
    global active_job_id
    with queue_lock:
        active_job_id = job_id

def remove_job(job_id):
    global active_job_id, processing_queue
    with queue_lock:
        # copy to a list first to avoid iterator issues, then rebuild deque
        processing_queue = deque([job for job in list(processing_queue) if job.job_id != job_id])
        if active_job_id == job_id:
            active_job_id = None

def job_status(job_id):
    with queue_lock:
        for job in processing_queue:
            if job.job_id == job_id:
                return job.status
    return "not_found"

@app.route("/queue_status/<job_id>")
def queue_status(job_id):
    pos = get_job_position(job_id)
    status = job_status(job_id)
    return jsonify({"position": pos, "status": status})

# Configure CSP with more permissive policy to handle browser extensions
@app.after_request
def set_csp_header(response):
    # More permissive CSP that allows browser extensions while maintaining security
    response.headers['Content-Security-Policy'] = "script-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self';"
    return response

BASE_DIR = Path(__file__).resolve().parent

# Prefer PVC-backed /logs for both log images and generated output when available.
# This ensures generated files are written to the cluster persistent volume
# (mounted at /logs) instead of the container's ephemeral filesystem.
if os.path.exists('/logs'):
    LOGS_DIR = Path('/logs')
    OUTPUT_DIR = LOGS_DIR / 'generated'
else:
    LOGS_DIR = BASE_DIR / 'logs'
    OUTPUT_DIR = BASE_DIR / 'generated'

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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

    True high-resolution version supporting up to 8K output.

    Args:
        img: Cropped PIL Image in RGBA mode.
        ratio: Either '16:9' or '1:1'.

    Returns:
        Upscaled PIL Image (original size preserved for high-quality processing).
    """
    # True high-resolution target sizes - preserve original image dimensions
    if ratio == '16:9':
        target_w, target_h = 7680, 4320  # 8K UHD
        max_w, max_h = 7680, 4320
    else:  # 1:1
        target_w, target_h = 7680, 7680  # 8K square
        max_w, max_h = 7680, 7680

    w, h = img.size
    print(f"Original image size: {w}x{h}, Max target: {target_w}x{target_h}")

    # For high-resolution processing, preserve original image dimensions
    # Only apply size limits for extremely large images that exceed 8K
    if w <= max_w and h <= max_h:
        print("Image within 8K limits, preserving original dimensions")
        return img

    # Only downscale if image exceeds 8K limits
    if w > max_w or h > max_h:
        scale_w = max_w / w if w > max_w else 1.0
        scale_h = max_h / h if h > max_h else 1.0
        scale = min(scale_w, scale_h)
        
        new_size = (int(w * scale), int(h * scale))
        print(f"Downscaling oversized image by factor {scale:.2f} to {new_size}")
        
        # Use high-quality resampling for downscaling
        return img.resize(new_size, Image.LANCZOS)
    
    # For smaller images, preserve original size rather than upscaling
    # This maintains quality and allows users to get their original resolution
    print("Preserving original image size for high-quality output")
    return img


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


def generate_single_style_highres(cropped_img: Image.Image, style: str, ratio: str, chosen_colour_hex: str, uid: str, opacity: float = 0.5, anvil_scale: float = 0.7, anvil_offset_x: float = 0.0, anvil_offset_y: float = 0.0) -> Dict[str, str]:
    """Generate a single style at high resolution for advanced processing.

    This function processes only the requested style with the high-resolution image data,
    saving high-res base and subject files with appropriate naming for layer packages.

    Args:
        cropped_img: High-resolution PIL Image (RGBA).
        style: Style name to generate ('Flat', 'Stroke', etc.).
        ratio: Aspect ratio ('16:9' or '1:1').
        chosen_colour_hex: Hex color code.
        uid: Unique session identifier.
        opacity: Opacity for color overlays (0.0-1.0).
        anvil_scale: Scale of anvil relative to canvas (0.0-1.0).
        anvil_offset_x: Horizontal offset (-1.0 to 1.0).
        anvil_offset_y: Vertical offset (-1.0 to 1.0).

    Returns:
        Dictionary mapping style name to file path.
    """
    # Create session directory
    session_dir = OUTPUT_DIR / uid
    session_dir.mkdir(exist_ok=True)
    
    # Ensure we have RGBA
    img = cropped_img.convert('RGBA')
    print(f"Starting high-res processing for {img.size} image, style: {style}")
    
    # Upscale if needed (preserves original dimensions for high-res)
    upscaled = upscale_image_if_needed(img, ratio)
    
    # Use original image dimensions for true high-resolution processing
    size = upscaled.size
    img_resized = upscaled if upscaled.size == size else upscaled.resize(size, Image.LANCZOS)
    
    # Save high-res base image to disk
    base_path = session_dir / f'highres_base_{style}.png'
    img_resized.save(base_path, format='PNG')
    print(f"High-res base image saved: {base_path}")
    
    # Convert chosen colour hex to RGB tuple
    hex_colour = chosen_colour_hex.lstrip('#')
    fill_colour = tuple(int(hex_colour[i:i+2], 16) for i in (0, 2, 4))
    
    # Compute anvil coordinates
    coords = compute_anvil_coords(size, anvil_scale, anvil_offset_x, anvil_offset_y)
    
    # Extract subject cutout and save high-res version
    subject_cutout_path = session_dir / f'highres_subject_{style}.png'
    if _has_rembg:
        print("Extracting high-res subject using rembg...")
        arr = remove_background_human(np.array(img_resized.convert('RGB')))
        if arr is not None:
            subject_cutout = Image.fromarray(arr).convert('RGBA')
            subject_cutout.save(subject_cutout_path, format='PNG')
            print("High-res subject extraction successful")
        else:
            print("High-res subject extraction failed, using fallback")
            img_resized.convert('RGBA').save(subject_cutout_path, format='PNG')
    else:
        # Fallback: use base image as subject
        img_resized.save(subject_cutout_path, format='PNG')
    
    print(f"High-res subject cutout saved: {subject_cutout_path}")
    
    # Create standalone anvil shape layer for layer packages
    anvil_shape_path = session_dir / f'highres_anvil_{style}.png'
    anvil_shape_img = Image.new('RGBA', size, (0, 0, 0, 0))
    
    if style == 'Flat':
        draw_anvil = ImageDraw.Draw(anvil_shape_img)
        flat_alpha = int(max(0.0, min(1.0, opacity)) * 255)
        draw_anvil.polygon(list(coords), fill=fill_colour + (flat_alpha,))
    elif style == 'Stroke':
        stroke_layer = draw_stroke_outline(size, fill_colour, coords=coords)
        anvil_shape_img.alpha_composite(stroke_layer)
    elif style == 'Gradient':
        grad_stops = get_gradient_stops(chosen_colour_hex)
        gradient_overlay = gradient_fill_anvil(size, grad_stops, coords=coords)
        anvil_shape_img.alpha_composite(gradient_overlay)
    elif style == 'Window':
        # For window style, create a mask that shows the anvil area
        mask = create_anvil_mask(size, invert=True, coords=coords)
        bg = Image.new('RGBA', size, fill_colour + (255,))
        anvil_shape_img = Image.composite(bg, Image.new('RGBA', size, (0, 0, 0, 0)), mask)
    elif style == 'Silhouette':
        draw_anvil = ImageDraw.Draw(anvil_shape_img)
        alpha_val = int(max(0.0, min(1.0, opacity)) * 255)
        draw_anvil.polygon(list(coords), fill=fill_colour + (alpha_val,))
    elif style == 'Gradient Silhouette':
        grad_stops = get_gradient_stops(chosen_colour_hex)
        grad_sil_overlay = gradient_fill_anvil(size, grad_stops, coords=coords)
        anvil_shape_img.alpha_composite(grad_sil_overlay)
    
    anvil_shape_img.save(anvil_shape_path, format='PNG')
    print(f"High-res anvil shape saved: {anvil_shape_path}")
    
    # Generate the requested style
    print(f"Generating high-res {style} style...")
    
    if style == 'Flat':
        base_img = Image.open(base_path).convert('RGBA')
        flat_overlay = Image.new('RGBA', size, (0, 0, 0, 0))
        draw_flat = ImageDraw.Draw(flat_overlay)
        flat_alpha = int(max(0.0, min(1.0, opacity)) * 255)
        draw_flat.polygon(list(coords), fill=fill_colour + (flat_alpha,))
        base_img.alpha_composite(flat_overlay)
        style_path = session_dir / f'highres_{style}.png'
        base_img.save(style_path, format='PNG')
        del base_img, flat_overlay
        
    elif style == 'Stroke':
        base_img = Image.open(base_path).convert('RGBA')
        subject_img = Image.open(subject_cutout_path).convert('RGBA')
        stroke_layer = draw_stroke_outline(size, fill_colour, coords=coords)
        base_img.alpha_composite(stroke_layer)
        base_img.alpha_composite(subject_img)
        style_path = session_dir / f'highres_{style}.png'
        base_img.save(style_path, format='PNG')
        del base_img, subject_img, stroke_layer
        
    elif style == 'Gradient':
        base_img = Image.open(base_path).convert('RGBA')
        grad_stops = get_gradient_stops(chosen_colour_hex)
        gradient_overlay = gradient_fill_anvil(size, grad_stops, coords=coords)
        base_img.alpha_composite(gradient_overlay)
        style_path = session_dir / f'highres_{style}.png'
        base_img.save(style_path, format='PNG')
        del base_img, gradient_overlay
        
    elif style == 'Window':
        base_img = Image.open(base_path).convert('RGBA')
        window_img = apply_window_style(base_img, size, fill_colour, coords=coords)
        style_path = session_dir / f'highres_{style}.png'
        window_img.save(style_path, format='PNG')
        del base_img, window_img
        
    elif style == 'Silhouette':
        base_img = Image.open(base_path).convert('RGBA')
        subject_img = Image.open(subject_cutout_path).convert('RGBA')
        overlay = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        alpha_val = int(max(0.0, min(1.0, opacity)) * 255)
        draw.polygon(list(coords), fill=fill_colour + (alpha_val,))
        base_img.alpha_composite(overlay)
        base_img.alpha_composite(subject_img)
        style_path = session_dir / f'highres_{style}.png'
        base_img.save(style_path, format='PNG')
        del base_img, subject_img, overlay
        
    elif style == 'Gradient Silhouette':
        base_img = Image.open(base_path).convert('RGBA')
        subject_img = Image.open(subject_cutout_path).convert('RGBA')
        grad_stops = get_gradient_stops(chosen_colour_hex)
        grad_sil_overlay = gradient_fill_anvil(size, grad_stops, coords=coords)
        base_img.alpha_composite(grad_sil_overlay)
        base_img.alpha_composite(subject_img)
        style_path = session_dir / f'highres_{style}.png'
        base_img.save(style_path, format='PNG')
        del base_img, subject_img, grad_sil_overlay
        
    else:
        raise ValueError(f"Unknown style: {style}")
    
    gc.collect()
    print(f"High-res {style} style generation completed: {style_path}")
    
    return {style: str(style_path)}


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
    
    # Use original image dimensions for true high-resolution processing
    orig_w, orig_h = upscaled.size
    size = (orig_w, orig_h)
    img_resized = upscaled if upscaled.size == size else upscaled.resize(size, Image.LANCZOS)
    
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


@app.route('/get_stats')
def get_stats() -> Any:
    """Get usage statistics including total images processed."""
    count = get_image_count()
    return jsonify({'images_processed': count})


@app.route('/')
def index() -> Any:
    """Serve the main page."""
    # Pass the default color explicitly if needed by the template
    default_color = COLOR_PALETTE.get('Blue 2', '#0070F2') # Fallback to original default if new palette key missing
    return render_template('index.html', colours=COLOR_PALETTE, default_color=default_color)


@app.route('/process', methods=['POST'])
def process() -> Any:
    """Queue-protected: Handle image and generate previews."""

    data = request.get_json(force=True)
    job_id = add_job_to_queue("preview", data)
    pos = get_job_position(job_id)
    if pos > 1:
        return jsonify({"status": "queued", "position": pos, "job_id": job_id}), 202

    set_active_job(job_id)

    try:
        uid = uuid.uuid4().hex
        # Use a per-session lock for concurrency protection
        if uid not in session_locks:
            session_locks[uid] = threading.Lock()
        lock = session_locks[uid]
        with lock:
            # Decode preview (moderate resolution) image sent by frontend cropper
            preview_data_url = data.get('imageData')
            if not preview_data_url:
                raise ValueError("Missing preview image data")
            cropped_img = decode_image(preview_data_url)

            # Frontend sends all crop/anvil params
            ratio = data.get('ratio', '16:9')
            colour = data.get('colour', '#0070F2')
            opacity = float(data.get('opacity', 0.5))
            anvilScale = float(data.get('anvilScale', 0.7))
            anvilOffsetX = float(data.get('anvilOffsetX', 0.0))
            anvilOffsetY = float(data.get('anvilOffsetY', 0.0))
            filename = data.get('filename') or "image"

            # Generate previews for all styles, save to disk, return as base64 for speed
            style_paths = generate_styles_sequential(
                cropped_img=cropped_img,
                ratio=ratio,
                chosen_colour_hex=colour,
                uid=uid,
                opacity=opacity,
                anvil_scale=anvilScale,
                anvil_offset_x=anvilOffsetX,
                anvil_offset_y=anvilOffsetY
            )

            # Convert previews to base64 strings for grid presentation
            previews = {}
            for style, path in style_paths.items():
                with open(path, "rb") as imgf:
                    previews[style] = base64.b64encode(imgf.read()).decode('utf-8')

            # Save log image for statistics/troubleshooting
            save_log_image(cropped_img, uid)

        remove_job(job_id)
        return jsonify({'status': 'done', 'uid': uid, 'previews': previews})
    except Exception as e:
        remove_job(job_id)
        return jsonify({'status': 'error', 'error': str(e), 'job_id': job_id}), 500


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


@app.route('/process_highres/<uid>/<style>/<format>', methods=['POST'])
def process_high_resolution(uid: str, style: str, format: str) -> Any:
    """Queue-protected: High-res image processing with optional high-resolution image data."""

    params = {"uid": uid, "style": style, "format": format}
    job_id = add_job_to_queue("highres", params)
    pos = get_job_position(job_id)
    if pos > 1:
        return jsonify({"status": "queued", "position": pos, "job_id": job_id}), 202

    set_active_job(job_id)

    try:
        # Use per-session lock to guard concurrent high-res processing
        if uid not in session_locks:
            session_locks[uid] = threading.Lock()
        lock = session_locks[uid]
        with lock:
            session_dir = OUTPUT_DIR / uid
            if not session_dir.exists():
                raise FileNotFoundError("Session not found")

            # Parse request data to check for high-resolution image data
            request_data = request.get_json() or {}
            high_res_data = request_data.get('highResImageData')
            
            if high_res_data and high_res_data.startswith('data:image'):
                print("High-resolution image data provided, processing from original image...")
                
                # Decode high-resolution image
                cropped_img = decode_image(high_res_data)
                
                # Get processing parameters from request
                ratio = request_data.get('ratio', '16:9')
                colour = request_data.get('colour', '#0070F2')
                opacity = float(request_data.get('opacity', 0.5))
                anvil_scale = float(request_data.get('anvilScale', 0.7))
                anvil_offset_x = float(request_data.get('anvilOffsetX', 0.0))
                anvil_offset_y = float(request_data.get('anvilOffsetY', 0.0))
                filename = request_data.get('filename', 'image')

                print(f"High-res processing: {cropped_img.size}, style: {style}")

                # Generate only the requested style at high resolution
                style_paths = generate_single_style_highres(
                    cropped_img=cropped_img,
                    style=style,
                    ratio=ratio,
                    chosen_colour_hex=colour,
                    uid=uid,
                    opacity=opacity,
                    anvil_scale=anvil_scale,
                    anvil_offset_x=anvil_offset_x,
                    anvil_offset_y=anvil_offset_y
                )
                
                style_img_path = Path(style_paths[style])
            else:
                print("No high-resolution data provided, using stored low-res image...")
                # Fallback to existing low-res processing
                style_img_path = session_dir / f"{style}.png"
                if not style_img_path.exists():
                    raise FileNotFoundError(f"Style image not found for {style}")

            if format == "png":
                # Send high-resolution image directly
                with open(style_img_path, "rb") as f:
                    data = f.read()
                remove_job(job_id)
                return send_file(
                    io.BytesIO(data),
                    mimetype='image/png',
                    as_attachment=True,
                    download_name=f"{uid}_{style}_8K.png"
                )
            elif format == "layers":
                # For layer package, assemble ZIP with base, subject, anvil, composite
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    if high_res_data:
                        # Use high-res generated files
                        base_path = session_dir / f"highres_base_{style}.png"
                        subject_path = session_dir / f"highres_subject_{style}.png"
                        anvil_path = session_dir / f"highres_anvil_{style}.png"
                    else:
                        # Use existing low-res files
                        base_path = session_dir / "base_temp.png"
                        subject_path = session_dir / "subject_temp.png"
                        anvil_path = None  # Not available for low-res
                    
                    composite_path = style_img_path

                    missing_files = []
                    if not base_path.exists():
                        missing_files.append("01_background.png")
                    if not subject_path.exists():
                        missing_files.append("02_subject_cutout.png")
                    if not composite_path.exists():
                        missing_files.append("final_composite.png")

                    if missing_files:
                        remove_job(job_id)
                        error_msg = (
                            f"Missing required files for high-res layer download: {', '.join(missing_files)}.\n"
                            "This session may have expired or preview processing did not complete correctly.\n"
                            "Please re-run the preview generation step and try again."
                        )
                        return jsonify({'status': 'error', 'error': error_msg, 'job_id': job_id}), 500

                    # Write existing files to zip
                    zf.write(base_path, "01_background.png")
                    zf.write(subject_path, "02_subject_cutout.png")
                    
                    # Add anvil shape layer if available (high-res only)
                    if anvil_path and anvil_path.exists():
                        zf.write(anvil_path, "03_anvil_shape.png")
                    
                    zf.write(composite_path, "final_composite.png")

                    # Save README-in-ZIP
                    anvil_layer_info = "03_anvil_shape.png - Standalone anvil shape layer\n" if (anvil_path and anvil_path.exists()) else ""
                    readme_content = (
                        "Layer package contents:\n"
                        "01_background.png - Original cropped image\n"
                        "02_subject_cutout.png - Extracted subject (if available)\n"
                        f"{anvil_layer_info}"
                        "final_composite.png - Final composite result\n"
                        "README.txt - This file\n\n"
                        "Processing details:\n"
                        f"- Style: {style}\n"
                        f"- Resolution: {'High-res (up to 8K)' if high_res_data else 'Preview resolution'}\n"
                        f"- Generated by Lloyd's Anvilizer\n"
                    )
                    zf.writestr("README.txt", readme_content.encode('utf-8'))
                zip_buffer.seek(0)
                remove_job(job_id)
                return send_file(
                    zip_buffer,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name=f"{uid}_{style}_layers.zip"
                )
            else:
                remove_job(job_id)
                return jsonify({'status': 'error', 'error': 'Unknown format', 'job_id': job_id}), 400

        # lock is released here
    except Exception as e:
        remove_job(job_id)
        return jsonify({'status': 'error', 'error': str(e), 'job_id': job_id}), 500


def save_log_image(image: Image.Image, uid: str) -> None:
    """Save a small log version of the original image (800px max on longest side).
    
    Args:
        image: PIL Image to save as log
        uid: Unique session identifier for filename
    """
    try:
        # Calculate scaling to fit 800px on longest side
        w, h = image.size
        max_size = 800
        
        if max(w, h) <= max_size:
            # Image is already small enough
            log_img = image.copy()
        else:
            # Scale down maintaining aspect ratio
            if w > h:
                new_w = max_size
                new_h = int(h * (max_size / w))
            else:
                new_h = max_size
                new_w = int(w * (max_size / h))
            
            log_img = image.resize((new_w, new_h), Image.LANCZOS)
        
        # Generate filename with timestamp and UID
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{uid}.jpg"
        log_path = LOGS_DIR / filename
        
        # Save as JPEG for smaller file size
        log_img.convert('RGB').save(log_path, format='JPEG', quality=85)
        print(f"Saved log image: {filename} ({log_img.size})")
        
    except Exception as e:
        print(f"Warning: Could not save log image: {e}")


def cleanup_old_sessions(max_age_hours: int = 24) -> None:
    """Clean up session directories older than specified hours.
    
    Args:
        max_age_hours: Maximum age in hours before a session is considered old
    """
    try:
        import time
        import shutil
        
        if not OUTPUT_DIR.exists():
            return
            
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600  # Convert hours to seconds
        cleaned_count = 0
        
        for session_dir in OUTPUT_DIR.iterdir():
            if session_dir.is_dir():
                try:
                    # Get the modification time of the session directory
                    dir_mtime = session_dir.stat().st_mtime
                    age_seconds = current_time - dir_mtime
                    
                    if age_seconds > max_age_seconds:
                        shutil.rmtree(session_dir, ignore_errors=True)
                        cleaned_count += 1
                        print(f"Cleaned up old session: {session_dir.name} (age: {age_seconds/3600:.1f}h)")
                except Exception as e:
                    print(f"Error cleaning session {session_dir.name}: {e}")
                    
        if cleaned_count > 0:
            print(f"Cleaned up {cleaned_count} old session(s)")
        else:
            print("No old sessions to clean up")
            
    except Exception as e:
        print(f"Error during session cleanup: {e}")


def cleanup_generated_files() -> None:
    """Legacy function - now calls cleanup_old_sessions for backwards compatibility."""
    cleanup_old_sessions(24)


def get_image_count() -> int:
    """Get the total number of processed images by counting log files."""
    try:
        if not LOGS_DIR.exists():
            return 0
        
        # Count only .jpg files in logs directory
        log_files = [f for f in LOGS_DIR.iterdir() if f.suffix.lower() == '.jpg']
        return len(log_files)
    except Exception as e:
        print(f"Error counting log files: {e}")
        return 0


# --- Admin routes and helpers ---
import socket
from datetime import datetime

def list_log_thumbnails(page=1, per_page=100):
    """Return paginated thumbnails from LOGS_DIR (sorted newest first)."""
    try:
        files = sorted(
            [f for f in LOGS_DIR.glob("*.jpg")],
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        total_count = len(files)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_files = files[start_idx:end_idx]
        
        thumbnails = []
        for f in page_files:
            dt = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            thumbnails.append({
                "filename": f.name,
                "timestamp": dt,
                "url": url_for('admin_log_image', filename=f.name)
            })
        
        return {
            "thumbnails": thumbnails,
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page,
            "has_next": end_idx < total_count,
            "has_prev": page > 1
        }
    except Exception as e:
        print(f"Error listing thumbnails: {e}")
        return {
            "thumbnails": [],
            "total_count": 0,
            "page": 1,
            "per_page": per_page,
            "total_pages": 0,
            "has_next": False,
            "has_prev": False
        }

def list_sessions():
    """Return details for all session dirs in OUTPUT_DIR, sorted newest first."""
    sessions = []
    for session_dir in sorted(OUTPUT_DIR.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True):
        if not session_dir.is_dir():
            continue
        uid = session_dir.name
        try:
            created = datetime.fromtimestamp(session_dir.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            created = "?"
        
        images = []
        status = []
        expected_styles = ['Flat', 'Stroke', 'Gradient', 'Window', 'Silhouette', 'Gradient Silhouette']
        
        for style in expected_styles:
            style_file = session_dir / f"{style}.png"
            if style_file.exists():
                images.append({
                    "style": style,
                    "url": url_for('download', uid=uid, style_name=style),
                    "thumb": url_for('admin_session_thumb', uid=uid, style=style)
                })
            else:
                status.append(f"missing {style}")
        
        base_temp = session_dir / "base_temp.png"
        if not base_temp.exists():
            status.append("missing base")
        
        if not images:
            status.append("no images")
        
        sessions.append({
            "uid": uid,
            "created": created,
            "images": images,
            "status": ", ".join(status) if status else "ok"
        })
    return sessions

@app.route("/admin")
def admin_page():
    """Admin HTML with server/pod name injected."""
    pod_name = socket.gethostname()
    return render_template("admin.html", pod_name=pod_name)

@app.route("/admin/api/logs")
def admin_logs_api():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 100))
    return jsonify(list_log_thumbnails(page=page, per_page=per_page))

@app.route("/admin/api/sessions")
def admin_sessions_api():
    return jsonify({"sessions": list_sessions()})

@app.route("/admin/api/queue")
def admin_queue_api():
    # Exposes the current memory queue, active job id, processed images, pod_name
    with queue_lock:
        queue_list = [
            {
                "job_id": job.job_id,
                "route": job.route,
                "params": job.params,
                "status": job.status
            }
            for job in processing_queue
        ]
        active = active_job_id
    
    return jsonify({
        "queue": queue_list,
        "active_job_id": active,
        "images_processed": get_image_count(),
        "pod_name": socket.gethostname()
    })

@app.route("/admin/api/session/<uid>/delete", methods=["POST"])
def admin_delete_session(uid):
    """Delete the whole session directory."""
    from shutil import rmtree
    session_dir = OUTPUT_DIR / uid
    if not session_dir.exists() or not session_dir.is_dir():
        return jsonify({"success": False, "error": "Session not found."})
    
    try:
        rmtree(session_dir)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/admin/logs/<filename>")
def admin_log_image(filename):
    """Serve jpg log file from LOGS_DIR."""
    file_path = LOGS_DIR / filename
    if not file_path.exists():
        return "Not found", 404
    return send_file(str(file_path), mimetype="image/jpeg")

@app.route("/admin/sessions/<uid>/<style>")
def admin_session_thumb(uid, style):
    """Serve a downsampled PNG for session preview style."""
    session_dir = OUTPUT_DIR / uid
    style_file = session_dir / f"{style}.png"
    if not style_file.exists():
        return "Not found", 404
    
    try:
        img = Image.open(style_file).convert("RGBA")
        img.thumbnail((60, 45))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception:
        return "Error", 500


if __name__ == '__main__':
    # Clean up old sessions on startup (24-hour retention)
    cleanup_old_sessions(24)

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
