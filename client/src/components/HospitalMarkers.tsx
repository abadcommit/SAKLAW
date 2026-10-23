import Papa from 'papaparse';
import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import hospitalCoords from '../../../model/data/hospital_coords.csv?raw';


import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});


const { data, errors } = Papa.parse(hospitalCoords, {
  header: true,
  skipEmptyLines: true,

  dynamicTyping: (col) => col === 'latitude' || col === 'longitude',
});
if (errors.length) console.warn('CSV parse issues:', errors);


const hospitals = data.filter(
  (h) => Number.isFinite(h.latitude) && Number.isFinite(h.longitude)
);

export function HospitalMarkers() {
  return hospitals.map((h) => (
    <Marker
      key={h['Health Facility Code']}
      position={[h.latitude, h.longitude]}
    >
      <Popup>
        <strong>{h['Facility Name']}</strong>
        <br />
        {h['Barangay Name']}, {h['City/Municipality Name']}
        <br />
        {h['Province Name']}
      </Popup>
    </Marker>
  ));
}