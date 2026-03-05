/**
 * SANCHAR-OPTIMIZE: Content Script (Video Interceptor)
 * Injects into video platforms and monitors playback state
 */

class VideoInterceptor {
  constructor() {
    this.platform = this.detectPlatform();
    this.videoElement = null;
    this.overlayInjected = false;
    this.isMonitoring = false;
    this.updateInterval = null;
    this.lastReportedTime = 0;
    this.reloadNotificationShown = false;
    this.overlayShownAt = null;
    this.summaryReadSeconds = 0;
    this.lastSummary = null;
    
    console.log(`🎯 Sanchar-Optimize active on ${this.platform}`);
  }

  /**
   * Detect which platform we're on
   */
  detectPlatform() {
    const hostname = window.location.hostname;
    
    if (hostname.includes('youtube.com')) {
      return 'youtube';
    } else if (hostname.includes('coursera.org')) {
      return 'coursera';
    } else {
      return 'generic';
    }
  }

  /**
   * Initialize the interceptor
   */
  async initialize() {
    console.log('🚀 Initializing Video Interceptor...');
    
    // Wait for video element to load
    await this.waitForVideoElement();
    
    // Start telemetry monitoring
    if (window.telemetryAgent) {
      window.telemetryAgent.startMonitoring(1000);
    }
    
    // Hook into video events
    this.attachVideoListeners();
    
    // Inject overlay
    this.injectOverlay();
    
    // Start monitoring loop
    this.startMonitoring();
    
    // Listen for messages from background
    this.listenForBackgroundMessages();
    
    console.log('✅ Video Interceptor initialized');
  }

  /**
   * Wait for video element to appear in DOM
   */
  async waitForVideoElement() {
    return new Promise((resolve) => {
      const findVideo = () => {
        const video = document.querySelector('video');
        if (video) {
          this.videoElement = video;
          console.log('📹 Video element found:', video);
          resolve(video);
        } else {
          setTimeout(findVideo, 500);
        }
      };
      findVideo();
    });
  }

  /**
   * Attach listeners to video events
   */
  attachVideoListeners() {
    if (!this.videoElement) return;

    // Track playback state
    this.videoElement.addEventListener('play', () => this.onVideoPlay());
    this.videoElement.addEventListener('pause', () => this.onVideoPause());
    this.videoElement.addEventListener('ended', () => this.onVideoEnd());
    this.videoElement.addEventListener('timeupdate', () => this.onTimeUpdate());
    this.videoElement.addEventListener('loadedmetadata', () => this.onMetadataLoaded());
    this.videoElement.addEventListener('waiting', () => this.onBuffering());
    this.videoElement.addEventListener('canplay', () => this.onBufferingEnd());

    console.log('🎧 Video event listeners attached');
  }

  /**
   * Video event handlers
   */
  onVideoPlay() {
    console.log('▶️ Video playing');
    this.sendVideoMetadata();
  }

  onVideoPause() {
    console.log('⏸️ Video paused');
  }

  onVideoEnd() {
    console.log('🏁 Video ended');
  }

  onTimeUpdate() {
    // Throttle updates - only report every 5 seconds
    const currentTime = this.videoElement.currentTime;
    if (Math.abs(currentTime - this.lastReportedTime) >= 5) {
      this.sendVideoMetadata();
      this.lastReportedTime = currentTime;
    }
  }

  onMetadataLoaded() {
    console.log('📊 Video metadata loaded');
    this.sendVideoMetadata();
  }

  onBuffering() {
    console.log('⏳ Video buffering...');
    
    // Note: Some buffering is normal (initial load, seeking, etc.)
    // We're trying to predict and prevent buffering caused by poor network
    // Only notify if buffering happens during active playback
    if (!this.videoElement.seeking && this.videoElement.currentTime > 0) {
      this.notifyBackground('BUFFERING_DETECTED', {
        currentTime: this.videoElement.currentTime,
        timestamp: Date.now(),
        wasPredicted: false // In Phase 1, we track if our prediction missed this
      });
    }
  }

  onBufferingEnd() {
    console.log('✅ Buffering ended');
  }

  /**
   * Start monitoring loop
   */
  startMonitoring() {
    if (this.isMonitoring) return;

    this.isMonitoring = true;
    
    // Send updates every 2 seconds
    this.updateInterval = setInterval(() => {
      if (this.videoElement && !this.videoElement.paused) {
        this.sendVideoMetadata();
      }
    }, 2000);

    console.log('👁️ Video monitoring started');
  }

  /**
   * Extract and send video metadata to background
   */
  sendVideoMetadata() {
    if (!this.videoElement) return;

    const metadata = this.extractMetadata();
    
    this.notifyBackground('VIDEO_METADATA', metadata);
  }

  /**
   * Extract metadata based on platform
   */
  extractMetadata() {
    const baseMetadata = {
      platform: this.platform,
      duration: this.videoElement.duration,
      currentTime: this.videoElement.currentTime,
      paused: this.videoElement.paused,
      ended: this.videoElement.ended,
      playbackRate: this.videoElement.playbackRate,
      volume: this.videoElement.volume,
      url: window.location.href,
      captionsSnippet: this.extractCaptionsSnippet()
    };

    // Platform-specific extraction
    if (this.platform === 'youtube') {
      return {
        ...baseMetadata,
        videoId: this.extractYouTubeVideoId(),
        title: this.extractYouTubeTitle()
      };
    } else if (this.platform === 'coursera') {
      return {
        ...baseMetadata,
        videoId: this.extractCourseraVideoId(),
        title: document.title
      };
    }

    return baseMetadata;
  }

  /**
   * Extract YouTube video ID from URL
   */
  extractYouTubeVideoId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('v') || 'unknown';
  }

  /**
   * Extract YouTube video title
   */
  extractYouTubeTitle() {
    // Try multiple selectors
    const titleElement = 
      document.querySelector('h1.ytd-watch-metadata yt-formatted-string') ||
      document.querySelector('h1.title') ||
      document.querySelector('meta[name="title"]');
    
    return titleElement?.textContent || titleElement?.content || document.title;
  }

  /**
   * Extract Coursera video ID
   */
  extractCourseraVideoId() {
    // Coursera video IDs are typically in the URL
    const match = window.location.pathname.match(/lecture\/([^/]+)/);
    return match ? match[1] : 'unknown';
  }

  extractCaptionsSnippet() {
    try {
      if (!this.videoElement || !this.videoElement.textTracks) {
        return null;
      }

      const snippets = [];
      for (const track of this.videoElement.textTracks) {
        const cues = track.activeCues;
        if (!cues || cues.length === 0) continue;
        for (let index = 0; index < cues.length; index++) {
          const cueText = (cues[index].text || '').trim();
          if (cueText) snippets.push(cueText);
        }
      }

      if (snippets.length === 0) {
        return null;
      }

      const unique = [...new Set(snippets)];
      return unique.join(' ').slice(0, 1200);
    } catch (error) {
      console.debug('Caption extraction unavailable:', error.message);
      return null;
    }
  }

  /**
   * Inject the Zero-Buffer overlay
   */
  injectOverlay() {
    if (this.overlayInjected) return;

    const overlayContainer = document.createElement('div');
    overlayContainer.id = 'sanchar-overlay-container';
    overlayContainer.style.display = 'none'; // Hidden by default
    overlayContainer.innerHTML = `
      <div id="sanchar-overlay" class="sanchar-hidden">
        <div class="sanchar-overlay-header">
          <div class="sanchar-logo">
            <span class="sanchar-icon">🛡️</span>
            <span class="sanchar-title">Sanchar-Optimize</span>
          </div>
          <div class="sanchar-status">
            <span class="sanchar-status-indicator"></span>
            <span class="sanchar-status-text">Network Resilience Active</span>
          </div>
        </div>
        
        <div class="sanchar-overlay-content">
          <div class="sanchar-message">
            <h2>📡 Network Signal Weak - Continuing Your Learning</h2>
            <p class="sanchar-subtitle">AI-Generated Summary replacing video stream</p>
          </div>
          
          <div class="sanchar-timeline">
            <div class="sanchar-timeline-bar">
              <div class="sanchar-timeline-progress"></div>
            </div>
            <div class="sanchar-timeline-labels">
              <span class="sanchar-time-current">0:00</span>
              <span class="sanchar-time-total">0:00</span>
            </div>
          </div>
          
          <div class="sanchar-summary-container">
            <div class="sanchar-summary-header">
              <h3>📝 Content Summary</h3>
              <span class="sanchar-ai-badge">AI-Generated</span>
            </div>
            
            <div id="sanchar-summary-content" class="sanchar-summary-content">
              <div class="sanchar-loading">
                <div class="sanchar-spinner"></div>
                <p>Generating intelligent summary...</p>
              </div>
            </div>
            
            <div class="sanchar-key-concepts">
              <h4>🎯 Key Concepts</h4>
              <ul id="sanchar-concepts-list"></ul>
            </div>
          </div>
          
          <div class="sanchar-actions">
            <button id="sanchar-resume-video" class="sanchar-btn sanchar-btn-primary" style="display:none;">
              ▶️ Resume Video
            </button>
            <button id="sanchar-continue-summary" class="sanchar-btn sanchar-btn-secondary">
              📄 Continue with Summary
            </button>
          </div>
        </div>
        
        <div class="sanchar-overlay-footer">
          <div class="sanchar-stats">
            <span class="sanchar-stat">
              <span class="sanchar-stat-label">Data Saved:</span>
              <span id="sanchar-data-saved" class="sanchar-stat-value">92%</span>
            </span>
            <span class="sanchar-stat">
              <span class="sanchar-stat-label">Compression:</span>
              <span id="sanchar-compression" class="sanchar-stat-value">8% of original</span>
            </span>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlayContainer);
    this.overlayInjected = true;
    
    // Attach button listeners
    this.attachOverlayListeners();

    console.log('🎨 Overlay injected into page');
  }

  /**
   * Attach listeners to overlay buttons
   */
  attachOverlayListeners() {
    const resumeBtn = document.getElementById('sanchar-resume-video');
    const continueBtn = document.getElementById('sanchar-continue-summary');

    if (resumeBtn) {
      resumeBtn.addEventListener('click', () => this.handleResumeVideo());
    }

    if (continueBtn) {
      continueBtn.addEventListener('click', () => this.handleContinueSummary());
    }
  }

  /**
   * Show the overlay with summary
   */
  showOverlay(summary) {
    const overlay = document.getElementById('sanchar-overlay');
    const summaryContent = document.getElementById('sanchar-summary-content');
    const conceptsList = document.getElementById('sanchar-concepts-list');

    if (!overlay || !summaryContent) return;

    this.lastSummary = summary;

    // Populate summary
    summaryContent.innerHTML = `
      <div class="sanchar-summary-text">
        ${summary.summary || 'Generating summary...'}
      </div>

      ${summary.keyFrame?.url ? `
        <div class="sanchar-visual-section">
          <h4>🖼️ Key Frame</h4>
          <img src="${summary.keyFrame.url}" alt="Key educational visual" style="max-width:100%;border-radius:12px;display:block;" />
        </div>
      ` : ''}
      
      ${summary.visualDescriptions ? `
        <div class="sanchar-visual-section">
          <h4>👁️ Visual Elements</h4>
          <ul>
            ${summary.visualDescriptions.map(desc => `<li>${desc}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    `;

    // Populate key concepts
    if (summary.keyConcepts && conceptsList) {
      conceptsList.innerHTML = summary.keyConcepts
        .map(concept => `<li>${concept}</li>`)
        .join('');
    }

    // Update stats
    if (summary.compressionRatio) {
      document.getElementById('sanchar-compression').textContent = 
        `${(summary.compressionRatio * 100).toFixed(0)}% of original`;
      document.getElementById('sanchar-data-saved').textContent = 
        `${(100 - summary.compressionRatio * 100).toFixed(0)}%`;
    }

    // Show overlay
    overlay.classList.remove('sanchar-hidden');
    overlay.classList.add('sanchar-visible');

    // Pause video
    if (this.videoElement) {
      this.videoElement.pause();
    }

    this.overlayShownAt = Date.now();
    this.summaryReadSeconds = 0;

    console.log('📺 Overlay displayed');
  }

  /**
   * Hide the overlay
   */
  hideOverlay() {
    const overlay = document.getElementById('sanchar-overlay');
    if (overlay) {
      overlay.classList.remove('sanchar-visible');
      overlay.classList.add('sanchar-hidden');
    }
  }

  /**
   * Handle resume video button
   */
  handleResumeVideo() {
    console.log('▶️ User chose to resume video');

    if (this.overlayShownAt) {
      this.summaryReadSeconds = Math.max(0, (Date.now() - this.overlayShownAt) / 1000);
    }

    const metadata = this.extractMetadata();

    chrome.runtime.sendMessage(
      {
        type: 'USER_RESUMED_VIDEO',
        data: {
          videoId: metadata.videoId,
          currentTime: metadata.currentTime,
          duration: metadata.duration,
          summaryReadSeconds: this.summaryReadSeconds,
          summaryAnchorText: this.lastSummary?.summary?.slice(0, 180) || ''
        },
        timestamp: Date.now()
      },
      (response) => {
        const mappedTime = response?.result?.mappedTime;

        if (typeof mappedTime === 'number' && this.videoElement) {
          this.videoElement.currentTime = mappedTime;
        }

        this.hideOverlay();

        if (this.videoElement) {
          this.videoElement.play();
        }
      }
    );
  }

  /**
   * Handle continue with summary button
   */
  handleContinueSummary() {
    console.log('📄 User chose to continue with summary');
    // Keep overlay visible, user wants to read
  }

  /**
   * Listen for messages from background script
   */
  listenForBackgroundMessages() {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      console.log('📨 Content script received:', message.type);

      switch (message.type) {
        case 'PREPARE_HANDSHAKE':
          this.handlePrepareHandshake(message.prediction);
          break;

        case 'SHOW_OVERLAY':
          this.handleShowOverlay(message.summary);
          break;

        case 'SIGNAL_RESTORED':
          this.handleSignalRestored(message.data);
          break;

        case 'RESUME_AT':
          this.handleResumeAt(message.data);
          break;

        default:
          console.warn('Unknown message type:', message.type);
      }

      sendResponse({ status: 'received' });
    });
  }

  /**
   * Handle prepare handshake (signal drop predicted)
   */
  async handlePrepareHandshake(prediction) {
    console.warn('⚠️ Preparing for handshake - signal drop imminent');
    console.log('Prediction:', prediction);

    // Request summary from background
    const metadata = this.extractMetadata();
    
    chrome.runtime.sendMessage(
      {
        type: 'REQUEST_SUMMARY',
        data: metadata
      },
      (response) => {
        if (response && response.status === 'success') {
          // Pre-cache the summary
          this.cachedSummary = response.summary;
          console.log('✅ Summary pre-cached and ready');
          
          // If network drops now, show overlay immediately
          this.checkNetworkAndShowOverlay();
        }
      }
    );
  }

  /**
   * Check network and show overlay if needed
   */
  checkNetworkAndShowOverlay() {
    // Check if network is actually degraded
    if (window.telemetryAgent && window.telemetryAgent.isNetworkDegraded()) {
      if (this.cachedSummary) {
        this.showOverlay(this.cachedSummary);
      }
    }
  }

  /**
   * Handle show overlay message
   */
  handleShowOverlay(summary) {
    this.showOverlay(summary);
  }

  /**
   * Handle signal restoration
   */
  handleSignalRestored(data) {
    console.log('✅ Signal restored - offering resume option');

    // Show resume button
    const resumeBtn = document.getElementById('sanchar-resume-video');
    if (resumeBtn) {
      resumeBtn.style.display = 'inline-block';
    }

    // Update status
    const statusText = document.querySelector('.sanchar-status-text');
    if (statusText) {
      statusText.textContent = 'Signal Restored - Resume Video?';
    }
  }

  handleResumeAt(data) {
    const mappedTime = data?.mappedTime;
    if (typeof mappedTime === 'number' && this.videoElement) {
      this.videoElement.currentTime = mappedTime;
    }
  }

  /**
   * Send message to background
   */
  notifyBackground(type, data) {
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
          // Silently handle common errors
          if (chrome.runtime.lastError) {
            // Service worker may be suspended - this is normal
            if (!chrome.runtime.lastError.message.includes('port closed')) {
              console.warn('Background communication warning:', chrome.runtime.lastError.message);
            }
          }
        }
      );
    } catch (error) {
      // Extension was reloaded - inform user
      if (error.message.includes('Extension context invalidated')) {
        console.log('ℹ️ Extension was reloaded. Refresh the page to reconnect.');
        this.showReloadNotification();
      }
    }
  }

  /**
   * Show notification that extension was reloaded
   */
  showReloadNotification() {
    // Only show once
    if (this.reloadNotificationShown) return;
    this.reloadNotificationShown = true;

    // Create a subtle notification
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 1rem 1.5rem;
      border-radius: 0.5rem;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      z-index: 999998;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 0.875rem;
      animation: slideIn 0.3s ease;
    `;
    notification.innerHTML = `
      <strong>🛡️ Sanchar-Optimize</strong><br>
      Extension reloaded. Refresh page to reconnect.
    `;

    document.body.appendChild(notification);

    // Remove after 5 seconds
    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 5000);
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    const interceptor = new VideoInterceptor();
    interceptor.initialize();
  });
} else {
  const interceptor = new VideoInterceptor();
  interceptor.initialize();
}

console.log('🎬 Content Script Loaded');
