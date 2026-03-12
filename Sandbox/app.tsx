import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { DeckGL } from '@deck.gl/react';
import { HexagonLayer } from '@deck.gl/aggregation-layers';
import { AmbientLight, PointLight, LightingEffect } from '@deck.gl/core';
import { Map } from 'react-map-gl/maplibre';
import { CSVLoader } from '@loaders.gl/csv';
import { load } from '@loaders.gl/core';

// Example CSV for testing
const DATA_URL =
  'https://raw.githubusercontent.com/visgl/deck.gl-data/master/examples/3d-heatmap/heatmap-data.csv';

// Lighting
const ambientLight = new AmbientLight({ color: [255, 255, 255], intensity: 1.0 });
const pointLight1 = new PointLight({ color: [255, 255, 255], intensity: 0.8, position: [-0.144528, 49.739968, 80000] });
const pointLight2 = new PointLight({ color: [255, 255, 255], intensity: 0.8, position: [-3.807751, 54.104682, 8000] });
const lightingEffect = new LightingEffect({ ambientLight, pointLight1, pointLight2 });

// Initial view
const INITIAL_VIEW_STATE = {
  longitude: -1.415727,
  latitude: 52.232395,
  zoom: 6.6,
  minZoom: 5,
  maxZoom: 15,
  pitch: 40.5,
  bearing: -27
};

// Purple-blue color scale
const colorRange = [
  [120, 0, 200],
  [90, 0, 220],
  [60, 0, 240],
  [30, 50, 255],
  [0, 100, 255]
];

// Component
function App() {
  const [data, setData] = useState<number[][]>([]);
  const [weights, setWeights] = useState({ density: 0.33, active: 0.33, transit: 0.34 });
  const [elevationScale, setElevationScale] = useState(50);

  // Load CSV
  useEffect(() => {
    load(DATA_URL, CSVLoader).then(csvData => {
      const points = csvData.data
        .map((d: any) => {
          const lng = parseFloat(d.lng);
          const lat = parseFloat(d.lat);
          if (!Number.isFinite(lng) || !Number.isFinite(lat)) return null;
          return [lng, lat];
        })
        .filter(Boolean) as number[][];
      setData(points);
    });
  }, []);

  const layer = new HexagonLayer<number[]>({
    id: 'hex-layer',
    data,
    getPosition: d => d,
    radius: 1000,
    extruded: true,
    elevationScale: elevationScale,
    elevationRange: [0, 3000],
    getElevationWeight: () => 1, // weighted logic can go here if using multiple fields
    elevationAggregation: 'MEAN',
    getColorWeight: () => 1,      // weighted logic can go here if using multiple fields
    colorAggregation: 'MEAN',
    colorRange,
    pickable: true
  });

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      <DeckGL
        layers={[layer]}
        effects={[lightingEffect]}
        initialViewState={INITIAL_VIEW_STATE}
        controller={true}
      >
        <Map reuseMaps mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json" />
      </DeckGL>

      <div style={{ position: 'absolute', top: 10, left: 10, background: 'rgba(255,255,255,0.9)', padding: 10, borderRadius: 6, zIndex: 10 }}>
        <label>
          Density: 
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={weights.density}
            onChange={e => {
              const val = parseFloat(e.target.value);
              const otherSum = weights.active + weights.transit;
              setWeights({
                density: val,
                active: otherSum === 0 ? 0.5*(1-val) : (weights.active/otherSum)*(1-val),
                transit: otherSum === 0 ? 0.5*(1-val) : (weights.transit/otherSum)*(1-val)
              });
            }}
          />
        </label>
        <br />
        <label>
          Active: 
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={weights.active}
            onChange={e => {
              const val = parseFloat(e.target.value);
              const otherSum = weights.density + weights.transit;
              setWeights({
                density: otherSum === 0 ? 0.5*(1-val) : (weights.density/otherSum)*(1-val),
                active: val,
                transit: otherSum === 0 ? 0.5*(1-val) : (weights.transit/otherSum)*(1-val)
              });
            }}
          />
        </label>
        <br />
        <label>
          Transit: 
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={weights.transit}
            onChange={e => {
              const val = parseFloat(e.target.value);
              const otherSum = weights.density + weights.active;
              setWeights({
                density: otherSum === 0 ? 0.5*(1-val) : (weights.density/otherSum)*(1-val),
                active: otherSum === 0 ? 0.5*(1-val) : (weights.active/otherSum)*(1-val),
                transit: val
              });
            }}
          />
        </label>
        <br />
        <label>
          Hex Height: 
          <input
            type="range"
            min="10"
            max="500"
            step="10"
            value={elevationScale}
            onChange={e => setElevationScale(parseFloat(e.target.value))}
          />
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
