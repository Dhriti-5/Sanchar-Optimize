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
    this.lastCaptionSnippet = null; // Cache last successful caption extraction
    this.captionCheckCount = 0;
    
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
    
    // Listen for network state changes from telemetry agent
    this.listenForNetworkChanges();
    
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
    const captionsSnippet = this.extractCaptionsSnippet();
    
    // Cache captions if we got them
    if (captionsSnippet) {
      this.lastCaptionSnippet = captionsSnippet;
    }
    
    const baseMetadata = {
      platform: this.platform,
      duration: this.videoElement.duration,
      currentTime: this.videoElement.currentTime,
      paused: this.videoElement.paused,
      ended: this.videoElement.ended,
      playbackRate: this.videoElement.playbackRate,
      volume: this.videoElement.volume,
      url: window.location.href,
      captionsSnippet: captionsSnippet || this.lastCaptionSnippet // Use cached if current extraction fails
    };

    // Platform-specific extraction
    if (this.platform === 'youtube') {
      return {
        ...baseMetadata,
        videoId: this.extractYouTubeVideoId(),
        title: this.extractYouTubeTitle(),
        channel: this.extractYouTubeChannel(),
        description: this.extractYouTubeDescription()
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
    // Try multiple selectors in order of preference
    const selectors = [
      'h1.ytd-watch-metadata yt-formatted-string',
      'h1.ytd-video-primary-info-renderer yt-formatted-string',
      'yt-formatted-string.style-scope.ytd-watch-metadata',
      'h1.title.style-scope.ytd-watch-metadata',
      '#container h1',
      'h1.title'
    ];
    
    for (const selector of selectors) {
      const titleElement = document.querySelector(selector);
      if (titleElement && titleElement.textContent?.trim()) {
        const title = titleElement.textContent.trim();
        console.log(`📺 Extracted YouTube title: "${title.substring(0, 50)}..."`);
        return title;
      }
    }
    
    // Fallback to meta tag
    const metaTitle = document.querySelector('meta[name="title"]');
    if (metaTitle?.content) {
      return metaTitle.content;
    }
    
    // Last resort: document title (includes " - YouTube")
    const docTitle = document.title.replace(' - YouTube', '').trim();
    console.log(`📺 Using document title: "${docTitle.substring(0, 50)}..."`);
    return docTitle;
  }

  /**
   * Extract YouTube channel name
   */
  extractYouTubeChannel() {
    const selectors = [
      'ytd-channel-name a',
      'ytd-video-owner-renderer a',
      '#upload-info a',
      '#owner-name a'
    ];
    
    for (const selector of selectors) {
      const channelElement = document.querySelector(selector);
      if (channelElement && channelElement.textContent?.trim()) {
        return channelElement.textContent.trim();
      }
    }
    
    return 'Unknown Channel';
  }

  /**
   * Extract YouTube video description snippet
   */
  extractYouTubeDescription() {
    const selectors = [
      'ytd-text-inline-expander#description-inline-expander',
      '#description yt-formatted-string',
      '#description',
      '.content.ytd-video-secondary-info-renderer'
    ];
    
    for (const selector of selectors) {
      const descElement = document.querySelector(selector);
      if (descElement && descElement.textContent?.trim()) {
        const desc = descElement.textContent.trim();
        // Return first 300 characters
        return desc.substring(0, 300);
      }
    }
    
    return null;
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
      // YouTube-specific caption extraction from DOM
      if (this.platform === 'youtube') {
        return this.extractYouTubeCaptions();
      }
      
      // Generic HTML5 textTracks for other platforms
      if (!this.videoElement || !this.videoElement.textTracks) {
        return null;
      }

      const snippets = [];
      for (const track of this.videoElement.textTracks) {
        // Only use showing or hidden tracks
        if (track.mode === 'disabled') continue;
        
        const cues = track.activeCues;
        if (!cues || cues.length === 0) continue;
        
        for (let index = 0; index < cues.length; index++) {
          const cueText = (cues[index].text || '').trim();
          if (cueText) snippets.push(cueText);
        }
      }

      if (snippets.length === 0) {
        console.log('ℹ️ No active captions found (captions may be off)');
        return null;
      }

      const unique = [...new Set(snippets)];
      const captionText = unique.join(' ').slice(0, 1200);
      console.log(`📝 Extracted ${captionText.length} chars of captions`);
      return captionText;
    } catch (error) {
      console.debug('Caption extraction unavailable:', error.message);
      return null;
    }
  }

  /**
   * Extract YouTube captions from DOM (YouTube-specific)
   */
  extractYouTubeCaptions() {
    try {
      this.captionCheckCount++;
      
      // YouTube renders captions in specific DOM elements
      const captionSelectors = [
        '.ytp-caption-segment',           // Individual caption segments
        '.caption-window .captions-text', // Caption window text
        '.ytp-caption-window-container',  // Caption container
        'div.ytp-caption-window-rollup span.ytp-caption-segment', // Specific YouTube structure
        '[class*="caption"]'              // Any element with caption in class
      ];

      let captionText = '';
      let foundSelector = null;
      
      // Try each selector
      for (const selector of captionSelectors) {
        const captionElements = document.querySelectorAll(selector);
        if (captionElements.length > 0) {
          const texts = Array.from(captionElements)
            .map(el => el.textContent?.trim())
            .filter(text => text && text.length > 0);
          
          if (texts.length > 0) {
            captionText = texts.join(' ');
            foundSelector = selector;
            console.log(`📝 ✅ Caption extraction SUCCESS! Found ${texts.length} segments using selector: "${selector}"`);
            console.log(`📝 Extracted ${captionText.length} chars: "${captionText.substring(0, 100)}..."`);
            break;
          }
        }
      }

      // Debug logging every 10 checks
      if (this.captionCheckCount % 10 === 0) {
        console.log(`🔍 Caption check #${this.captionCheckCount}:`);
        console.log('  - Testing selectors:', captionSelectors);
        
        // Check if caption container exists
        const container = document.querySelector('.ytp-caption-window-container');
        console.log('  - Caption container exists:', !!container);
        
        if (container) {
          console.log('  - Container innerHTML:', container.innerHTML.substring(0, 200));
        }
        
        // Check if CC button is active
        const ccButton = document.querySelector('.ytp-subtitles-button');
        if (ccButton) {
          const isActive = ccButton.getAttribute('aria-pressed') === 'true';
          console.log('  - CC button pressed:', isActive);
        }
      }

      // If no captions found in DOM, they might be off
      if (!captionText || captionText.length < 10) {
        if (this.captionCheckCount <= 5) {
          console.log(`ℹ️ No YouTube captions visible yet (check #${this.captionCheckCount}). Make sure CC button is enabled.`);
        }
        return null;
      }

      // Return up to 1200 characters
      return captionText.slice(0, 1200);
    } catch (error) {
      console.error('❌ YouTube caption extraction error:', error);
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
    const overlayContainer = document.getElementById('sanchar-overlay-container');
    const overlay = document.getElementById('sanchar-overlay');
    const summaryContent = document.getElementById('sanchar-summary-content');
    const conceptsList = document.getElementById('sanchar-concepts-list');

    if (!overlay || !summaryContent) {
      console.error('❌ Overlay elements not found');
      return;
    }

    // Make sure container is visible
    if (overlayContainer) {
      overlayContainer.style.display = 'block';
    }

    this.lastSummary = summary;

    // Format timestamp
    const formatTime = (seconds) => {
      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const currentTime = summary.timestamp || this.videoElement?.currentTime || 0;
    const duration = this.videoElement?.duration || 0;

    // Update timeline
    const timelineProgress = document.querySelector('.sanchar-timeline-progress');
    const timeCurrent = document.querySelector('.sanchar-time-current');
    const timeTotal = document.querySelector('.sanchar-time-total');
    
    if (timelineProgress && duration > 0) {
      const progress = (currentTime / duration) * 100;
      timelineProgress.style.width = `${progress}%`;
    }
    
    if (timeCurrent) timeCurrent.textContent = formatTime(currentTime);
    if (timeTotal) timeTotal.textContent = formatTime(duration);

    // Populate summary with educational structure
    summaryContent.innerHTML = `
      <div class="sanchar-stop-indicator">
        <h3>⏸️ Video Paused at ${formatTime(currentTime)}</h3>
        <p class="sanchar-subtitle">Network unstable - AI summary generated for continuous learning</p>
      </div>

      ${summary.keyConcepts && summary.keyConcepts.length > 0 ? `
        <div class="sanchar-learning-section">
          <h4>🎯 Key Concepts (Current Segment)</h4>
          <ul class="sanchar-concept-list">
            ${summary.keyConcepts.map(concept => `<li>${concept}</li>`).join('')}
          </ul>
        </div>
      ` : ''}

      <div class="sanchar-summary-text">
        <h4>📖 What's Being Covered</h4>
        ${summary.summary || 'Generating summary...'}
      </div>

      ${summary.whatYouLearned ? `
        <div class="sanchar-learning-section sanchar-past">
          <h4>✅ What You Just Learned (Before ${formatTime(Math.max(0, currentTime - 30))})</h4>
          <p>${summary.whatYouLearned}</p>
        </div>
      ` : ''}

      ${summary.whatsNext ? `
        <div class="sanchar-learning-section sanchar-future">
          <h4>➡️ What's Coming Next (After ${formatTime(currentTime + 30)})</h4>
          <p>${summary.whatsNext}</p>
        </div>
      ` : ''}

      ${summary.keyFrame?.url ? `
        <div class="sanchar-visual-section">
          <h4>🖼️ Key Visual</h4>
          <img src="${summary.keyFrame.url}" alt="Key educational visual" style="max-width:100%;border-radius:12px;display:block;" />
        </div>
      ` : ''}
      
      ${summary.visualDescriptions && summary.visualDescriptions.length > 0 ? `
        <div class="sanchar-visual-section">
          <h4>👁️ Visual Elements</h4>
          <ul>
            ${summary.visualDescriptions.map(desc => `<li>${desc}</li>`).join('')}
          </ul>
        </div>
      ` : ''}

      <div class="sanchar-resume-info">
        <p><strong>💡 Tip:</strong> When network improves, video will resume from ${formatTime(currentTime)}</p>
      </div>
    `;

    // Populate key concepts sidebar (if different from inline)
    if (summary.keyConcepts && conceptsList) {
      conceptsList.innerHTML = summary.keyConcepts
        .map(concept => `<li>${concept}</li>`)
        .join('');
    }

    // Update stats
    if (summary.compressionRatio) {
      const compressionEl = document.getElementById('sanchar-compression');
      const dataSavedEl = document.getElementById('sanchar-data-saved');
      if (compressionEl) {
        compressionEl.textContent = `${(summary.compressionRatio * 100).toFixed(0)}% of original`;
      }
      if (dataSavedEl) {
        dataSavedEl.textContent = `${(100 - summary.compressionRatio * 100).toFixed(0)}%`;
      }
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

    console.log('📺 Overlay displayed with educational context at', formatTime(currentTime));
  }

  /**
   * Hide the overlay
   */
  hideOverlay() {
    const overlayContainer = document.getElementById('sanchar-overlay-container');
    const overlay = document.getElementById('sanchar-overlay');
    
    if (overlay) {
      overlay.classList.remove('sanchar-visible');
      overlay.classList.add('sanchar-hidden');
    }
    
    // Hide container too
    if (overlayContainer) {
      overlayContainer.style.display = 'none';
    }
    
    console.log('📺 Overlay hidden');
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
   * Listen for network state changes from telemetry agent
   */
  listenForNetworkChanges() {
    window.addEventListener('sanchar-check-network', (event) => {
      console.log('🔍 Network check triggered, degraded:', event.detail.degraded);
      
      // If network is degraded and we have a cached summary, show overlay immediately
      if (event.detail.degraded && this.cachedSummary) {
        console.log('📺 Network degraded - showing cached summary overlay');
        this.showOverlay(this.cachedSummary);
      } else if (event.detail.degraded && !this.cachedSummary) {
        // Network degraded but no cached summary - request one now
        console.log('⚠️ Network degraded but no cached summary - requesting...');
        this.requestAndShowSummary();
      } else if (!event.detail.degraded) {
        // Network restored - hide overlay and resume
        console.log('✅ Network restored - hiding overlay');
        this.handleSignalRestored();
      }
    });

    // Add manual test trigger (Ctrl+Shift+S)
    document.addEventListener('keydown', (event) => {
      if (event.ctrlKey && event.shiftKey && event.key === 'S') {
        console.log('🧪 Manual overlay test triggered');
        this.testShowOverlay();
      }
    });
  }

  /**
   * Test overlay display with real data extraction
   */
  testShowOverlay() {
    console.log('🧪 Manual test triggered - extracting real video data...');
    
    // Extract real metadata from video
    const metadata = this.extractMetadata();
    
    console.log('🧪 Test metadata:', {
      title: metadata.title,
      channel: metadata.channel,
      videoId: metadata.videoId,
      currentTime: metadata.currentTime,
      hasCaptions: !!metadata.captionsSnippet,
      captionLength: metadata.captionsSnippet?.length || 0
    });
    
    // Request real summary from background (not mock data)
    this.requestAndShowSummary();
  }

  /**
   * Request summary and show overlay immediately
   */
  requestAndShowSummary() {
    const metadata = this.extractMetadata();
    
    console.log('📊 Requesting summary with metadata:', {
      videoId: metadata.videoId,
      title: metadata.title,
      currentTime: metadata.currentTime,
      duration: metadata.duration,
      hasCaptions: !!metadata.captionsSnippet,
      captionsLength: metadata.captionsSnippet?.length || 0
    });
    
    chrome.runtime.sendMessage(
      {
        type: 'REQUEST_SUMMARY',
        data: metadata
      },
      (response) => {
        if (response && response.status === 'success' && response.summary) {
          this.cachedSummary = response.summary;
          console.log('✅ Summary received, displaying overlay');
          this.showOverlay(response.summary);
        } else {
          console.warn('⚠️ Summary request failed, showing fallback');
          // Show a basic overlay with loading message
          this.showOverlay({
            summary: '⚠️ Network connection lost. Working to retrieve content summary...',
            keyConcepts: ['Network offline', 'Attempting to recover session'],
            compressionRatio: 0.05
          });
        }
      }
    );
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
    console.log('✅ Signal restored - auto-resuming video');

    // Hide overlay automatically
    this.hideOverlay();
    
    // Resume video playback
    if (this.videoElement && this.videoElement.paused) {
      this.videoElement.play().then(() => {
        console.log('▶️ Video resumed automatically');
      }).catch(err => {
        console.warn('Could not auto-resume video:', err.message);
      });
    }
    
    // Show a brief notification
    this.showRestorationNotification();
  }
  
  /**
   * Show brief notification that signal was restored
   */
  showRestorationNotification() {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 80px;
      right: 20px;
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: white;
      padding: 1rem 1.5rem;
      border-radius: 0.75rem;
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
      z-index: 999997;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 0.875rem;
      animation: slideInRight 0.3s ease;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    `;
    notification.innerHTML = `
      <span style="font-size: 1.5rem;">✅</span>
      <div>
        <strong>Network Restored</strong><br>
        <span style="opacity: 0.9; font-size: 0.813rem;">Video resumed automatically</span>
      </div>
    `;

    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
      notification.style.animation = 'slideOutRight 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 3000);
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
    window.videoInterceptor = new VideoInterceptor();
    window.videoInterceptor.initialize();
  });
} else {
  window.videoInterceptor = new VideoInterceptor();
  window.videoInterceptor.initialize();
}

console.log('🎬 Content Script Loaded');
