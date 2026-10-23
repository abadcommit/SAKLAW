import { useEffect, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  ZoomControl,
  CircleMarker,
  Tooltip,
  Popup,
  useMap, 
} from "react-leaflet";
import L from "leaflet";
import type { FeatureCollection } from "geojson";
import "leaflet/dist/leaflet.css";
import barangays from "../../../model/data/region3_barangay_shape_with_population.json";
import { HospitalMarkers } from "./HospitalMarkers";
import { useGetCandidates, type CandidateSite } from "../hooks/useGetCandidates.tsx"; // adjust path

const Region3Bounds: L.LatLngBoundsExpression = [
  [14.1, 119.5],
  [16.4, 122.3],
];

const baseStyle = { color: "#3388ff", weight: 1.5, fillColor: "#3388ff", fillOpacity: 0.15 };
const hoverStyle = { color: "#ff6a00", weight: 3, fillColor: "#ff6a00", fillOpacity: 0.45 };
const selectedStyle = { color: "#d00000", weight: 3, fillColor: "#d00000", fillOpacity: 0.5 };

function FitToSites({ sites }: { sites: CandidateSite[] }) {
  const map = useMap();
  useEffect(() => {
    if (!sites.length) return;
    const bounds = L.latLngBounds(sites.map((s) => [s.latitude, s.longitude] as L.LatLngTuple));
    map.fitBounds(bounds, { padding: [80, 80], maxZoom: 13 });
  }, [sites, map]);
  return null;
}

function CandidateMarkers({ sites }: { sites: CandidateSite[] }) {
  return (
    <>
      {sites.map((s) => (
        <CircleMarker
          key={String(s.candidate_id)}
          center={[s.latitude, s.longitude]}
          radius={11}
          pathOptions={{ color: "#fff", weight: 3, fillColor: "#2a9d8f", fillOpacity: 1 }}
        >
          <Tooltip direction="top" offset={[0, -8]}>
            {s.selection_order != null ? `#${s.selection_order} · ` : ""}
            New site {String(s.candidate_id)}
          </Tooltip>
          <Popup>
            <strong>Proposed hospital site</strong>
            <br />
            ID: {String(s.candidate_id)}
            <br />
            {s.latitude.toFixed(5)}, {s.longitude.toFixed(5)}
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

export default function RegionMap() {
  const geoRef = useRef<L.GeoJSON>(null);
  const selected = useRef<L.Path | null>(null);

  const { data, loading, error, getCandidates } = useGetCandidates();
  const [rank, setRank] = useState(1);

  const combination = data?.combinations.find((c) => c.rank === rank) ?? data?.combinations[0];
  const sites = combination?.sites ?? [];

  const onEachFeature = (feature: any, layer: L.Layer) => {
    const p = feature.properties;

    layer.bindTooltip(`${p.ADM4_EN}, ${p.ADM3_EN}`, { sticky: false });

    layer.on({
      mouseover: (e: L.LeafletMouseEvent) => {
        if (e.target === selected.current) return;
        e.target.setStyle(hoverStyle);
        e.target.bringToFront();
      },
      mouseout: (e: L.LeafletMouseEvent) => {
        if (e.target !== selected.current) geoRef.current?.resetStyle(e.target);
      },
      click: (e: L.LeafletMouseEvent) => {
        if (selected.current) geoRef.current?.resetStyle(selected.current);
        selected.current = e.target;
        e.target.setStyle(selectedStyle);
        e.target.bringToFront();
      },
    });
  };

  return (
    <div style={{ position: "relative", width: "100dvw", height: "100dvh" }}>
      <MapContainer
        center={[15.3, 120.7]}
        zoom={10}
        minZoom={9}
        maxBounds={Region3Bounds}
        maxBoundsViscosity={1.0}
        style={{ position: "absolute", inset: 0, zIndex: 0 }}
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />

        <GeoJSON
          ref={geoRef}
          data={barangays as FeatureCollection}
          style={() => baseStyle}
          onEachFeature={onEachFeature}
        />

        <HospitalMarkers />
        <CandidateMarkers sites={sites} />
        <FitToSites sites={sites} />
        <ZoomControl position="topright" />
      </MapContainer>

      {/* Controls live outside MapContainer so clicks don't reach the map */}
      <div
        style={{
          position: "absolute",
          bottom: 24,
          left: 24,
          zIndex: 1100,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <button onClick={() => getCandidates()} disabled={loading}>
          {loading ? "Finding sites…" : "Suggest new hospital sites"}
        </button>

        {data && data.combinations.length > 1 && (
          <select
            value={combination?.rank}
            onChange={(e) => setRank(Number(e.target.value))}
          >
            {data.combinations.map((c) => (
              <option key={c.rank} value={c.rank}>
                Option {c.rank}
              </option>
            ))}
          </select>
        )}

        {error && <div style={{ color: "#e63946" }}>{error}</div>}
      </div>
    </div>
  );
}