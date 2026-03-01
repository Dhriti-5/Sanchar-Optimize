# Sanchar-Optimize Backend - Phase 2

**Scalable FastAPI Backend for Agentic Content Resiliency System**

## 🏗️ Architecture Overview

This backend implements three core agentic components:

1. **Network Sentry Agent** - Predictive network monitoring with LSTM models
2. **Modality Orchestrator** - AI-powered decision engine using Amazon Bedrock
3. **Multi-Modal Transformer** - RAG-based content summarization pipeline

## 📁 Project Structure

```
Backend/
├── main.py                      # FastAPI application entry point
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment configuration template
├── README.md                    # This file
│
├── app/
│   ├── __init__.py
│   ├── api/                     # API endpoints
│   │   ├── __init__.py
│   │   ├── telemetry.py         # Telemetry ingestion endpoints
│   │   ├── modality.py          # Modality decision endpoints
│   │   └── health.py            # Health check endpoints
│   │
│   ├── core/                    # Core configuration
│   │   ├── __init__.py
│   │   ├── config.py            # Application settings
│   │   ├── logging_config.py    # Logging configuration
│   │   └── security.py          # Security utilities
│   │
│   ├── models/                  # Data models
│   │   ├── __init__.py
│   │   ├── telemetry.py         # Telemetry data models
│   │   ├── modality.py          # Modality decision models
│   │   └── content.py           # Content models
│   │
│   ├── services/                # Business logic
│   │   ├── __init__.py
│   │   ├── network_sentry.py    # Network prediction service
│   │   ├── modality_orchestrator.py  # Decision engine service
│   │   └── multi_modal_transformer.py  # Content transformation service
│   │
│   ├── ml/                      # Machine learning models
│   │   ├── __init__.py
│   │   ├── lstm_predictor.py    # LSTM time-series prediction
│   │   └── model_loader.py      # Model loading utilities
│   │
│   ├── aws/                     # AWS integrations
│   │   ├── __init__.py
│   │   ├── bedrock_client.py    # Amazon Bedrock client
│   │   ├── timestream_client.py # AWS Timestream client
│   │   ├── s3_client.py         # S3 storage client
│   │   └── lambda_edge.py       # Lambda@Edge deployment
│   │
│   ├── db/                      # Database clients
│   │   ├── __init__.py
│   │   ├── redis_client.py      # Redis cache
│   │   └── dynamodb_client.py   # DynamoDB session store
│   │
│   └── utils/                   # Utilities
│       ├── __init__.py
│       ├── telemetry_processor.py
│       └── validators.py
│
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── property/                # Property-based tests (Hypothesis)
│
├── deployment/                  # Deployment configurations
│   ├── docker/
│   │   └── Dockerfile
│   ├── lambda/
│   │   └── template.yaml        # SAM template
│   └── terraform/               # Infrastructure as Code
│
└── scripts/                     # Utility scripts
    ├── train_lstm_model.py
    └── setup_aws_resources.py
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- AWS Account with Bedrock access
- Redis (optional, for caching)

### 2. Installation

```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
# Edit .env with your AWS credentials
```

### 3. Configuration

Edit `.env` file with your credentials:
- AWS credentials
- Amazon Bedrock model ID
- Database connection strings

### 4. Run Development Server

```powershell
# Run with hot reload
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Test the API

```powershell
# Health check
curl http://localhost:8000/api/v1/health

# View API documentation
# Open: http://localhost:8000/docs
```

## 📡 API Endpoints

### Health & Status
- `GET /` - Root endpoint
- `GET /api/v1/health` - Health check
- `GET /api/v1/health/ready` - Readiness probe
- `GET /api/v1/health/live` - Liveness probe

### Telemetry
- `POST /api/v1/telemetry` - Submit network telemetry
- `POST /api/v1/telemetry/batch` - Batch telemetry submission
- `GET /api/v1/telemetry/predict` - Get signal drop prediction

### Modality Decision
- `POST /api/v1/modality/decide` - Get modality transition decision
- `POST /api/v1/modality/panic` - Handle panic signal from extension
- `GET /api/v1/modality/status/{session_id}` - Get current modality status

### Content Transformation
- `POST /api/v1/transform/summary` - Generate AI summary
- `GET /api/v1/transform/transcript/{content_id}` - Get cached transcript

## 🧪 Testing

```powershell
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run property-based tests
pytest tests/property/

# Run specific test file
pytest tests/unit/test_network_sentry.py
```

## 🔧 Development

### Code Quality

```powershell
# Format code
black .

# Lint
flake8

# Type checking
mypy app/
```

### Training ML Models

```powershell
# Train LSTM predictor
python scripts/train_lstm_model.py --data ./data/telemetry.csv
```

## 🚢 Deployment

### Docker

```powershell
# Build image
docker build -t sanchar-optimize-backend -f deployment/docker/Dockerfile .

# Run container
docker run -p 8000:8000 --env-file .env sanchar-optimize-backend
```

### AWS Lambda@Edge

```powershell
# Deploy with SAM
cd deployment/lambda
sam build
sam deploy --guided
```

### Terraform

```powershell
# Initialize
cd deployment/terraform
terraform init

# Plan
terraform plan

# Apply
terraform apply
```

## 📊 Monitoring

- **Metrics**: Prometheus metrics exposed at `/metrics`
- **Logs**: Structured JSON logging to stdout
- **Tracing**: AWS X-Ray integration (optional)

## 🔐 Security

- CORS configured for extension origins
- Rate limiting per IP/session
- Input validation with Pydantic
- AWS credentials via IAM roles (production)

## 🤝 Contributing

1. Check the implementation against [design.md](../design.md)
2. Follow property-based testing guidelines
3. Maintain >80% code coverage
4. All tests must pass

## 📚 Additional Resources

- [Design Document](../design.md)
- [Requirements](../requirements.md)
- [Phase 1 Quick Start](../QUICK_START_PHASE1.md)
- [Extension README](../extension/README.md)

## 📝 License

Built for **AI for Bharat Hackathon 2026** by Team Eka

---

**Status**: Phase 2 - Backend Implementation Complete ✅
