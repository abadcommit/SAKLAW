// RegionMap.jsx
import { useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import barangays from '../../../model/data/region3_barangay_shape_with_population.json';
import { HospitalMarkers } from './HospitalMarkers';


const Region3Bounds = [[14.1, 119.5], [16.4, 122.3]];

const baseStyle = { color: '#3388ff', weight: 1.5, fillColor: '#3388ff', fillOpacity: 0.15 };
const hoverStyle = { color: '#ff6a00', weight: 3, fillColor: '#ff6a00', fillOpacity: 0.45 };
const selectedStyle = { color: '#d00000', weight: 3, fillColor: '#d00000', fillOpacity: 0.5 };

export default function RegionMap({ onSelect }) {
  const geoRef = useRef(null);
  const selected = useRef(null);

  const onEachFeature = (feature, layer) => {
    const p = feature.properties;

    layer.bindTooltip(`${p.ADM4_EN}, ${p.ADM3_EN}`, { sticky: false });

    layer.on({
      mouseover: (e) => {
        if (e.target === selected.current) return;
        e.target.setStyle(hoverStyle);
        e.target.bringToFront();
      },
      mouseout: (e) => {
        if (e.target !== selected.current) geoRef.current?.resetStyle(e.target);
      },
      click: (e) => {
        if (selected.current) geoRef.current?.resetStyle(selected.current);
        selected.current = e.target;
        e.target.setStyle(selectedStyle);
        e.target.bringToFront();
      },
    });
  };

  return (
    <MapContainer
      center={[15.3, 120.7]}
      zoom={10}
      minZoom={9}
      maxBounds={Region3Bounds}
      maxBoundsViscosity={1.0}
      style={{ height: '100dvh', width: '100dvw' }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />

      <GeoJSON
        ref={geoRef}
        data={barangays}
        style={() => baseStyle}
        onEachFeature={onEachFeature}
      />

      <HospitalMarkers />
    </MapContainer>
  );
}