# 🚀 Sanchar-Optimize Deployment Guide
**Version**: 2.0.0  
**Last Updated**: March 6, 2026

---

## 📋 Pre-Deployment Checklist

✅ All backend tests passed (8/8)  
✅ LSTM model operational  
✅ AI services validated  
⏳ Manual extension testing required  

---

## 🎯 Quick Deployment Steps

### Option A: Local Testing & Demo (Recommended First)

#### 1. Start Backend Server
```powershell
# Navigate to backend directory
cd d:\Projects\Sanchar-Optimize\Backend

# Activate virtual environment (if using)
.\venv\Scripts\Activate.ps1

# Start server
python main.py
```

**Expected Output**:
```
INFO: Uvicorn running on http://0.0.0.0:8000
>>> LSTM MODEL LOADED SUCCESSFULLY AT STARTUP <<<
INFO: Application startup complete.
```

**Verify Backend**:
- Open: http://localhost:8000
- You should see: `{"service":"Sanchar-Optimize","version":"2.0.0"...}`

---

#### 2. Load Browser Extension

**Step-by-step**:

1. **Open Chrome Extensions**:
   - Navigate to `chrome://extensions/`
   - OR click three dots → Extensions → Manage Extensions

2. **Enable Developer Mode**:
   - Toggle switch in top-right corner

3. **Load Extension**:
   - Click "Load unpacked"
   - Navigate to: `d:\Projects\Sanchar-Optimize\extension`
   - Click "Select Folder"

4. **Grant Permissions** (CRITICAL):
   - Click "Details" on Sanchar-Optimize extension
   - Scroll down
   - Enable: "Allow access to file URLs"
   - This allows testing with local HTML files

5. **Verify Installation**:
   - Extension icon should appear in toolbar
   - Click icon → popup should open
   - Status should show network metrics

**Troubleshooting**:
- If icon red/inactive → Backend not running
- If no telemetry → Check CORS configuration
- If API errors → Check console (F12)

---

#### 3. Test Extension Functionality

**Quick Smoke Test** (2 minutes):

1. Open YouTube video:
   ```
   https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

2. Open Chrome Console (F12)

3. Play video

4. Look for log messages:
   ```
   🏥 Backend health check: OK ✓
   📊 Telemetry submitted successfully
   🎬 Video detected: dQw4w9WgXcQ
   ```

5. Click extension icon:
   - Should show network stats
   - Should show session info
   - Should be green/active

**Full Integration Test** (10 minutes):

Follow the detailed checklist in: `EXTENSION_TEST_CHECKLIST.md`

Key steps:
1. Play YouTube video with good network
2. Open DevTools → Network tab
3. Throttle to "Fast 3G"
4. Observe prediction API calls
5. Throttle to "Slow 3G"
6. Observe modality decision
7. Throttle to "Offline"
8. Verify content summary displayed

---

### Option B: Production AWS Deployment

#### Prerequisites
- AWS Account with Bedrock access
- AWS CLI configured
- SAM CLI installed (for Lambda deployment)

#### 1. Update Configuration

**Backend API URL**:
```javascript
// extension/utils/api-client.js
const API_CONFIG = {
    // Change from:
    BASE_URL: 'http://localhost:8000/api/v1',
    
    // To:
    BASE_URL: 'https://2f8kolu7j4.execute-api.ap-south-1.amazonaws.com/production/api/v1',
    ...
}
```

**AWS Credentials**:
```bash
# Backend/.env (create from .env.example)
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Optional: Gemini API key (free tier)
GEMINI_API_KEY=your-gemini-api-key
```

#### 2. Deploy Backend to AWS Lambda

```powershell
cd d:\Projects\Sanchar-Optimize\Backend

# Deploy using SAM
sam build
sam deploy --guided

# Follow prompts:
# - Stack Name: sanchar-optimize-prod
# - AWS Region: ap-south-1
# - Confirm changes: Y
# - Allow SAM CLI IAM role creation: Y
# - Disable rollback: N
# - Save arguments to config: Y
```

**Alternative**: Use deployment script
```powershell
.\deployment\deploy.ps1
```

#### 3. Configure DynamoDB (Optional)

```powershell
cd Backend\scripts
python setup_aws_resources.py
```

This creates:
- DynamoDB table for sessions
- S3 bucket for content storage
- Timestream database for telemetry

#### 4. Package Extension for Chrome Web Store

```powershell
cd d:\Projects\Sanchar-Optimize\extension

# Create zip package
Compress-Archive -Path * -DestinationPath ..\sanchar-optimize-extension.zip
```

**Upload to Chrome Web Store**:
1. Go to: https://chrome.google.com/webstore/devconsole
2. Click "New Item"
3. Upload `sanchar-optimize-extension.zip`
4. Fill in details:
   - Name: Sanchar-Optimize
   - Description: (from manifest.json)
   - Category: Productivity
   - Screenshots: (prepare 5 screenshots)
5. Submit for review

---

## 🔧 Configuration Files

### Critical Files to Review

1. **Backend Configuration**:
   - `Backend/.env` - Environment variables
   - `Backend/app/core/config.py` - Application settings
   - `Backend/deployment/lambda/template.yaml` - AWS SAM template

2. **Extension Configuration**:
   - `extension/utils/api-client.js` - API endpoints
   - `extension/manifest.json` - Extension metadata

### Production URLs

**Backend API**:
- Health: `https://2f8kolu7j4.execute-api.ap-south-1.amazonaws.com/production/api/v1/health`
- Telemetry: `https://2f8kolu7j4.execute-api.ap-south-1.amazonaws.com/production/api/v1/telemetry`

**Update in**:
- `extension/utils/api-client.js`
- `backend-url.txt` (for documentation)

---

## 🧪 Post-Deployment Testing

### 1. Verify Backend Deployment

```powershell
# Test health endpoint
curl https://your-api-url/api/v1/health

# Should return:
# {"status":"healthy","timestamp":...}
```

### 2. Test Extension with Production

1. Reload extension in Chrome
2. Open YouTube video
3. Check console for API calls
4. Verify data reaches backend
5. Test all modality transitions

### 3. Monitor Logs

**AWS CloudWatch**:
```bash
# View Lambda logs
aws logs tail /aws/lambda/sanchar-optimize-backend --follow
```

**Local Backend**:
```powershell
# Logs are in console and logs/ directory
cd Backend\logs
ls -Sort LastWriteTime | Select -First 5
```

---

## 📊 Monitoring & Maintenance

### Health Checks

**Automated**:
- Set up AWS CloudWatch alarms
- Monitor API response times
- Track error rates

**Manual**:
- Check health endpoint daily
- Review telemetry data
- Monitor LSTM prediction accuracy

### Performance Optimization

1. **Enable Redis Caching**:
   ```python
   # In .env
   REDIS_URL=redis://your-redis-host:6379
   ```

2. **Optimize LSTM Model**:
   - Retrain with production data monthly
   - Adjust prediction thresholds based on accuracy

3. **Scale Backend**:
   - Configure Lambda concurrency limits
   - Set up API Gateway throttling
   - Enable CloudFront CDN

---

## 🚨 Troubleshooting

### Common Issues

#### Backend Won't Start
```
Error: "No module named 'tensorflow.tsl.protobuf'"
```
**Fix**:
```powershell
pip install --upgrade tensorflow
# OR use requirements.txt
pip install -r requirements.txt
```

#### Extension Shows "Backend Unavailable"
**Check**:
1. Backend is running: http://localhost:8000
2. CORS is enabled in `.env`
3. API URL is correct in `api-client.js`
4. No firewall blocking requests

#### LSTM Model Won't Load
```
Error: "Failed to load LSTM model"
```
**Fix**:
1. Check model file exists: `Backend/app/ml/models/lstm_network_predictor.keras`
2. Verify TensorFlow installed: `pip list | grep tensorflow`
3. System will use heuristic fallback if model fails

#### API Requests Timeout
**Fix**:
1. Increase timeout in `api-client.js`:
   ```javascript
   TIMEOUT: 10000  // 10 seconds
   ```
2. Check network connectivity
3. Verify AWS credentials if using Bedrock

#### Extension Permissions Error
**Fix**:
1. Go to `chrome://extensions/`
2. Click "Details" on extension
3. Enable "Allow access to file URLs"
4. Reload extension

---

## 📚 Additional Resources

### Documentation
- `README.md` - Project overview
- `requirements.md` - Detailed requirements
- `design.md` - Architecture design
- `TEST_REPORT.md` - Complete test results
- `EXTENSION_TEST_CHECKLIST.md` - Extension testing guide

### Scripts
- `test_e2e.py` - End-to-end testing script
- `Backend/scripts/train_lstm_model.py` - Retrain LSTM
- `Backend/deployment/deploy.ps1` - Automated deployment

### Support
- Check logs in `Backend/logs/`
- Review console errors in Chrome DevTools
- Test individual API endpoints with curl/Postman

---

## ✅ Final Checklist

Before going live:

### Backend
- [ ] All tests pass (`python test_e2e.py`)
- [ ] LSTM model loaded successfully
- [ ] AWS credentials configured
- [ ] Production URL in use
- [ ] CORS configured for production domain
- [ ] Logging configured appropriately
- [ ] Error handling tested
- [ ] Monitoring/alerts set up

### Extension
- [ ] Loaded in Chrome successfully
- [ ] Production API URL configured
- [ ] All permissions granted
- [ ] Tested on YouTube
- [ ] Telemetry verified
- [ ] Modality transitions tested
- [ ] Icons and branding complete
- [ ] Package created for distribution

### Documentation
- [ ] README updated
- [ ] API documentation complete
- [ ] Installation instructions verified
- [ ] Demo video created (optional)
- [ ] Support contact information added

---

## 🎉 You're Ready to Deploy!

**Current Status**:
- ✅ Backend fully tested and operational
- ✅ All core features working
- ⏳ Extension requires manual browser testing

**Next Steps**:
1. Load extension in Chrome (follow steps above)
2. Test on YouTube video
3. Verify telemetry and decisions
4. Update to production URLs
5. Deploy! 🚀

---

**Questions?** Review the test report and documentation files in the project root.

**Good luck with your AI for Bharat Hackathon 2026 submission!** 🇮🇳
