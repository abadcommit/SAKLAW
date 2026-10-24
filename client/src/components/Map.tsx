
import { useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  ZoomControl,
  Marker,
  Tooltip,
  Popup,
  useMap,
  ImageOverlay,
} from "react-leaflet";
import L from "leaflet";
import type { FeatureCollection } from "geojson";
import "leaflet/dist/leaflet.css";
import barangays from "../../../model/data/region3_barangay_shape_with_population.json";
import { HospitalMarkers } from "./HospitalMarkers";
import type { CandidateSite } from "../hooks/useGetCandidates";

const Region3Bounds: L.LatLngBoundsExpression = [
  [14.1, 119.5],
  [16.4, 122.3],
];

const baseStyle = {
  color: "#2878c8",
  weight: 0.85,
  opacity: 0.7,
  fillColor: "#3388ff",
  fillOpacity: 0.04,
};

const hoverStyle = {
  color: "#ff8c42",
  weight: 2,
  opacity: 1,
  fillColor: "#ff8c42",
  fillOpacity: 0.2,
};

const selectedStyle = {
  color: "#d00000",
  weight: 2,
  opacity: 1,
  fillColor: "#d00000",
  fillOpacity: 0.25,
};

const candidateIcon = L.divIcon({
  className: "saklaw-candidate-icon",
  html: `
    <div style="
      width: 26px;
      height: 26px;
      background: #facc15;
      border: 3px solid white;
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      box-shadow: 0 2px 6px rgba(0,0,0,0.35);
      box-sizing: border-box;
      position: relative;
    ">
      <div style="
        width: 7px;
        height: 7px;
        background: #785b00;
        border-radius: 50%;
        position: absolute;
        top: 7px;
        left: 7px;
      "></div>
    </div>
  `,
  iconSize: [26, 34],
  iconAnchor: [13, 32],
  popupAnchor: [0, -30],
});

function FitToSites({ sites }: { sites: CandidateSite[] }) {
  const map = useMap();
  const previousSites = useRef("");

  useEffect(() => {
    if (!sites.length) return;

    const siteKey = sites
      .map((site) => `${site.latitude},${site.longitude}`)
      .join("|");

    if (siteKey === previousSites.current) return;
    previousSites.current = siteKey;

    const bounds = L.latLngBounds(
      sites.map(
        (site) => [site.latitude, site.longitude] as L.LatLngTuple
      )
    );

    if (bounds.isValid()) {
      map.fitBounds(bounds, {
        padding: [80, 80],
        maxZoom: 13,
      });
    }
  }, [sites, map]);

  return null;
}

function CandidateMarkers({ sites }: { sites: CandidateSite[] }) {
  return (
    <>
      {sites.map((site, index) => (
        <Marker
          key={`${site.candidate_id}-${site.latitude}-${site.longitude}`}
          position={[site.latitude, site.longitude]}
          icon={candidateIcon}
          zIndexOffset={1000}
        >
          <Tooltip direction="top" offset={[0, -8]}>
            {site.selection_order != null
              ? `#${site.selection_order} · `
              : `#${index + 1} · `}
            Proposed site {String(site.candidate_id)}
          </Tooltip>

          <Popup>
            <strong>Proposed hospital site</strong>
            <br />
            ID: {String(site.candidate_id)}
            <br />
            Latitude: {site.latitude.toFixed(5)}
            <br />
            Longitude: {site.longitude.toFixed(5)}
          </Popup>
        </Marker>
      ))}
    </>
  );
}

interface MapProps {
  sites: CandidateSite[];
  showHospitals?: boolean;
  showPopulation?: boolean;
}

export default function RegionMap({
  sites,
  showHospitals = true,
  showPopulation = true,
}: MapProps) {
  const geoRef = useRef<L.GeoJSON>(null);
  const selected = useRef<L.Path | null>(null);

  const onEachFeature = (
    feature: GeoJSON.Feature,
    layer: L.Layer
  ) => {
    const properties = feature.properties;

    if (properties) {
      layer.bindTooltip(
        `${properties.ADM4_EN ?? "Unknown barangay"}, ${
          properties.ADM3_EN ?? "Unknown municipality"
        }`,
        { sticky: false }
      );
    }

    layer.on({
      mouseover: (event: L.LeafletMouseEvent) => {
        if (event.target === selected.current) return;

        event.target.setStyle(hoverStyle);
        event.target.bringToFront();
      },

      mouseout: (event: L.LeafletMouseEvent) => {
        if (event.target !== selected.current) {
          geoRef.current?.resetStyle(event.target);
        }
      },

      click: (event: L.LeafletMouseEvent) => {
        if (selected.current) {
          geoRef.current?.resetStyle(selected.current);
        }

        selected.current = event.target;
        event.target.setStyle(selectedStyle);
        event.target.bringToFront();
      },
    });
  };

  return (
    <div
      style={{
        position: "relative",
        width: "100dvw",
        height: "100dvh",
      }}
    >
      <MapContainer
        center={[15.3, 120.7]}
        zoom={10}
        minZoom={9}
        maxBounds={Region3Bounds}
        maxBoundsViscosity={1}
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 0,
        }}
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />

        {showPopulation && (
          <ImageOverlay
            url="/population-region3.png"
            bounds={[
              [14.1, 119.5],
              [16.4, 122.3],
            ]}
            opacity={0.55}
            pane="overlayPane"
            zIndex={1}
          />
        )}

        <GeoJSON
          ref={geoRef}
          data={barangays as FeatureCollection}
          style={() => baseStyle}
          onEachFeature={onEachFeature}
        />

        {showHospitals && <HospitalMarkers />}

        <CandidateMarkers sites={sites} />
        <FitToSites sites={sites} />
        <ZoomControl position="topright" />
      </MapContainer>
    </div>
  );
}
