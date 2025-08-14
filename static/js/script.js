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

// Cropper.js instance
// We disable Cropper usage in this build to retain the custom crop box
// functionality.  The variable remains for compatibility but is never
// initialised.  If Cropper is later enabled, this variable can be
// assigned a Cropper instance.
let cropper = null;

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
// overlays and the anvil preview based on the current crop box
// dimensions.  When using Cropper.js, this function retrieves the
// crop box data from the cropper instance instead of relying on our
// custom crop box element.
function updateMaskAndAnvil() {
    updateCropMask();
    updateAnvilPreview();
}

// Initialise Cropper.js on the loaded image.  This will replace the
// custom crop box and use Cropper's built‑in crop box UI.  The aspect
// ratio is set according to currentRatio.  When the crop box is
// changed by the user, the 'crop' event triggers updates for the
// dark overlay masks and the anvil preview.
function initCropper() {
    if (cropper) {
        cropper.destroy();
        cropper = null;
    }
    cropper = new Cropper(imageElement, {
        viewMode: 1,
        aspectRatio: currentRatio,
        autoCropArea: 1.0,
        responsive: true,
        background: false,
        zoomOnWheel: false,
        ready() {
            // Hide the custom crop box element as Cropper handles
            // cropping UI internally
            cropBox.style.display = 'none';
            // Ensure mask overlays are visible
            maskTop.style.display = 'block';
            maskLeft.style.display = 'block';
            maskRight.style.display = 'block';
            maskBottom.style.display = 'block';
            // Set zoom slider defaults
            zoomSlider.min = '0.3';
            zoomSlider.max = '1';
            zoomSlider.step = '0.01';
            zoomSlider.value = '1';
            // Perform initial mask and anvil update
            updateMaskAndAnvil();
            // Set the crop box to the maximum size corresponding to the
            // current ratio.  This ensures that the initial view
            // reflects the full image when possible.  Without this,
            // Cropper may choose a default crop that does not match
            // our zoom slider behaviour.
            updateCropBoxForZoom();
        },
        crop() {
            // Update overlays whenever the crop box changes
            updateMaskAndAnvil();
        }
    });
}

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
    currentRatio = ratioVal === '1:1' ? 1 : 16 / 9;
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
        currentRatio = this.value === '1:1' ? 1 : 16 / 9;
        // Update Cropper aspect ratio if initialised
        if (cropper) {
            // If Cropper is ever enabled, update its aspect ratio and reset zoom
            cropper.setAspectRatio(currentRatio);
            zoomSlider.value = '1';
            updateCropBoxForZoom();
        } else {
            // For the custom crop box, rebuild it to match the new ratio
            setupCropBox();
        }
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

// Update the crop box dimensions based on the zoom slider value.  The
// crop box shrinks as the user zooms in (value < 1).  The centre of
// the box is preserved where possible.
function updateCropBoxForZoom() {
    // When using Cropper.js, adjust via Cropper's API.  Otherwise,
    // adjust the custom crop box element.  The zoom slider controls
    // the fraction of the maximum crop size (1 = max).  Preserve
    // the centre of the existing crop box when resizing and clamp
    // within the wrapper or container boundaries.
    if (cropper) {
        const zoomFactor = parseFloat(zoomSlider.value);
        const containerData = cropper.getContainerData();
        let baseW, baseH;
        if ((containerData.width / currentRatio) <= containerData.height) {
            baseW = containerData.width;
            baseH = baseW / currentRatio;
        } else {
            baseH = containerData.height;
            baseW = baseH * currentRatio;
        }
        const newW = baseW * zoomFactor;
        const newH = baseH * zoomFactor;
        const cropBoxData = cropper.getCropBoxData();
        let centerX = cropBoxData.left + cropBoxData.width / 2;
        let centerY = cropBoxData.top + cropBoxData.height / 2;
        let newLeft = centerX - newW / 2;
        let newTop = centerY - newH / 2;
        if (newLeft < 0) newLeft = 0;
        if (newTop < 0) newTop = 0;
        if (newLeft + newW > containerData.width) newLeft = containerData.width - newW;
        if (newTop + newH > containerData.height) newTop = containerData.height - newH;
        cropper.setCropBoxData({ left: newLeft, top: newTop, width: newW, height: newH });
        // Update overlays
        updateMaskAndAnvil();
    } else {
        // Custom crop box logic: adjust the cropBox element itself.
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
}

// Update mask overlay positions and sizes based on crop box
function updateCropMask() {
    // When using Cropper.js, obtain the crop box data from the cropper.
    // Otherwise fall back to the manual crop box values.  If neither are
    // available, do nothing.
    const wrapperWidth = cropWrapper.clientWidth;
    const wrapperHeight = cropWrapper.clientHeight;
    let cropLeft, cropTop, cropW, cropH;
    if (cropper) {
        const box = cropper.getCropBoxData();
        const container = cropper.getContainerData();
        // Adjust crop coordinates relative to the cropWrapper by
        // subtracting the container's offset (usually 0,0)
        cropLeft = box.left - container.left;
        cropTop = box.top - container.top;
        cropW = box.width;
        cropH = box.height;
    } else if (cropBox && cropBox.style.display !== 'none') {
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
    // Determine the crop box dimensions.  Use Cropper.js if available,
    // otherwise fall back to the manual crop box values.  If neither
    // exist, exit early.
    let cropW, cropH, cropLeft, cropTop;
    if (cropper) {
        const box = cropper.getCropBoxData();
        const container = cropper.getContainerData();
        cropW = box.width;
        cropH = box.height;
        // Convert crop box coordinates to the cropWrapper coordinate system
        cropLeft = box.left - container.left;
        cropTop = box.top - container.top;
    } else if (cropBox && cropBox.style.display !== 'none') {
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

// Generate button click
generateBtn.addEventListener('click', function () {
    if (!imageElement.src || !selectedColour) return;
    // Use Cropper.js to generate the cropped region at the target
    // resolution.  This ensures that the selected region in the UI
    // exactly matches what is sent to the backend.  If Cropper is not
    // initialised, fall back to the original image without cropping.
    let dataUrl;
    const ratioValue = document.querySelector('input[name="ratio"]:checked').value;
    let targetW = 1920;
    let targetH = ratioValue === '1:1' ? 1920 : 1080;
    if (cropper) {
        const canvas = cropper.getCroppedCanvas({
            width: targetW,
            height: targetH,
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high',
            fillColor: '#00000000'
        });
        dataUrl = canvas.toDataURL('image/png');
    } else {
        // No cropper instance; compute the crop based on the custom crop box
        // Determine the bounding rectangles of the displayed image and the crop box.
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
        // Create a canvas and draw the cropped region at the target resolution
        const canvas = document.createElement('canvas');
        canvas.width = targetW;
        canvas.height = targetH;
        const ctx = canvas.getContext('2d');
        // Draw the cropped region scaled to the target output size
        ctx.drawImage(imageElement, sx, sy, sw, sh, 0, 0, targetW, targetH);
        dataUrl = canvas.toDataURL('image/png');
    }
    // Convert opacity slider (0-100) to 0-1 range
    const opacityValue = opacitySlider ? parseFloat(opacitySlider.value) / 100.0 : 0.5;
    // Prepare anvil parameters for backend
    const scaleParam = anvilScale;
    const offsetXParam = anvilOffsetX;
    const offsetYParam = anvilOffsetY;
    // Show loading overlay while processing
    if (loadingOverlay) {
        loadingOverlay.style.display = 'flex';
    }
    fetch('/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            imageData: dataUrl,
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
            if (data.error) {
                alert('Error: ' + data.error);
                return;
            }
            renderPreviews(data.uid, data.previews);
            // Hide loading overlay after previews rendered
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }
        })
        .catch(err => {
            console.error(err);
            alert('An error occurred while processing the image.');
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }
        });
});

// Render preview grid
function renderPreviews(uid, previews) {
    const container = document.getElementById('previews');
    container.innerHTML = '';
    // Mapping of internal style keys to human‑friendly labels for display
    const labelMap = {
        'Gradient Silhouette': 'Gradient Silhouette',
        'Silhouette': 'Silhouette',
        'Gradient': 'Gradient',
        'Stroke': 'Stroke',
        'Flat': 'Flat',
        'Window': 'Window'
    };
    Object.keys(previews).forEach(function (style) {
        const previewData = previews[style];
        const card = document.createElement('div');
        card.className = 'preview-card';
        const img = document.createElement('img');
        // Base64 encoded preview thumbnail
        img.src = 'data:image/png;base64,' + previewData;
        // Store preview data and style on the element for the modal
        img.dataset.preview = previewData;
        img.dataset.style = style;
        // Click handler to open modal with larger view.  The modal will
        // display the preview using the base64 data (to avoid broken
        // network requests) while the download link points to the high
        // resolution asset on the server.
        img.style.cursor = 'pointer';
        img.addEventListener('click', function () {
            const modal = document.getElementById('modal');
            const modalImg = document.getElementById('modal-image');
            const modalDownload = document.getElementById('modal-download');
            const styleName = this.dataset.style;
            // Set download link for full resolution asset
            modalDownload.href = `/download/${uid}/${styleName}`;
            // Compose a friendly filename using the original file name, style and colour
            const extIndex = uploadFilename.lastIndexOf('.');
            const baseName = extIndex >= 0 ? uploadFilename.slice(0, extIndex) : uploadFilename;
            const colourName = (selectedColour || '').replace('#', '');
            const slugStyle = styleName.toLowerCase().replace(/\s+/g, '');
            modalDownload.download = `${baseName}_${slugStyle}_${colourName}.png`;
            // Fetch the high resolution image and display it in the modal.  This
            // ensures the preview is large and sharp.
            fetch(`/download/${uid}/${styleName}`)
                .then(response => response.blob())
                .then(blob => {
                    const url = URL.createObjectURL(blob);
                    modalImg.src = url;
                })
                .catch(() => {
                    // If fetch fails, fall back to the thumbnail preview
                    modalImg.src = 'data:image/png;base64,' + this.dataset.preview;
                });
            modal.style.display = 'flex';
        });
        const info = document.createElement('div');
        info.className = 'info';
        const name = document.createElement('span');
        const displayName = labelMap[style] || style;
        name.textContent = displayName;
        // Create a download link instead of a button.  The file name will
        // be provided by the server based on meta.json, so the download
        // attribute can be left unset.  Styling is handled via CSS to
        // match the appearance of buttons.
        const link = document.createElement('a');
        link.textContent = 'Download';
        link.href = `/download/${uid}/${style}`;
        link.setAttribute('target', '_blank');
        // Add the button class for consistent styling
        link.className = 'download-link';
        info.appendChild(name);
        info.appendChild(link);
        card.appendChild(img);
        card.appendChild(info);
        container.appendChild(card);
    });
    // Create download all button
    // Add a small "Download All" button below the grid
    const allBtn = document.createElement('button');
    allBtn.textContent = 'Download All';
    allBtn.className = 'button';
    // Use inline styles to keep the button compact and consistent with other
    // controls. Set fixed dimensions to prevent scaling with browser zoom.
    allBtn.style.marginTop = '12px';
    allBtn.style.padding = '8px 16px';
    allBtn.style.width = '120px';
    allBtn.style.height = '32px';
    allBtn.style.fontSize = '14px';
    allBtn.style.boxSizing = 'border-box';
    allBtn.style.display = 'block';
    allBtn.style.flexShrink = '0';
    allBtn.style.minWidth = '120px';
    allBtn.style.maxWidth = '120px';
    allBtn.addEventListener('click', function () {
        const url = `/download_all/${uid}`;
        window.open(url, '_blank');
    });
    container.appendChild(allBtn);
}

// Modal close handling
document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('modal');
    const closeBtn = document.getElementById('close-modal');
    if (closeBtn) {
        closeBtn.addEventListener('click', function () {
            modal.style.display = 'none';
        });
    }
    // Close modal when clicking outside content
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }
});
