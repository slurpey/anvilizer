"""
Security fixes for the Anvilizer Flask application.

This module contains security enhancements to address critical vulnerabilities:
1. File upload validation
2. Rate limiting
3. Input sanitization
4. Memory management
5. Content Security Policy improvements
6. Basic authentication for admin routes

Usage:
- Import and apply these fixes to app.py
- Ensure flask-limiter is installed: pip install flask-limiter
"""

import base64
import io
import re
from functools import wraps
from typing import Optional, Tuple
from PIL import Image
from flask import request, jsonify, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Configuration constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_BASE64_SIZE = int(MAX_FILE_SIZE * 4/3)  # Account for base64 overhead
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 
    'image/gif', 'image/webp'
}
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Maximum image dimensions for memory safety
MAX_IMAGE_PIXELS = 50_000_000  # ~7K x 7K pixels max
MAX_DIMENSION = 8192  # Max width or height

# Rate limiting configuration
UPLOAD_RATE_LIMIT = "10 per minute"
DOWNLOAD_RATE_LIMIT = "100 per minute"
ADMIN_RATE_LIMIT = "30 per minute"

def create_limiter(app):
    """Create and configure rate limiter."""
    return Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["1000 per hour"]
    )

def validate_image_data(data_url: str) -> Image.Image:
    """
    Validate and decode image data with comprehensive security checks.
    
    Args:
        data_url: Base64 encoded image data URL
        
    Returns:
        PIL Image object
        
    Raises:
        ValueError: If validation fails
    """
    if not data_url:
        raise ValueError("Missing image data")
    
    if not isinstance(data_url, str):
        raise ValueError("Image data must be a string")
    
    # Check data URL format
    if not data_url.startswith('data:image/'):
        raise ValueError("Invalid image data format - must be data URL")
    
    try:
        header, encoded = data_url.split(',', 1)
    except ValueError:
        raise ValueError("Invalid data URL structure")
    
    # Extract and validate MIME type
    mime_match = re.match(r'data:(image/[^;]+)', header)
    if not mime_match:
        raise ValueError("Invalid image MIME type in header")
    
    mime_type = mime_match.group(1).lower()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported image type: {mime_type}. Allowed: {', '.join(ALLOWED_MIME_TYPES)}")
    
    # Check encoded data size (prevents memory exhaustion)
    if len(encoded) > MAX_BASE64_SIZE:
        raise ValueError(f"Image data too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    # Validate base64 encoding
    try:
        img_data = base64.b64decode(encoded, validate=True)
    except Exception:
        raise ValueError("Invalid base64 encoding")
    
    # Check decoded size
    if len(img_data) > MAX_FILE_SIZE:
        raise ValueError(f"Decoded image too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    # Load and validate image
    try:
        img = Image.open(io.BytesIO(img_data))
        img.load()  # Force loading to validate image data
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image data: {str(e)}")
    
    # Check image dimensions
    width, height = img.size
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions")
    
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValueError(f"Image dimensions too large. Maximum: {MAX_DIMENSION}x{MAX_DIMENSION}")
    
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"Image too large. Maximum pixels: {MAX_IMAGE_PIXELS}")
    
    # Convert to RGBA for consistent processing
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA')
    
    return img

def validate_numeric_parameter(value, param_name: str, min_val: float, max_val: float, default: float) -> float:
    """
    Validate and sanitize numeric parameters.
    
    Args:
        value: Raw parameter value
        param_name: Parameter name for error messages
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        default: Default value if invalid
        
    Returns:
        Validated float value
    """
    if value is None:
        return default
    
    try:
        num_val = float(value)
        if not (min_val <= num_val <= max_val):
            raise ValueError(f"{param_name} must be between {min_val} and {max_val}")
        return num_val
    except (ValueError, TypeError):
        return default

def validate_uid(uid: str) -> bool:
    """
    Validate UID format to prevent path traversal attacks.
    
    Args:
        uid: User session identifier
        
    Returns:
        True if valid, False otherwise
    """
    if not uid or not isinstance(uid, str):
        return False
    
    # Check length (UUIDs are typically 32 hex chars)
    if len(uid) != 32:
        return False
    
    # Check for hex characters only
    if not re.match(r'^[a-f0-9]{32}$', uid):
        return False
    
    # Prevent path traversal
    if '..' in uid or '/' in uid or '\\' in uid:
        return False
    
    return True

def validate_style_name(style: str) -> bool:
    """
    Validate style name parameter.
    
    Args:
        style: Style name
        
    Returns:
        True if valid, False otherwise
    """
    allowed_styles = {
        'Flat', 'Stroke', 'Gradient', 'Window', 
        'Silhouette', 'Gradient Silhouette'
    }
    return style in allowed_styles

def validate_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not filename or not isinstance(filename, str):
        return "image"
    
    # Remove path components
    filename = filename.split('/')[-1].split('\\')[-1]
    
    # Remove dangerous characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Limit length
    if len(filename) > 100:
        filename = filename[:100]
    
    # Ensure we have something
    if not filename or filename.startswith('.'):
        filename = "image"
    
    return filename

def validate_color_hex(color: str) -> str:
    """
    Validate and sanitize hex color code.
    
    Args:
        color: Hex color string
        
    Returns:
        Validated hex color
    """
    if not color or not isinstance(color, str):
        return "#0070F2"  # Default blue
    
    # Remove whitespace
    color = color.strip()
    
    # Add # if missing
    if not color.startswith('#'):
        color = '#' + color
    
    # Validate hex format
    if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
        return "#0070F2"  # Default blue
    
    return color.upper()

def create_secure_csp_header():
    """
    Create a secure Content Security Policy header.
    
    Returns:
        CSP header string
    """
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "media-src 'none'; "
        "object-src 'none'; "
        "child-src 'none'; "
        "worker-src 'none'; "
        "frame-src 'none'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "manifest-src 'self';"
    )

def require_admin_auth(f):
    """
    Decorator for admin routes requiring basic authentication.
    
    Note: This is basic protection. For production, use proper OAuth/SAML.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For now, just check for a simple header
        # In production, implement proper authentication
        auth_header = request.headers.get('X-Admin-Auth')
        if not auth_header or auth_header != 'admin-access-2025':
            abort(401)
        return f(*args, **kwargs)
    return decorated_function

def log_security_event(event_type: str, details: str, ip_address: str = None):
    """
    Log security-related events for monitoring.
    
    Args:
        event_type: Type of security event
        details: Event details
        ip_address: Client IP address
    """
    if not ip_address:
        ip_address = request.remote_addr if request else 'unknown'
    
    import datetime
    timestamp = datetime.datetime.now().isoformat()
    
    print(f"SECURITY_EVENT [{timestamp}] {event_type} from {ip_address}: {details}")
    
    # In production, this should go to a proper security log

# Error handler for validation errors
def handle_validation_error(error_message: str, status_code: int = 400):
    """
    Handle validation errors consistently.
    
    Args:
        error_message: Error message to return
        status_code: HTTP status code
        
    Returns:
        JSON error response
    """
    log_security_event("VALIDATION_ERROR", error_message)
    return jsonify({
        'status': 'error',
        'error': error_message,
        'code': 'VALIDATION_ERROR'
    }), status_code
