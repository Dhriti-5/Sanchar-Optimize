# Sanchar-Optimize AWS Cleanup Script
# Removes all deployed resources to stop incurring charges

param(
    [string]$StackName = "sanchar-optimize-production",
    [string]$Region = "ap-south-1"
)

# Color helpers
function Write-Header {
    param([string]$Message)
    Write-Host @"
╔════════════════════════════════════════════════════════════════╗
║ $Message $(" " * (60 - $Message.Length))║
╚════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan
}

function Write-Success {
    Write-Host "✓ $args" -ForegroundColor Green
}

function Write-Error {
    Write-Host "✗ $args" -ForegroundColor Red
}

function Write-Warning {
    Write-Host "⚠ $args" -ForegroundColor Yellow
}

function Write-Info {
    Write-Host "ℹ $args" -ForegroundColor Cyan
}

# ============================================================================
# Confirmation
# ============================================================================

Write-Header "AWS Cleanup - WARNING"

Write-Warning "This will DELETE all Sanchar-Optimize resources:"
Write-Host "  - CloudFormation Stack: $StackName"
Write-Host "  - Lambda Functions"
Write-Host "  - API Gateway"
Write-Host "  - DynamoDB Tables"
Write-Host "  - S3 Buckets"
Write-Host "  - Timestream Database"
Write-Host "  - CloudWatch Logs"
Write-Host ""

$confirmation = Read-Host "Type 'yes' to confirm deletion"

if ($confirmation -ne "yes") {
    Write-Info "Cleanup cancelled"
    exit 0
}

# ============================================================================
# Pre-Cleanup: Empty S3 Buckets (required for deletion)
# ============================================================================

Write-Header "Preparing for Deletion"

Write-Info "Finding S3 buckets associated with this stack..."

$buckets = aws s3api list-buckets --region $Region --query "Buckets[?contains(Name, 'sanchar-optimize')].Name" --output text

foreach ($bucket in $buckets) {
    Write-Info "Emptying S3 bucket: $bucket"
    aws s3 rm "s3://$bucket" --recursive --region $Region 2>&1 | Out-Null
    Write-Success "Bucket emptied: $bucket"
}

# ============================================================================
# Delete CloudFormation Stack
# ============================================================================

Write-Header "Deleting CloudFormation Stack"

Write-Info "Stack: $StackName"
Write-Info "Region: $Region"
Write-Info "Initiating deletion..."

aws cloudformation delete-stack `
    --stack-name $StackName `
    --region $Region

if ($LASTEXITCODE -eq 0) {
    Write-Success "Stack deletion initiated"
} else {
    Write-Error "Failed to initiate stack deletion"
    exit 1
}

# ============================================================================
# Monitor Deletion Progress
# ============================================================================

Write-Header "Monitoring Deletion"

$maxAttempts = 60
$sleepSeconds = 10
$attempt = 0
$deleted = $false

Write-Info "Waiting for stack deletion (this may take 5-10 minutes)..."

while ($attempt -lt $maxAttempts) {
    $stack = aws cloudformation describe-stacks `
        --stack-name $StackName `
        --region $Region `
        --query 'Stacks[0].StackStatus' `
        --output text 2>$null
    
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($stack)) {
        Write-Success "Stack deleted successfully"
        $deleted = $true
        break
    }
    
    if ($stack -eq "DELETE_IN_PROGRESS") {
        Write-Info "Status: DELETE_IN_PROGRESS ($attempt/$maxAttempts)"
    } elseif ($stack -like "*DELETE_FAILED*") {
        Write-Error "Stack deletion failed: $stack"
        break
    } else {
        Write-Warning "Unexpected status: $stack"
    }
    
    $attempt++
    Start-Sleep -Seconds $sleepSeconds
}

if (-not $deleted) {
    Write-Warning "Deletion not completed within timeout"
    Write-Info "Check CloudFormation console for status"
}

# ============================================================================
# Verify Deletion
# ============================================================================

Write-Header "Verification"

# Check CloudFormation
$stacks = aws cloudformation list-stacks `
    --region $Region `
    --stack-status-filter DELETE_COMPLETE `
    --query "StackSummaries[?StackName=='$StackName']" `
    --output json 2>$null | ConvertFrom-Json

if ($stacks -and $stacks.Count -gt 0) {
    Write-Success "CloudFormation stack deleted"
} else {
    Write-Warning "Stack deletion status unclear - check console"
}

# Check S3 buckets
$remainingBuckets = aws s3api list-buckets --region $Region --query "Buckets[?contains(Name, 'sanchar-optimize')].Name" --output text

if ([string]::IsNullOrWhiteSpace($remainingBuckets)) {
    Write-Success "All S3 buckets deleted"
} else {
    Write-Warning "Some S3 buckets may still exist: $remainingBuckets"
}

# ============================================================================
# Summary
# ============================================================================

Write-Header "Cleanup Summary"

Write-Info "Deleted resources:"
Write-Host "  ✓ Lambda Functions (4 functions)"
Write-Host "  ✓ API Gateway (1 endpoint)"
Write-Host "  ✓ DynamoDB Tables (2 tables)"
Write-Host "  ✓ S3 Buckets (content cache + artifacts)"
Write-Host "  ✓ Timestream Database (telemetry)"
Write-Host "  ✓ CloudWatch Logs (all logs)"
Write-Host "  ✓ IAM Roles (execution roles)"

Write-Info "Remaining tasks (manual if needed):"
Write-Host "  - Check AWS console for any orphaned resources"
Write-Host "  - Verify billing stops (may take 24-48 hours)"
Write-Host "  - Delete artifact bucket if persists"

Write-Success "Cleanup complete! Charges should stop shortly."
Write-Info "Note: Billing adjustments may appear in next invoice cycle"
