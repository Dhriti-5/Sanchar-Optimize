/**
 * SANCHAR-OPTIMIZE: Telemetry Agent
 * Collects network health metrics and GPS data from the browser
 */

class TelemetryAgent {
  constructor() {
    this.isMonitoring = false;
    this.monitoringInterval = null;
    this.gpsWatchId = null;
    this.mockGPSInterval = null;
    this.lastPosition = null;
    this.lastVelocity = 0;
    this.mockSpeed = 0; // For simulated speed ramping
  }

  /**
   * Start monitoring network and GPS
   */
  startMonitoring(intervalMs = 1000) {
    if (this.isMonitoring) {
      console.warn('⚠️ Telemetry monitoring already active');
      return;
    }

    this.isMonitoring = true;
    console.log('📡 Telemetry monitoring started');

    // Start network monitoring
    this.monitoringInterval = setInterval(() => {
      this.collectNetworkTelemetry();
    }, intervalMs);

    // Start GPS monitoring
    this.startGPSTracking();

    // Initial collection
    this.collectNetworkTelemetry();
  }

  /**
   * Stop all monitoring
   */
  stopMonitoring() {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }

    if (this.gpsWatchId !== null) {
      navigator.geolocation.clearWatch(this.gpsWatchId);
      this.gpsWatchId = null;
    }

    this.stopMockGPSFallback();

    this.isMonitoring = false;
    console.log('🛑 Telemetry monitoring stopped');
  }

  /**
   * Collect network telemetry using Network Information API
   */
  collectNetworkTelemetry() {
    if (!navigator.connection && !navigator.mozConnection && !navigator.webkitConnection) {
      console.warn('⚠️ Network Information API not supported');
      return;
    }

    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;

    const telemetry = {
      timestamp: Date.now(),
      effectiveType: connection.effectiveType || 'unknown', // 'slow-2g', '2g', '3g', '4g'
      downlink: connection.downlink || 0, // Mbps
      downlinkMax: connection.downlinkMax || 0, // Mbps
      rtt: connection.rtt || 0, // Round-trip time in milliseconds
      saveData: connection.saveData || false,
      type: connection.type || 'unknown' // 'wifi', 'cellular', etc.
    };

    // Send to background script
    this.sendToBackground('NETWORK_TELEMETRY', telemetry);

    return telemetry;
  }

  /**
   * Start GPS tracking for velocity calculation
   */
  startGPSTracking() {
    if (!navigator.geolocation) {
      console.warn('⚠️ Geolocation API not supported');
      return;
    }

    console.log('🌍 GPS tracking started');

    this.gpsWatchId = navigator.geolocation.watchPosition(
      (position) => this.handleGPSUpdate(position),
      (error) => this.handleGPSError(error),
      {
        enableHighAccuracy: false, // Set to false to reduce timeout issues
        timeout: 10000, // Increased to 10 seconds
        maximumAge: 30000 // Allow cached position up to 30 seconds old
      }
    );

    // Fallback: Start sending mock data immediately
    // Real GPS will override if/when it becomes available
    this.startMockGPSFallback();
  }

  /**
   * Handle GPS position update and calculate velocity
   */
  handleGPSUpdate(position) {
    const currentPosition = {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      timestamp: position.timestamp,
      accuracy: position.coords.accuracy
    };

    // Calculate velocity if we have a previous position
    let velocity = 0;
    if (this.lastPosition) {
      velocity = this.calculateVelocity(this.lastPosition, currentPosition);
    }

    this.lastVelocity = velocity;
    this.lastPosition = currentPosition;

    // Send to background
    this.sendToBackground('GPS_VELOCITY', {
      latitude: currentPosition.latitude,
      longitude: currentPosition.longitude,
      velocity: velocity, // km/h
      accuracy: currentPosition.accuracy,
      timestamp: currentPosition.timestamp
    });

    console.log(`🚄 Current velocity: ${velocity.toFixed(2)} km/h`);
  }

  /**
   * Handle GPS errors
   */
  handleGPSError(error) {
    const errorMessages = {
      1: 'PERMISSION_DENIED',
      2: 'POSITION_UNAVAILABLE',
      3: 'TIMEOUT'
    };
    
    // Only log non-timeout errors as warnings (timeout is expected and handled)
    if (error.code !== 3) {
      console.warn(`📍 GPS ${errorMessages[error.code] || 'ERROR'}: ${error.message}`);
    }
    
    // Mock GPS is already running from startGPSTracking, but ensure it's active
    this.startMockGPSFallback();
  }

  /**
   * Start periodic mock GPS updates as fallback
   */
  startMockGPSFallback() {
    // Only start if not already running
    if (this.mockGPSInterval) {
      return;
    }

    console.log('🎭 Mock GPS fallback activated');
    
    // Send mock data every 5 seconds
    this.mockGPSInterval = setInterval(() => {
      this.sendMockGPSData();
    }, 5000);
    
    // Send first mock data immediately
    this.sendMockGPSData();
  }

  /**
   * Stop mock GPS fallback
   */
  stopMockGPSFallback() {
    if (this.mockGPSInterval) {
      clearInterval(this.mockGPSInterval);
      this.mockGPSInterval = null;
    }
  }

  /**
   * Send mock GPS data for testing
   */
  sendMockGPSData() {
    // Simulate realistic speed variations (ramping up/down)
    // This simulates someone getting on a train/bus
    const randomChange = (Math.random() - 0.5) * 20; // +/- 10 km/h
    this.mockSpeed = Math.max(0, Math.min(120, this.mockSpeed + randomChange));
    
    // Occasionally simulate high-speed mode (>60 km/h)
    if (Math.random() < 0.01) { // 1% chance to jump to high speed
      this.mockSpeed = 60 + Math.random() * 60; // 60-120 km/h
    }

    this.sendToBackground('GPS_VELOCITY', {
      latitude: 28.6139, // Delhi (mock)
      longitude: 77.2090,
      velocity: this.mockSpeed,
      accuracy: 10,
      timestamp: Date.now(),
      isMock: true
    });
    
    console.log(`🎭 Mock velocity: ${this.mockSpeed.toFixed(2)} km/h`);
  }

  /**
   * Calculate velocity between two GPS coordinates
   * Uses Haversine formula
   */
  calculateVelocity(pos1, pos2) {
    const R = 6371; // Earth radius in km

    const lat1 = this.toRadians(pos1.latitude);
    const lat2 = this.toRadians(pos2.latitude);
    const deltaLat = this.toRadians(pos2.latitude - pos1.latitude);
    const deltaLon = this.toRadians(pos2.longitude - pos1.longitude);

    const a = Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
              Math.cos(lat1) * Math.cos(lat2) *
              Math.sin(deltaLon / 2) * Math.sin(deltaLon / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distance = R * c; // Distance in km

    const timeDelta = (pos2.timestamp - pos1.timestamp) / 1000 / 60 / 60; // Convert ms to hours

    if (timeDelta === 0) return 0;

    const velocity = distance / timeDelta; // km/h

    return Math.abs(velocity);
  }

  /**
   * Convert degrees to radians
   */
  toRadians(degrees) {
    return degrees * (Math.PI / 180);
  }

  /**
   * Send message to background script
   */
  sendToBackground(type, data) {
    if (typeof chrome === 'undefined' || !chrome.runtime) {
      console.warn('⚠️ Chrome runtime not available');
      return;
    }

    try {
      chrome.runtime.sendMessage(
        {
          type: type,
          data: data,
          timestamp: Date.now()
        },
        (response) => {
          // Check for errors but don't spam console
          if (chrome.runtime.lastError) {
            // This is normal - service worker may have been suspended
            // Only log if it's not the common "port closed" error
            if (!chrome.runtime.lastError.message.includes('port closed')) {
              console.warn('Message send warning:', chrome.runtime.lastError.message);
            }
          }
        }
      );
    } catch (error) {
      // Extension context was invalidated - this is normal during development
      if (error.message.includes('Extension context invalidated')) {
        console.log('ℹ️ Extension was reloaded. Please refresh the page.');
      } else {
        console.error('Send message error:', error.message);
      }
    }
  }

  /**
   * Get current network status (synchronous)
   */
  getCurrentNetworkStatus() {
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    
    if (!connection) {
      return {
        online: navigator.onLine,
        effectiveType: 'unknown',
        downlink: 0
      };
    }

    return {
      online: navigator.onLine,
      effectiveType: connection.effectiveType,
      downlink: connection.downlink,
      rtt: connection.rtt
    };
  }

  /**
   * Check if network is degraded
   */
  isNetworkDegraded() {
    const status = this.getCurrentNetworkStatus();
    
    // Consider network degraded if:
    // - Offline
    // - Effective type is 2g or slow-2g
    // - Downlink < 0.5 Mbps
    
    return !status.online || 
           status.effectiveType === '2g' || 
           status.effectiveType === 'slow-2g' ||
           status.downlink < 0.5;
  }
}

// Create global instance
window.telemetryAgent = new TelemetryAgent();

console.log('📊 Telemetry Agent loaded');
