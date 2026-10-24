
#!/usr/bin/env python3
from pathlib import Path
import json

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RASTER_PATH = ROOT / "model/data/population_calibrated_region3.tif"
GEOJSON_PATH = ROOT / "model/data/region3_barangay_shape_with_population.json"
OUTPUT_PATH = ROOT / "client/public/population-region3.png"

# Region III bounding box: west, south, east, north.
BOUNDS = (119.5, 14.1, 122.3, 16.4)
MAX_SIZE = 1400


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    geometries = [
        feature["geometry"]
        for feature in geojson.get("features", [])
        if feature.get("geometry")
    ]

    if not geometries:
        raise ValueError(f"No geometries found in {GEOJSON_PATH}")

    with rasterio.open(RASTER_PATH) as src:
        if src.crs is None or src.crs.to_epsg() != 4326:
            raise ValueError(
                f"Expected raster CRS EPSG:4326, got {src.crs}"
            )

        window = (
            from_bounds(*BOUNDS, transform=src.transform)
            .round_offsets()
            .round_lengths()
        )

        data = src.read(1, window=window, masked=True)
        transform = src.window_transform(window)

        # Keep pixels inside Region III barangay boundaries.
        inside = geometry_mask(
            geometries,
            out_shape=data.shape,
            transform=transform,
            invert=True,
            all_touched=False,
        )

        values = data.data.astype(np.float32)
        valid = (
            (~np.ma.getmaskarray(data))
            & inside
            & np.isfinite(values)
        )

        if not np.any(valid):
            raise ValueError(
                "No valid population pixels intersect Region III."
            )

        positive = values[valid & (values > 0)]

        if positive.size == 0:
            raise ValueError("No positive population values found.")

        # Robust logarithmic scaling limits the influence of extreme values.
        upper = max(float(np.percentile(positive, 99)), 1.0)

        scaled = np.zeros(values.shape, dtype=np.float32)
        scaled[valid] = np.clip(
            np.log1p(np.maximum(values[valid], 0))
            / np.log1p(upper),
            0,
            1,
        )

        # Resize while preserving the overall regional pattern.
        height, width = scaled.shape
        scale = min(1.0, MAX_SIZE / max(height, width))

        out_width = max(1, int(width * scale))
        out_height = max(1, int(height * scale))

        intensity_img = Image.fromarray(
            np.uint8(np.round(scaled * 255)),
            mode="L",
        )

        alpha_img = Image.fromarray(
            np.uint8(valid * 255),
            mode="L",
        )

        intensity_img = intensity_img.resize(
            (out_width, out_height),
            Image.Resampling.BILINEAR,
        )

        alpha_img = alpha_img.resize(
            (out_width, out_height),
            Image.Resampling.NEAREST,
        )

        intensity = (
            np.asarray(intensity_img).astype(np.float32) / 255.0
        )
        valid_alpha = np.asarray(alpha_img)

        # High-contrast gradient: yellow -> orange -> red -> dark red.
        stops = np.array(
            [
                [255, 255, 0],   # Yellow: lower intensity
                [255, 170, 0],   # Yellow-orange
                [255, 75, 0],    # Orange-red
                [220, 0, 0],     # Red: high intensity
                [120, 0, 0],     # Dark red: very high intensity
            ],
            dtype=np.float32,
        )

        # Brighten moderate values so the pattern is easier to see.
        adjusted = np.clip(intensity, 0, 1) ** 0.7

        position = adjusted * (len(stops) - 1)
        index = np.minimum(
            position.astype(np.int32),
            len(stops) - 2,
        )
        fraction = (position - index)[..., None]

        rgb = (
            stops[index] * (1 - fraction)
            + stops[index + 1] * fraction
        )

        # Increase visibility while retaining some base-map detail.
        # Empty and zero-valued pixels remain transparent.
        alpha = np.where(
            (intensity > 0) & (valid_alpha > 0),
            220,
            0,
        ).astype(np.uint8)

        rgba = np.dstack([rgb.astype(np.uint8), alpha])

        Image.fromarray(rgba, mode="RGBA").save(
            OUTPUT_PATH,
            optimize=True,
        )

    print(f"Created: {OUTPUT_PATH}")
    print(f"Image size: {out_width} x {out_height}")
    print(
        "Overlay bounds: west=119.5, south=14.1, "
        "east=122.3, north=16.4"
    )
    print(f"99th percentile used for scaling: {upper:.2f}")


if __name__ == "__main__":
    main()
