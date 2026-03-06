# Automated Deployment Fix Script
# This script will delete the failed stack and redeploy cleanly

param(
    [string]$AwsRegion = "ap-south-1",
    [string]$StackName = "sanchar-optimize-production",
    [switch]$SkipConfirmation = $false
)

# Color output helpers
function Write-Success { param([string]$Message) Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Error { param([string]$Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }
function Write-Info { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Warning { param([string]$Message) Write-Host "[WARNING] $Message" -ForegroundColor Yellow }

Write-Host "`n===========================================================`n" -ForegroundColor Cyan
Write-Host "   Sanchar-Optimize Deployment Fix Automation" -ForegroundColor Cyan
Write-Host "===========================================================`n" -ForegroundColor Cyan

# Step 1: Check current stack status
Write-Info "Step 1/4: Checking current stack status..."
$stackStatus = aws cloudformation describe-stacks --stack-name $StackName --region $AwsRegion --query 'Stacks[0].StackStatus' --output text 2>&1

if ($stackStatus -like "*does not exist*" -or $LASTEXITCODE -ne 0) {
    Write-Success "No existing stack found. Proceeding with fresh deployment..."
    $needsCleanup = $false
} else {
    Write-Warning "Stack exists with status: $stackStatus"
    
    if ($stackStatus -eq "ROLLBACK_COMPLETE" -or $stackStatus -like "*FAILED*") {
        Write-Warning "Stack is in failed state and needs cleanup"
        $needsCleanup = $true
    } elseif ($stackStatus -like "*IN_PROGRESS*") {
        Write-Error "Stack operation is currently in progress. Please wait for it to complete."
        exit 1
    } else {
        Write-Warning "Stack exists in state: $stackStatus"
        if (-not $SkipConfirmation) {
            $response = Read-Host "Do you want to delete and recreate it? (yes/no)"
            if ($response -ne "yes") {
                Write-Error "Deployment cancelled by user"
                exit 0
            }
        }
        $needsCleanup = $true
    }
}

# Step 2: Delete stack if needed
if ($needsCleanup) {
    Write-Info "Step 2/4: Deleting failed stack..."
    
    aws cloudformation delete-stack --stack-name $StackName --region $AwsRegion
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Delete command issued successfully"
        Write-Info "Waiting for stack deletion (this takes 2-5 minutes)..."
        
        # Wait for deletion with timeout
        $timeout = 600  # 10 minutes
        $elapsed = 0
        $interval = 10
        
        while ($elapsed -lt $timeout) {
            Start-Sleep -Seconds $interval
            $elapsed += $interval
            
            $checkStatus = aws cloudformation describe-stacks --stack-name $StackName --region $AwsRegion --query 'Stacks[0].StackStatus' --output text 2>&1
            
            if ($checkStatus -like "*does not exist*" -or $LASTEXITCODE -ne 0) {
                Write-Success "Stack deleted successfully!"
                break
            } else {
                Write-Host "." -NoNewline
            }
        }
        
        if ($elapsed -ge $timeout) {
            Write-Error "Stack deletion timed out. Check AWS Console:"
            Write-Host "https://console.aws.amazon.com/cloudformation/home?region=$AwsRegion#/stacks" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Error "Failed to issue delete command. Check AWS credentials and permissions."
        exit 1
    }
} else {
    Write-Info "Step 2/4: Stack cleanup not needed"
}

# Step 3: Validate template
Write-Info "`nStep 3/4: Validating SAM template..."
Set-Location $PSScriptRoot

$validation = sam validate --template Backend\deployment\lambda\template-complete.yaml --lint 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Success "Template is valid"
} else {
    Write-Error "Template validation failed:"
    Write-Host $validation
    exit 1
}

# Step 4: Deploy fresh stack
Write-Info "`nStep 4/4: Deploying fresh stack..."
Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "Starting deployment..." -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

.\Backend\deployment\deploy.ps1 -Environment production -AwsRegion $AwsRegion

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n===========================================================`n" -ForegroundColor Green
    Write-Success "DEPLOYMENT SUCCESSFUL!"
    Write-Host "===========================================================`n" -ForegroundColor Green
    
    # Show API endpoint
    if (Test-Path "backend-url.txt") {
        $apiUrl = Get-Content "backend-url.txt"
        Write-Info "API Endpoint saved to backend-url.txt:"
        Write-Host "  $apiUrl" -ForegroundColor Green
    }
} else {
    Write-Host "`n===========================================================`n" -ForegroundColor Red
    Write-Error "DEPLOYMENT FAILED"
    Write-Host "===========================================================`n" -ForegroundColor Red
    
    Write-Error "Deployment failed. Check deploy.log for details"
    Write-Info "View errors: Get-Content deploy.log | Select-String 'error|failed' -CaseSensitive"
    exit 1
}
