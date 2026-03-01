/**
 * Backend API Client for Sanchar-Optimize Extension
 * Handles communication with Phase 2 FastAPI backend
 */

const API_CONFIG = {
    // Update this to your backend URL
    BASE_URL: 'http://localhost:8000/api/v1',
    
    // Endpoints
    ENDPOINTS: {
        HEALTH: '/health',
        TELEMETRY: '/telemetry',
        TELEMETRY_BATCH: '/telemetry/batch',
        PREDICT: '/telemetry/predict',
        MODALITY_DECIDE: '/modality/decide',
        MODALITY_PANIC: '/modality/panic',
        MODALITY_STATUS: '/modality/status'
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
            
            console.log('🏥 Backend health check:', this.enabled ? 'OK' : 'Failed');
            return this.enabled;
        } catch (error) {
            console.error('❌ Backend health check failed:', error);
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
     * Submit batch telemetry to backend
     */
    async submitTelemetryBatch(deviceId, sessionId, telemetryArray) {
        if (!this.enabled) {
            return null;
        }

        try {
            const batch = {
                device_id: deviceId,
                session_id: sessionId,
                telemetry: telemetryArray
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
    async getPrediction(deviceId, sessionId, recentTelemetry) {
        if (!this.enabled) {
            return null;
        }

        try {
            const request = {
                device_id: deviceId,
                session_id: sessionId,
                recent_telemetry: recentTelemetry
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

// Export singleton instance
const backendAPI = new BackendAPI();

// Check health on initialization (non-blocking)
backendAPI.checkHealth().catch(err => {
    console.warn('Initial health check failed, will retry later');
});

// Re-check health every 5 minutes
setInterval(() => {
    backendAPI.checkHealth();
}, 5 * 60 * 1000);
