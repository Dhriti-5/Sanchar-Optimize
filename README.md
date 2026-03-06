# Sanchar-Optimize 🚀

**Agentic Content Resiliency System for Rural India's Educational Access**

[![AWS](https://img.shields.io/badge/AWS-Lambda%40Edge-orange)](https://aws.amazon.com/lambda/edge/)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon%20Bedrock-Claude%203.5-blue)](https://aws.amazon.com/bedrock/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green)](https://www.python.org/)


> AI for Bharat Hackathon 2026 | Track 02 - AI for Media, Content & Digital Experiences

## 🎯 Problem Statement

Students and workers in rural India and high-speed train/bus commuters face a critical challenge: **unstable 4G/5G networks** that interrupt educational video streaming with constant buffering. Traditional Adaptive Bitrate (ABR) streaming reactively reduces quality until buffering occurs, creating a frustrating learning experience.

## 💡 Solution: Agentic Cognitive Fallback

Sanchar-Optimize employs **true agentic behavior** with predictive intelligence. The system:

1. **Predicts** network signal drops before they occur using GPS velocity and historical patterns
2. **Proactively transforms** content modality: Video → Audio → AI-Generated Summary
3. **Maintains continuity** with Zero-Buffer experience and contextual memory

Unlike reactive ABR, Sanchar-Optimize uses AI agents powered by **Amazon Bedrock** to make intelligent, context-aware decisions about content adaptation.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Device Layer                     │
│  Video Player | GPS Sensor | Network Monitor            │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────┼───────────────────────────────────────┐
│      AWS Edge Layer (Lambda@Edge)                        │
│                 │                                         │
│  ┌──────────────▼──────────┐  ┌────────────────────┐   │
│  │ Network Sentry Agent    │  │ Modality           │   │
│  │ (LSTM Prediction)       │─→│ Orchestrator       │   │
│  └─────────────────────────┘  │ (AI Decision)      │   │
│                                └──────────┬─────────┘   │
└────────────────────────────────────────────┼───────────┘
                                             │
┌─────────────────────────────────────────────┼───────────┐
│         AWS Regional Layer                  │            │
│                                ┌────────────▼─────────┐ │
│                                │ Multi-Modal          │ │
│                                │ Transformer          │ │
│                                │ (RAG Pipeline)       │ │
│                                └──────────┬───────────┘ │
│  ┌─────────��───┐  ┌─────────────────┐    │            │
│  │ Amazon      │  │ Time-Series DB  │    │            │
│  │ Bedrock     │←─┤ (Timestream)    │    │            │
│  │ Claude 3.5  │  └─────────────────┘    │            │
│  └─────────────┘                          │            │
└───────────────────────────────────────────────────────┘
```

## 🤖 Core Agentic Components

### 1. **Network Sentry Agent** 🔍
- **Predictive monitoring** using LSTM time-series models
- Analyzes signal strength, latency, packet loss, GPS velocity
- Triggers Signal_Drop_Events with >75% confidence
- Adapts monitoring frequency (1-4 Hz) based on movement speed

### 2. **Modality Orchestrator** 🎭
- **AI-powered decision engine** using Amazon Bedrock (Claude 3.5 Sonnet)
- Evaluates bandwidth, content importance, user context
- Makes autonomous modality transitions:
  - `>1 Mbps` → Maintain VIDEO
  - `500 Kbps - 1 Mbps` → Transition to AUDIO
  - `<500 Kbps` → Transition to AI TEXT_SUMMARY

### 3. **Multi-Modal Transformer** 📝
- **RAG-based pipeline** for intelligent content summarization
- Extracts transcripts, visual context, key concepts
- Generates compressed summaries (<10% original size)
- Creates AI images for visual demonstrations

## ✨ Key Features

### 🎯 Zero-Buffer Continuity
- Seamless modality transitions in <2 seconds
- No visible buffering indicators
- Proactive handshake initiated before network failure

### 🧠 Contextual Memory
- Tracks exact content position across transitions
- Perfect resume from video → audio → video
- 7-day session persistence

### 📊 Intelligent Content Analysis
- Semantic understanding of educational content
- Identifies critical learning moments
- Preserves >90% of key concepts in summaries

### 🌍 Edge-First Design
- AWS Lambda@Edge for <500ms decision latency
- Geographic distribution for rural accessibility
- Automatic failover to regional infrastructure

## 📊 Quick Start

### Prerequisites
- Python 3.9+
- Chrome Browser
- AWS Account (for production deployment)

### Local Development Setup

**1. Backend Setup:**
```powershell
# Navigate to backend directory
cd Backend

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your AWS credentials

# Start the FastAPI server
python main.py
```

**2. Chrome Extension Setup:**
```powershell
# Load extension in Chrome
# 1. Navigate to chrome://extensions/
# 2. Enable "Developer mode" (top right)
# 3. Click "Load unpacked"
# 4. Select the extension/ folder

# Test on any YouTube video!
```

### AWS Deployment

The application uses AWS Lambda, Amazon Bedrock, DynamoDB, and TimeStream for production deployment. Key deployment files:
- `Backend/deployment/deploy.sh` - Automated deployment script
- `Backend/samconfig.toml` - AWS SAM configuration

For production deployment, ensure you have:
- AWS CLI configured with appropriate credentials
- Amazon Bedrock access enabled in your region
- AWS SAM CLI installed

## 📚 Documentation

- **[Backend README](Backend/README.md)** - Backend API documentation and architecture
- **[Requirements Document](requirements.md)** - Detailed functional requirements
- **[Design Document](design.md)** - System architecture and implementation details

## 🏆 Why This is Truly Agentic

Sanchar-Optimize demonstrates **genuine agentic behavior** because:

1. **Autonomous Perception**: Agents actively monitor environment (network conditions, GPS, content)
2. **Intelligent Reasoning**: Uses Amazon Bedrock for context-aware decision making, not rule-based logic
3. **Proactive Action**: Takes preventive measures before problems occur (predictive handshake)
4. **Adaptive Learning**: LSTM models adapt to regional network patterns
5. **Goal-Oriented**: Optimizes for learning continuity and content preservation

This is NOT just reactive quality adjustment—it's **cognitive content transformation** powered by AI agents.

## 🛠️ Technology Stack

### Backend
- **FastAPI** - High-performance Python web framework
- **Amazon Bedrock** - Claude 3.5 Sonnet for AI summarization
- **AWS Lambda** - Serverless compute for edge processing
- **DynamoDB** - Session persistence and state management
- **Amazon TimeStream** - Time-series telemetry data storage
- **LSTM Models** - Network prediction and pattern recognition

### Frontend/Extension
- **Chrome Extension API** - Browser integration
- **JavaScript ES6+** - Modern client-side logic
- **WebRTC** - Real-time network monitoring
- **Service Workers** - Background processing

### Infrastructure
- **AWS SAM** - Serverless application deployment
- **CloudWatch** - Monitoring and logging
- **S3** - Static asset storage

## 📁 Project Structure

```
Sanchar-Optimize/
├── Backend/                 # FastAPI backend server
│   ├── app/                # Application modules
│   │   ├── api/           # API endpoints (health, content, telemetry, etc.)
│   │   ├── aws/           # AWS service clients (Bedrock, DynamoDB, S3)
│   │   ├── core/          # Core configuration and logging
│   │   ├── lambda_handlers/  # AWS Lambda functions
│   │   ├── ml/            # Machine learning models (LSTM)
│   │   ├── models/        # Data models and schemas
│   │   └── services/      # Business logic services
│   ├── deployment/        # Deployment scripts and configs
│   ├── scripts/           # Utility scripts (training, setup)
│   └── main.py           # Application entry point
├── extension/             # Chrome browser extension
│   ├── background/       # Service worker scripts
│   ├── content/          # Content scripts for page injection
│   ├── popup/            # Extension popup UI
│   ├── ui/               # Overlay and UI components
│   └── utils/            # Helper utilities (API client, telemetry)
├── design.md             # System design documentation
└── requirements.md       # Functional requirements
```

## 🌟 Impact

- **🎓 Educational Access**: Enables uninterrupted learning for rural students
- **🚄 Commuter Learning**: Supports mobile learners on trains/buses
- **📉 Data Efficiency**: 98% data reduction in blackout mode
- **🇮🇳 Bharat Focus**: Designed for Indian telecom infrastructure


## 👥 Team : Eka

**Built for AI for Bharat Hackathon 2026**

- **Developer**: [@Dhriti-5](https://github.com/Dhriti-5)

*Transforming network instability from a barrier into an opportunity for intelligent content adaptation.*
