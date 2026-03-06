# Browser Extension Testing Checklist
# Sanchar-Optimize - End-to-End Testing

## ✅ Pre-Deployment Testing Checklist

### 1. Backend Status
- [x] Backend server running on http://localhost:8000
- [x] LSTM model loaded successfully
- [x] All API endpoints responding correctly
- [x] Bedrock/Gemini integration working

### 2. Extension Installation
- [ ] Extension loaded in Chrome/Edge (Developer Mode)
- [ ] All permissions granted (storage, tabs, webRequest, geolocation, alarms)
- [ ] Extension icon visible in toolbar
- [ ] "Allow access to file URLs" enabled
- [ ] No console errors in extension background page

### 3. Extension Components Testing

#### A. Background Service Worker
Test Steps:
1. Open Chrome DevTools for extension (chrome://extensions → Details → Inspect views)
2. Check console for initialization messages
3. Verify "Sanchar-Optimize Background Service Worker initialized" message
4. Check for any errors in console

Expected Results:
- ✓ Service worker starts successfully
- ✓ No errors in console
- ✓ API client initialized
- ✓ Storage initialized

#### B. Telemetry Agent
Test Steps:
1. Open any webpage
2. Open page console (F12)
3. Look for telemetry messages
4. Check if GPS location is being tracked
5. Verify network metrics are being collected

Expected Results:
- ✓ Telemetry data collected every 1-2 seconds
- ✓ Network quality metrics (effectiveType, downlink, rtt)
- ✓ GPS velocity calculated correctly
- ✓ Data sent to backend successfully

#### C. Content Script (Video Interceptor)
Test Steps:
1. Navigate to YouTube video (e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ)
2. Open console
3. Play the video
4. Check for content script messages
5. Verify video metadata is extracted

Expected Results:
- ✓ Content script injected on YouTube page
- ✓ Video player detected
- ✓ Video ID extracted correctly
- ✓ Playback position tracked
- ✓ Video metadata sent to background

#### D. Popup Dashboard
Test Steps:
1. Click extension icon in toolbar
2. Verify popup opens
3. Check network statistics display
4. Check session information
5. Test enable/disable toggle

Expected Results:
- ✓ Popup opens without errors
- ✓ Network stats displayed correctly
- ✓ Session information shown
- ✓ Visual indicators working (colors, icons)
- ✓ Controls functional

### 4. Core Functionality Testing

#### Test Case 1: Telemetry Collection
**Scenario**: Normal browsing with good network

Steps:
1. Open YouTube
2. Play a video
3. Let it run for 30 seconds
4. Check backend logs for telemetry data

Expected:
- Telemetry sent every 1-2 seconds
- Device ID and session ID consistent
- Network metrics accurate
- No errors in submission

**Status**: ___________

---

#### Test Case 2: Network Prediction
**Scenario**: Simulated network degradation

Steps:
1. Open Chrome DevTools → Network tab
2. Throttle to "Fast 3G"
3. Play YouTube video
4. Monitor console for prediction messages
5. Check if prediction API is called

Expected:
- Network degradation detected
- Prediction API called with recent telemetry
- Response contains should_prepare_transition flag
- Console shows prediction results

**Status**: ___________

---

#### Test Case 3: Modality Decision
**Scenario**: Trigger modality transition

Steps:
1. Play YouTube video
2. Throttle network to "Slow 3G"
3. Wait for modality decision
4. Check console for AI reasoning

Expected:
- Modality decision API called
- AI reasoning provided (from Gemini/Bedrock)
- Target modality recommended (AUDIO or TEXT_SUMMARY)
- Transition timing specified

**Status**: ___________

---

#### Test Case 4: Content Summary Generation
**Scenario**: Request AI summary of video content

Steps:
1. Play YouTube video
2. Wait 30 seconds
3. Throttle to "Offline"
4. Check if summary is generated/fetched

Expected:
- Content summary API called
- AI-generated summary received
- Key concepts extracted
- Compression ratio > 20x

**Status**: ___________

---

#### Test Case 5: Session Persistence
**Scenario**: Test session memory across restarts

Steps:
1. Play video for 2 minutes
2. Close browser
3. Reopen browser
4. Check storage for session data

Expected:
- Session ID persisted
- Video position remembered
- 7-day TTL set correctly
- Data retrievable on restart

**Status**: ___________

---

### 5. Integration Testing

#### End-to-End Full Flow Test

**Scenario**: Complete agentic behavior simulation

Steps:
1. Start with good network (4G)
2. Open YouTube educational video
3. Play for 1 minute
4. **Action**: Throttle to Fast 3G
   - Expected: System monitors, no action yet
5. **Action**: Throttle to Slow 3G
   - Expected: Prediction API called, modality decision requested
6. **Action**: Throttle to Offline
   - Expected: Content summary fetched/generated, overlay shown
7. **Action**: Restore to 4G
   - Expected: Resume video playback from correct position

**Validation Points**:
- [ ] Telemetry sent continuously
- [ ] Network degradation detected proactively
- [ ] LSTM prediction triggered
- [ ] Modality orchestrator makes decision
- [ ] AI reasoning is sensible
- [ ] Content transformation happens
- [ ] Zero-buffer experience (no visible buffering indicator)
- [ ] Contextual memory maintained across transitions
- [ ] Seamless resume when network restored

**Status**: ___________

---

### 6. Error Handling Testing

#### Test Case: Backend Unavailable
Steps:
1. Stop backend server
2. Load extension
3. Open YouTube video
4. Check graceful degradation

Expected:
- Extension doesn't crash
- Error messages logged
- Fallback to client-side prediction
- User notified of limited functionality

**Status**: ___________

---

#### Test Case: API Timeout
Steps:
1. Set API timeout to 1ms (in api-client.js)
2. Make API call
3. Verify timeout handling

Expected:
- Request times out gracefully
- Error caught and logged
- Retry mechanism triggered (if implemented)
- No extension crash

**Status**: ___________

---

### 7. Performance Testing

#### Metrics to Verify:
- [ ] Extension memory usage < 100MB
- [ ] CPU usage < 5% (idle)
- [ ] API response times < 500ms (decision endpoint)
- [ ] Telemetry overhead < 1KB/s
- [ ] No memory leaks after 1 hour of usage

**Tools**:
- Chrome Task Manager (Shift+Esc)
- Chrome DevTools Performance tab
- Network tab for API calls

---

### 8. Compatibility Testing

Test on:
- [ ] Google Chrome (latest version)
- [ ] Microsoft Edge (latest version)
- [ ] Different screen resolutions
- [ ] Different network conditions
- [ ] Mobile emulation mode

---

### 9. Security & Privacy

Verify:
- [ ] No sensitive data in console logs
- [ ] Device ID is anonymized
- [ ] Location data is hashed
- [ ] HTTPS used for API calls (production)
- [ ] No credentials in client-side code
- [ ] CORS properly configured

---

### 10. Production Readiness

Before deployment, ensure:
- [ ] API_CONFIG.BASE_URL points to production
- [ ] Debug logging disabled or minimized
- [ ] Error tracking implemented
- [ ] Analytics/telemetry properly anonymized
- [ ] Extension reviewed for Chrome Web Store policies
- [ ] Icons and branding complete
- [ ] README updated with installation instructions
- [ ] Demo video created (if needed)

---

## 📊 Test Results Summary

| Category | Tests Passed | Tests Failed | Status |
|----------|--------------|--------------|--------|
| Backend APIs | 8/8 | 0 | ✅ PASS |
| Extension Install | 0/5 | 0 | ⏳ PENDING |
| Telemetry | 0/5 | 0 | ⏳ PENDING |
| Content Script | 0/5 | 0 | ⏳ PENDING |
| Modality Decision | 0/4 | 0 | ⏳ PENDING |
| Integration | 0/1 | 0 | ⏳ PENDING |
| Error Handling | 0/2 | 0 | ⏳ PENDING |
| **TOTAL** | **8/30** | **0** | **🔄 IN PROGRESS** |

---

## 🚀 Manual Testing Instructions

### For Reviewer/Tester:

1. **Setup Backend** (5 minutes):
   ```powershell
   cd d:\Projects\Sanchar-Optimize\Backend
   python main.py
   ```
   Wait for "LSTM MODEL LOADED" message

2. **Load Extension** (2 minutes):
   - Go to `chrome://extensions/`
   - Enable Developer mode
   - Load unpacked: `d:\Projects\Sanchar-Optimize\extension`
   - Enable "Allow access to file URLs"

3. **Quick Smoke Test** (3 minutes):
   - Open YouTube video
   - Check extension icon (should show green/active)
   - Click icon to see popup with stats
   - Play video, check console for telemetry logs

4. **Full Integration Test** (10 minutes):
   - Follow "End-to-End Full Flow Test" above
   - Use Chrome DevTools Network throttling
   - Document any issues

---

## 📝 Notes

- All backend tests passed ✅
- Extension requires manual testing in browser
- Use Chrome DevTools extensively for debugging
- Check both extension console and page console for logs

---

**Tester**: ___________
**Date**: ___________
**Chrome Version**: ___________
**OS**: ___________
