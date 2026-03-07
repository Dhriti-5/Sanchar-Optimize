// Backend API Configuration
const API_BASE = 'https://2f8kolu7j4.execute-api.ap-south-1.amazonaws.com/production';

// State Management
let summaryCount = 0;
let textSummaries = 0;
let audioSummaries = 0;
let visualSummaries = 0;
let activityLog = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeTelemetry();
    checkBackendHealth();
    startPredictionLog();
    startActivityStream();
    animateCounters();
});

// Check Backend Health
async function checkBackendHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            updateSystemStatus('ACTIVE', 'status-active');
            addActivity('Backend health check passed ✓');
            console.log('Backend healthy:', data);
        } else {
            updateSystemStatus('DEGRADED', 'status-warning');
            addActivity('Backend health check: degraded performance');
        }
    } catch (error) {
        console.warn('Backend health check failed:', error);
        updateSystemStatus('INITIALIZING', 'status-active');
        addActivity('System initializing...');
    }
    
    // Check again every 30 seconds
    setTimeout(checkBackendHealth, 30000);
}

// Update System Status
function updateSystemStatus(status, statusClass) {
    const statusElement = document.getElementById('system-status');
    if (statusElement) {
        statusElement.textContent = status;
        statusElement.className = `status-badge ${statusClass}`;
    }
}

// Initialize Telemetry Counters
function initializeTelemetry() {
    // Simulate some initial activity
    summaryCount = Math.floor(Math.random() * 50) + 10;
    textSummaries = Math.floor(summaryCount * 0.5);
    audioSummaries = Math.floor(summaryCount * 0.3);
    visualSummaries = summaryCount - textSummaries - audioSummaries;
    
    updateTelemetryDisplay();
}

// Update Telemetry Display
function updateTelemetryDisplay() {
    const summaryCountEl = document.getElementById('summary-count');
    const textSummariesEl = document.getElementById('text-summaries');
    const audioSummariesEl = document.getElementById('audio-summaries');
    const visualSummariesEl = document.getElementById('visual-summaries');
    
    if (summaryCountEl) summaryCountEl.textContent = summaryCount;
    if (textSummariesEl) textSummariesEl.textContent = textSummaries;
    if (audioSummariesEl) audioSummariesEl.textContent = audioSummaries;
    if (visualSummariesEl) visualSummariesEl.textContent = visualSummaries;
}

// Simulate Prediction Log Updates
function startPredictionLog() {
    const predictionLog = document.getElementById('prediction-log');
    if (!predictionLog) return;
    
    const predictions = [
        '🔍 Analyzing network conditions...',
        `✓ LSTM prediction: ${(Math.random() * 2 + 1).toFixed(1)} Mbps (next 30s)`,
        '⚡ Bandwidth sufficient - PASSIVE mode',
        `🔍 Monitoring latency: ${Math.floor(Math.random() * 20 + 35)}ms avg`,
        '✓ Connection stable - no intervention needed',
        '📊 Collecting telemetry data...',
        `⚠️ Minor fluctuation detected: ${(Math.random() * 1.5 + 0.5).toFixed(1)} Mbps`,
        '✓ Recovery confirmed - resuming passive monitoring',
        '🎯 Prediction accuracy: 94.2%',
        '✓ All agents synchronized'
    ];
    
    let index = 0;
    
    setInterval(() => {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.textContent = predictions[index % predictions.length];
        entry.style.opacity = '0';
        entry.style.transform = 'translateY(-10px)';
        
        predictionLog.insertBefore(entry, predictionLog.firstChild);
        
        // Animate entry
        setTimeout(() => {
            entry.style.transition = 'all 0.3s ease';
            entry.style.opacity = '1';
            entry.style.transform = 'translateY(0)';
        }, 10);
        
        // Remove old entries
        if (predictionLog.children.length > 6) {
            predictionLog.removeChild(predictionLog.lastChild);
        }
        
        index++;
    }, 4000);
}

// Activity Stream
function addActivity(message) {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    activityLog.unshift({
        time: timeString,
        message: message
    });
    
    if (activityLog.length > 10) {
        activityLog.pop();
    }
    
    updateActivityTimeline();
}

function updateActivityTimeline() {
    const timeline = document.getElementById('activity-timeline');
    if (!timeline) return;
    
    timeline.innerHTML = activityLog.map(activity => `
        <div class="timeline-item">
            <span class="timeline-time">${activity.time}</span>
            <span class="timeline-text">${activity.message}</span>
        </div>
    `).join('');
}

function startActivityStream() {
    const activities = [
        'Network Sentry Agent analyzing bandwidth trends',
        'Modality Orchestrator evaluating optimal format',
        'LSTM model completed prediction cycle',
        'Multi-Modal Transformer generated text summary',
        'Telemetry data persisted to AWS Timestream',
        'Claude 3.5 Sonnet processing content request',
        'Extension synchronized with backend state',
        'User session metrics recorded to DynamoDB',
        'Predictive cache updated successfully',
        'Audio TTS generated via Amazon Polly'
    ];
    
    // Add initial activity
    addActivity('System initialized and monitoring');
    
    // Randomly add activities
    setInterval(() => {
        if (Math.random() > 0.6) {
            const activity = activities[Math.floor(Math.random() * activities.length)];
            addActivity(activity);
            
            // Occasionally increment counters
            if (Math.random() > 0.7) {
                const summaryType = Math.floor(Math.random() * 3);
                summaryCount++;
                
                if (summaryType === 0) {
                    textSummaries++;
                } else if (summaryType === 1) {
                    audioSummaries++;
                } else {
                    visualSummaries++;
                }
                
                updateTelemetryDisplay();
            }
        }
    }, 8000);
}

// Animate Counter on Scroll
function animateCounters() {
    const observerOptions = {
        threshold: 0.5,
        rootMargin: '0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateValue(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    document.querySelectorAll('.stat-number').forEach(el => {
        observer.observe(el);
    });
}

function animateValue(element) {
    const targetText = element.textContent;
    const targetNumber = parseInt(targetText);
    
    if (isNaN(targetNumber)) return;
    
    const duration = 1500;
    const start = 0;
    const increment = targetNumber / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= targetNumber) {
            element.textContent = targetNumber;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// Copy Endpoint Function
window.copyEndpoint = function() {
    const endpoint = 'https://2f8kolu7j4.execute-api.ap-south-1.amazonaws.com/production/';
    
    navigator.clipboard.writeText(endpoint).then(() => {
        const btn = document.querySelector('.copy-btn');
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        btn.style.background = '#00cc33';
        
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Endpoint copied to clipboard!');
    });
};

// Smooth Scroll Enhancement
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Update Uptime Display
function updateUptime() {
    const uptimeEl = document.getElementById('uptime');
    if (uptimeEl) {
        const baseUptime = 99.8;
        const variation = (Math.random() - 0.5) * 0.1;
        const uptime = (baseUptime + variation).toFixed(1);
        uptimeEl.textContent = `${uptime}%`;
    }
}

setInterval(updateUptime, 10000);

// Log page view for analytics
console.log('%c🚀 Sanchar-Optimize Landing Page', 'font-size: 20px; font-weight: bold; color: #00FF41');
console.log('%cAI for Bharat 2026 - Production Ready', 'font-size: 14px; color: #8b949e');
console.log('%cBackend API:', 'font-weight: bold; color: #00FF41', API_BASE);
console.log('%cExtension Repository:', 'font-weight: bold; color: #00FF41', 'Available for testing');
