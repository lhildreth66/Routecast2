/**
 * Weather Layer Manager
 * Manages multiple weather layers for the interactive map
 * Uses 100% FREE APIs: RainViewer, NWS, NOAA
 */

export interface WeatherLayer {
  id: string;
  name: string;
  type: 'raster' | 'geojson';
  source: string | any;
  visible: boolean;
  opacity: number;
  zIndex: number;
  updateInterval?: number; // ms
  color?: string;
}

export const WEATHER_LAYERS: WeatherLayer[] = [
  {
    id: 'radar-precipitation',
    name: 'Radar',
    type: 'raster',
    source: '', // Set dynamically with timestamp
    visible: true,
    opacity: 0.7,
    zIndex: 10,
    updateInterval: 600000, // 10 min
  },
  {
    id: 'severe-alerts',
    name: 'Severe Weather',
    type: 'geojson',
    source: null,
    visible: true,
    opacity: 0.5,
    zIndex: 20,
    updateInterval: 300000, // 5 min
  },
];

export const LAYER_PRESETS: Record<string, string[]> = {
  basic: ['radar-precipitation'],
  severe: ['radar-precipitation', 'severe-alerts'],
  all: ['radar-precipitation', 'severe-alerts'],
};

export class WeatherLayerManager {
  private layers: Map<string, WeatherLayer> = new Map();
  private updateTimers: Map<string, any> = new Map();
  private listeners: Set<() => void> = new Set();

  constructor() {
    this.initializeLayers();
  }

  private initializeLayers() {
    WEATHER_LAYERS.forEach(layer => {
      this.layers.set(layer.id, { ...layer });
    });
  }

  getLayers(): WeatherLayer[] {
    return Array.from(this.layers.values());
  }

  getLayer(layerId: string): WeatherLayer | undefined {
    return this.layers.get(layerId);
  }

  toggleLayer(layerId: string): boolean {
    const layer = this.layers.get(layerId);
    if (!layer) return false;
    
    layer.visible = !layer.visible;
    this.notifyListeners();
    
    return layer.visible;
  }

  setOpacity(layerId: string, opacity: number) {
    const layer = this.layers.get(layerId);
    if (layer) {
      layer.opacity = Math.max(0, Math.min(1, opacity));
      this.notifyListeners();
    }
  }

  applyPreset(presetName: string) {
    const preset = LAYER_PRESETS[presetName];
    if (!preset) return;

    // Hide all layers
    this.layers.forEach(layer => {
      layer.visible = false;
    });

    // Show preset layers
    preset.forEach(layerId => {
      const layer = this.layers.get(layerId);
      if (layer) layer.visible = true;
    });

    this.notifyListeners();
  }

  async updateRadarTimestamp(): Promise<string | null> {
    try {
      const response = await fetch('https://api.rainviewer.com/public/weather-maps.json');
      const data = await response.json();
      const latest = data.radar.past[data.radar.past.length - 1];
      
      const layer = this.layers.get('radar-precipitation');
      if (layer) {
        layer.source = `https://tilecache.rainviewer.com/v2/radar/${latest.time}/256/{z}/{x}/{y}/2/1_1.png`;
        this.notifyListeners();
        return layer.source;
      }
    } catch (error) {
      console.error('Failed to fetch radar timestamp:', error);
    }
    return null;
  }

  async updateSevereAlerts(): Promise<any> {
    try {
      const response = await fetch('https://api.weather.gov/alerts/active?status=actual');
      const data = await response.json();
      
      const layer = this.layers.get('severe-alerts');
      if (layer) {
        layer.source = data;
        this.notifyListeners();
        return data;
      }
    } catch (error) {
      console.error('Failed to fetch severe alerts:', error);
    }
    return null;
  }

  subscribe(listener: () => void) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notifyListeners() {
    this.listeners.forEach(listener => listener());
  }

  startAutoUpdate() {
    // Update radar every 10 minutes
    const radarTimer = setInterval(() => {
      this.updateRadarTimestamp();
    }, 600000);
    this.updateTimers.set('radar', radarTimer);

    // Update alerts every 5 minutes
    const alertsTimer = setInterval(() => {
      this.updateSevereAlerts();
    }, 300000);
    this.updateTimers.set('alerts', alertsTimer);

    // Initial fetch
    this.updateRadarTimestamp();
    this.updateSevereAlerts();
  }

  cleanup() {
    this.updateTimers.forEach(timer => clearInterval(timer));
    this.updateTimers.clear();
    this.listeners.clear();
  }
}
