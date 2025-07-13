# F1 Telemetry Analysis Dashboard

A containerized web application for interactive Formula 1 telemetry analysis using FastF1 data. Analyze driver performance, compare lap times, and visualize racing lines with speed data.

## Features

- **Interactive Driver Comparison**: Select multiple drivers and compare their fastest laps
- **Dynamic Race Selection**: Choose from different years, races, and sessions
- **Speed-Colored Track Maps**: Visualize racing lines with speed color coding
- **Speed Trace Analysis**: Compare speed differences along track distance
- **Containerized Deployment**: Run anywhere Docker is supported

## Quick Start

### Option 1: Docker Run (Simplest)

```bash
# Build the container
docker build -t f1-telemetry-app .

# Run the application
docker run -p 8050:8050 -v $(pwd)/cache:/app/cache f1-telemetry-app
```

Visit `http://localhost:8050` in your browser.

### Option 2: Docker Compose (Recommended)

```bash
# Start the application
docker-compose up --build

# For production with nginx proxy
docker-compose --profile production up --build
```

### Option 3: Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

## Usage

1. **Select Session**: Choose year, race, and session type from the dropdowns
2. **Pick Drivers**: Select 1-3 drivers to compare from the available list
3. **Analyze Data**: View interactive track maps and speed comparisons
4. **Explore**: Hover over data points for detailed telemetry information

## Deployment Options

### Local Development
```bash
docker run -p 8050:8050 f1-telemetry-app
```

### Cloud Platforms

#### AWS ECS/Fargate
```bash
# Tag for ECR
docker tag f1-telemetry-app:latest your-account.dkr.ecr.region.amazonaws.com/f1-telemetry-app:latest

# Push to ECR
docker push your-account.dkr.ecr.region.amazonaws.com/f1-telemetry-app:latest
```

#### Google Cloud Run
```bash
# Tag for GCR
docker tag f1-telemetry-app:latest gcr.io/your-project/f1-telemetry-app:latest

# Deploy to Cloud Run
gcloud run deploy f1-telemetry-app \
  --image gcr.io/your-project/f1-telemetry-app:latest \
  --platform managed \
  --port 8050
```

#### Railway
```bash
# Connect to Railway (one-time setup)
railway login
railway link your-project

# Deploy
railway up
```

### Self-Hosted/On-Premises

#### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: f1-telemetry-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: f1-telemetry-app
  template:
    metadata:
      labels:
        app: f1-telemetry-app
    spec:
      containers:
      - name: f1-telemetry-app
        image: f1-telemetry-app:latest
        ports:
        - containerPort: 8050
        volumeMounts:
        - name: cache-volume
          mountPath: /app/cache
      volumes:
      - name: cache-volume
        persistentVolumeClaim:
          claimName: f1-cache-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: f1-telemetry-service
spec:
  selector:
    app: f1-telemetry-app
  ports:
  - port: 80
    targetPort: 8050
  type: LoadBalancer
```

## Environment Variables

- `FASTF1_CACHE_DIR`: Directory for FastF1 data cache (default: `/app/cache`)
- `PYTHONUNBUFFERED`: Enable Python output buffering (set to `1`)

## Data Caching

The application caches F1 data locally to improve performance:

- **Local Development**: Cache stored in `./cache/` directory
- **Docker**: Mount volume for persistent cache: `-v $(pwd)/cache:/app/cache`
- **Production**: Use persistent volumes for cache storage

## Performance Tips

1. **First Load**: Initial data loading takes 30-60 seconds per session
2. **Cache Persistence**: Always use volume mounting for cache in production
3. **Memory Usage**: ~500MB RAM per session loaded
4. **Concurrent Users**: Single worker handles ~10 concurrent users efficiently

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs <container-id>

# Debug interactively
docker run -it f1-telemetry-app /bin/bash
```

### Data Loading Issues
- Ensure internet connectivity for FastF1 API access
- Check if race/session exists in FastF1 database
- Verify cache directory permissions

### Performance Issues
- Increase worker timeout: `--timeout 600`
- Add more workers: `--workers 2`
- Use persistent cache volumes

## Development

### Project Structure
```
f1-simulator/
├── app.py              # Main Dash application
├── requirements.txt    # Python dependencies
├── Dockerfile         # Container configuration
├── docker-compose.yml # Multi-service setup
├── nginx.conf         # Reverse proxy config
├── main.py           # Original matplotlib analysis
└── cache/            # FastF1 data cache
```

### Adding New Features

1. **New Visualizations**: Add Plotly charts in `app.py`
2. **Additional Data**: Extend FastF1 queries in callbacks
3. **UI Improvements**: Modify Dash layout components
4. **Performance**: Add caching with `@lru_cache` decorator

## License

This project uses FastF1 for F1 data access. Please respect Formula 1 and FIA data usage policies.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test with Docker locally
4. Submit a pull request

## Support

For issues related to:
- **F1 Data**: Check [FastF1 documentation](https://docs.fastf1.dev/)
- **Dash Framework**: See [Dash documentation](https://dash.plotly.com/)
- **Container Issues**: Review Docker logs and ensure proper resource allocation
