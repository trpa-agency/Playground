import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { DeckGL } from '@deck.gl/react';
import { HexagonLayer } from '@deck.gl/aggregation-layers';
import { AmbientLight, PointLight, LightingEffect } from '@deck.gl/core';
import { Map } from 'react-map-gl';
import maplibregl from 'maplibre-gl';

// ArcGIS Feature Service
const FEATURE_SERVICE_URL =
  'https://services5.arcgis.com/fXXSUzHD5JjcOt1v/arcgis/rest/services/PIA_Index/FeatureServer/1/query';

// Lights
const ambientLight = new AmbientLight({ color: [255, 255, 255], intensity: 1.0 });
const pointLight1 = new PointLight({ color: [255, 255, 255], intensity: 0.8, position: [-0.144528, 49.739968, 80000] });
const pointLight2 = new PointLight({ color: [255, 255, 255], intensity: 0.8, position: [-3.807751, 54.104682, 8000] });
const lightingEffect = new LightingEffect({ ambientLight, pointLight1, pointLight2 });

// Map initial view
const INITIAL_VIEW_STATE = {
  longitude: -120,
  latitude: 39.1,
  zoom: 8,
  minZoom: 5,
  maxZoom: 15,
  pitch: 30,
  bearing: 0
};

// Purple-blue color range
const colorRange = [
  [120, 0, 200],
  [90, 0, 220],
  [60, 0, 240],
  [30, 50, 255],
  [0, 100, 255]
];

type DataPoint = {
  position: [number, number];
  density: number;
  active: number;
  transit: number;
  normDensity?: number;
  normActive?: number;
  normTransit?: number;
};

function App() {
  const [data, setData] = useState<DataPoint[]>([]);
  const [weights, setWeights] = useState({ density: 0.33, active: 0.33, transit: 0.34 });
  const [elevationScale, setElevationScale] = useState(50);

  useEffect(() => {
    async function fetchFeatures() {
      let offset = 0;
      const pageSize = 1000;
      const allPoints: DataPoint[] = [];

      while (true) {
        const url = `${FEATURE_SERVICE_URL}?where=1=1&outFields=density_index_preprocessed,bike_ped_index_preprocessed,Transit_Index_PREPROCESSED,latitude,longitude&f=json&resultOffset=${offset}&resultRecordCount=${pageSize}`;
        const res = await fetch(url);
        const json = await res.json();
        if (!json.features || json.features.length === 0) break;

        json.features.forEach((f: any) => {
          const lat = parseFloat(f.attributes.latitude);
          const lng = parseFloat(f.attributes.longitude);
          if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

          allPoints.push({
            position: [lng, lat],
            density: f.attributes.density_index_preprocessed ?? 0,
            active: f.attributes.bike_ped_index_preprocessed ?? 0,
            transit: f.attributes.Transit_Index_PREPROCESSED ?? 0
          });
        });

        offset += json.features.length;
      }

      // Normalize
      const maxD = Math.max(...allPoints.map(p => p.density));
      const maxA = Math.max(...allPoints.map(p => p.active));
      const maxT = Math.max(...allPoints.map(p => p.transit));

      allPoints.forEach(p => {
        p.normDensity = maxD ? p.density / maxD : 0;
        p.normActive = maxA ? p.active / maxA : 0;
        p.normTransit = maxT ? p.transit / maxT : 0;
      });

      setData(allPoints);
    }

    fetchFeatures();
  }, []);

  const weightedValue = (p: DataPoint) =>
    (p.normDensity || 0) * weights.density +
    (p.normActive || 0) * weights.active +
    (p.normTransit || 0) * weights.transit;

  const layer = new HexagonLayer<DataPoint>({
    id: 'hex-layer',
    data,
    getPosition: d => d.position,
    radius: 1000,
    extruded: true,
    elevationScale,
    elevationRange: [0, 3000],
    getElevationWeight: weightedValue,
    elevationAggregation: 'MEAN',
    getColorWeight: weightedValue,
    colorAggregation: 'MEAN',
    colorRange,
    pickable: true
  });

  const normalizeSliders = (changed: keyof typeof weights, value: number) => {
    const remaining = 1 - value;
    const others = Object.keys(weights).filter(k => k !== changed) as (keyof typeof weights)[];
    const sumOthers = others.reduce((acc, k) => acc + weights[k], 0) || 1;
    const newWeights: typeof weights = { ...weights };
    newWeights[changed] = value;
    others.forEach(k => (newWeights[k] = (weights[k] / sumOthers) * remaining));
    setWeights(newWeights);
  };

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      <DeckGL layers={[layer]} effects={[lightingEffect]} initialViewState={INITIAL_VIEW_STATE} controller={true}>
        <Map
          reuseMaps
          mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json"
          mapLib={maplibregl}
        />
      </DeckGL>

      <div style={{ position: 'absolute', top: 10, left: 10, background: 'rgba(255,255,255,0.9)', padding: 10, borderRadius: 6, zIndex: 10 }}>
        <label>
          Density:
          <input type="range" min="0" max="1" step="0.01" value={weights.density} onChange={e => normalizeSliders('density', parseFloat(e.target.value))} />
        </label>
        <br />
        <label>
          Active:
          <input type="range" min="0" max="1" step="0.01" value={weights.active} onChange={e => normalizeSliders('active', parseFloat(e.target.value))} />
        </label>
        <br />
        <label>
          Transit:
          <input type="range" min="0" max="1" step="0.01" value={weights.transit} onChange={e => normalizeSliders('transit', parseFloat(e.target.value))} />
        </label>
        <br />
        <label>
          Hex Height:
          <input type="range" min="10" max="500" step="10" value={elevationScale} onChange={e => setElevationScale(parseFloat(e.target.value))} />
        </label>
      </div>
    </div>
  );
}

// Mount
const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<App />);
}
