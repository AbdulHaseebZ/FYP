// custom_components/my_inverter/frontend/ai_summary_panel.js
// AI Insights Sidebar Panel

class MyInverterAIPanel extends HTMLElement {
  setConfig(config) {
    this.config = config;
  }

  connectedCallback() {
    this.render();
    // Refresh every 5 seconds
    setInterval(() => this.render(), 5000);
  }

  async render() {
    try {
      const response = await fetch('/api/my_inverter/ai_data');
      if (!response.ok) throw new Error('Failed to fetch AI data');
      
      const data = await response.json();
      
      this.innerHTML = `
        <div style="padding: 16px; font-family: Roboto, sans-serif;">
          <h1 style="margin: 0 0 16px 0; font-size: 20px;">🤖 AI Insights</h1>
          
          <div style="background: #f5f5f5; padding: 12px; border-radius: 4px; margin-bottom: 16px;">
            <p style="margin: 0 0 8px 0; font-size: 12px; color: #666;">Last Updated: ${data.timestamp ? new Date(data.timestamp).toLocaleString() : 'Never'}</p>
            <p style="margin: 0; font-size: 12px; color: ${data.status === 'success' ? '#4CAF50' : '#FF6B6B'};">
              Status: ${data.status.toUpperCase()}
              ${data.error ? ` - ${data.error}` : ''}
            </p>
          </div>

          ${data.active_tags && data.active_tags.length > 0 ? `
            <div style="margin-bottom: 16px;">
              <h2 style="margin: 0 0 8px 0; font-size: 14px; font-weight: 500;">Active Tags</h2>
              <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                ${data.active_tags.map(tag => `
                  <span style="
                    background: #E8F5E9;
                    color: #2E7D32;
                    padding: 4px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: 500;
                  ">✓ ${tag}</span>
                `).join('')}
              </div>
            </div>
          ` : ''}

          ${data.active_rules && data.active_rules.length > 0 ? `
            <div style="margin-bottom: 16px;">
              <h2 style="margin: 0 0 8px 0; font-size: 14px; font-weight: 500;">💡 Recommendations</h2>
              ${data.active_rules.map((rule, idx) => `
                <div style="
                  background: #FFF3E0;
                  border-left: 4px solid #FF9800;
                  padding: 12px;
                  margin-bottom: 8px;
                  border-radius: 2px;
                  font-size: 12px;
                  line-height: 1.5;
                ">
                  <strong style="display: block; margin-bottom: 4px; color: #E65100;">Recommendation ${idx + 1}</strong>
                  ${rule}
                </div>
              `).join('')}
            </div>
          ` : ''}

          <div style="font-size: 11px; color: #999; text-align: center; margin-top: 16px;">
            My Inverter AI Insights • Auto-updates every 5 seconds
          </div>
        </div>
      `;
    } catch (error) {
      this.innerHTML = `
        <div style="padding: 16px; color: #d32f2f;">
          <p>❌ Error loading AI Insights</p>
          <p style="font-size: 12px; color: #666;">${error.message}</p>
        </div>
      `;
    }
  }
}

customElements.define('my-inverter-ai-panel', MyInverterAIPanel);

// Export for Home Assistant
window.customElements.define('my-inverter-ai-panel', MyInverterAIPanel);