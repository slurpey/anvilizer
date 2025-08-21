// Client-side script for SAP Anvil Tool

// Custom cropping implementation variables
let selectedColour = null;
const fileInput = document.getElementById('file-input');
const imageElement = document.getElementById('image');
const generateBtn = document.getElementById('generate-btn');
const cropWrapper = document.getElementById('crop-wrapper');
const cropBox = document.getElementById('crop-box');
const zoomSlider = document.getElementById('zoom-slider');
const zoomControl = document.querySelector('.zoom-control');
const fitButton = document.getElementById('fit-button');

// Anvil customisation sliders
const anvilSizeSlider = document.getElementById('anvil-size-slider');
const anvilOffsetXSlider = document.getElementById('anvil-offset-x-slider');
const anvilOffsetYSlider = document.getElementById('anvil-offset-y-slider');
const anvilOverlay = document.getElementById('anvil-overlay');
const anvilSizeControl = document.querySelector('.anvil-size-control');
const anvilOffsetControl = document.querySelector('.anvil-offset-control');

// Mask overlays for darkening outside the crop area
const maskTop = document.getElementById('mask-top');
const maskLeft = document.getElementById('mask-left');
const maskRight = document.getElementById('mask-right');
const maskBottom = document.getElementById('mask-bottom');

// Values for anvil customisation
let anvilScale = 0.7; // 0.5 to 1.0
let anvilOffsetX = 0.0; // -1 to 1
let anvilOffsetY = 0.0; // -1 to 1

// Pure vanilla JavaScript implementation - no external libraries
// All cropping functionality is handled by custom crop box

// Opacity slider for silhouette style
const opacitySlider = document.getElementById('opacity-slider');

// Loading overlay element for showing processing animation
const loadingOverlay = document.getElementById('loading-overlay');


let currentRatio = 16 / 9;

// Store the maximum crop box dimensions.  When zooming we will scale
// these values down.  They are computed in setupCropBox().
let maxCropWidth = 0;
let maxCropHeight = 0;

// Store the original file name for server naming
let uploadFilename = 'image';
let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let cropStartLeft = 0;
let cropStartTop = 0;

// Helper to enable/disable generate button
function updateGenerateButton() {
    if (imageElement.src && selectedColour) {
        generateBtn.classList.add('enabled');
        generateBtn.disabled = false;
        generateBtn.style.pointerEvents = 'auto';
    }
}

// Helper called whenever the crop box changes.  It updates the mask
// overlays and the anvil preview based on the current crop box dimensions.
function updateMaskAndAnvil() {
    updateCropMask();
    updateAnvilPreview();
}

// Custom crop box implementation only - no external libraries needed
// All cropping is handled by the custom crop box element

// File input change handler
fileInput.addEventListener('change', function (e) {
    const file = e.target.files[0];
    if (!file) return;
    uploadFilename = file.name || 'image';
    const reader = new FileReader();
    reader.onload = function (event) {
        imageElement.onload = function () {
            // Show wrapper and controls
            cropWrapper.style.display = 'block';
            zoomControl.style.display = 'flex';
            anvilSizeControl.style.display = 'block';
            anvilOffsetControl.style.display = 'block';
            anvilOverlay.style.display = 'block';
            // Reset zoom
            zoomSlider.value = 1;
            imageElement.style.transform = 'scale(1)';
            // Set image dimensions to fit wrapper width
            imageElement.style.width = '100%';
            imageElement.style.height = 'auto';
            // Compute wrapper height based on natural ratio
            const wrapperWidth = cropWrapper.clientWidth;
            const imgRatio = imageElement.naturalHeight / imageElement.naturalWidth;
            // Compute desired wrapper height to maintain the natural ratio but
            // constrain it to a maximum so that the offset sliders remain
            // visible below the crop area.  Limiting the height prevents the
            // Y slider and tip text from being pushed off screen when
            // portrait images are uploaded.
            let wrapperHeight = wrapperWidth * imgRatio;
            const maxWrapperHeight = 300;
            if (wrapperHeight > maxWrapperHeight) {
                wrapperHeight = maxWrapperHeight;
            }
            cropWrapper.style.height = wrapperHeight + 'px';
            // Set up the custom crop box implementation.  We do not
            // initialise Cropper.js here so that the existing zoom
            // slider and anvil positioning controls continue to work.
            setupCropBox();
            // Reset the anvil preview and dark overlays
            updateCropMask();
            updateAnvilPreview();
            updateGenerateButton();
        };
        imageElement.src = event.target.result;
        imageElement.style.display = 'block';
    };
    reader.readAsDataURL(file);
});

function setupCropBox() {
    // Determine aspect ratio from selected radio
    const ratioVal = document.querySelector('input[name="ratio"]:checked').value;
    if (ratioVal === '1:1') {
        currentRatio = 1;
    } else if (ratioVal === '9:16') {
        currentRatio = 9 / 16;
    } else {
        currentRatio = 16 / 9;
    }
    const wrapperWidth = cropWrapper.clientWidth;
    const wrapperHeight = cropWrapper.clientHeight;
    // Compute crop box maximum size so that it fills the wrapper as much
    // as possible while maintaining the aspect ratio.  If the selected
    // ratio matches the image ratio, this results in a full‑frame crop.
    let cropW, cropH;
    // Determine which dimension is limiting: if the wrapper width / ratio
    // is less than or equal to the wrapper height, use the full width;
    // otherwise use the full height.
    if ((wrapperWidth / currentRatio) <= wrapperHeight) {
        cropW = wrapperWidth;
        cropH = cropW / currentRatio;
    } else {
        cropH = wrapperHeight;
        cropW = cropH * currentRatio;
    }
    // Store maximum crop dimensions for zoom behaviour
    maxCropWidth = cropW;
    maxCropHeight = cropH;
    // Set initial size to maximum (zoom = 1)
    cropBox.style.width = cropW + 'px';
    cropBox.style.height = cropH + 'px';
    cropBox.style.left = ((wrapperWidth - cropW) / 2) + 'px';
    cropBox.style.top = ((wrapperHeight - cropH) / 2) + 'px';
    cropBox.style.display = 'block';
    // Show mask overlays
    maskTop.style.display = 'block';
    maskLeft.style.display = 'block';
    maskRight.style.display = 'block';
    maskBottom.style.display = 'block';
    // Initialise zoom slider range: 0.3–1 for finer control (min 30% of max size)
    zoomSlider.min = '0.3';
    zoomSlider.max = '1';
    zoomSlider.step = '0.01';
    zoomSlider.value = '1';
    // Update masks based on crop position
    updateCropMask();
    // Update anvil preview since crop box changed
    updateAnvilPreview();
}

// Ratio change listener to update crop box
document.querySelectorAll('input[name="ratio"]').forEach(function (elem) {
    elem.addEventListener('change', function () {
        if (this.value === '1:1') {
            currentRatio = 1;
        } else if (this.value === '9:16') {
            currentRatio = 9 / 16;
        } else {
            currentRatio = 16 / 9;
        }
        // For the custom crop box, rebuild it to match the new ratio
        setupCropBox();
        // Update mask and anvil preview to reflect the ratio change
        updateCropMask();
        updateAnvilPreview();
    });
});

// Colour palette selection
document.querySelectorAll('.colour-swatch').forEach(function (swatch) {
    swatch.addEventListener('click', function () {
        document.querySelectorAll('.colour-swatch').forEach(function (s) {
            s.classList.remove('selected');
        });
        this.classList.add('selected');
        selectedColour = this.dataset.colour;
        updateGenerateButton();
    });
});

// Auto-select "Blue 2" (#0070F2) as default color on page load
document.addEventListener('DOMContentLoaded', function() {
    const blue2Swatch = document.querySelector('.colour-swatch[data-colour="#0070F2"]');
    if (blue2Swatch) {
        blue2Swatch.classList.add('selected');
        selectedColour = '#0070F2';
        updateGenerateButton();
    }
});

// Dragging the crop box
cropBox.addEventListener('mousedown', function (e) {
    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    cropStartLeft = parseFloat(cropBox.style.left);
    cropStartTop = parseFloat(cropBox.style.top);
    e.preventDefault();
});
document.addEventListener('mousemove', function (e) {
    if (!isDragging) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    const wrapperWidth = cropWrapper.clientWidth;
    const wrapperHeight = cropWrapper.clientHeight;
    const cropW = parseFloat(cropBox.style.width);
    const cropH = parseFloat(cropBox.style.height);
    let newLeft = cropStartLeft + dx;
    let newTop = cropStartTop + dy;
    // Clamp within wrapper
    newLeft = Math.max(0, Math.min(newLeft, wrapperWidth - cropW));
    newTop = Math.max(0, Math.min(newTop, wrapperHeight - cropH));
    cropBox.style.left = newLeft + 'px';
    cropBox.style.top = newTop + 'px';
    // Update anvil overlay when dragging
    updateAnvilPreview();
    updateCropMask();
});
document.addEventListener('mouseup', function () {
    isDragging = false;
});

// Zoom slider handler
zoomSlider.addEventListener('input', function () {
    // Adjust the crop box size instead of scaling the image.  The zoom
    // slider controls the fraction of the maximum crop size (1 = max,
    // smaller values zoom in by shrinking the box).  Keep the crop box
    // centred as much as possible when resizing.
    updateCropBoxForZoom();
});

// Fit button handler
if (fitButton) {
    fitButton.addEventListener('click', function () {
        // Set zoom to 1 (fit) which makes the crop box as large as
        // possible within the wrapper.  This effectively shows the
        // entire image within the crop area when the aspect ratio
        // allows.
        zoomSlider.value = '1';
        updateCropBoxForZoom();
    });
}

// Update the crop box dimensions based on the zoom slider value.
// Custom crop box logic: adjust the cropBox element itself.
function updateCropBoxForZoom() {
    if (!cropBox || cropBox.style.display === 'none') return;
    
    const zoomFactor = parseFloat(zoomSlider.value);
    const newW = maxCropWidth * zoomFactor;
    const newH = maxCropHeight * zoomFactor;
    const wrapperW = cropWrapper.clientWidth;
    const wrapperH = cropWrapper.clientHeight;
    
    // Determine current centre of the crop box
    let currentW = parseFloat(cropBox.style.width);
    let currentH = parseFloat(cropBox.style.height);
    let centerX = parseFloat(cropBox.style.left) + currentW / 2;
    let centerY = parseFloat(cropBox.style.top) + currentH / 2;
    
    // Compute new top-left so that centre remains at same coordinates
    let newLeft = centerX - newW / 2;
    let newTop = centerY - newH / 2;
    
    // Clamp within wrapper boundaries
    newLeft = Math.max(0, Math.min(newLeft, wrapperW - newW));
    newTop = Math.max(0, Math.min(newTop, wrapperH - newH));
    
    cropBox.style.width = newW + 'px';
    cropBox.style.height = newH + 'px';
    cropBox.style.left = newLeft + 'px';
    cropBox.style.top = newTop + 'px';
    
    // Update overlays
    updateAnvilPreview();
    updateCropMask();
}

// Update mask overlay positions and sizes based on crop box
function updateCropMask() {
    const wrapperWidth = cropWrapper.clientWidth;
    const wrapperHeight = cropWrapper.clientHeight;
    let cropLeft, cropTop, cropW, cropH;
    
    if (cropBox && cropBox.style.display !== 'none') {
        cropLeft = parseFloat(cropBox.style.left);
        cropTop = parseFloat(cropBox.style.top);
        cropW = parseFloat(cropBox.style.width);
        cropH = parseFloat(cropBox.style.height);
    }
    
    if (cropLeft == null || isNaN(cropLeft) || cropTop == null || isNaN(cropTop) || cropW == null || isNaN(cropW) || cropH == null || isNaN(cropH)) {
        return;
    }
    
    // Top overlay
    maskTop.style.top = '0px';
    maskTop.style.left = '0px';
    maskTop.style.width = wrapperWidth + 'px';
    maskTop.style.height = cropTop + 'px';
    // Bottom overlay
    maskBottom.style.top = (cropTop + cropH) + 'px';
    maskBottom.style.left = '0px';
    maskBottom.style.width = wrapperWidth + 'px';
    maskBottom.style.height = (wrapperHeight - (cropTop + cropH)) + 'px';
    // Left overlay
    maskLeft.style.top = cropTop + 'px';
    maskLeft.style.left = '0px';
    maskLeft.style.width = cropLeft + 'px';
    maskLeft.style.height = cropH + 'px';
    // Right overlay
    maskRight.style.top = cropTop + 'px';
    maskRight.style.left = (cropLeft + cropW) + 'px';
    maskRight.style.width = (wrapperWidth - (cropLeft + cropW)) + 'px';
    maskRight.style.height = cropH + 'px';
}

// Update zoom slider min based on natural image size to allow full view
function updateZoomLimits() {
    if (!imageElement || !imageElement.naturalWidth) return;
    const wrapperW = cropWrapper.clientWidth;
    const wrapperH = cropWrapper.clientHeight;
    const minScaleW = wrapperW / imageElement.naturalWidth;
    const minScaleH = wrapperH / imageElement.naturalHeight;
    const minScale = Math.min(minScaleW, minScaleH, 1);
    zoomSlider.min = minScale.toFixed(3);
    if (parseFloat(zoomSlider.value) < minScale) {
        zoomSlider.value = minScale;
        imageElement.style.transform = 'scale(' + minScale + ')';
    }
}

// Reposition the image to stay centred within the crop wrapper when zooming
function updateImagePosition() {
    // When zooming, keep the image anchored at the top‑left corner.  If the
    // transform origin is set to top left (see CSS), no repositioning is
    // necessary.  This prevents misalignment and ensures the cropping
    // calculations (which assume the image starts at (0,0)) remain
    // accurate.
    if (!imageElement) return;
    imageElement.style.left = '0px';
    imageElement.style.top = '0px';
}

// Update anvil overlay preview based on current crop box, scale and offsets
function updateAnvilPreview() {
    let cropW, cropH, cropLeft, cropTop;
    
    if (cropBox && cropBox.style.display !== 'none') {
        cropW = parseFloat(cropBox.style.width);
        cropH = parseFloat(cropBox.style.height);
        cropLeft = parseFloat(cropBox.style.left);
        cropTop = parseFloat(cropBox.style.top);
    }
    
    if (cropW == null || isNaN(cropW) || cropH == null || isNaN(cropH)) return;
    
    // Compute anvil dimensions relative to crop box
    // Desired width and height from current anvilScale (0.5–1)
    let aw = cropW * anvilScale;
    let ah = aw / 2;
    // Ensure the anvil fits vertically; if not, scale down
    if (ah > cropH) {
        ah = cropH;
        aw = ah * 2;
    }
    // Compute base offsets to centre
    const maxDx = (cropW - aw) / 2;
    const maxDy = (cropH - ah) / 2;
    let left = cropLeft + maxDx + anvilOffsetX * maxDx;
    let top = cropTop + maxDy + anvilOffsetY * maxDy;
    // Update overlay element
    anvilOverlay.style.width = aw + 'px';
    anvilOverlay.style.height = ah + 'px';
    anvilOverlay.style.left = left + 'px';
    anvilOverlay.style.top = top + 'px';
}

// Anvil size slider handler
if (anvilSizeSlider) {
    anvilSizeSlider.addEventListener('input', function () {
        const val = parseFloat(this.value); // 50–100
        anvilScale = val / 100.0;
        updateAnvilPreview();
    });
}

// Anvil offset X slider handler
if (anvilOffsetXSlider) {
    anvilOffsetXSlider.addEventListener('input', function () {
        const val = parseFloat(this.value); // -100–100
        anvilOffsetX = val / 100.0;
        updateAnvilPreview();
    });
}

// Anvil offset Y slider handler
if (anvilOffsetYSlider) {
    anvilOffsetYSlider.addEventListener('input', function () {
        const val = parseFloat(this.value);
        anvilOffsetY = val / 100.0;
        updateAnvilPreview();
    });
}

// Reset button functionality
function resetAllSliders() {
    // Reset all sliders to their default values
    if (zoomSlider) {
        zoomSlider.value = '1';
        updateCropBoxForZoom();
    }
    if (anvilSizeSlider) {
        anvilSizeSlider.value = '70';
        anvilScale = 0.7;
        updateAnvilPreview();
    }
    if (anvilOffsetXSlider) {
        anvilOffsetXSlider.value = '0';
        anvilOffsetX = 0.0;
        updateAnvilPreview();
    }
    if (anvilOffsetYSlider) {
        anvilOffsetYSlider.value = '0';
        anvilOffsetY = 0.0;
        updateAnvilPreview();
    }
    if (opacitySlider) {
        opacitySlider.value = '50';
    }
    
    // Reset aspect ratio to 16:9
    const ratio16x9 = document.querySelector('input[name="ratio"][value="16:9"]');
    if (ratio16x9) {
        ratio16x9.checked = true;
        // Use the same logic as other functions
        if (ratio16x9.value === '1:1') {
            currentRatio = 1;
        } else if (ratio16x9.value === '9:16') {
            currentRatio = 9 / 16;
        } else {
            currentRatio = 16 / 9;
        }
        if (imageElement.src) {
            setupCropBox();
        }
    }
    
    // Clear color selection
    document.querySelectorAll('.colour-swatch').forEach(function (s) {
        s.classList.remove('selected');
    });
    selectedColour = null;
    updateGenerateButton();
}

// Reset button click handler
const resetBtn = document.getElementById('reset-btn');
if (resetBtn) {
    resetBtn.addEventListener('click', resetAllSliders);
}

// Generate button click
generateBtn.addEventListener('click', function () {
    if (!imageElement.src || !selectedColour) return;
    
    // Custom crop box implementation - compute the crop based on the crop box
    const ratioValue = document.querySelector('input[name="ratio"]:checked').value;
    
    // TWO-TIER APPROACH: Preview processing vs High-res processing
    // For PREVIEW generation: Use moderate resolution for speed
    // For HIGH-RES processing: Use original crop dimensions (stored separately)
    let previewTargetW, previewTargetH;
    if (ratioValue === '1:1') {
        previewTargetW = 1920;
        previewTargetH = 1920;
    } else if (ratioValue === '9:16') {
        previewTargetW = 1080;  // Phone portrait: narrower width
        previewTargetH = 1920;  // Phone portrait: taller height
    } else {
        previewTargetW = 1920;  // Landscape: wider width
        previewTargetH = 1080;  // Landscape: shorter height
    }
    
    // Determine the bounding rectangles of the displayed image and the crop box
    const imgRect = imageElement.getBoundingClientRect();
    const cropRect = cropBox.getBoundingClientRect();
    const imgNatW = imageElement.naturalWidth;
    const imgNatH = imageElement.naturalHeight;
    
    // Calculate the selected region in natural image coordinates
    let sx = ((cropRect.left - imgRect.left) / imgRect.width) * imgNatW;
    let sy = ((cropRect.top - imgRect.top) / imgRect.height) * imgNatH;
    let sw = (cropRect.width / imgRect.width) * imgNatW;
    let sh = (cropRect.height / imgRect.height) * imgNatH;
    
    // Clamp to image boundaries
    sx = Math.max(0, Math.min(sx, imgNatW));
    sy = Math.max(0, Math.min(sy, imgNatH));
    sw = Math.max(1, Math.min(sw, imgNatW - sx));
    sh = Math.max(1, Math.min(sh, imgNatH - sy));
    
    console.log(`Original image: ${imgNatW}x${imgNatH}, Crop region: ${sw.toFixed(0)}x${sh.toFixed(0)}`);
    
    // PREVIEW PROCESSING: Create downscaled version for fast preview generation
    const previewCanvas = document.createElement('canvas');
    previewCanvas.width = previewTargetW;
    previewCanvas.height = previewTargetH;
    const previewCtx = previewCanvas.getContext('2d');
    
    // Draw the cropped region scaled to preview resolution
    previewCtx.drawImage(imageElement, sx, sy, sw, sh, 0, 0, previewTargetW, previewTargetH);
    const previewDataUrl = previewCanvas.toDataURL('image/png');
    
    // HIGH-RES PROCESSING: Store original crop data for later high-res processing
    // Calculate optimal high-res output dimensions (preserve aspect ratio)
    const cropAspectRatio = sw / sh;
    let highresW, highresH;
    
    if (ratioValue === '1:1') {
        // For square images, use the smaller dimension to maintain square
        const maxDim = Math.min(sw, sh);
        highresW = maxDim;
        highresH = maxDim;
    } else if (ratioValue === '9:16') {
        // For phone portrait, preserve the crop dimensions
        highresW = sw;
        highresH = sh;
    } else {
        // For 16:9 landscape, preserve the crop dimensions up to reasonable limits
        highresW = sw;
        highresH = sh;
    }
    
    // Create high-resolution canvas with ORIGINAL crop dimensions
    const highresCanvas = document.createElement('canvas');
    highresCanvas.width = highresW;
    highresCanvas.height = highresH;
    const highresCtx = highresCanvas.getContext('2d');
    
    // Draw at FULL RESOLUTION - no downscaling
    highresCtx.drawImage(imageElement, sx, sy, sw, sh, 0, 0, highresW, highresH);
    const highresDataUrl = highresCanvas.toDataURL('image/png');
    
    console.log(`Preview resolution: ${previewTargetW}x${previewTargetH}, High-res: ${highresW}x${highresH}`);
    
    // Store high-res data globally for later use
    window.currentHighResData = {
        dataUrl: highresDataUrl,
        dimensions: { width: highresW, height: highresH },
        originalCrop: { sx, sy, sw, sh },
        naturalDimensions: { width: imgNatW, height: imgNatH }
    };
    // Convert opacity slider (0-100) to 0-1 range
    const opacityValue = opacitySlider ? parseFloat(opacitySlider.value) / 100.0 : 0.5;
    // Prepare anvil parameters for backend
    const scaleParam = anvilScale;
    const offsetXParam = anvilOffsetX;
    const offsetYParam = anvilOffsetY;
    // Show loading overlay while processing
    if (loadingOverlay) {
        loadingOverlay.style.display = 'flex';
        
        // Start rotating status messages for the standard loading screen
        startStatusRotation();
    }
    fetch('/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            imageData: previewDataUrl,  // Use preview resolution for fast processing
            highResData: highresDataUrl, // Store high-res data for later use
            ratio: ratioValue,
            colour: selectedColour,
            opacity: opacityValue,
            anvilScale: scaleParam,
            anvilOffsetX: offsetXParam,
            anvilOffsetY: offsetYParam,
            filename: uploadFilename
        })
    })
        .then(response => response.json())
        .then(data => {
            // Handle image queue information
            if (data.status === 'queued' && data.job_id) {
                pollQueueStatus(data.job_id, 'process');
                return;
            }
            if (data.status === 'error') {
                alert('Error: ' + data.error);
                if (loadingOverlay) loadingOverlay.style.display = 'none';
                return;
            }
            // Completed
            renderPreviews(data.uid, data.previews);
            loadUsageStats();
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
                stopStatusRotation();
            }
        })
        .catch(err => {
            console.error(err);
            alert('An error occurred while processing the image.');
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }
        });

function pollQueueStatus(jobId, routeType) {
    const POLLING_TIMEOUT = 5 * 60 * 1000; // 5 minutes in milliseconds
    const POLLING_INTERVAL = 2000; // 2 seconds
    const startTime = Date.now();
    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 3;
    
    let pollingInterval = setInterval(() => {
        // Check for timeout
        if (Date.now() - startTime > POLLING_TIMEOUT) {
            clearInterval(pollingInterval);
            console.error('Queue polling timeout after 5 minutes');
            
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
                stopStatusRotation();
            }
            
            alert('Processing is taking longer than expected. Please try refreshing the page or try again later.');
            return;
        }
        
        fetch(`/queue_status/${jobId}`)
            .then(resp => {
                if (!resp.ok) {
                    throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
                }
                return resp.json();
            })
            .then(qdata => {
                // Reset error counter on successful response
                consecutiveErrors = 0;
                
                // Update UI with queue info
                if (loadingOverlay) {
                    let textElem = loadingOverlay.querySelector('.processing-status-text');
                    if (textElem) {
                        if (qdata.position && qdata.position > 1) {
                            textElem.textContent = `In queue: You are #${qdata.position} for processing`;
                        } else {
                            textElem.textContent = 'Processing started...';
                        }
                    }
                }
                
                if (qdata.status === "done") {
                    clearInterval(pollingInterval);
                    
                    // Handle completed job result
                    if (qdata.result && routeType === 'process') {
                        // Preview generation completed
                        renderPreviews(qdata.result.uid, qdata.result.previews);
                        loadUsageStats();
                        if (loadingOverlay) {
                            loadingOverlay.style.display = 'none';
                            stopStatusRotation();
                        }
                    } else {
                        // Fallback to page reload if no result data
                        if (loadingOverlay) {
                            loadingOverlay.style.display = 'none';
                            stopStatusRotation();
                        }
                        window.location.reload();
                    }
                }
                else if (qdata.status === "error" || qdata.status === "not_found") {
                    clearInterval(pollingInterval);
                    console.error('Job processing failed:', qdata);
                    
                    if (loadingOverlay) {
                        loadingOverlay.style.display = 'none';
                        stopStatusRotation();
                    }
                    
                    alert('Image processing failed, please try again.');
                }
            })
            .catch(error => {
                consecutiveErrors++;
                console.error(`Queue polling error (attempt ${consecutiveErrors}):`, error);
                
                // Stop polling after too many consecutive errors
                if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
                    clearInterval(pollingInterval);
                    
                    if (loadingOverlay) {
                        loadingOverlay.style.display = 'none';
                        stopStatusRotation();
                    }
                    
                    alert('Connection issues detected. Please check your internet connection and try again.');
                }
                // Otherwise continue polling - temporary network issues might resolve
            });
    }, POLLING_INTERVAL);
}
});

// Render preview grid
function renderPreviews(uid, previews) {
    const container = document.getElementById('previews');
    container.innerHTML = '';
    
    // Change title from "Examples" to "Previews" and show download hint
    const title = document.getElementById('preview-title');
    const instructions = document.getElementById('example-instructions');
    const downloadHint = document.getElementById('download-hint');
    if (title) {
        title.textContent = 'Previews';
    }
    if (instructions) {
        instructions.style.display = 'none';
    }
    if (downloadHint) {
        downloadHint.style.display = 'block';
    }
    
    // Mapping of internal style keys to human‑friendly labels for display
    const labelMap = {
        'Gradient Silhouette': 'Gradient Silhouette',
        'Silhouette': 'Silhouette',
        'Gradient': 'Gradient',
        'Stroke': 'Stroke',
        'Flat': 'Flat',
        'Window': 'Window'
    };
    
    // Define the same order as the example template: Window, Silhouette, Stroke, Gradient Silhouette, Gradient, Flat
    const orderedStyles = ['Window', 'Silhouette', 'Stroke', 'Gradient Silhouette', 'Gradient', 'Flat'];
    
    orderedStyles.forEach(function (style) {
        if (!previews[style]) return; // Skip if this style doesn't exist in the response
        const previewData = previews[style];
        
        // Create preview card with new simplified download interface
        const card = document.createElement('div');
        card.className = 'preview-card';
        
        const img = document.createElement('img');
        img.src = 'data:image/png;base64,' + previewData;
        img.alt = style + ' Style Preview';
        img.style.cursor = 'pointer';
        
        // Click handler to show larger preview in modal
        img.addEventListener('click', function() {
            showPreviewModal(uid, style, this.src);
        });
        
        const info = document.createElement('div');
        info.className = 'info';
        
        const name = document.createElement('span');
        name.textContent = labelMap[style] || style;
        
        // Simplified download buttons
        const downloadButtons = document.createElement('div');
        downloadButtons.className = 'download-buttons';
        
        // Primary download button
        const downloadBtn = document.createElement('a');
        downloadBtn.textContent = 'Download';
        downloadBtn.href = `/download/${uid}/${style}`;
        downloadBtn.className = 'button quick-download';
        downloadBtn.setAttribute('target', '_blank');
        
        // Advanced download button
        const advancedBtn = document.createElement('button');
        advancedBtn.textContent = 'Advanced';
        advancedBtn.className = 'button advanced-download';
        advancedBtn.addEventListener('click', function() {
            openHighResModal(uid, style);
        });
        
        downloadButtons.appendChild(downloadBtn);
        downloadButtons.appendChild(advancedBtn);
        
        info.appendChild(name);
        info.appendChild(downloadButtons);
        card.appendChild(img);
        card.appendChild(info);
        container.appendChild(card);
    });
    
    // Create download all button
    const allBtn = document.createElement('button');
    allBtn.textContent = 'Download All';
    allBtn.className = 'button action-btn enabled';
    allBtn.addEventListener('click', function () {
        const url = `/download_all/${uid}`;
        window.open(url, '_blank');
    });
    container.appendChild(allBtn);
}

// Show preview modal with larger image (not full resolution)
function showPreviewModal(uid, style, imageSrc) {
    const modal = document.getElementById('modal');
    const modalImg = document.getElementById('modal-image');
    const modalDownload = document.getElementById('modal-download');
    const modalAdvanced = document.getElementById('modal-advanced');
    
    if (!modal || !modalImg) return;
    
    // Set the larger preview image - use full download URL for generated images, or full-size samples
    if (uid && style) {
        // Generated image - use download URL
        modalImg.src = `/download/${uid}/${encodeURIComponent(style)}`;
    } else {
        // Sample image - use full-size sample instead of tiny thumbnail
        const styleMap = {
            'Window': '/static/images/AdobeStock_707229709_window_Blue2.png',
            'Silhouette': '/static/images/AdobeStock_707229709_silhouette_Blue2.png',
            'Stroke': '/static/images/AdobeStock_707229709_stroke_Blue2.png',
            'Gradient Silhouette': '/static/images/AdobeStock_707229709_gradient silhouette_Blue2.png',
            'Gradient': '/static/images/AdobeStock_707229709_gradient_Blue2.png',
            'Flat': '/static/images/AdobeStock_707229709_flat_Blue2.png'
        };
        modalImg.src = styleMap[style] || imageSrc;
    }
    
    // Always show buttons, but configure them differently for samples vs generated images
    if (modalDownload) modalDownload.style.display = 'inline-block';
    if (modalAdvanced) modalAdvanced.style.display = 'inline-block';
    
    if (uid && style) {
        // Generated image - enable full functionality
        modalDownload.href = `/download/${uid}/${style}`;
        modalDownload.style.opacity = '1';
        modalDownload.style.pointerEvents = 'auto';
        
        // Create friendly filename
        const extIndex = uploadFilename.lastIndexOf('.');
        const baseName = extIndex >= 0 ? uploadFilename.slice(0, extIndex) : uploadFilename;
        const colourName = (selectedColour || '').replace('#', '');
        const slugStyle = style.toLowerCase().replace(/\s+/g, '');
        modalDownload.download = `${baseName}_${slugStyle}_${colourName}.png`;
        
        // Configure advanced button
        if (modalAdvanced) {
            modalAdvanced.style.opacity = '1';
            modalAdvanced.style.pointerEvents = 'auto';
            modalAdvanced.onclick = function() {
                modal.style.display = 'none'; // Close preview modal first
                openHighResModal(uid, style);
            };
        }
    } else {
        // Sample image - disable buttons but keep them visible for layout
        modalDownload.href = '#';
        modalDownload.style.opacity = '0.5';
        modalDownload.style.pointerEvents = 'none';
        modalDownload.removeAttribute('download');
        
        if (modalAdvanced) {
            modalAdvanced.style.opacity = '0.5';
            modalAdvanced.style.pointerEvents = 'none';
            modalAdvanced.onclick = null;
        }
    }
    
    // Show modal
    modal.style.display = 'flex';
}

// Handle sample and generated preview clicks
function setupSamplePreviews() {
    // Handle sample preview clicks (before any image is uploaded)
    document.querySelectorAll('.sample-preview.clickable-preview').forEach(function(previewItem) {
        previewItem.addEventListener('click', function(e) {
            const img = this.querySelector('img');
            const styleName = this.dataset.style;
            
            // Show larger preview without download option
            showPreviewModal(null, styleName, img.src);
        });
    });
    
    // Show download hint when previews are generated
    const downloadHint = document.getElementById('download-hint');
    if (downloadHint) {
        downloadHint.style.display = 'block';
    }
}

// Handle clicks on generated preview images
function setupGeneratedPreviews() {
    document.querySelectorAll('.preview-item.clickable-preview').forEach(function(previewItem) {
        previewItem.addEventListener('click', function(e) {
            // Only handle clicks on generated previews, not samples
            if (this.classList.contains('sample-preview')) return;
            
            const img = this.querySelector('img');
            const styleName = this.dataset.style;
            const uid = this.dataset.uid; // We'll need to set this when creating previews
            
            if (!uid) return; // No UID means it's a sample
            
            // Open high-res modal for generated previews
            openHighResModal(uid, styleName);
        });
    });
}


// Modal close handling
document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('modal');
    const closeBtn = document.getElementById('close-modal');
    if (closeBtn) {
        closeBtn.addEventListener('click', function () {
            modal.style.display = 'none';
            // Show download button again when closing
            const modalDownload = document.getElementById('modal-download');
            if (modalDownload) {
                modalDownload.style.display = 'inline-block';
            }
        });
    }
    // Close modal when clicking outside content
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                modal.style.display = 'none';
                // Show download button again when closing
                const modalDownload = document.getElementById('modal-download');
                if (modalDownload) {
                    modalDownload.style.display = 'inline-block';
                }
            }
        });
    }
    
    // Setup sample preview functionality
    setupSamplePreviews();
    
    // Setup high-resolution modal functionality
    setupHighResModal();
    
    // Load usage statistics on page load
    loadUsageStats();
});

// Load and display usage statistics
function loadUsageStats() {
    fetch('/get_stats')
        .then(response => response.json())
        .then(data => {
            updateCounter(data.images_processed || 0);
        })
        .catch(error => {
            console.log('Could not load usage stats:', error);
            updateCounter(0);
        });
}

// Update the counter display
function updateCounter(count) {
    const counterText = document.getElementById('counter-text');
    if (counterText) {
        const plural = count === 1 ? 'anvilization' : 'anvilizations';
        counterText.textContent = `Total all time: ${count} ${plural}`;
    }
}

// High-Resolution Modal Functions
function openHighResModal(uid, style) {
    const modal = document.getElementById('highres-modal');
    if (!modal) return;
    
    // Store current processing info
    modal.dataset.uid = uid;
    modal.dataset.style = style;
    
    // Reset format selection to PNG
    const pngRadio = modal.querySelector('input[name="format"][value="png"]');
    if (pngRadio) pngRadio.checked = true;
    
    // Show modal
    modal.style.display = 'flex';
    
    // Update button state after modal is shown and format is selected
    setTimeout(function() {
        const startBtn = document.getElementById('start-highres');
        const selectedFormat = modal.querySelector('input[name="format"]:checked');
        if (startBtn) {
            if (selectedFormat) {
                startBtn.classList.add('enabled');
                startBtn.disabled = false;
                startBtn.style.opacity = '1';
                startBtn.style.pointerEvents = 'auto';
            } else {
                startBtn.classList.remove('enabled');
                startBtn.disabled = true;
                startBtn.style.opacity = '0.5';
                startBtn.style.pointerEvents = 'none';
            }
        }
    }, 50);
}

function setupHighResModal() {
    const modal = document.getElementById('highres-modal');
    const closeBtn = document.getElementById('close-highres-modal');
    const cancelBtn = document.getElementById('cancel-highres');
    const startBtn = document.getElementById('start-highres');
    
    // Close button handlers
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            modal.style.display = 'none';
        });
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            modal.style.display = 'none';
        });
    }
    
    // Close when clicking outside
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }
    
    // Function to update Start Processing button state
    function updateStartButton() {
        const selectedFormat = modal.querySelector('input[name="format"]:checked');
        if (startBtn) {
            if (selectedFormat) {
                startBtn.classList.add('enabled');
                startBtn.disabled = false;
                startBtn.style.opacity = '1';
                startBtn.style.pointerEvents = 'auto';
            } else {
                startBtn.classList.remove('enabled');
                startBtn.disabled = true;
                startBtn.style.opacity = '0.5';
                startBtn.style.pointerEvents = 'none';
            }
        }
    }
    
    // Handle radio button selection styling manually (CSP-safe)
    const formatOptions = modal.querySelectorAll('.format-option');
    formatOptions.forEach(function(option) {
        const radio = option.querySelector('input[type="radio"]');
        if (radio) {
            radio.addEventListener('change', function() {
                // Reset all options
                formatOptions.forEach(function(opt) {
                    opt.style.borderColor = '#e0e0e0';
                    opt.style.backgroundColor = 'transparent';
                });
                
                // Style the selected option
                if (this.checked) {
                    option.style.borderColor = '#0070F2';
                    option.style.backgroundColor = '#f8f9ff';
                }
                
                // Update button state when format selection changes
                updateStartButton();
            });
        }
    });
    
    // Start processing button
    if (startBtn) {
        startBtn.addEventListener('click', function() {
            const uid = modal.dataset.uid;
            const style = modal.dataset.style;
            const selectedFormat = modal.querySelector('input[name="format"]:checked');
            
            if (!uid || !style || !selectedFormat) {
                alert('Missing processing information. Please try again.');
                return;
            }
            
            const format = selectedFormat.value;
            
            // Close modal and start processing
            modal.style.display = 'none';
            startHighResProcessing(uid, style, format);
        });
    }
}

// Status rotation for standard loading screen
let statusRotationInterval = null;

function startStatusRotation() {
    const statusMessages = [
        '🔍 Analyzing your masterpiece...',
        '🎨 Extracting subjects and backgrounds...',
        '⚒️ Forging anvil shapes with precision...',
        '🌈 Applying SAP brand colors...',
        '✨ Generating 6 stunning styles...',
        '🚀 Almost ready for download...'
    ];
    
    const statusElement = loadingOverlay ? loadingOverlay.querySelector('.processing-status-text') : null;
    if (!statusElement) return;
    
    let currentIndex = 0;
    statusElement.textContent = statusMessages[0];
    
    // Clear any existing interval
    if (statusRotationInterval) {
        clearInterval(statusRotationInterval);
    }
    
    // Start rotating messages every 12 seconds
    statusRotationInterval = setInterval(() => {
        currentIndex = (currentIndex + 1) % statusMessages.length;
        statusElement.textContent = statusMessages[currentIndex];
    }, 12000);
}

function stopStatusRotation() {
    if (statusRotationInterval) {
        clearInterval(statusRotationInterval);
        statusRotationInterval = null;
    }
}

function startHighResProcessing(uid, style, format) {
    // Ensure DOM is fully loaded before accessing elements
    if (document.readyState !== 'complete') {
        console.warn('DOM not fully loaded, waiting...');
        window.addEventListener('load', function() {
            startHighResProcessing(uid, style, format);
        });
        return;
    }
    
    // Show full-screen high-resolution loading overlay
    const highresOverlay = document.getElementById('highres-loading-overlay');
    
    if (!highresOverlay) {
        console.error('High-res loading overlay element not found');
        console.error('Available elements:', document.querySelectorAll('[id*="loading"]'));
        alert('Error: Loading overlay not found. Please refresh the page and try again.');
        return;
    }
    
    const loadingText = highresOverlay.querySelector('.loading-text');
    const subText = highresOverlay.querySelector('.loading-subtext');
    const statusText = highresOverlay.querySelector('.processing-status-text');
    
    // Add null checks for child elements
    if (!loadingText || !subText || !statusText) {
        console.error('Loading overlay child elements not found');
        alert('Error: Loading interface elements not found. Please refresh the page and try again.');
        return;
    }
    
    // Update loading messages based on format
    if (format === 'png') {
        loadingText.textContent = 'Processing 8K PNG Image...';
        subText.textContent = 'This may take 30-60 seconds for high-resolution processing';
        statusText.textContent = 'Enhancing your image to 8K resolution...';
    } else {
        loadingText.textContent = 'Creating Layer Package...';
        subText.textContent = 'This may take 1-2 minutes for complete layer separation';
        statusText.textContent = 'Generating editable layers for professional use...';
    }
    
    // Show the overlay
    highresOverlay.style.display = 'flex';
    
    // Disable modal closing during processing
    const modal = document.getElementById('highres-modal');
    if (modal) {
        const closeButtons = modal.querySelectorAll('.close-modal, #cancel-highres');
        closeButtons.forEach(btn => {
            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.5';
        });
    }
    
    // Update status text every 15 seconds to keep user engaged
    const statusMessages = [
        format === 'png' ? 'Analyzing image structure...' : 'Extracting background layer...',
        format === 'png' ? 'Applying high-resolution enhancements...' : 'Isolating subject elements...',
        format === 'png' ? 'Optimizing image quality...' : 'Creating anvil overlay layer...',
        format === 'png' ? 'Finalizing 8K image...' : 'Packaging layers for download...'
    ];
    
    let statusIndex = 0;
    const statusInterval = setInterval(() => {
        if (statusIndex < statusMessages.length) {
            statusText.textContent = statusMessages[statusIndex];
            statusIndex++;
        }
    }, 15000);
    
    // Prepare the high-resolution processing request payload
    let requestPayload = {};
    
    // Include high-resolution image data if available
    if (window.currentHighResData && window.currentHighResData.dataUrl) {
        requestPayload.highResImageData = window.currentHighResData.dataUrl;
        requestPayload.highResDimensions = window.currentHighResData.dimensions;
        requestPayload.originalCrop = window.currentHighResData.originalCrop;
        requestPayload.naturalDimensions = window.currentHighResData.naturalDimensions;
        
        console.log(`High-res processing with original data: ${window.currentHighResData.dimensions.width}x${window.currentHighResData.dimensions.height}`);
        
        // Also include current anvil settings for high-res processing
        requestPayload.anvilScale = anvilScale;
        requestPayload.anvilOffsetX = anvilOffsetX;
        requestPayload.anvilOffsetY = anvilOffsetY;
        requestPayload.opacity = opacitySlider ? parseFloat(opacitySlider.value) / 100.0 : 0.5;
        requestPayload.colour = selectedColour;
        requestPayload.ratio = document.querySelector('input[name="ratio"]:checked').value;
        requestPayload.filename = uploadFilename;
    } else {
        console.warn('No high-resolution data available, falling back to stored low-res image');
    }
    
    // Start the processing request
    fetch(`/process_highres/${uid}/${style}/${format}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload)
    })
    .then(response => {
        // Check if response is JSON (error) or blob (success)
        const contentType = response.headers.get("content-type");
        
        if (contentType && contentType.includes("application/json")) {
            // JSON response indicates an error
            return response.json().then(err => {
                throw new Error(err.error || 'Processing failed');
            });
        } else {
            // Non-JSON response should be the file blob
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.blob();
        }
    })
    .then(blob => {
        // Processing successful - trigger download
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        // Generate filename
        const extIndex = uploadFilename.lastIndexOf('.');
        const baseName = extIndex >= 0 ? uploadFilename.slice(0, extIndex) : uploadFilename;
        const colourName = (selectedColour || '').replace('#', '');
        const slugStyle = style.toLowerCase().replace(/\s+/g, '');
        
        if (format === 'png') {
            a.download = `${baseName}_${slugStyle}_${colourName}_8K.png`;
        } else {
            a.download = `${baseName}_${slugStyle}_${colourName}_layers.zip`;
        }
        
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        // Hide high-resolution loading overlay
        clearInterval(statusInterval);
        highresOverlay.style.display = 'none';
        
        // Re-enable modal buttons
        if (modal) {
            const closeButtons = modal.querySelectorAll('.close-modal, #cancel-highres');
            closeButtons.forEach(btn => {
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';
            });
        }
    })
    .catch(error => {
        console.error('High-res processing error:', error);
        
        // Hide loading overlay
        clearInterval(statusInterval);
        highresOverlay.style.display = 'none';
        
        // Re-enable modal buttons
        if (modal) {
            const closeButtons = modal.querySelectorAll('.close-modal, #cancel-highres');
            closeButtons.forEach(btn => {
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';
            });
        }
        
        // Show error message
        alert('High-resolution processing failed: ' + error.message);
    });
}
