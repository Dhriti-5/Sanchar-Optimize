# Sanchar-Optimize Frontend Deployment Script
# This script helps deploy the landing page to various platforms

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('s3', 'github', 'netlify', 'local')]
    [string]$Platform = 'local'
)

Write-Host "Sanchar-Optimize Frontend Deployment" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

# Navigate to frontend directory
$frontendPath = Join-Path $PSScriptRoot "."
Set-Location $frontendPath

# Verify extension.zip exists
if (-not (Test-Path "extension.zip")) {
    Write-Host "WARNING: extension.zip not found. Creating it now..." -ForegroundColor Yellow
    $extensionPath = Join-Path (Split-Path $frontendPath -Parent) "extension"
    
    if (Test-Path $extensionPath) {
        Compress-Archive -Path "$extensionPath\*" -DestinationPath "extension.zip" -Force
        Write-Host "Created extension.zip" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Extension folder not found at: $extensionPath" -ForegroundColor Red
        exit 1
    }
}

# Verify required files
$requiredFiles = @('index.html', 'styles.css', 'script.js')
$missingFiles = $requiredFiles | Where-Object { -not (Test-Path $_) }

if ($missingFiles.Count -gt 0) {
    Write-Host "ERROR: Missing required files:" -ForegroundColor Red
    $missingFiles | ForEach-Object { Write-Host "   - $_" -ForegroundColor Red }
    exit 1
}

Write-Host "All required files present`n" -ForegroundColor Green

# Deployment based on platform
switch ($Platform) {
    's3' {
        Write-Host "Deploying to AWS S3..." -ForegroundColor Cyan
        
        $bucketName = Read-Host "Enter S3 bucket name (e.g. sanchar-optimize-landing)"
        
        if ([string]::IsNullOrWhiteSpace($bucketName)) {
            Write-Host "ERROR: Bucket name is required" -ForegroundColor Red
            exit 1
        }
        
        # Check if AWS CLI is installed
        $awsCli = Get-Command aws -ErrorAction SilentlyContinue
        if (-not $awsCli) {
            Write-Host "ERROR: AWS CLI not found. Please install it first:" -ForegroundColor Red
            Write-Host "   https://aws.amazon.com/cli/" -ForegroundColor Yellow
            exit 1
        }
        
        # Sync to S3
        Write-Host "Uploading files to s3://$bucketName..." -ForegroundColor Yellow
        aws s3 sync . "s3://$bucketName" --exclude "*.md" --exclude "deploy.ps1" --delete
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Files uploaded successfully" -ForegroundColor Green
            
            # Enable static website hosting
            Write-Host "Enabling static website hosting..." -ForegroundColor Yellow
            aws s3 website "s3://$bucketName" --index-document index.html --error-document index.html
            
            $region = aws configure get region
            if ([string]::IsNullOrWhiteSpace($region)) { $region = "ap-south-1" }
            
            $websiteUrl = "http://$bucketName.s3-website-$region.amazonaws.com"
            
            Write-Host "`nDeployment complete!" -ForegroundColor Green
            Write-Host "Website URL: $websiteUrl" -ForegroundColor Cyan
            Write-Host "`nNote: Ensure the S3 bucket has public read permissions." -ForegroundColor Yellow
        } else {
            Write-Host "ERROR: Deployment failed" -ForegroundColor Red
            exit 1
        }
    }
    
    'github' {
        Write-Host "Preparing for GitHub Pages..." -ForegroundColor Cyan
        
        $gitRoot = Split-Path $frontendPath -Parent
        Set-Location $gitRoot
        
        # Check if git is initialized
        if (-not (Test-Path ".git")) {
            Write-Host "ERROR: Not a git repository. Initialize git first:" -ForegroundColor Red
            Write-Host "   git init" -ForegroundColor Yellow
            Write-Host "   git add ." -ForegroundColor Yellow
            Write-Host "   git commit -m 'Initial commit'" -ForegroundColor Yellow
            Write-Host "   git remote add origin <your-repo-url>" -ForegroundColor Yellow
            exit 1
        }
        
        Write-Host "Creating gh-pages branch..." -ForegroundColor Yellow
        git subtree push --prefix frontend origin gh-pages
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "`nPushed to gh-pages branch!" -ForegroundColor Green
            Write-Host "Your site will be available at:" -ForegroundColor Cyan
            Write-Host "https://yourusername.github.io/repository-name" -ForegroundColor Cyan
            Write-Host "`nNote: Replace with your actual GitHub username and repo name." -ForegroundColor Yellow
        } else {
            Write-Host "ERROR: GitHub Pages deployment failed" -ForegroundColor Red
            exit 1
        }
    }
    
    'netlify' {
        Write-Host "Preparing for Netlify..." -ForegroundColor Cyan
        Write-Host "`nOptions for Netlify deployment:" -ForegroundColor Yellow
        Write-Host "1. Drag and Drop: Visit https://app.netlify.com/drop" -ForegroundColor White
        Write-Host "2. Netlify CLI: Run 'netlify deploy --prod'" -ForegroundColor White
        
        $useNetlifyCli = Read-Host "`nDo you want to use Netlify CLI? (y/n)"
        
        if ($useNetlifyCli -eq 'y') {
            $netlifyCli = Get-Command netlify -ErrorAction SilentlyContinue
            
            if (-not $netlifyCli) {
                Write-Host "Installing Netlify CLI..." -ForegroundColor Yellow
                npm install -g netlify-cli
            }
            
            Write-Host "Deploying to Netlify..." -ForegroundColor Yellow
            netlify deploy --prod --dir .
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "`nDeployed to Netlify!" -ForegroundColor Green
            }
        } else {
            Write-Host "`nCurrent directory: $frontendPath" -ForegroundColor Cyan
            Write-Host "Drag and drop this folder to: https://app.netlify.com/drop" -ForegroundColor Yellow
        }
    }
    
    'local' {
        Write-Host "Starting local server..." -ForegroundColor Cyan
        
        # Try Python HTTP server
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) {
            $python = Get-Command python3 -ErrorAction SilentlyContinue
        }
        
        if ($python) {
            Write-Host "Starting Python HTTP server on port 8000" -ForegroundColor Green
            Write-Host "Open: http://localhost:8000" -ForegroundColor Cyan
            Write-Host "`nPress Ctrl+C to stop the server`n" -ForegroundColor Yellow
            
            python -m http.server 8000
        } else {
            # Try npx serve as fallback
            $node = Get-Command node -ErrorAction SilentlyContinue
            
            if ($node) {
                Write-Host "Starting Node.js server on port 3000" -ForegroundColor Green
                Write-Host "Open: http://localhost:3000" -ForegroundColor Cyan
                Write-Host "`nPress Ctrl+C to stop the server`n" -ForegroundColor Yellow
                
                npx serve -l 3000 .
            } else {
                Write-Host "ERROR: Neither Python nor Node.js found" -ForegroundColor Red
                Write-Host "`nPlease install one of the following:" -ForegroundColor Yellow
                Write-Host "  - Python: https://www.python.org/downloads/" -ForegroundColor White
                Write-Host "  - Node.js: https://nodejs.org/" -ForegroundColor White
                exit 1
            }
        }
    }
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Deployment script completed" -ForegroundColor Green
