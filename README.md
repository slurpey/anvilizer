# Anvilizer - SAP Brand Compliant Image Processing Tool

A Flask-based web application that transforms uploaded images into SAP brand-compliant anvil-styled graphics. Upload any image, crop it to your desired aspect ratio, and generate professional anvil overlays in multiple styles with high-resolution output up to 8K.

![Anvilizer Preview](static/images/previews/sample_gradient_silhouette.png)

## Features

### 🎨 Anvil Styles
- Flat: Semi-transparent colored overlay
- Stroke: Outlined anvil border with subject preserved
- Gradient: Multi-tone gradient fill within anvil shape
- Window: Image visible only within anvil shape
- Silhouette: Subject cutout over colored anvil background
- Gradient Silhouette: Subject cutout over gradient anvil background

### 🖼️ Image Processing
- High-resolution support up to 8K (7680×4320)
- Large file handling (up to 60MB)
- Dual pipeline: fast preview + high-res final output
- AI background removal (rembg with model fallbacks)

### Customization
- SAP color palette
- Aspect ratios: 16:9 and 1:1
- Interactive controls: scale, position, opacity
- Live preview updates

### Export
- Preview downloads (PNG)
- ZIP package with 3-layer Photoshop-ready PNGs
- Smart automated naming

## Quick Start

### Prerequisites
- Python 3.9+
- pip (Python package installer)

### Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/slurpey/anvilizer.git
   cd anvilizer
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

4. **Open your browser:**  
   Navigate to `http://localhost:5000`

## Usage Workflow

1. Upload your image
2. Crop and adjust settings
3. Generate previews
4. Download PNGs or ZIP packages

## Folder Structure

```
anvilizer/
├── app.py                 # Flask application
├── requirements.txt       # Dependencies
├── layer_package_generator.py
├── static/
│   ├── css/styles.css
│   ├── js/script.js
│   ├── images/
│   └── favicon.ico
├── templates/
│   └── index.html
├── generated/             # Temporary files (auto-cleanup)
└── logs/                  # Persistent logs
```

## Troubleshooting

- Ensure Python and all dependencies are installed
- Supported image formats: JPG, PNG, WebP, HEIC
- Check application logs in `logs/` for issues

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes and push
4. Open a Pull Request

## License

This project is designed for internal SAP use with brand-compliant image processing capabilities.

---

*Built for SAP Brand Compliance*
