// custom_components/my_inverter/frontend/ai_summary_panel.js

class MyInverterAIPanel extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this.aiData = {
            summary: 'Loading...',
            timestamp: null,
            error: null,
            status: 'loading'
        };
        this._updateInterval = null;
    }

    setConfig(config) {
        this._config = config;
    }

    set hass(hass) {
        this._hass = hass;
        if (!this._updateInterval) {
            this.startAutoRefresh();
        }
        this.render();
    }

    connectedCallback() {
        this.render();
        this.fetchAIData();
    }

    disconnectedCallback() {
        this.stopAutoRefresh();
    }

    startAutoRefresh() {
        // Fetch AI data every 10 seconds
        this._updateInterval = setInterval(() => {
            this.fetchAIData();
        }, 10000);
    }

    stopAutoRefresh() {
        if (this._updateInterval) {
            clearInterval(this._updateInterval);
            this._updateInterval = null;
        }
    }

    async fetchAIData() {
        if (!this._hass) return;

        try {
            const response = await this._hass.callWS({
                type: 'call_service',
                domain: 'system_log',
                service: 'write',
                service_data: {
                    message: 'Fetching AI data...',
                    level: 'debug'
                }
            }).catch(() => {});

            // Fetch from our custom API endpoint
            const result = await fetch('/api/my_inverter/ai_data', {
                headers: {
                    'Authorization': `Bearer ${this._hass.auth.data.access_token}`
                }
            });

            if (result.ok) {
                this.aiData = await result.json();
                this.render();
            } else {
                console.error('Failed to fetch AI data:', result.status);
            }
        } catch (error) {
            console.error('Error fetching AI data:', error);
            this.aiData.error = error.message;
            this.aiData.status = 'error';
            this.render();
        }
    }

    async handleRefresh() {
        // Call the refresh service
        if (this._hass) {
            try {
                await this._hass.callService('my_inverter', 'refresh_ai_summary', {});
                
                // Wait a moment then fetch the updated data
                setTimeout(() => {
                    this.fetchAIData();
                }, 1000);
                
                // Show loading state immediately
                this.aiData.status = 'updating';
                this.render();
            } catch (error) {
                console.error('Failed to refresh AI summary:', error);
            }
        }
    }

    formatTimestamp(isoString) {
        if (!isoString) return 'Never';
        const date = new Date(isoString);
        return date.toLocaleString();
    }

    getStatusColor() {
        switch (this.aiData.status) {
            case 'success': return '#4caf50';
            case 'error': return '#f44336';
            case 'updating': return '#ff9800';
            default: return '#2196f3';
        }
    }

    getStatusText() {
        switch (this.aiData.status) {
            case 'success': return 'Active';
            case 'error': return 'Error';
            case 'updating': return 'Updating...';
            case 'initializing': return 'Initializing...';
            default: return 'Loading...';
        }
    }

    render() {
        if (!this.shadowRoot) return;

        const statusColor = this.getStatusColor();
        const statusText = this.getStatusText();

        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: block;
                    padding: 16px;
                    background-color: var(--primary-background-color);
                    height: 100%;
                    overflow-y: auto;
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                
                .header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 24px;
                    padding-bottom: 16px;
                    border-bottom: 1px solid var(--divider-color);
                }
                
                .header-content {
                    display: flex;
                    align-items: center;
                    gap: 16px;
                }
                
                .icon {
                    width: 48px;
                    height: 48px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 28px;
                }
                
                .title-section h1 {
                    margin: 0;
                    font-size: 28px;
                    font-weight: 500;
                    color: var(--primary-text-color);
                }
                
                .title-section p {
                    margin: 4px 0 0 0;
                    font-size: 14px;
                    color: var(--secondary-text-color);
                }
                
                .refresh-btn {
                    padding: 10px 20px;
                    background-color: var(--primary-color);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    transition: all 0.2s;
                }
                
                .refresh-btn:hover {
                    opacity: 0.9;
                    transform: translateY(-1px);
                }
                
                .refresh-btn:active {
                    transform: translateY(0);
                }
                
                .content-card {
                    background-color: var(--card-background-color);
                    border-radius: 12px;
                    padding: 24px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    margin-bottom: 16px;
                }
                
                .status-bar {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 12px 16px;
                    background-color: var(--secondary-background-color);
                    border-radius: 8px;
                    margin-bottom: 20px;
                }
                
                .status-indicator {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 14px;
                    font-weight: 500;
                }
                
                .status-dot {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    background-color: ${statusColor};
                    animation: pulse 2s infinite;
                }
                
                .timestamp {
                    font-size: 13px;
                    color: var(--secondary-text-color);
                }
                
                .ai-summary {
                    background-color: var(--secondary-background-color);
                    padding: 20px;
                    border-radius: 8px;
                    border-left: 4px solid var(--primary-color);
                }
                
                .ai-summary h3 {
                    margin: 0 0 12px 0;
                    font-size: 18px;
                    font-weight: 500;
                    color: var(--primary-text-color);
                }
                
                .ai-summary-text {
                    margin: 0;
                    font-size: 15px;
                    line-height: 1.6;
                    color: var(--primary-text-color);
                    white-space: pre-wrap;
                }
                
                .error-message {
                    background-color: #ffebee;
                    color: #c62828;
                    padding: 16px;
                    border-radius: 8px;
                    margin-top: 16px;
                }
                
                .info-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 16px;
                    margin-top: 20px;
                }
                
                .info-item {
                    background-color: var(--secondary-background-color);
                    padding: 16px;
                    border-radius: 8px;
                }
                
                .info-label {
                    font-size: 12px;
                    color: var(--secondary-text-color);
                    margin-bottom: 4px;
                }
                
                .info-value {
                    font-size: 18px;
                    font-weight: 500;
                    color: var(--primary-text-color);
                }
                
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
            </style>
            
            <div class="container">
                <div class="header">
                    <div class="header-content">
                        <div class="icon">ðŸ¤–</div>
                        <div class="title-section">
                            <h1>Inverter AI Insights</h1>
                            <p>AI-powered analysis via Ollama</p>
                        </div>
                    </div>
                    <button class="refresh-btn" onclick="this.getRootNode().host.handleRefresh()">
                        <span>ðŸ”„</span>
                        <span>Refresh</span>
                    </button>
                </div>
                
                <div class="content-card">
                    <div class="status-bar">
                        <div class="status-indicator">
                            <div class="status-dot"></div>
                            <span>Status: ${statusText}</span>
                        </div>
                        <div class="timestamp">
                            Last updated: ${this.formatTimestamp(this.aiData.timestamp)}
                        </div>
                    </div>
                    
                    <div class="ai-summary">
                        <h3>AI Response</h3>
                        <p class="ai-summary-text">${this.aiData.summary || 'No data yet...'}</p>
                    </div>
                    
                    ${this.aiData.error ? `
                        <div class="error-message">
                            <strong>Error:</strong> ${this.aiData.error}
                        </div>
                    ` : ''}
                    
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">Integration Status</div>
                            <div class="info-value">Active</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">AI Provider</div>
                            <div class="info-value">Ollama</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Update Interval</div>
                            <div class="info-value">1 minute</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
}

// Register the custom element
customElements.define('my-inverter-ai-panel', MyInverterAIPanel);

// This is required for Home Assistant to load the panel
window.customPanelDefinition = {
    tag: 'my-inverter-ai-panel',
    name: 'My Inverter AI Panel'
};