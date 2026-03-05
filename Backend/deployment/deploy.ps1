# Sanchar-Optimize AWS Deployment Script
# Automates build, packaging, and deployment to AWS

param(
    [string]$Environment = "production",
    [string]$AwsRegion = "ap-south-1",
    [string]$StackName = "sanchar-optimize-$Environment",
    [switch]$SkipBuild = $false,
    [switch]$SkipDeploy = $false,
    [switch]$DryRun = $false
)

# Color output helpers
function Write-Header {
    param([string]$Message)
    Write-Host @"
╔════════════════════════════════════════════════════════════════╗
║ $Message $(' ' * (60 - $Message.Length))║
╚════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

# ============================================================================
# Prerequisites Check
# ============================================================================

Write-Header "Checking Prerequisites"

# Check AWS CLI
try {
    $awsVersion = aws --version 2>$null
    Write-Success "AWS CLI: $awsVersion"
} catch {
    Write-Error "AWS CLI not found. Please install AWS CLI v2"
    Write-Info "Download: https://aws.amazon.com/cli/"
    exit 1
}

# Check SAM CLI
try {
    $samVersion = sam --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "SAM CLI: $samVersion"
    }
} catch {
    # SAM CLI not in PATH, try to find it
    $samPath = "C:\Program Files\Amazon\AWSSAMCLI\bin"
    if (Test-Path $samPath) {
        Write-Info "SAM CLI found but not in PATH. Adding to current session..."
        $env:Path = "$samPath;" + $env:Path
        $samVersion = sam --version 2>$null
        Write-Success "SAM CLI: $samVersion"
    } else {
        Write-Error "SAM CLI not found. Please install AWS SAM CLI"
        Write-Info "Download: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html"
        exit 1
    }
}

# Verify AWS Credentials
try {
    $identity = aws sts get-caller-identity --region $AwsRegion 2>$null | ConvertFrom-Json
    Write-Success "AWS Account: $($identity.Account)"
    Write-Success "AWS Region: $AwsRegion"
} catch {
    Write-Error "AWS credentials not configured or invalid"
    Write-Info "Run: aws configure"
    exit 1
}

# Check Bedrock access
Write-Info "Checking Amazon Bedrock availability in region..."
try {
    $bedrockCheck = aws bedrock list-foundation-models --region $AwsRegion 2>$null
    if ($bedrockCheck) {
        Write-Success "Amazon Bedrock available in $AwsRegion"
    }
} catch {
    Write-Warning "Bedrock may not be available in region $AwsRegion"
    Write-Info "Available regions for Bedrock: us-east-1, us-west-2, eu-west-1, ap-northeast-1, ap-south-1"
}

# ============================================================================
# Project Setup
# ============================================================================

Write-Header "Setting Up Deployment"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = $scriptDir | Split-Path -Parent
$projectDir = $backendDir | Split-Path -Parent
$lambdaDir = $backendDir + "\deployment\lambda"

Write-Info "Project Directory: $projectDir"
Write-Info "Backend Directory: $backendDir"
Write-Info "Lambda Directory: $lambdaDir"

# Check if required files exist
$requiredFiles = @(
    "$lambdaDir\template-complete.yaml",
    "$backendDir\requirements.txt",
    "$backendDir\main.py"
)

foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-Error "Missing required file: $file"
        exit 1
    }
}

Write-Success "All required files found"

# ============================================================================
# Build Phase
# ============================================================================

if (-not $SkipBuild) {
    Write-Header "Building Application"
    
    # Install Python dependencies
    Write-Info "Installing Python dependencies..."
    Set-Location $backendDir
    
    # Create virtual environment if needed
    if (-not (Test-Path "venv")) {
        Write-Info "Creating Python virtual environment..."
        python -m venv venv
        & ".\venv\Scripts\Activate.ps1"
    } else {
        & ".\venv\Scripts\Activate.ps1"
    }
    
    Write-Info "Installing packages..."
    pip install --quiet -q -r requirements.txt
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Dependencies installed"
    } else {
        Write-Error "Failed to install dependencies"
        exit 1
    }
    
    # Validate Python syntax
    Write-Info "Validating Python syntax..."
    $pythonFiles = @(
        "main.py",
        "app\lambda_handlers\backend.py",
        "app\lambda_handlers\network_sentry.py",
        "app\lambda_handlers\modality_orchestrator.py",
        "app\lambda_handlers\transformer.py"
    )
    
    foreach ($file in $pythonFiles) {
        python -m py_compile $file
        if ($LASTEXITCODE -eq 0) {
            Write-Success $file
        } else {
            Write-Error "Syntax error in $file"
            exit 1
        }
    }
    
    # Test imports
    Write-Info "Testing imports..."
    python -c "from main import app; print('FastAPI app loaded successfully')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "FastAPI app imports successfully"
    } else {
        Write-Error "Import error in FastAPI app"
        exit 1
    }
}

# ============================================================================
# SAM Build and Package
# ============================================================================

Write-Header "Building SAM Application"

Set-Location $projectDir

# Run SAM build
Write-Info "Running SAM build..."
if ($DryRun) {
    sam build --template $lambdaDir\template-complete.yaml --debug --use-container
} else {
    sam build --template $lambdaDir\template-complete.yaml --use-container 2>&1 | Tee-Object -FilePath "build.log"
}

if ($LASTEXITCODE -eq 0) {
    Write-Success "SAM build completed"
} else {
    Write-Error "SAM build failed. Check build.log"
    exit 1
}

# ============================================================================
# Deployment
# ============================================================================

if (-not $SkipDeploy) {
    Write-Header "Deploying to AWS"
    
    # Create S3 bucket for SAM artifacts if needed
    $artifactBucket = "sanchar-optimize-sam-artifacts-$($identity.Account)"
    
    Write-Info "Checking artifact bucket: $artifactBucket"
    try {
        aws s3api head-bucket --bucket $artifactBucket --region $AwsRegion 2>$null
    } catch {
        Write-Info "Creating artifact S3 bucket..."
        aws s3api create-bucket `
            --bucket $artifactBucket `
            --region $AwsRegion `
            --create-bucket-configuration LocationConstraint=$AwsRegion 2>$null
        Write-Success "Artifact bucket created: $artifactBucket"
    }
    
    # Run SAM deploy
    Write-Info "Deploying CloudFormation stack..."
    Write-Info "Stack Name: $StackName"
    Write-Info "Region: $AwsRegion"
    
    if ($DryRun) {
        sam deploy `
            --template .aws-sam/build/template.yaml `
            --stack-name $StackName `
            --s3-bucket $artifactBucket `
            --region $AwsRegion `
            --parameter-overrides EnvironmentName=$Environment `
            --no-execute-changeset
        Write-Warning "DRY RUN: No resources created"
    } else {
        sam deploy `
            --template .aws-sam/build/template.yaml `
            --stack-name $StackName `
            --s3-bucket $artifactBucket `
            --region $AwsRegion `
            --parameter-overrides EnvironmentName=$Environment AllowMockResponses=false `
            --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM `
            --no-fail-on-empty-changeset 2>&1 | Tee-Object -FilePath "deploy.log"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "CloudFormation deployment completed"
        } else {
            Write-Error "CloudFormation deployment failed. Check deploy.log"
            exit 1
        }
    }
}

# ============================================================================
# Extract Outputs
# ============================================================================

Write-Header "Deployment Summary"

try {
    $outputs = aws cloudformation describe-stacks `
        --stack-name $StackName `
        --region $AwsRegion `
        --query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' `
        --output json 2>$null | ConvertFrom-Json
    
    if ($outputs) {
        Write-Info "Stack Outputs:"
        Write-Host ""
        
        foreach ($output in $outputs) {
            Write-Host "  $($output.Key):" -ForegroundColor Cyan
            Write-Host "    $($output.Value)" -ForegroundColor White
        }
        
        # Save API endpoint to file
        $apiEndpoint = ($outputs | Where-Object { $_.Key -eq "ApiEndpoint" }).Value
        if ($apiEndpoint) {
            $apiEndpoint | Out-File "backend-url.txt"
            Write-Success "Backend URL saved to backend-url.txt"
            Write-Host ""
            Write-Info "Production Backend URL:"
            Write-Host "    $apiEndpoint" -ForegroundColor Green
        }
    }
} catch {
    Write-Warning "Could not retrieve stack outputs (may still be initializing)"
}

# ============================================================================
# Next Steps
# ============================================================================

Write-Header "Next Steps"

Write-Info "1. Update extension configuration:"
Write-Host "    File: extension/utils/api-client.js"
Write-Host "    Find: const BASE_URL = '...'"
Write-Host "    Update with your API endpoint from backend-url.txt"

Write-Info "2. Load extension in Chrome:"
Write-Host "    chrome://extensions/ → Load unpacked → select /extension"

Write-Info "3. Test on a video streaming site:"
Write-Host "    YouTube or other streaming platform"

Write-Info "4. Monitor deployment:"
Write-Host "    CloudWatch: https://console.aws.amazon.com/cloudwatch"
Write-Host "    CloudFormation: https://console.aws.amazon.com/cloudformation"

Write-Success "Deployment process complete!"
