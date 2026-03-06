#!/bin/bash

# Sanchar-Optimize AWS Deployment Script (Bash)
# Automates build, packaging, and deployment to AWS

set -e

# Configuration
ENVIRONMENT="${1:-production}"
AWS_REGION="${2:-ap-south-1}"
STACK_NAME="sanchar-optimize-${ENVIRONMENT}"
SKIP_BUILD="${SKIP_BUILD:-false}"
SKIP_DEPLOY="${SKIP_DEPLOY:-false}"
DRY_RUN="${DRY_RUN:-false}"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
write_header() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║ $1 $(printf '%*s' $((60 - ${#1})) '' )║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

write_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

write_error() {
    echo -e "${RED}✗ $1${NC}"
}

write_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

write_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# ============================================================================
# Prerequisites Check
# ============================================================================

write_header "Checking Prerequisites"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    write_error "AWS CLI not found. Please install AWS CLI v2"
    write_info "Download: https://aws.amazon.com/cli/"
    exit 1
fi
write_success "AWS CLI: $(aws --version 2>&1 | head -1)"

# Check SAM CLI
if ! command -v sam &> /dev/null; then
    write_error "SAM CLI not found. Please install AWS SAM CLI"
    write_info "Download: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html"
    exit 1
fi
write_success "SAM CLI: $(sam --version)"

# Verify AWS Credentials
if ! ACCOUNT_ID=$(aws sts get-caller-identity --region "$AWS_REGION" --query Account --output text 2>/dev/null); then
    write_error "AWS credentials not configured or invalid"
    write_info "Run: aws configure"
    exit 1
fi
write_success "AWS Account: $ACCOUNT_ID"
write_success "AWS Region: $AWS_REGION"

# ============================================================================
# Project Setup
# ============================================================================

write_header "Setting Up Deployment"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKEND_DIR="$PROJECT_DIR/Backend"
LAMBDA_DIR="$BACKEND_DIR/deployment/lambda"

write_info "Project Directory: $PROJECT_DIR"
write_info "Backend Directory: $BACKEND_DIR"
write_info "Lambda Directory: $LAMBDA_DIR"

# Check required files
for file in "$LAMBDA_DIR/template-complete.yaml" "$BACKEND_DIR/requirements.txt" "$BACKEND_DIR/main.py"; do
    if [ ! -f "$file" ]; then
        write_error "Missing required file: $file"
        exit 1
    fi
done

write_success "All required files found"

# ============================================================================
# Build Phase
# ============================================================================

if [ "$SKIP_BUILD" != "true" ]; then
    write_header "Building Application"
    
    cd "$BACKEND_DIR"
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        write_info "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    write_info "Installing packages..."
    pip install -q -r requirements.txt
    
    if [ $? -eq 0 ]; then
        write_success "Dependencies installed"
    else
        write_error "Failed to install dependencies"
        exit 1
    fi
    
    # Validate Python syntax
    write_info "Validating Python syntax..."
    for file in main.py app/lambda_handlers/backend.py app/lambda_handlers/network_sentry.py app/lambda_handlers/modality_orchestrator.py app/lambda_handlers/transformer.py; do
        python3 -m py_compile "$file"
        if [ $? -eq 0 ]; then
            write_success "$file"
        else
            write_error "Syntax error in $file"
            exit 1
        fi
    done
    
    # Test imports
    write_info "Testing imports..."
    python3 -c "from main import app; print('FastAPI app loaded successfully')" 2>&1
    if [ $? -eq 0 ]; then
        write_success "FastAPI app imports successfully"
    else
        write_error "Import error in FastAPI app"
        exit 1
    fi
fi

# ============================================================================
# SAM Build and Package
# ============================================================================

write_header "Building SAM Application"

cd "$PROJECT_DIR"

write_info "Running SAM build..."
if [ "$DRY_RUN" = "true" ]; then
    sam build --template "$LAMBDA_DIR/template-complete.yaml" --debug --use-container
else
    sam build --template "$LAMBDA_DIR/template-complete.yaml" --use-container 2>&1 | tee "$PROJECT_DIR/build.log"
fi

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    write_success "SAM build completed"
else
    write_error "SAM build failed. Check build.log for details"
    write_info "Common issues:"
    write_info "  - Missing Python dependencies: pip install -r requirements.txt"
    write_info "  - Invalid template syntax: sam validate --lint"
    write_error "Build log saved to: $PROJECT_DIR/build.log"
    exit 1
fi

# ============================================================================
# Deployment
# ============================================================================

if [ "$SKIP_DEPLOY" != "true" ]; then
    write_header "Deploying to AWS"
    
    # Create S3 bucket for SAM artifacts
    ARTIFACT_BUCKET="sanchar-optimize-sam-artifacts-${ACCOUNT_ID}"
    
    write_info "Checking artifact bucket: $ARTIFACT_BUCKET"
    if ! aws s3api head-bucket --bucket "$ARTIFACT_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
        write_info "Creating artifact S3 bucket..."
        aws s3api create-bucket \
            --bucket "$ARTIFACT_BUCKET" \
            --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION" 2>/dev/null
        write_success "Artifact bucket created: $ARTIFACT_BUCKET"
    fi
    
    write_info "Deploying CloudFormation stack..."
    write_info "Stack Name: $STACK_NAME"
    write_info "Region: $AWS_REGION"
    
    if [ "$DRY_RUN" = "true" ]; then
        sam deploy \
            --template .aws-sam/build/template.yaml \
            --stack-name "$STACK_NAME" \
            --s3-bucket "$ARTIFACT_BUCKET" \
            --region "$AWS_REGION" \
            --parameter-overrides EnvironmentName="$ENVIRONMENT" \
            --no-execute-changeset
        write_warning "DRY RUN: No resources created"
    else
        sam deploy \
            --template .aws-sam/build/template.yaml \
            --stack-name "$STACK_NAME" \
            --s3-bucket "$ARTIFACT_BUCKET" \
            --region "$AWS_REGION" \
            --parameter-overrides EnvironmentName="$ENVIRONMENT" AllowMockResponses=false \
            --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
            --no-fail-on-empty-changeset 2>&1 | tee "$PROJECT_DIR/deploy.log"
        
        if [ ${PIPESTATUS[0]} -eq 0 ]; then
            write_success "CloudFormation deployment completed"
        else
            write_error "CloudFormation deployment failed"
            echo ""
            write_info "Troubleshooting steps:"
            write_info "1. Check deploy.log in: $PROJECT_DIR/deploy.log"
            write_info "2. View CloudFormation events:"
            echo "   aws cloudformation describe-stack-events --stack-name $STACK_NAME --region $AWS_REGION --max-items 20"
            write_info "3. Validate template:"
            echo "   sam validate --template $LAMBDA_DIR/template-complete.yaml --lint"
            write_info "4. Check CloudFormation console:"
            echo "   https://console.aws.amazon.com/cloudformation/home?region=$AWS_REGION"
            echo ""
            write_info "Common deployment errors:"
            write_info "  - IAM permissions: Ensure deploying user has CloudFormation, Lambda, API Gateway, S3, DynamoDB, Timestream permissions"
            write_info "  - Resource limits: Check AWS service quotas"
            write_info "  - Invalid parameters: Review template parameter values"
            write_info "  - Bedrock access: Ensure Bedrock is enabled in your account"
            exit 1
        fi
    fi
fi

# ============================================================================
# Extract Outputs
# ============================================================================

write_header "Deployment Summary"

OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' \
    --output json 2>/dev/null)

if [ ! -z "$OUTPUTS" ]; then
    write_info "Stack Outputs:"
    echo ""
    echo "$OUTPUTS" | jq -r '.[] | "  \(.Key):\n    \(.Value)"'
    
    # Save API endpoint
    API_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.Key=="ApiEndpoint") | .Value' 2>/dev/null)
    if [ ! -z "$API_ENDPOINT" ]; then
        echo "$API_ENDPOINT" > backend-url.txt
        write_success "Backend URL saved to backend-url.txt"
        echo ""
        write_info "Production Backend URL:"
        echo -e "    ${GREEN}$API_ENDPOINT${NC}"
    fi
fi

# ============================================================================
# Next Steps
# ============================================================================

write_header "Next Steps"

write_info "1. Update extension configuration:"
echo "    File: extension/utils/api-client.js"
echo "    Find: const BASE_URL = '...'"
echo "    Update with your API endpoint from backend-url.txt"

write_info "2. Load extension in Chrome:"
echo "    chrome://extensions/ → Load unpacked → select /extension"

write_info "3. Test on a video streaming site:"
echo "    YouTube or other streaming platform"

write_info "4. Monitor deployment:"
echo "    CloudWatch: https://console.aws.amazon.com/cloudwatch"
echo "    CloudFormation: https://console.aws.amazon.com/cloudformation"

write_success "Deployment process complete!"
