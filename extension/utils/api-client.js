/**
 * Backend API Client for Sanchar-Optimize Extension
 * Handles communication with Phase 2 FastAPI backend
 */

const API_CONFIG = {
    // IMPORTANT: Change this to your backend URL
    // Local development: http://localhost:8000/api/v1
    // Production AWS: https://2f8kolu7j4.execute-api.ap-south-1.amazonaws.com/production/api/v1
    BASE_URL: 'https://2f8kolu7j4.execute-api.ap-south-1.amazonaws.com/production/api/v1',
    
    // Endpoints
    ENDPOINTS: {
        HEALTH: '/health',
        TELEMETRY: '/telemetry',
        TELEMETRY_ENHANCED: '/telemetry/enhanced',
        TELEMETRY_BATCH: '/telemetry/batch',
        PREDICT: '/telemetry/predict',
        LOCATION_HISTORY: '/telemetry/location/history',
        LOCATION_STATISTICS: '/telemetry/location/statistics',
        SHADOW_ZONES: '/telemetry/shadow-zones',
        MODALITY_DECIDE: '/modality/decide',
        MODALITY_PANIC: '/modality/panic',
        MODALITY_STATUS: '/modality/status',
        SESSION_CREATE: '/session/create',
        SESSION_GET: '/session',
        SESSION_POSITION: '/session',
        SESSION_TRANSITION: '/session',
        SESSION_RESUME_MAP: '/session',
        CONTENT_SUMMARY: '/content/summary'
    },
    
    // Timeout in milliseconds
    TIMEOUT: 5000
};

class BackendAPI {
    constructor() {
        this.baseUrl = API_CONFIG.BASE_URL;
        this.enabled = true; // Can be disabled if backend unavailable
        this.lastHealthCheck = null;
    }

    /**
     * Check if backend is available
     */
    async checkHealth() {
        try {
            const response = await this._fetch(API_CONFIG.ENDPOINTS.HEALTH, {
                method: 'GET'
            });
            
            this.enabled = response && response.status === 'healthy';
            this.lastHealthCheck = Date.now();
            
            console.log('🏥 Backend health check:', this.enabled ? 'OK ✓' : 'Failed ✗');
            if (response) {
                console.log('   Service:', response.service, '| Version:', response.version);
            }
            return this.enabled;
        } catch (error) {
            console.error('❌ Backend health check failed:', error.message);
            console.warn('   Will attempt direct calls to API. Check:');
            console.warn('   1. Backend running? Start with: python Backend/main.py');
            console.warn('   2. URL correct? http://localhost:8000');
            console.warn('   3. CORS enabled? Check .env ALLOWED_ORIGINS');
            this.enabled = false;
            return false;
        }
    }

    /**
     * Submit telemetry to backend
     */
    async submitTelemetry(telemetry) {
        if (!this.enabled) {
            console.warn('Backend disabled, skipping telemetry submission');
            return null;
        }

        try {
            const response = await this._fetch(API_CONFIG.ENDPOINTS.TELEMETRY, {
                method: 'POST',
                body: JSON.stringify(telemetry)
            });
            
            return response;
        } catch (error) {
            console.error('Failed to submit telemetry:', error);
            return null;
        }
    }

    /**
     * Submit enhanced telemetry with location to backend (Phase 3)
     * This stores data in Timestream for historical pattern analysis
     */
    async submitEnhancedTelemetry(enhancedTelemetry) {
        if (!this.enabled) {
            return null;
        }

        try {
            const response = await this._fetch(API_CONFIG.ENDPOINTS.TELEMETRY_ENHANCED, {
                method: 'POST',
                body: JSON.stringify(enhancedTelemetry)
            });
            
            return response;
        } catch (error) {
            console.error('Failed to submit enhanced telemetry:', error);
            return null;
        }
    }

    /**
     * Get historical network patterns for a location
     */
    async getLocationHistory(latitude, longitude, timeRangeHours = 24) {
        if (!this.enabled) {
            return null;
        }

        try {
            const params = new URLSearchParams({
                latitude: latitude.toString(),
                longitude: longitude.toString(),
                time_range_hours: timeRangeHours.toString()
            });

            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.LOCATION_HISTORY}?${params}`,
                { method: 'GET' }
            );
            
            return response;
        } catch (error) {
            console.error('Failed to get location history:', error);
            return null;
        }
    }

    /**
     * Get statistical summary for a location
     */
    async getLocationStatistics(latitude, longitude, timeRangeHours = 168) {
        if (!this.enabled) {
            return null;
        }

        try {
            const params = new URLSearchParams({
                latitude: latitude.toString(),
                longitude: longitude.toString(),
                time_range_hours: timeRangeHours.toString()
            });

            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.LOCATION_STATISTICS}?${params}`,
                { method: 'GET' }
            );
            
            return response;
        } catch (error) {
            console.error('Failed to get location statistics:', error);
            return null;
        }
    }

    /**
     * Get shadow zones (areas with poor network)
     */
    async getShadowZones(minSamples = 50) {
        if (!this.enabled) {
            return null;
        }

        try {
            const params = new URLSearchParams({
                min_samples: minSamples.toString()
            });

            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.SHADOW_ZONES}?${params}`,
                { method: 'GET' }
            );
            
            console.log('🌑 Shadow zones retrieved:', response?.zone_count || 0);
            return response;
        } catch (error) {
            console.error('Failed to get shadow zones:', error);
            return null;
        }
    }

    /**
     * Create a new session (Phase 3)
     */
    async createSession(sessionId = null, platform = 'web') {
        try {
            console.log(`📋 Creating session: ${sessionId} (enabled=${this.enabled})`);
            
            const response = await this._fetch(API_CONFIG.ENDPOINTS.SESSION_CREATE, {
                method: 'POST',
                body: JSON.stringify({
                    session_id: sessionId,
                    platform: platform
                })
            });
            
            if (response && response.session_id) {
                console.log('📋 Session created:', response?.session_id);
                this.enabled = true; // Assume backend is working since request succeeded
                return response;
            }
            
            throw new Error('Invalid session response');
        } catch (error) {
            console.error('Failed to create session:', error);
            return { session_id: sessionId || this._generateSessionId(), status: 'local_only' };
        }
    }

    /**
     * Get session data
     */
    async getSession(sessionId) {
        if (!this.enabled) {
            return null;
        }

        try {
            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.SESSION_GET}/${sessionId}`,
                { method: 'GET' }
            );
            
            return response;
        } catch (error) {
            console.error('Failed to get session:', error);
            return null;
        }
    }

    /**
     * Update content position (Contextual Memory)
     */
    async updatePosition(sessionId, contentId, timestamp, modality, semanticContext = null) {
        if (!this.enabled) {
            return { status: 'local_only' };
        }

        try {
            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.SESSION_POSITION}/${sessionId}/position`,
                {
                    method: 'POST',
                    body: JSON.stringify({
                        content_id: contentId,
                        timestamp: timestamp,
                        modality: modality,
                        semantic_context: semanticContext
                    })
                }
            );
            
            return response;
        } catch (error) {
            console.error('Failed to update position:', error);
            return { status: 'failed' };
        }
    }

    /**
     * Get saved content position
     */
    async getPosition(sessionId, contentId) {
        if (!this.enabled) {
            return null;
        }

        try {
            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.SESSION_POSITION}/${sessionId}/position/${contentId}`,
                { method: 'GET' }
            );
            
            return response;
        } catch (error) {
            console.error('Failed to get position:', error);
            return null;
        }
    }

    /**
     * Record modality transition (Multi-Modal Handshake)
     */
    async recordTransition(sessionId, contentId, fromModality, toModality, timestamp, reason, networkConditions) {
        if (!this.enabled) {
            return { status: 'local_only' };
        }

        try {
            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.SESSION_TRANSITION}/${sessionId}/transition`,
                {
                    method: 'POST',
                    body: JSON.stringify({
                        content_id: contentId,
                        from_modality: fromModality,
                        to_modality: toModality,
                        timestamp: timestamp,
                        reason: reason,
                        network_conditions: networkConditions
                    })
                }
            );
            
            console.log('🔄 Transition recorded:', `${fromModality} → ${toModality}`);
            return response;
        } catch (error) {
            console.error('Failed to record transition:', error);
            return { status: 'failed' };
        }
    }

    /**
     * Get transition history
     */
    async getTransitions(sessionId, limit = 50) {
        if (!this.enabled) {
            return null;
        }

        try {
            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.SESSION_TRANSITION}/${sessionId}/transitions?limit=${limit}`,
                { method: 'GET' }
            );
            
            return response;
        } catch (error) {
            console.error('Failed to get transitions:', error);
            return null;
        }
    }

    async mapResumePosition(sessionId, payload) {
        if (!this.enabled) {
            return null;
        }

        try {
            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.SESSION_RESUME_MAP}/${sessionId}/resume-map`,
                {
                    method: 'POST',
                    body: JSON.stringify(payload)
                }
            );

            return response;
        } catch (error) {
            console.error('Failed to map resume position:', error);
            return null;
        }
    }

    /**
     * Generate a session ID
     */
    _generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Submit batch telemetry to backend
     */
    async submitTelemetryBatch(deviceIdOrTelemetryArray, sessionId, telemetryArray) {
        if (!this.enabled) {
            return null;
        }

        try {
            let resolvedDeviceId = deviceIdOrTelemetryArray;
            let resolvedSessionId = sessionId;
            let resolvedTelemetry = telemetryArray;

            if (Array.isArray(deviceIdOrTelemetryArray) && !sessionId && !telemetryArray) {
                resolvedTelemetry = deviceIdOrTelemetryArray;
                resolvedSessionId = (resolvedTelemetry[0] && resolvedTelemetry[0].session_id) || this._generateSessionId();
                resolvedDeviceId = `device_${resolvedSessionId}`;
            }

            const batch = {
                device_id: resolvedDeviceId,
                session_id: resolvedSessionId,
                telemetry: resolvedTelemetry
            };

            const response = await this._fetch(API_CONFIG.ENDPOINTS.TELEMETRY_BATCH, {
                method: 'POST',
                body: JSON.stringify(batch)
            });
            
            console.log('📊 Batch telemetry submitted:', response);
            return response;
        } catch (error) {
            console.error('Failed to submit batch telemetry:', error);
            return null;
        }
    }

    /**
     * Get signal drop prediction from backend
     */
    async getPrediction(deviceIdOrRecentTelemetry, sessionId, recentTelemetry) {
        if (!this.enabled) {
            return null;
        }

        try {
            let resolvedDeviceId = deviceIdOrRecentTelemetry;
            let resolvedSessionId = sessionId;
            let resolvedTelemetry = recentTelemetry;

            if (Array.isArray(deviceIdOrRecentTelemetry) && !sessionId && !recentTelemetry) {
                resolvedTelemetry = deviceIdOrRecentTelemetry;
                resolvedSessionId = (resolvedTelemetry[0] && resolvedTelemetry[0].session_id) || this._generateSessionId();
                resolvedDeviceId = `device_${resolvedSessionId}`;
            }

            const request = {
                device_id: resolvedDeviceId,
                session_id: resolvedSessionId,
                recent_telemetry: resolvedTelemetry
            };

            const response = await this._fetch(API_CONFIG.ENDPOINTS.PREDICT, {
                method: 'POST',
                body: JSON.stringify(request)
            });
            
            if (response && response.prediction) {
                console.log('🔮 Prediction received:', {
                    confidence: response.prediction.confidence,
                    time_to_drop: response.prediction.predicted_time_seconds,
                    action: response.recommended_action
                });
            }
            
            return response;
        } catch (error) {
            console.error('Failed to get prediction:', error);
            return null;
        }
    }

    async requestContentSummary(request) {
        if (!this.enabled) {
            return null;
        }

        try {
            return await this._fetch(API_CONFIG.ENDPOINTS.CONTENT_SUMMARY, {
                method: 'POST',
                body: JSON.stringify(request)
            });
        } catch (error) {
            console.error('Failed to get content summary:', error);
            return null;
        }
    }

    /**
     * Get modality decision from backend (AI-powered)
     */
    async getModalityDecision(request) {
        if (!this.enabled) {
            return null;
        }

        try {
            const response = await this._fetch(API_CONFIG.ENDPOINTS.MODALITY_DECIDE, {
                method: 'POST',
                body: JSON.stringify(request)
            });
            
            if (response) {
                console.log('🎭 Modality decision received:', {
                    target: response.target_modality,
                    timing: response.transition_timing,
                    confidence: response.decision_confidence,
                    reasoning: response.reasoning
                });
            }
            
            return response;
        } catch (error) {
            console.error('Failed to get modality decision:', error);
            return null;
        }
    }

    /**
     * Send panic signal to backend for immediate decision
     */
    async sendPanicSignal(deviceId, sessionId, contentId, contentPosition, currentModality, bandwidth, isBuffering, bufferLevel) {
        if (!this.enabled) {
            return null;
        }

        try {
            const panic = {
                device_id: deviceId,
                session_id: sessionId,
                content_id: contentId,
                content_position: contentPosition,
                current_modality: currentModality,
                current_bandwidth_kbps: bandwidth,
                is_buffering: isBuffering,
                buffer_level_seconds: bufferLevel
            };

            const response = await this._fetch(API_CONFIG.ENDPOINTS.MODALITY_PANIC, {
                method: 'POST',
                body: JSON.stringify(panic)
            });
            
            console.warn('🚨 PANIC SIGNAL sent:', response);
            return response;
        } catch (error) {
            console.error('Failed to send panic signal:', error);
            return null;
        }
    }

    /**
     * Get modality status for a session
     */
    async getModalityStatus(sessionId) {
        if (!this.enabled) {
            return null;
        }

        try {
            const response = await this._fetch(
                `${API_CONFIG.ENDPOINTS.MODALITY_STATUS}/${sessionId}`,
                { method: 'GET' }
            );
            
            return response;
        } catch (error) {
            console.error('Failed to get modality status:', error);
            return null;
        }
    }

    /**
     * Internal fetch wrapper with timeout and error handling
     */
    async _fetch(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), API_CONFIG.TIMEOUT);

        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                signal: controller.signal
            });

            clearTimeout(timeout);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeout);
            
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }
            
            throw error;
        }
    }

    /**
     * Set backend URL (for configuration)
     */
    setBaseUrl(url) {
        this.baseUrl = url;
        console.log('🔧 Backend URL updated:', url);
    }

    /**
     * Enable or disable backend communication
     */
    setEnabled(enabled) {
        this.enabled = enabled;
        console.log('🔧 Backend communication:', enabled ? 'enabled' : 'disabled');
    }
}

// Export for ES6 modules (Manifest V3 service workers)
export { BackendAPI, API_CONFIG };

// Export singleton instance
export const backendAPI = new BackendAPI();

// Check health on initialization (non-blocking)
backendAPI.checkHealth().catch(err => {
    console.warn('Initial health check failed, will retry later');
});

// Re-check health every 5 minutes
setInterval(() => {
    backendAPI.checkHealth();
}, 5 * 60 * 1000);
