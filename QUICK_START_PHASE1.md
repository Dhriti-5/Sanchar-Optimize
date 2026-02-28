# 🚀 Phase 1 Quick Start Guide

Welcome to **Sanchar-Optimize Phase 1**! This guide will get you up and running in 5 minutes.

## ⚡ Quick Installation (3 Steps)

### 1. Open Chrome Extensions
- Navigate to: `chrome://extensions/`
- Enable **Developer mode** (toggle in top-right corner)

### 2. Load the Extension
- Click **"Load unpacked"**
- Navigate to: `d:\Projects\Sanchar-Optimize\extension`
- Click **"Select Folder"**

### 3. Enable File URL Access ⚠️ IMPORTANT
- In `chrome://extensions/`, find **Sanchar-Optimize**
- Click **"Details"**
- Scroll down and **enable "Allow access to file URLs"**
- This lets the extension work with the test page

### 4. Grant Permissions
- Allow **location access** when prompted (when you open a page)
- Extension icon should appear in toolbar ✅

---

## 🧪 Quick Test (2 Minutes)

### Option A: Test Page (with File URL Access)
1. **FIRST**: Make sure you enabled "Allow access to file URLs" (see step 3 above)
2. **Reload** the test page if it was already open
3. Open: `d:\Projects\Sanchar-Optimize\extension\test\test-page.html` in your browser
4. You should see: "✅ Sanchar-Optimize extension detected!"
5. Click **Play** on the test video
6. Click **"Simulate Signal Drop"** button
7. ✅ You should see the Zero-Buffer Overlay!

### Option A2: Test Page (with Local Server - No File Access Needed!)
```powershell
# Run this in PowerShell:
cd "d:\Projects\Sanchar-Optimize\extension\test"
.\start-test-server.ps1

# Or manually:
python -m http.server 8000

# Then open: http://localhost:8000/test-page.html
```

### Option B: YouTube
1. Go to any YouTube video
2. Press **F12** (open DevTools)
3. Click **Play** on the video
4. Check Console - you should see:
   ```
   🎯 Sanchar-Optimize active on youtube
   📹 Video element found
   ▶️ Video playing
   ```

---

## 📊 Check Status

Click the **Sanchar-Optimize icon** in your browser toolbar to see:
- System status (should be green/passive)
- Network quality
- Real-time statistics

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| **"Extension not detected"** error | **See detailed fix:** [EXTENSION_NOT_DETECTED_FIX.md](extension/EXTENSION_NOT_DETECTED_FIX.md) |
| Extension not detected on test page | Go to `chrome://extensions/` → Click "Details" on Sanchar-Optimize → Enable "Allow access to file URLs" → Reload test page |
| Extension not loading | Check that you selected the `extension` folder, not the root folder |
| No GPS data | Grant location permission, or use test page (mock data) |
| Overlay not showing | Click "Test Handshake" in the popup |
| No console logs | Make sure you're on a supported site (YouTube, Coursera) or enabled file URL access |

---

## 📚 Full Documentation

See [extension/README.md](extension/README.md) for complete documentation including:
- Architecture details
- All features implemented
- Testing procedures
- Development guide

---

## ✅ Phase 1 Complete!

Once you've verified the extension works:
- ✅ Network telemetry is being collected
- ✅ Video playback is being monitored
- ✅ Overlay can be triggered
- ✅ Popup shows real-time stats

**Ready for Phase 2!** 🎉

---

**Questions?** Check the [extension README](extension/README.md) or examine the console logs in DevTools.
