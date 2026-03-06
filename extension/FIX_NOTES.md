# Extension Module Loading Fix

## Issue Fixed
The service worker was trying to use `importScripts()` (for classic scripts) while being configured as an ES6 module in the manifest. This caused:
1. `Failed to execute 'importScripts' on 'WorkerGlobalScope': Module scripts don't support importScripts()`
2. `BackendAPI is not a constructor` - because the class wasn't properly exported/imported

## Changes Made

### 1. api-client.js
Added proper ES6 exports at the end of the file:
```javascript
// Export for ES6 modules (Manifest V3 service workers)
export { BackendAPI, API_CONFIG };

// Export singleton instance
export const backendAPI = new BackendAPI();
```

### 2. service-worker.js
Changed from `importScripts()` to ES6 import:
```javascript
// OLD (doesn't work with Manifest V3 modules):
importScripts('../utils/api-client.js');

// NEW (ES6 modules):
import { BackendAPI, backendAPI, API_CONFIG } from '../utils/api-client.js';
```

Also removed the redundant instantiation:
```javascript
// OLD:
backendAPI = typeof BackendAPI !== 'undefined' ? new BackendAPI() : null;

// NEW:
// backendAPI is already imported as a singleton from api-client.js
```

## Testing Instructions

1. **Reload Extension**:
   - Go to `chrome://extensions/`
   - Click the reload icon on Sanchar-Optimize
   
2. **Check Service Worker Console**:
   - Click "service worker" link next to "Inspect views"
   - You should see:
     ```
     🌟 Sanchar-Optimize Background Service Worker Loaded
     🚀 Sanchar-Optimize Extension Installed
     🏥 Backend health check: OK ✓
     ```
   - NO MORE ERRORS about importScripts or BackendAPI constructor

3. **Verify Backend Connection**:
   - Should see: `🏥 Backend connected: Phase 2 features enabled`
   - If backend is down: `⚠️ Backend unavailable: Using Phase 1 fallback mode`

4. **Test on YouTube**:
   - Open any YouTube video
   - Check page console for: `📊 Telemetry submitted successfully`

## Verification
Run the test script in the service worker console:
- Copy contents of `test-service-worker.js`
- Paste into service worker dev console
- All tests should pass

## Why This Happened
Manifest V3 uses ES6 modules for service workers by default when you include `"type": "module"` in the manifest. The old extension code was written for Manifest V2 which used classic scripts with `importScripts()`.

## Status
✅ **FIXED** - Extension should now load properly without errors
