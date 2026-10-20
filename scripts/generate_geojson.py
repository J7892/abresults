#!/usr/bin/env python3
"""
Converts Elections Alberta Electoral Division Shapefiles (2019/2026 boundaries)
from NAD_1983_10TM (EPSG:3400) to an optimized, lightweight EPSG:4326 GeoJSON.
"""

import os
import json
import shapefile
import pyproj
from shapely.geometry import shape, mapping
from shapely.ops import transform

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_GEOJSON = os.path.join(DATA_DIR, "alberta_ridings.geojson")

SHP_PATH = "/tmp/ed_shapes/EDS_ENACTED_BILL33_15DEC2017.shp"
PRJ_PATH = "/tmp/ed_shapes/EDS_ENACTED_BILL33_15DEC2017.prj"

def convert():
    if not os.path.exists(SHP_PATH):
        raise FileNotFoundError(f"Shapefile not found at {SHP_PATH}")

    with open(PRJ_PATH, "r", encoding="utf-8") as f:
        prj_text = f.read()

    crs_source = pyproj.CRS.from_wkt(prj_text)
    crs_target = pyproj.CRS.from_epsg(4326)
    transformer = pyproj.Transformer.from_crs(crs_source, crs_target, always_xy=True)

    sf = shapefile.Reader(SHP_PATH)
    features = []

    for shape_rec in sf.shapeRecords():
        rec = shape_rec.record.as_dict()
        ed_num = f"{int(rec['EDNumber20']):02d}"
        ed_name = rec['EDName2017']

        geom = shape(shape_rec.shape.__geo_interface__)
        # Simplify geometry with 60m tolerance to produce a ~400KB file for smooth web mapping
        simplified_geom = geom.simplify(tolerance=60, preserve_topology=True)
        projected_geom = transform(transformer.transform, simplified_geom)

        geojson_geom = mapping(projected_geom)
        def round_coords(coords):
            if isinstance(coords[0], (int, float)):
                return [round(coords[0], 5), round(coords[1], 5)]
            return [round_coords(c) for c in coords]
        geojson_geom['coordinates'] = round_coords(geojson_geom['coordinates'])

        features.append({
            'type': 'Feature',
            'id': ed_num,
            'properties': {
                'ward': ed_num,
                'wardName': f"{ed_num} - {ed_name}",
                'name': ed_name,
                'km2': round(rec.get('Km2', 0), 1)
            },
            'geometry': geojson_geom
        })

    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_GEOJSON, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, separators=(',', ':'))

    print(f"Successfully converted {len(features)} ridings to {OUTPUT_GEOJSON}")

if __name__ == "__main__":
    convert()
