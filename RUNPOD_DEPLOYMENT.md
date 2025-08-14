# RunPod Deployment Guide

## Quick Setup Steps

### 1. Push Dockerfile to GitHub
```bash
git add Dockerfile RUNPOD_DEPLOYMENT.md
git commit -m "Add RunPod Dockerfile and deployment guide"
git push
```

### 2. RunPod Template Setup

1. **Go to RunPod Console**: https://www.runpod.io/console
2. **Navigate to**: Templates → Create Template
3. **Fill in**:
   - **Template Name**: `anvilizer-flask-app`
   - **Container Image**: `python:3.11-slim` (we'll build from this)
   - **Container Registry Credentials**: Leave blank (public image)
   - **Container Start Command**: 
     ```bash
     bash -c "git clone https://github.com/slurpey/anvilizer.git /app && cd /app && pip install -r requirements.txt && python app.py"
     ```
   - **Container Disk**: `5 GB` (minimum)
   - **Expose HTTP Ports**: `5000`
   - **Expose TCP Ports**: Leave blank

### 3. Pod Configuration (Cheapest Options)

**Recommended Settings for Cost Optimization:**
- **GPU**: `RTX 3070` or `RTX 4060` (cheapest GPU options)
- **vCPU**: `4 vCPU` (minimum)
- **RAM**: `15 GB` (comes with GPU, plenty for rembg)
- **Storage**: `Ephemeral` (as requested)
- **Region**: Choose cheapest available

### 4. Deploy Pod

1. **Create Pod** from your template
2. **Wait for deployment** (2-3 minutes)
3. **Access via**: `https://[pod-id]-5000.proxy.runpod.net`

### 5. Test the Application

Once deployed, test:
- Upload an image
- Try different aspect ratios (16:9, 1:1)
- Test all 6 styles including Silhouette (rembg)
- Verify memory usage is stable

## Troubleshooting

**If pod fails to start:**
- Check logs in RunPod console
- Verify GitHub repo is public
- Try different GPU type if current one unavailable

**If app is slow:**
- First rembg model download takes time (176MB)
- Subsequent requests should be fast
- Consider upgrading to faster GPU if needed

## Cost Optimization Tips

- **Stop pod when not in use** (ephemeral storage means no data loss concern)
- **Use spot instances** if available (cheaper but can be interrupted)
- **Monitor usage** in RunPod billing dashboard

## Expected Performance

With GPU acceleration:
- **rembg processing**: ~2-3 seconds per image
- **6 style generation**: ~5-10 seconds total
- **Memory usage**: ~2-4GB (well within limits)
