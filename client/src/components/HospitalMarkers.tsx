
import { useEffect, useState } from "react";
import Papa from "papaparse";
import { CircleMarker, Popup } from "react-leaflet";

type Hospital = {
  "Health Facility Code": string;
  "Facility Name": string;
  "Barangay Name": string;
  "City/Municipality Name": string;
  "Province Name": string;
  latitude: number;
  longitude: number;
};

export function HospitalMarkers() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);

  useEffect(() => {
    fetch("/data/hospital_coords.csv")
      .then((response) => {
        if (!response.ok) throw new Error("Failed to load hospitals");
        return response.text();
      })
      .then((text) => {
        const { data, errors } = Papa.parse<Hospital>(text, {
          header: true,
          skipEmptyLines: true,
          dynamicTyping: (column) =>
            column === "latitude" || column === "longitude",
        });

        if (errors.length) console.warn("CSV parse issues:", errors);

        setHospitals(
          data.filter(
            (hospital) =>
              Number.isFinite(hospital.latitude) &&
              Number.isFinite(hospital.longitude)
          )
        );
      })
      .catch((error) => console.error(error));
  }, []);

  return (
    <>
      {hospitals.map((hospital) => (
        <CircleMarker
          key={hospital["Health Facility Code"]}
          center={[hospital.latitude, hospital.longitude]}
          radius={6}
          pathOptions={{
            color: "#ffffff",
            weight: 1.5,
            opacity: 1,
            fillColor: "#28658a",
            fillOpacity: 1,
          }}
        >
          <Popup>
            <strong>{hospital["Facility Name"]}</strong>
            <br />
            {hospital["Barangay Name"]},{" "}
            {hospital["City/Municipality Name"]}
            <br />
            {hospital["Province Name"]}
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}
