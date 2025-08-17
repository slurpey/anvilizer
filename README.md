# Anvilizer - SAP Brand Compliant Image Processing Tool

A Flask-based web application that transforms uploaded images into SAP brand-compliant anvil-styled graphics. Upload any image, crop it to your desired aspect ratio, and generate professional anvil overlays in multiple styles with high-resolution output up to 8K.

![Anvilizer Preview](static/images/previews/sample_gradient_silhouette.png)

## Features

### 🎨 **Six Anvil Styles**
- **Flat**: Semi-transparent colored overlay
- **Stroke**: Outlined anvil border with subject preserved
- **Gradient**: Multi-tone gradient fill within anvil shape
- **Window**: Image visible only within anvil shape
- **Silhouette**: Subject cutout over colored anvil background
- **Gradient Silhouette**: Subject cutout over gradient anvil background

### 🖼️ **Advanced Image Processing**
- **High-Resolution Support**: Process images up to 8K resolution (7680×4320)
- **Smart Upscaling**: Automatic high-quality upscaling for smaller images
- **Memory Optimization**: Sequential processing to handle large images efficiently
- **Background Removal**: AI-powered subject extraction using rembg

### 🎯 **Customization Options**
- **SAP Color Palette**: 27 brand-compliant colors including blues, teals, greens, and more
- **Aspect Ratios**: Support for 16:9 and 1:1 formats
- **Anvil Positioning**: Adjustable scale and positioning within the canvas
- **Opacity Control**: Customizable transparency for overlay effects

### 📦 **Export Options**
- **Individual Downloads**: High-resolution PNG files for each style
- **Bulk Download**: ZIP archive with all styles
- **Layer Packages**: Advanced exports with separate layers for professional editing
- **Friendly Filenames**: Automatic naming with style and color information

## Quick Start

### Prerequisites
- Python 3.9+
- Docker (for containerized deployment)

### Local Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/slurpey/anvilizer.git
   cd anvilizer
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Open your browser**
   Navigate to `http://localhost:5000`

### Docker Deployment

1. **Build the image**
   ```bash
   docker build -t anvilizer .
   ```

2. **Run the container**
   ```bash
   docker run -p 5000:5000 anvilizer
   ```

## Usage

1. **Upload Image**: Select any image file (JPG, PNG, etc.)
2. **Crop**: Use the interactive crop tool to select your desired area
3. **Choose Style**: Select from six available anvil styles
4. **Pick Color**: Choose from the SAP brand color palette
5. **Customize**: Adjust anvil size, position, and opacity as needed
6. **Generate**: Click "Generate Anvil Images" to process
7. **Download**: Get individual files or download all as ZIP

## Architecture

### Core Components
- **Flask Backend**: Main application server with image processing endpoints
- **PIL/Pillow**: High-quality image manipulation and processing
- **rembg**: AI-powered background removal for silhouette effects
- **NumPy**: Efficient array operations for image data

### Processing Pipeline
1. **Image Upload & Validation**: Secure file handling with format validation
2. **Interactive Cropping**: Browser-based crop interface with preview
3. **High-Resolution Processing**: Sequential style generation to optimize memory
4. **Style Application**: Custom algorithms for each anvil style
5. **Export Generation**: Multiple format outputs with metadata

### Memory Management
- Sequential processing prevents memory overflow
- Temporary disk storage for intermediate results
- Automatic cleanup of processed files
- Configurable memory limits for large images

## API Endpoints

### Main Routes
- `GET /` - Main application interface
- `POST /process` - Process uploaded image and generate previews
- `GET /download/<uid>/<style>` - Download individual processed image
- `GET /download_all/<uid>` - Download ZIP archive of all styles
- `POST /process_highres/<uid>/<style>/<format>` - Generate high-resolution exports

### Statistics
- `GET /get_stats` - Usage statistics including total images processed

## Configuration

### Environment Variables
- `PORT` - Server port (default: 5000)
- `MAX_SQUARE_PIXELS` - Maximum pixels for square images (default: 2,100,000)

### Color Palette
The application includes a comprehensive SAP brand color palette with 27 colors:
- Blues: Light Blue variants, Standard Blues, Navy tones
- Greens: Light Green, Standard Green, Teal variants
- Accent Colors: Yellow, Orange, Red, Pink variants
- Neutrals: White, Black, Gray variants

## File Structure

```
anvilizer/
├── app.py                          # Main Flask application
├── layer_package_generator.py      # Advanced export functionality
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container configuration
├── static/
│   ├── css/styles.css             # Application styling
│   ├── js/script.js               # Frontend JavaScript
│   ├── images/                    # Brand assets and previews
│   └── favicon.ico                # Site icon
├── templates/
│   └── index.html                 # Main application template
├── generated/                     # Temporary processing files
└── logs/                         # Application logs
```

## Performance

### Capabilities
- **Resolution**: Up to 8K (7680×4320) output
- **Memory Usage**: Optimized for large image processing
- **Processing Speed**: Sequential generation prevents timeouts
- **Concurrent Users**: Supports multiple simultaneous sessions

### Limitations
- Large images (>8K) are automatically resized for memory efficiency
- Processing time scales with image size and complexity
- Background removal requires additional processing time

## Dependencies

### Core Requirements
```
Flask==3.0.0           # Web framework
Pillow==10.1.0         # Image processing
rembg[cpu,cli]==2.0.58 # Background removal
click==8.1.7           # Command line interface
filetype==1.2.0        # File type detection
```

### Optional Dependencies
- **NumPy**: Enhanced array operations
- **CairoSVG**: SVG processing (if needed)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is designed for internal SAP use with brand-compliant image processing.

## Support

For issues or questions:
1. Check the application logs in the `logs/` directory
2. Review the browser console for client-side issues
3. Ensure all dependencies are properly installed
4. Verify image formats are supported (JPG, PNG, WebP)

## Version History

- **Latest**: Enhanced high-resolution processing, memory optimization, layer exports
- **Previous**: Basic anvil generation with standard resolution output

---

**Built with ❤️ for SAP Brand Compliance**
