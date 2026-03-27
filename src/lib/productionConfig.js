/**
 * productionConfig — Runtime configuration for Aurora production deployment
 * Manages API endpoints, feature flags, and environment-specific settings
 */

const isProduction = window.location.hostname === 'api.aurora-osi.io' || 
                    window.location.hostname === 'aurora-osi.io';

const config = {
  // API endpoints — update based on ALB DNS or custom domain
  api: {
    baseURL: isProduction
      ? 'https://api.aurora-osi.io'
      : import.meta.env.VITE_API_URL || 'http://localhost:8000',
    
    health: '/api/v1/health',
    scan: '/api/v1/scan',
    datasets: '/api/v1/datasets',
    twin: '/api/v1/twin',
    reports: '/api/v1/reports',
    export: '/api/v1/export',
  },

  // Feature flags
  features: {
    enableGroundTruth: true,
    enablePilotTracking: true,
    enablePortfolioRanking: true,
    enableCommercialPackaging: true,
    enableRealtimeUpdates: true,
  },

  // Deployment metadata
  deployment: {
    environment: isProduction ? 'production' : 'development',
    region: 'us-east-1',
    timestamp: new Date().toISOString(),
  },

  // Timeout and retry settings
  http: {
    timeout: 30000,
    retries: 3,
    retryDelay: 1000,
  },

  // Map and visualization defaults
  map: {
    maxZoom: 18,
    defaultZoom: 6,
    tileServer: 'https://tiles.openstreetmap.org/{z}/{x}/{y}.png',
  },

  // Data retention and limits
  limits: {
    maxVoxelsPerQuery: 50000,
    maxAOISizeSqKm: 50000,
    maxExportSizeMB: 500,
  },
};

export default config;