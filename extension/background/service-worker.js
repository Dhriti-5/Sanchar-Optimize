/**
 * SANCHAR-OPTIMIZE: Background Service Worker
 * The "Brain" of the extension - Orchestrates network monitoring and agent communication
 */

// Backend API instance (will be initialized dynamically)
let backendAPI = null;
let isBackendAvailable = false;
let BackendAPI = null;

// Try to import Backend API Client (Phase 2 Integration)
try {
  importScripts('../utils/api-client.js');
} catch (error) {
  console.warn('⚠️ Could not load api-client.js:', error.message);
}

// ==========================================
// 1. STATE MANAGEMENT
// ==========================================
const SystemState = {
  PASSIVE: 'passive',        // Green - Signal strong, pre-fetching content
  WARNING: 'warning',        // Yellow - Signal drop predicted
  ACTIVE_RESILIENCE: 'active_resilience'  // Red - Network failed, overlay active
};

let currentState = SystemState.PASSIVE;
let heartbeatInterval = 1000; // Default: 1 second
let monitoringInterval = null;
let telemetryHistory = [];
const MAX_TELEMETRY_HISTORY = 300; // 5 minutes at 1Hz

// User session tracking
let userSessions = new Map(); // tabId -> session data

// ==========================================
// 2. INITIALIZATION
// ==========================================
chrome.runtime.onInstalled.addListener(async () => {
  console.log('🚀 Sanchar-Optimize Extension Installed');
  
  // Set initial icon (green - passive state)
  updateExtensionIcon(SystemState.PASSIVE);
  
  // Initialize storage
  chrome.storage.local.set({
    systemState: SystemState.PASSIVE,
    telemetryHistory: [],
    cachedSummaries: {},
    sessionMemory: {}
  });
  
  // Initialize backend connection (Phase 2)
  await initializeBackendConnection();
  
  // Start monitoring
  startNetworkMonitoring();
});

// Listen for extension startup
chrome.runtime.onStartup.addListener(async () => {
  console.log('🔄 Sanchar-Optimize Extension Started');
  await initializeBackendConnection();
  startNetworkMonitoring();
});

// ==========================================
// 2.5 BACKEND CONNECTION (Phase 2)
// ==========================================
async function initializeBackendConnection() {
  try {
    backendAPI = typeof BackendAPI !== 'undefined' ? new BackendAPI() : null;
    if (backendAPI) {
      isBackendAvailable = await backendAPI.checkHealth();
      if (isBackendAvailable) {
        console.log('🏥 Backend connected: Phase 2 features enabled');
      } else {
        console.warn('⚠️ Backend unavailable: Using Phase 1 fallback mode');
      }
    } else {
      console.warn('⚠️ Backend API not loaded: Using Phase 1 fallback mode');
      isBackendAvailable = false;
    }
  } catch (error) {
    console.warn('⚠️ Backend connection failed:', error.message);
    isBackendAvailable = false;
  }

  // Periodic health check every 5 minutes
  setInterval(async () => {
    if (backendAPI) {
      const wasAvailable = isBackendAvailable;
      isBackendAvailable = await backendAPI.checkHealth();
      if (isBackendAvailable && !wasAvailable) {
        console.log('✅ Backend recovered: Phase 2 features re-enabled');
      } else if (!isBackendAvailable && wasAvailable) {
        console.warn('⚠️ Backend lost: Falling back to Phase 1 mode');
      }
    }
  }, 5 * 60 * 1000); // 5 minutes
}

// Handle service worker activation (after being suspended)
self.addEventListener('activate', (event) => {
  console.log('⚡ Service Worker activated');
  event.waitUntil(
    Promise.resolve().then(() => {
      // Restart monitoring if needed
      if (!monitoringInterval) {
        startNetworkMonitoring();
      }
    })
  );
});

// ==========================================
// 3. NETWORK MONITORING & TELEMETRY
// ==========================================
function startNetworkMonitoring() {
  if (monitoringInterval) {
    clearInterval(monitoringInterval);
  }
  
  monitoringInterval = setInterval(async () => {
    const telemetry = await collectTelemetry();
    processTelemetry(telemetry);
  }, heartbeatInterval);
  
  console.log(`📡 Network monitoring started (interval: ${heartbeatInterval}ms)`);
}

async function collectTelemetry() {
  const telemetry = {
    timestamp: Date.now(),
    // Network info is collected by content script and sent via message
    // GPS velocity is collected by content script
    systemState: currentState,
    activeTab: await getActiveTab()
  };
  
  return telemetry;
}

function processTelemetry(telemetry) {
  // Store telemetry history
  telemetryHistory.push(telemetry);
  if (telemetryHistory.length > MAX_TELEMETRY_HISTORY) {
    telemetryHistory.shift(); // Remove oldest entry
  }
  
  // Update storage periodically (every 10 samples)
  if (telemetryHistory.length % 10 === 0) {
    chrome.storage.local.set({ telemetryHistory: telemetryHistory });
  }
}

// ==========================================
// 4. MESSAGE HANDLING (Content Script ↔ Background)
// ==========================================
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Always send a response to prevent "port closed" errors
  const respond = (response) => {
    try {
      sendResponse(response);
    } catch (error) {
      // Port may have closed - this is normal
      console.log('Response send skipped (port closed)');
    }
  };

  console.log('📨 Message received:', message.type);
  
  switch (message.type) {
    case 'NETWORK_TELEMETRY':
      handleNetworkTelemetry(message.data, sender.tab);
      respond({ status: 'received' });
      break;
      
    case 'GPS_VELOCITY':
      handleGPSVelocity(message.data, sender.tab);
      respond({ status: 'received' });
      break;
      
    case 'VIDEO_METADATA':
      handleVideoMetadata(message.data, sender.tab);
      respond({ status: 'received' });
      break;
      
    case 'REQUEST_SUMMARY':
      handleSummaryRequest(message.data, sender.tab)
        .then(summary => respond({ status: 'success', summary }))
        .catch(error => respond({ status: 'error', error: error.message }));
      return true; // Keep channel open for async response
      
    case 'SIGNAL_RESTORED':
      handleSignalRestoration(message.data, sender.tab);
      respond({ status: 'received' });
      break;

    case 'BUFFERING_DETECTED':
      console.warn('⚠️ Buffering detected - prediction may have missed this event');
      respond({ status: 'received' });
      break;
      
    default:
      console.warn('Unknown message type:', message.type);
      respond({ status: 'error', message: 'Unknown message type' });
  }
  
  // Return false for synchronous responses
  return false;
});

// ==========================================
// 5. TELEMETRY HANDLERS
// ==========================================
async function handleNetworkTelemetry(data, tab) {
  const { effectiveType, downlink, rtt, saveData } = data;
  
  // Store in telemetry history
  const telemetryEntry = {
    timestamp: Date.now(),
    tabId: tab.id,
    effectiveType,
    downlink, // Mbps
    rtt, // Round-trip time in ms
    saveData
  };
  
  telemetryHistory.push(telemetryEntry);
  
  // Submit telemetry to backend (Phase 2) in batches
  if (isBackendAvailable && backendAPI && telemetryHistory.length % 5 === 0) {
    submitTelemetryToBackend(tab);
  }
  
  // Predict signal drop - use backend LSTM if available, else heuristic
  const prediction = await predictSignalDrop(telemetryEntry, tab);
  
  if (prediction.dropPredicted) {
    handlePredictedDrop(prediction, tab);
  }
}

// Submit batched telemetry to backend
async function submitTelemetryToBackend(tab) {
  if (!isBackendAvailable || !backendAPI) return;
  
  try {
    const session = userSessions.get(tab.id) || {};
    const gpsData = session.lastGPS || {};
    
    // Convert recent telemetry to backend format
    const recentTelemetry = telemetryHistory.slice(-10).map(t => ({
      timestamp: t.timestamp / 1000, // Convert to seconds
      signal_strength_dbm: estimateSignalStrength(t.downlink),
      bandwidth_kbps: (t.downlink || 0) * 1000, // Mbps to Kbps
      latency_ms: t.rtt || 0,
      packet_loss_percent: estimatePacketLoss(t.effectiveType),
      effective_type: t.effectiveType,
      gps_latitude: gpsData.latitude || 0,
      gps_longitude: gpsData.longitude || 0,
      gps_velocity_kmh: gpsData.velocity || 0
    }));
    
    await backendAPI.submitTelemetryBatch(recentTelemetry);
    console.log('📊 Batch telemetry submitted to backend');
  } catch (error) {
    console.warn('⚠️ Failed to submit telemetry:', error.message);
  }
}

// Helper: Estimate signal strength from bandwidth
function estimateSignalStrength(downlinkMbps) {
  // Rough estimation: Good signal = -60 to -70 dBm, Poor = -90 to -100 dBm
  if (!downlinkMbps || downlinkMbps < 0.1) return -100;
  if (downlinkMbps > 10) return -60;
  return -100 + (downlinkMbps * 4); // Linear approximation
}

// Helper: Estimate packet loss from connection type
function estimatePacketLoss(effectiveType) {
  const lossMap = {
    '4g': 0.5,
    '3g': 2.0,
    '2g': 5.0,
    'slow-2g': 10.0
  };
  return lossMap[effectiveType] || 1.0;
}

function handleGPSVelocity(data, tab) {
  const { velocity, latitude, longitude } = data;
  
  console.log(`🚄 Velocity: ${velocity} km/h`);
  
  // Adaptive monitoring: If speed > 60 km/h, increase frequency
  if (velocity > 60 && heartbeatInterval !== 500) {
    heartbeatInterval = 500; // 2 Hz
    startNetworkMonitoring();
    console.log('⚡ High-speed mode activated (500ms polling)');
  } else if (velocity <= 60 && heartbeatInterval !== 1000) {
    heartbeatInterval = 1000; // 1 Hz
    startNetworkMonitoring();
    console.log('🐢 Normal-speed mode (1000ms polling)');
  }
  
  // Store GPS data with session
  if (!userSessions.has(tab.id)) {
    userSessions.set(tab.id, {});
  }
  userSessions.get(tab.id).lastGPS = { velocity, latitude, longitude, timestamp: Date.now() };
}

function handleVideoMetadata(data, tab) {
  const { videoId, platform, duration, currentTime, title, url } = data;
  
  console.log(`📹 Video tracked: ${title} (${platform})`);
  
  // Store session data
  if (!userSessions.has(tab.id)) {
    userSessions.set(tab.id, {});
  }
  
  const session = userSessions.get(tab.id);
  session.videoId = videoId;
  session.platform = platform;
  session.duration = duration;
  session.currentTime = currentTime;
  session.title = title;
  session.url = url;
  session.lastUpdate = Date.now();
  
  // Save to persistent storage (for 7-day memory)
  saveSessionMemory(tab.id, session);
  
  // Start speculative prefetching if signal is strong
  if (currentState === SystemState.PASSIVE) {
    speculativePrefetch(videoId, platform);
  }
}

// ==========================================
// 6. PREDICTION LOGIC (Simplified LSTM)
// ==========================================
async function predictSignalDrop(currentTelemetry, tab) {
  // Phase 2: Use backend LSTM prediction if available, else fallback to heuristic
  
  if (telemetryHistory.length < 10) {
    return { dropPredicted: false, confidence: 0 };
  }
  
  // Try backend prediction first (Phase 2)
  if (isBackendAvailable && backendAPI) {
    try {
      const session = userSessions.get(tab.id) || {};
      const gpsData = session.lastGPS || {};
      
      // Convert recent telemetry for backend
      const recentTelemetry = telemetryHistory.slice(-20).map(t => ({
        timestamp: t.timestamp / 1000,
        signal_strength_dbm: estimateSignalStrength(t.downlink),
        bandwidth_kbps: (t.downlink || 0) * 1000,
        latency_ms: t.rtt || 0,
        packet_loss_percent: estimatePacketLoss(t.effectiveType),
        effective_type: t.effectiveType,
        gps_latitude: gpsData.latitude || 0,
        gps_longitude: gpsData.longitude || 0,
        gps_velocity_kmh: gpsData.velocity || 0
      }));
      
      const prediction = await backendAPI.getPrediction(recentTelemetry);
      
      if (prediction.will_drop) {
        console.warn(`🔮 Backend prediction: Signal drop in ${prediction.time_to_drop_sec}s (confidence: ${(prediction.confidence * 100).toFixed(0)}%)`);
      }
      
      return {
        dropPredicted: prediction.will_drop,
        confidence: prediction.confidence,
        horizonSeconds: prediction.time_to_drop_sec || 5,
        reasoning: {
          model: prediction.model_used,
          predictedSignal: prediction.predicted_signal_strength_dbm,
          recommendedAction: prediction.recommended_action
        }
      };
    } catch (error) {
      console.warn('⚠️ Backend prediction failed, using heuristic:', error.message);
      // Fall through to heuristic fallback
    }
  }
  
  // Phase 1 Fallback: Heuristic-based prediction
  const recentSamples = telemetryHistory.slice(-10);
  const downlinkTrend = calculateTrend(recentSamples.map(s => s.downlink));
  const rttTrend = calculateTrend(recentSamples.map(s => s.rtt));
  
  const currentDownlink = currentTelemetry.downlink || 0;
  const isDownlinkLow = currentDownlink < 0.5;
  const isDownlinkDropping = downlinkTrend < -0.3;
  const isLatencyRising = rttTrend > 0.5;
  
  let confidence = 0;
  if (isDownlinkLow) confidence += 0.4;
  if (isDownlinkDropping) confidence += 0.3;
  if (isLatencyRising) confidence += 0.3;
  
  const dropPredicted = confidence > 0.75;
  
  if (dropPredicted) {
    console.warn(`⚠️ Heuristic prediction: Signal drop! Confidence: ${(confidence * 100).toFixed(0)}%`);
  }
  
  return {
    dropPredicted,
    confidence,
    horizonSeconds: 5,
    reasoning: {
      model: 'heuristic',
      downlink: currentDownlink,
      downlinkTrend,
      rttTrend,
      isDownlinkLow,
      isDownlinkDropping,
      isLatencyRising
    }
  };
}

function calculateTrend(values) {
  if (values.length < 2) return 0;
  
  const first = values[0] || 0;
  const last = values[values.length - 1] || 0;
  
  if (first === 0) return 0;
  
  return (last - first) / first; // Percentage change
}

// ==========================================
// 7. SIGNAL DROP HANDLING
// ==========================================
function handlePredictedDrop(prediction, tab) {
  // Change state to WARNING
  if (currentState === SystemState.PASSIVE) {
    currentState = SystemState.WARNING;
    updateExtensionIcon(SystemState.WARNING);
    
    console.log('⚠️ Entering WARNING state - Signal drop imminent');
    
    // Notify content script to prepare (if tab exists)
    if (tab && tab.id) {
      chrome.tabs.sendMessage(tab.id, {
        type: 'PREPARE_HANDSHAKE',
        prediction: prediction
      }).catch(error => {
        // Tab might have been closed - this is normal
        console.log('Could not notify tab (may be closed)');
      });
    }
    
    // Pre-load summary from cache or request generation
    const session = userSessions.get(tab?.id);
    if (session && session.videoId) {
      preloadSummary(session.videoId, session.platform, session.currentTime);
    }
  }
}

function handleSignalRestoration(data, tab) {
  console.log('✅ Signal restored');
  
  // Transition back to PASSIVE state
  if (currentState !== SystemState.PASSIVE) {
    currentState = SystemState.PASSIVE;
    updateExtensionIcon(SystemState.PASSIVE);
    
    // Notify content script (if tab exists)
    if (tab && tab.id) {
      chrome.tabs.sendMessage(tab.id, {
        type: 'SIGNAL_RESTORED',
        data: data
      }).catch(error => {
        console.log('Could not notify tab about signal restoration');
      });
    }
  }
}

// ==========================================
// 8. SUMMARY MANAGEMENT
// ==========================================
async function handleSummaryRequest(data, tab) {
  const { videoId, platform, currentTime } = data;
  
  // Check cache first
  const cacheKey = `${platform}_${videoId}`;
  const cached = await getCachedSummary(cacheKey);
  
  if (cached) {
    console.log('📦 Serving cached summary');
    return cached;
  }
  
  // Request from backend (Phase 2 integration point)
  console.log('🌐 Requesting summary from backend...');
  
  // For Phase 1, return mock summary
  const mockSummary = generateMockSummary(videoId, currentTime);
  
  // Cache it
  await cacheSummary(cacheKey, mockSummary);
  
  return mockSummary;
}

async function preloadSummary(videoId, platform, currentTime) {
  console.log('⚡ Pre-loading summary for:', videoId);
  
  try {
    await handleSummaryRequest({ videoId, platform, currentTime }, null);
  } catch (error) {
    console.error('Failed to preload summary:', error);
  }
}

function speculativePrefetch(videoId, platform) {
  // Phase 1: Basic implementation
  // Phase 3: Will implement "next 3 videos" prediction
  console.log('🔮 Speculative prefetch queued for:', videoId);
}

// ==========================================
// 9. STORAGE UTILITIES
// ==========================================
async function getCachedSummary(cacheKey) {
  const result = await chrome.storage.local.get('cachedSummaries');
  const summaries = result.cachedSummaries || {};
  return summaries[cacheKey];
}

async function cacheSummary(cacheKey, summary) {
  const result = await chrome.storage.local.get('cachedSummaries');
  const summaries = result.cachedSummaries || {};
  summaries[cacheKey] = {
    ...summary,
    cachedAt: Date.now()
  };
  await chrome.storage.local.set({ cachedSummaries: summaries });
}

async function saveSessionMemory(tabId, session) {
  const result = await chrome.storage.local.get('sessionMemory');
  const memory = result.sessionMemory || {};
  memory[tabId] = session;
  await chrome.storage.local.set({ sessionMemory: memory });
}

// ==========================================
// 10. UI UTILITIES
// ==========================================
function updateExtensionIcon(state) {
  const iconColors = {
    [SystemState.PASSIVE]: 'green',
    [SystemState.WARNING]: 'yellow',
    [SystemState.ACTIVE_RESILIENCE]: 'red'
  };
  
  const color = iconColors[state] || 'green';
  console.log(`🎨 Icon updated: ${color}`);
  
  // In Phase 1, we'll use badge color until custom icons are added
  chrome.action.setBadgeBackgroundColor({ color: color });
  chrome.action.setBadgeText({ text: state === SystemState.PASSIVE ? '' : '!' });
}

// ==========================================
// 11. HELPER FUNCTIONS
// ==========================================
async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0]?.id || null;
}

function generateMockSummary(videoId, currentTime) {
  // Mock data for Phase 1 testing
  return {
    videoId: videoId,
    timestamp: currentTime,
    keyConcepts: [
      'Introduction to the topic',
      'Core principle explanation',
      'Practical examples and applications'
    ],
    summary: `This is an AI-generated summary of the content. In a real implementation, this would contain the actual semantic distillation of the video content from timestamp ${currentTime}s onwards.`,
    visualDescriptions: [
      'The instructor demonstrates a concept on the whiteboard'
    ],
    compressionRatio: 0.08, // 8% of original size
    generatedBy: 'Mock Generator (Phase 1)',
    generatedAt: Date.now()
  };
}

// ==========================================
// 12. CLEANUP
// ==========================================
chrome.tabs.onRemoved.addListener((tabId) => {
  // Clean up session data
  if (userSessions.has(tabId)) {
    console.log('🧹 Cleaning up session for tab:', tabId);
    userSessions.delete(tabId);
  }
});

console.log('🌟 Sanchar-Optimize Background Service Worker Loaded');
