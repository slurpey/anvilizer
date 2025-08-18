# Anvilizer - SAP Brand Compliant Image Processing Tool

A Flask-based web application that transforms uploaded images into SAP brand-compliant anvil-styled graphics. Upload any image, crop it to your desired aspect ratio, and generate professional anvil overlays in multiple styles with high-resolution output up to 8K.

🔗 **Live Demo**: [Available on request]

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
- **Large File Handling**: Upload images up to 60MB
- **Dual Processing Pipeline**: Fast previews (920px) + full-resolution final output
- **Smart Memory Management**: Sequential processing prevents crashes on large images
- **Background Removal**: AI-powered subject extraction using rembg with multiple model fallbacks

### 🎯 **Customization Options**
- **Extended SAP Color Palette**: 27 brand-compliant colors across blues, teals, greens, neutrals
- **Aspect Ratios**: Support for 16:9 and 1:1 formats
- **Interactive Anvil Control**: Adjustable scale, position (X/Y offset), and opacity
- **Real-time Preview**: Live preview updates as you adjust settings

### 📦 **Export Options**
- **Preview Downloads**: Quick PowerPoint-ready images from previews
- **Advanced High-Resolution**: Single-style processing at native resolution (up to 8K)
- **Layer Packages**: Professional 3-layer ZIP exports for Photoshop/design tools
  - Background layer (original image)
  - Subject cutout (AI-extracted, transparent background)  
  - Anvil overlay (shape with transparency)
  - Final composite + metadata JSON + README instructions
- **Bulk Download**: ZIP archive with all 6 styles
- **Smart Naming**: Automatic filenames with image name, style, and color

## Quick Start

### Prerequisites
- Python 3.9+
- Docker (for containerized deployment)
- Kubernetes cluster (for cloud deployment)

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
   docker run -p 5000:5000 -v ./logs:/logs anvilizer
   ```

### Cloud Deployment

The application is cloud-ready and supports deployment on various Kubernetes platforms with proper resource allocation and scaling capabilities.

#### Production Features
- **Scalable Architecture**: Container-based deployment
- **Resource Management**: Configurable CPU and memory limits
- **Health Monitoring**: Built-in health checks and logging
- **Persistent Storage**: Session data and usage logging
- **High Availability**: Auto-restart and failover capabilities

## Usage Workflow

### Standard Processing
1. **Upload**: Select image file (up to 60MB)
2. **Crop**: Interactive crop tool with aspect ratio selection
3. **Customize**: Choose color, adjust anvil size/position/opacity
4. **Generate**: Creates 6 preview styles (920px max) for quick review
5. **Download**: Individual PNG downloads or complete ZIP package

### Advanced High-Resolution Processing
1. **Choose Style**: Click advanced button on any preview style
2. **Select Format**: 
   - **PNG**: Single high-res image at native resolution (up to 8K)
   - **Layers**: 3-layer ZIP package for professional editing
3. **Process**: Full-resolution processing using original uploaded image
4. **Download**: High-quality output preserving original image dimensions

## Architecture

### Application Components
- **Flask Backend**: Main server with REST API endpoints
- **Image Processing**: PIL/Pillow with memory-optimized sequential processing
- **AI Background Removal**: rembg with u2net_human_seg and silueta model fallbacks
- **Layer Generation**: Advanced export system with separate PNG layers
- **Storage**: Automatic detection of persistent vs local storage

### Processing Pipeline
1. **Upload & Validation**: Secure file handling, size/format validation
2. **Dual Image Storage**: Preview resolution + original high-resolution
3. **Preview Generation**: Fast 920px processing for 6 styles
4. **Advanced Processing**: On-demand full-resolution single-style processing
5. **Export Generation**: Multiple formats with metadata and instructions

### Memory Management
- **Sequential Processing**: One style at a time to prevent memory overflow
- **Disk Buffering**: Temporary file storage during processing
- **Resource Limits**: 2GB memory allocation for large image processing
- **Automatic Cleanup**: Session cleanup and old file removal

### Storage Strategy
- **Development**: Local `logs/` directory
- **Kubernetes**: Persistent volume mounted at `/logs`
- **Auto-detection**: Environment-aware storage path selection
- **Image Logging**: Small 800px versions saved for usage tracking

## API Endpoints

### Core Processing
- `GET /` - Main application interface
- `POST /process` - Process uploaded image, generate previews
- `GET /download/<uid>/<style>` - Download preview-resolution image
- `GET /download_all/<uid>` - Download ZIP with all 6 styles
- `POST /process_highres/<uid>/<style>/<format>` - Advanced high-res processing

### Utilities
- `GET /get_stats` - Usage statistics (total images processed)

### Advanced Export Formats
- `format=png` - High-resolution single PNG
- `format=layers` - 3-layer ZIP package with:
  - `01_background.png` - Original image
  - `02_subject_cutout.png` - AI-extracted subject
  - `03_anvil_shape.png` - Anvil overlay with transparency
  - `final_composite.png` - Flattened result
  - `layer_info.json` - Technical metadata
  - `README.txt` - Usage instructions

## Configuration

### Environment Variables
- `PORT` - Server port (default: 5000)
- `KUBERNETES_SERVICE_HOST` - Auto-detected in Kubernetes for storage path

### Resource Requirements
- **Memory**: 2GB recommended for large image processing
- **CPU**: 500m sufficient for typical workloads
- **Storage**: 2GB+ for persistent logging
- **Network**: HTTP/HTTPS with optional service mesh

### Processing Limits
- **Upload Size**: 60MB maximum file size
- **Output Resolution**: 8K maximum (7680×4320)
- **Auto-resize**: Images exceeding 8K are automatically scaled down
- **Memory Safety**: Sequential processing prevents OOM crashes

## File Structure

```
anvilizer/
├── app.py                          # Main Flask application
├── layer_package_generator.py      # Advanced layer export system
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Multi-stage container build
├── SAP/
│   ├── k8s-deployment.yaml        # Kubernetes deployment, service, gateway
│   ├── pvc.yaml                   # Persistent volume claim
│   └── DEPLOYMENT_SUMMARY.md      # Cloud deployment documentation
├── static/
│   ├── css/styles.css             # Responsive UI styling
│   ├── js/script.js               # Frontend processing logic
│   ├── images/                    # Brand assets and style previews
│   └── favicon.ico                # Site icon
├── templates/
│   └── index.html                 # Single-page application template
├── generated/                     # Temporary processing files (auto-cleanup)
└── logs/                         # Persistent image processing logs
```

## Performance & Scalability

### Processing Capabilities
- **Resolution**: Up to 8K (7680×4320) native output
- **File Size**: 60MB upload limit with smart compression
- **Memory Usage**: 2GB allocation handles largest images with AI processing
- **Processing Speed**: Sequential generation prevents timeouts
- **Concurrent Users**: Session-based processing supports multiple users

### Performance Optimizations
- **Preview First**: Fast 920px previews for immediate feedback
- **On-Demand High-Res**: Full resolution only when requested
- **Memory Management**: Disk buffering and automatic cleanup
- **Model Caching**: AI models loaded once and reused
- **Smart Resize**: Automatic scaling for oversized images

### Cloud Production Features
- **Auto-scaling**: Kubernetes HPA ready with custom metrics
- **Health Monitoring**: Liveness/readiness probes for reliability
- **Persistent Logging**: Usage tracking across pod restarts
- **Service Mesh**: Istio integration for advanced traffic management
- **Resource Isolation**: Proper CPU/memory limits prevent resource contention

## Dependencies

### Core Requirements
```
Flask==3.0.0           # Web application framework
Pillow==10.1.0         # Advanced image processing
rembg[cpu,cli]==2.0.58 # AI background removal with multiple models
numpy>=1.24.0          # Numerical operations
click==8.1.7           # CLI utilities
filetype==1.2.0        # File type detection
```

### Container & Deployment
```
Docker                 # Containerization
Kubernetes 1.20+       # Container orchestration  
Istio (optional)       # Service mesh for advanced networking
```

## Deployment Guide

### Local Development
```bash
git clone https://github.com/slurpey/anvilizer.git
cd anvilizer
pip install -r requirements.txt
python app.py
```

### Docker Production
```bash
docker build -t anvilizer:latest .
docker run -d -p 5000:5000 -v /data/logs:/logs anvilizer:latest
```

### Cloud Platform Deployment
The application includes Kubernetes deployment configurations for enterprise cloud platforms. Deployment details and configurations are maintained separately for security reasons.

## Troubleshooting

### Common Issues

**Memory Usage**
- Ensure adequate memory allocation for large image processing
- Recommended: 2GB+ for processing high-resolution images
- Monitor memory usage during intensive operations

**Large Image Processing**
- Images >8K are auto-resized for stability
- Use advanced processing for native resolution output
- Check application logs for processing details

**Storage Issues**
- Ensure proper write permissions for log directory
- Monitor disk space usage for persistent storage
- Verify volume mounts in containerized environments

### Debugging
```bash
# Local debugging
python app.py  # Run with debug output

# Check application logs
tail -f logs/*.jpg  # Monitor log files

# Test functionality
curl http://localhost:5000/get_stats  # Check application status
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Install dev dependencies
pip install -r requirements.txt

# Run tests (if available)
python -m pytest

# Format code
black app.py layer_package_generator.py

# Run locally with debug
FLASK_ENV=development python app.py
```

## License

This project is designed for internal SAP use with brand-compliant image processing capabilities.

## Support & Documentation

### Resources
- **Source Code**: https://github.com/slurpey/anvilizer
- **Live Demo**: Available on request for authorized users

### Getting Help
1. Check application logs in `logs/` directory
2. Review browser console for client-side issues  
3. Verify dependencies and system requirements
4. Ensure supported image formats (JPG, PNG, WebP, HEIC)

### Monitoring
- **Usage Stats**: Available at `/get_stats` endpoint
- **Application Logs**: Saved locally with timestamps
- **Health Monitoring**: Built-in application health checks

## Version History

### Latest (v2.0)
- ✅ **High-resolution processing** up to 8K native output
- ✅ **Advanced layer exports** with 3-layer ZIP packages  
- ✅ **Memory optimization** with 2GB allocation for large images
- ✅ **Kubernetes deployment** with persistent storage
- ✅ **Dual processing pipeline** (preview + high-res)
- ✅ **Enhanced UI** with interactive anvil controls
- ✅ **AI model fallbacks** for reliable background removal
- ✅ **Automatic crash recovery** with proper resource limits

### Previous (v1.0)
- Basic anvil generation with standard resolution output
- Simple Flask deployment
- Limited memory management

---

**Built with ❤️ for SAP Brand Compliance**  
*Deployed on Kyma with Kubernetes for enterprise-grade reliability*
