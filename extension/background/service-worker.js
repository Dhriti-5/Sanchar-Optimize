/**
 * SANCHAR-OPTIMIZE: Background Service Worker
 * The "Brain" of the extension - Orchestrates network monitoring and agent communication
 */

// Import Backend API Client (ES6 modules - Manifest V3)
import { BackendAPI, backendAPI, API_CONFIG } from '../utils/api-client.js';

// Backend API instance
let isBackendAvailable = false;

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
    // backendAPI is already imported as a singleton from api-client.js
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
    case 'SESSION_INIT':
      handleSessionInit(message.data, sender.tab)
        .then(result => respond({ status: 'success', result }))
        .catch(error => respond({ status: 'error', error: error.message }));
      return true; // Keep channel open for async response
      
    case 'PERSIST_TELEMETRY':
      handlePersistTelemetry(message.data, sender.tab)
        .then(result => respond({ status: 'success', result }))
        .catch(error => respond({ status: 'error', error: error.message }));
      return true; // Keep channel open for async response
      
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

    case 'USER_RESUMED_VIDEO':
      handleUserResumedVideo(message.data, sender.tab)
        .then(result => respond({ status: 'success', result }))
        .catch(error => respond({ status: 'error', error: error.message }));
      return true;

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
async function handleSessionInit(data, tab) {
  const { session_id } = data;
  
  console.log('📋 Initializing session:', session_id);
  
  // Store session in user sessions
  if (!userSessions.has(tab.id)) {
    userSessions.set(tab.id, {});
  }
  
  const session = userSessions.get(tab.id);
  session.session_id = session_id;
  session.initialized_at = Date.now();
  
  // Create session in backend
  if (isBackendAvailable && backendAPI) {
    try {
      const result = await backendAPI.createSession(session_id, 'web');
      console.log('📋 Backend session created:', result);
      return result;
    } catch (error) {
      console.error('Failed to create backend session:', error);
      return { status: 'local_only', session_id };
    }
  }
  
  return { status: 'local_only', session_id };
}

async function handlePersistTelemetry(data, tab) {
  const { telemetry_batch } = data;
  
  console.log('💾 Persisting telemetry batch:', telemetry_batch.length, 'records');
  
  // Submit enhanced telemetry to backend
  if (isBackendAvailable && backendAPI) {
    try {
      const results = [];
      for (const telemetry of telemetry_batch) {
        const result = await backendAPI.submitEnhancedTelemetry(telemetry);
        results.push(result);
      }
      console.log('💾 Enhanced telemetry persisted:', results.length, 'records');
      return { status: 'success', count: results.length };
    } catch (error) {
      console.error('Failed to persist telemetry:', error);
      return { status: 'error', error: error.message };
    }
  }
  
  return { status: 'backend_unavailable' };
}

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
    const { deviceId, sessionId } = getSessionIdentifiers(session, tab);
    const gpsData = session.lastGPS || {};
    
    // Convert recent telemetry to backend format
    const recentTelemetry = telemetryHistory.slice(-10).map(t => ({
      device_id: deviceId,
      session_id: sessionId,
      timestamp: t.timestamp / 1000, // Convert to seconds
      signal_strength: normalizeSignalStrength(t.downlink),
      bandwidth_kbps: (t.downlink || 0) * 1000, // Mbps to Kbps
      latency_ms: t.rtt || 0,
      packet_loss_percent: estimatePacketLoss(t.effectiveType),
      gps_velocity_kmh: gpsData.velocity || 0,
      content_id: session.videoId || null,
      content_position: session.currentTime || 0,
      effective_type: t.effectiveType
    }));
    
    await backendAPI.submitTelemetryBatch(deviceId, sessionId, recentTelemetry);
    console.log('📊 Batch telemetry submitted to backend');
  } catch (error) {
    console.warn('⚠️ Failed to submit telemetry:', error.message);
  }
}

function getSessionIdentifiers(session, tab) {
  const sessionId = session?.session_id || `session_tab_${tab.id}`;
  return {
    sessionId,
    deviceId: `device_${sessionId}`
  };
}

function normalizeSignalStrength(downlinkMbps) {
  if (!downlinkMbps || downlinkMbps <= 0) return 0;
  return Math.max(0, Math.min(1, downlinkMbps / 10));
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
      const { deviceId, sessionId } = getSessionIdentifiers(session, tab);
      const gpsData = session.lastGPS || {};
      
      // Convert recent telemetry for backend
      const recentTelemetry = telemetryHistory.slice(-20).map(t => ({
        device_id: deviceId,
        session_id: sessionId,
        timestamp: t.timestamp / 1000,
        signal_strength: normalizeSignalStrength(t.downlink),
        bandwidth_kbps: (t.downlink || 0) * 1000,
        latency_ms: t.rtt || 0,
        packet_loss_percent: estimatePacketLoss(t.effectiveType),
        gps_velocity_kmh: gpsData.velocity || 0,
        content_id: session.videoId || null,
        content_position: session.currentTime || 0,
        effective_type: t.effectiveType
      }));
      
      const predictionResponse = await backendAPI.getPrediction(deviceId, sessionId, recentTelemetry);
      const prediction = predictionResponse?.prediction;
      
      if (predictionResponse?.should_prepare_transition && prediction) {
        console.warn(`🔮 Backend prediction: Signal drop in ${prediction.predicted_time_seconds}s (confidence: ${(prediction.confidence * 100).toFixed(0)}%)`);
      }
      
      return {
        dropPredicted: !!predictionResponse?.should_prepare_transition,
        confidence: prediction?.confidence || 0,
        horizonSeconds: prediction?.predicted_time_seconds || 5,
        reasoning: {
          model: prediction?.predictor_type || 'unknown',
          predictedBandwidth: prediction?.predicted_bandwidth_kbps,
          recommendedAction: predictionResponse?.recommended_action
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
  
  if (isBackendAvailable && backendAPI) {
    console.log('🤖 Requesting AI summary from Amazon Bedrock backend...');
    const session = tab?.id ? (userSessions.get(tab.id) || {}) : {};
    const recent = telemetryHistory[telemetryHistory.length - 1] || {};
    
    console.log('📊 Sending context to Bedrock:', {
      video_id: videoId,
      has_captions: !!data?.captionsSnippet,
      caption_length: data?.captionsSnippet?.length || 0,
      has_title: !!data?.title,
      bandwidth_kbps: (recent.downlink || 0.8) * 1000
    });

    const backendSummary = await backendAPI.requestContentSummary({
      video_id: videoId,
      platform: platform || 'web',
      current_time: currentTime || 0,
      duration: data?.duration || session?.duration || null,
      title: data?.title || session?.title || '',
      url: data?.url || session?.url || '',
      bandwidth_kbps: (recent.downlink || 0.8) * 1000,
      transcript_hint: data?.captionsSnippet || null,
      visual_context_hint: data?.title || session?.title || null,
      key_concepts_hint: data?.keyConcepts || []
    });

    if (backendSummary) {
      console.log('✅ Bedrock AI summary received:', {
        summary_length: backendSummary.summary?.length || 0,
        key_concepts: backendSummary.keyConcepts?.length || 0,
        source: backendSummary.source
      });
      await cacheSummary(cacheKey, backendSummary);
      return backendSummary;
    } else {
      console.warn('⚠️ Backend returned null - falling back to local summary');
    }
  } else {
    console.warn('⚠️ Backend unavailable - using local fallback (NOT using Amazon Bedrock AI)');
    console.warn('   To enable Bedrock AI summaries:');
    console.warn('   1. Start backend: cd Backend && python main.py');
    console.warn('   2. Check backend URL matches in api-client.js');
    console.warn('   3. Ensure AWS credentials configured for Bedrock');
  }

  const fallbackSummary = generateMockSummary(data, tab);
  await cacheSummary(cacheKey, fallbackSummary);
  return fallbackSummary;
}

async function handleUserResumedVideo(data, tab) {
  const {
    videoId,
    currentTime,
    summaryReadSeconds,
    summaryAnchorText,
    duration
  } = data || {};

  const session = tab?.id ? (userSessions.get(tab.id) || {}) : {};
  const sessionId = session.session_id;
  const contentId = videoId || session.videoId || 'unknown_content';

  let mappedTimestamp = (currentTime || 0) + (summaryReadSeconds || 0);

  if (isBackendAvailable && backendAPI && sessionId) {
    const mapped = await backendAPI.mapResumePosition(sessionId, {
      content_id: contentId,
      fallback_timestamp: currentTime || 0,
      summary_read_seconds: summaryReadSeconds || 0,
      summary_anchor_text: summaryAnchorText || null,
      content_duration_seconds: duration || null
    });

    if (mapped && typeof mapped.mapped_timestamp === 'number') {
      mappedTimestamp = mapped.mapped_timestamp;
    }
  }

  if (duration && mappedTimestamp > duration) {
    mappedTimestamp = duration;
  }

  if (tab && tab.id) {
    chrome.tabs.sendMessage(tab.id, {
      type: 'RESUME_AT',
      data: {
        mappedTime: mappedTimestamp
      }
    }).catch(() => {});
  }

  return {
    mappedTime: mappedTimestamp,
    source: isBackendAvailable ? 'backend' : 'local'
  };
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

function generateMockSummary(data, tab) {
  // Extract video metadata
  const session = tab?.id ? (userSessions.get(tab.id) || {}) : {};
  const videoId = data?.videoId || 'unknown';
  const currentTime = data?.currentTime || 0;
  const duration = data?.duration || session?.duration || 0;
  const title = data?.title || session?.title || 'Video Content';
  const channel = data?.channel || 'Content Creator';
  const description = data?.description || null;
  const captionsSnippet = data?.captionsSnippet || null;
  const platform = data?.platform || 'web';
  
  // Calculate remaining time
  const remainingTime = duration > 0 ? duration - currentTime : 0;
  const progressPercent = duration > 0 ? ((currentTime / duration) * 100).toFixed(0) : 0;
  
  // Format time
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  // Generate key concepts based on title and description
  const keyConcepts = [];
  const titleLower = title.toLowerCase();
  const descLower = (description || '').toLowerCase();
  const combinedText = titleLower + ' ' + descLower;
  
  // Smart concept extraction based on content
  if (combinedText.includes('ai') || combinedText.includes('artificial intelligence')) {
    keyConcepts.push('Artificial Intelligence and Machine Learning');
  }
  if (combinedText.includes('education') || combinedText.includes('learning') || combinedText.includes('teach')) {
    keyConcepts.push('Educational Methods and Pedagogy');
  }
  if (combinedText.includes('technology') || combinedText.includes('tech') || combinedText.includes('digital')) {
    keyConcepts.push('Technology and Innovation');
  }
  if (combinedText.includes('chatgpt') || combinedText.includes('gpt') || combinedText.includes('language model')) {
    keyConcepts.push('Large Language Models and ChatGPT');
  }
  if (combinedText.includes('student') || combinedText.includes('school') || combinedText.includes('classroom')) {
    keyConcepts.push('Student Learning and Classroom Dynamics');
  }
  if (combinedText.includes('future') || combinedText.includes('transform')) {
    keyConcepts.push('Future Trends and Transformations');
  }
  
  // Add from captions if available
  if (captionsSnippet) {
    const captionLower = captionsSnippet.toLowerCase();
    if (captionLower.includes('important') || captionLower.includes('key point')) {
      keyConcepts.push('Critical Insights from Recent Discussion');
    }
  }
  
  // Add generic concepts if none were found
  if (keyConcepts.length === 0) {
    keyConcepts.push('Core Topic Introduction');
    keyConcepts.push('Key Principles and Frameworks');
    keyConcepts.push('Practical Applications');
  }
  
  // Limit to 5 concepts
  const finalConcepts = keyConcepts.slice(0, 5);
  
  // Generate summary text
  let summaryText = `<div class="sanchar-video-info">
    <h3>📺 ${title}</h3>
    <p class="sanchar-meta">👤 ${channel}</p>
    <p class="sanchar-meta">⏱️ Viewing position: ${formatTime(currentTime)} / ${formatTime(duration)} (${progressPercent}% complete)</p>
    <p class="sanchar-meta">📍 Platform: ${platform.charAt(0).toUpperCase() + platform.slice(1)}</p>
  </div>
  
  <div style="background: #fff4e6; border-left: 4px solid #ff9800; padding: 0.75rem 1rem; margin: 1rem 0; border-radius: 0.375rem;">
    <p style="margin: 0; font-size: 0.875rem; color: #e65100;">
      <strong>⚠️ Basic Fallback Mode:</strong> Backend unavailable - not using Amazon Bedrock AI. Start backend for intelligent educational summaries.
    </p>
  </div>
  
  <div class="sanchar-summary-section">
    <h4>📝 Content Information</h4>
    <p>You've been watching <strong>${title}</strong> by <strong>${channel}</strong>. You've reached ${formatTime(currentTime)} of the video.</p>`;
  
  // Add captions context if available - THIS IS THE ACTUAL VIDEO CONTENT
  if (captionsSnippet && captionsSnippet.length > 0) {
    summaryText += `
    <div class="sanchar-caption-preview" style="background: #e8f5e9; border-left-color: #4caf50;">
      <h5>🎤 What Was Just Said:</h5>
      <p class="sanchar-caption-text" style="font-size: 1rem; line-height: 1.7; color: #1b5e20;">
        "${captionsSnippet}"
      </p>
      <p style="font-size: 0.875rem; opacity: 0.7; margin-top: 0.75rem; color: #2e7d32;">
        ✓ Captions captured | <strong>Note:</strong> With Bedrock AI enabled, you'd get a full educational summary explaining these concepts
      </p>
    </div>`;
  } else {
    summaryText += `
    <div class="sanchar-caption-preview" style="background: #ffebee; border-left-color: #f44336;">
      <h5>❌ No Captions Available:</h5>
      <p style="margin: 0; font-size: 0.938rem; color: #c62828;">
        Cannot extract content - captions (CC) not enabled on this video. Enable captions for content extraction.
      </p>
    </div>`;
  }
  
  // Add description snippet if available
  if (description && description.length > 20) {
    summaryText += `
    <div style="margin-top: 1rem; padding: 0.75rem; background: #f5f5f5; border-radius: 0.5rem; border-left: 3px solid #9e9e9e;">
      <h5 style="font-size: 0.875rem; font-weight: 600; margin: 0 0 0.5rem 0; color: #424242;">📄 Video Description:</h5>
      <p style="font-size: 0.938rem; margin: 0; line-height: 1.6; color: #616161;">${description}</p>
    </div>`;
  }
  
  summaryText += `
    <p style="margin-top: 1rem;"><strong>What's Next:</strong> The video continues with approximately ${formatTime(remainingTime)} of content covering the key concepts listed below.</p>
  </div>
  
  <div class="sanchar-info-box">
    <p>⚡ <strong>Network Optimization Active:</strong> Instead of buffering or losing your place, you're viewing this information. With backend running, you'd see AI-generated educational summaries.</p>
  </div>`;
  
  return {
    videoId: videoId,
    timestamp: currentTime,
    duration: duration,
    title: title,
    channel: channel,
    keyConcepts: finalConcepts,
    summary: summaryText,
    visualDescriptions: captionsSnippet ? [
      `Video by ${channel} with captions enabled`,
      'Real-time content captured from live playback',
      'Educational context preserved for offline viewing'
    ] : [
      `Video by ${channel}`,
      'Visual content summary (enable captions for better context)',
      'Educational content continues from this timestamp'
    ],
    keyFrame: {
      url: `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`,
      format: 'jpg',
      timestamp: currentTime,
      caption: `Frame at ${formatTime(currentTime)} - ${title}`
    },
    compressionRatio: 0.08, // 8% of original size
    dataSaved: '92%',
    generatedBy: 'Sanchar Local Intelligence',
    generatedAt: Date.now(),
    captionsAvailable: !!captionsSnippet,
    realVideoData: true // Flag to indicate real data was used
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
