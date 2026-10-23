// BicolMap.jsx
import { useMemo } from 'react';
import { MapContainer, TileLayer, Polygon, Tooltip, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix missing default marker icons under Vite/webpack
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const BICOL_BOUNDS = [[11.7, 122.3], [14.4, 124.5]]; // [SW, NE]

const SECTIONS = [
  { id: 'a', name: 'Section A', coords: [[13.30, 123.40], [13.30, 123.80], [13.00, 123.80], [13.00, 123.40]] },
  { id: 'b', name: 'Section B', coords: [[13.00, 123.60], [13.00, 124.00], [12.70, 124.00], [12.70, 123.60]] },
];

const baseStyle = { color: '#3388ff', weight: 2, fillColor: '#3388ff', fillOpacity: 0.15 };
const hoverStyle = { color: '#ff6a00', weight: 4, fillColor: '#ff6a00', fillOpacity: 0.45 };

function Section({ name, coords }) {
  const handlers = useMemo(() => ({
    mouseover: (e) => {
      e.target.setStyle(hoverStyle);
      e.target.bringToFront();
    },
    mouseout: (e) => e.target.setStyle(baseStyle),
  }), []);

  return (
    <Polygon positions={coords} pathOptions={baseStyle} eventHandlers={handlers}>
      <Tooltip sticky>{name}</Tooltip>
    </Polygon>
  );
}

export default function Map() {
  return (
    <MapContainer
      center={[13.2, 123.6]}
      zoom={9}
      minZoom={8}
      maxBounds={BICOL_BOUNDS}
      maxBoundsViscosity={1.0}
      style={{ height: '100dvh', width: '100100dvw' }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />

      {SECTIONS.map((s) => <Section key={s.id} {...s} />)}
    </MapContainer>
  );
}