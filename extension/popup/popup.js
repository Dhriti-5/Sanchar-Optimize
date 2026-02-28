/**
 * SANCHAR-OPTIMIZE: Popup Script
 * Displays extension status and statistics
 */

// Update popup UI with current stats
async function updatePopupUI() {
  try {
    // Get data from storage
    const result = await chrome.storage.local.get([
      'systemState',
      'telemetryHistory',
      'sessionMemory',
      'cachedSummaries'
    ]);

    const systemState = result.systemState || 'passive';
    const telemetryHistory = result.telemetryHistory || [];
    const cachedSummaries = result.cachedSummaries || {};

    // Update status indicator
    updateStatusIndicator(systemState);

    // Update network quality
    if (telemetryHistory.length > 0) {
      const latestTelemetry = telemetryHistory[telemetryHistory.length - 1];
      updateNetworkQuality(latestTelemetry);
    }

    // Update statistics
    updateStatistics(telemetryHistory, cachedSummaries);

  } catch (error) {
    console.error('Failed to update popup:', error);
  }
}

function updateStatusIndicator(state) {
  const indicator = document.getElementById('status-indicator');
  const statusText = document.getElementById('status-text');

  indicator.className = 'status-indicator';
  
  switch (state) {
    case 'passive':
      indicator.classList.add('passive');
      statusText.textContent = 'Passive Mode - All Systems Normal';
      statusText.style.color = '#10b981';
      break;
    case 'warning':
      indicator.classList.add('warning');
      statusText.textContent = 'Warning - Signal Drop Predicted';
      statusText.style.color = '#fbbf24';
      break;
    case 'active_resilience':
      indicator.classList.add('active');
      statusText.textContent = 'Active Resilience - Overlay Active';
      statusText.style.color = '#ef4444';
      break;
  }
}

function updateNetworkQuality(telemetry) {
  const qualityElement = document.getElementById('network-quality');
  
  if (!telemetry.effectiveType) {
    qualityElement.textContent = 'Unknown';
    return;
  }

  const effectiveType = telemetry.effectiveType;
  
  let quality = 'Unknown';
  let color = '#6b7280';
  
  switch (effectiveType) {
    case '4g':
      quality = 'Excellent';
      color = '#10b981';
      break;
    case '3g':
      quality = 'Good';
      color = '#3b82f6';
      break;
    case '2g':
      quality = 'Poor';
      color = '#f59e0b';
      break;
    case 'slow-2g':
      quality = 'Very Poor';
      color = '#ef4444';
      break;
  }
  
  qualityElement.textContent = quality;
  qualityElement.style.color = color;

  // Update velocity if available
  const velocityElement = document.getElementById('velocity');
  if (telemetry.velocity !== undefined) {
    velocityElement.textContent = `${Math.round(telemetry.velocity)} km/h`;
  }
}

function updateStatistics(telemetryHistory, cachedSummaries) {
  // Count summaries
  const summariesCount = Object.keys(cachedSummaries).length;
  document.getElementById('summaries-generated').textContent = summariesCount;

  // Calculate data saved (mock calculation for now)
  const dataSavedMB = summariesCount * 15; // Assume 15MB saved per summary
  document.getElementById('data-saved').textContent = `${dataSavedMB} MB`;

  // Monitoring frequency (derive from telemetry)
  if (telemetryHistory.length >= 2) {
    const timeDiff = telemetryHistory[telemetryHistory.length - 1].timestamp - 
                     telemetryHistory[telemetryHistory.length - 2].timestamp;
    const frequency = timeDiff ? (1000 / timeDiff).toFixed(1) : '1.0';
    document.getElementById('monitoring-freq').textContent = `${frequency} Hz`;
  }
}

// Test handshake button
document.getElementById('test-handshake').addEventListener('click', async () => {
  console.log('🧪 Testing handshake...');
  
  // Get active tab
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tabs[0]) {
    // Send test message
    chrome.tabs.sendMessage(tabs[0].id, {
      type: 'PREPARE_HANDSHAKE',
      prediction: {
        dropPredicted: true,
        confidence: 0.95,
        horizonSeconds: 5,
        reasoning: { test: true }
      }
    });
    
    alert('Test handshake initiated! Check the active tab.');
  }
});

// Clear cache button
document.getElementById('clear-cache').addEventListener('click', async () => {
  if (confirm('Clear all cached summaries?')) {
    await chrome.storage.local.set({
      cachedSummaries: {},
      telemetryHistory: []
    });
    
    alert('Cache cleared successfully!');
    updatePopupUI();
  }
});

// Documentation link
document.getElementById('view-docs').addEventListener('click', (e) => {
  e.preventDefault();
  chrome.tabs.create({ 
    url: 'https://github.com/Dhriti-5/Sanchar-Optimize' 
  });
});

// GitHub link
document.getElementById('view-github').addEventListener('click', (e) => {
  e.preventDefault();
  chrome.tabs.create({ 
    url: 'https://github.com/Dhriti-5/Sanchar-Optimize' 
  });
});

// Update UI on load
document.addEventListener('DOMContentLoaded', () => {
  updatePopupUI();
  
  // Refresh every 2 seconds
  setInterval(updatePopupUI, 2000);
});
