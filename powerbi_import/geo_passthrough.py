"""
GeoJSON / shapefile passthrough for Power BI shape maps.

Copies spatial data files (GeoJSON, TopoJSON) into the PBIP project
so that shape map visuals can reference them.  Also generates the
``shapeMapResources`` configuration block for ``report.json``.

Qlik maps often embed custom geography via GeoJSON layers.  This module
preserves that spatial data during migration by:

1. Detecting GeoJSON references in Qlik visualizations.
2. Copying or inlining the GeoJSON data into the PBIP ``RegisteredResources/``
   folder.
3. Generating the ``shapeMap.shape`` visual property referencing the
   bundled GeoJSON resource.

Usage::

    from powerbi_import.geo_passthrough import (
        detect_geo_sources,
        copy_geo_resources,
        build_shape_map_config,
    )

    sources = detect_geo_sources(visualizations)
    copy_geo_resources(sources, project_dir)
    config = build_shape_map_config(sources)
"""

import json
import os
import re
import shutil
import logging

logger = logging.getLogger(__name__)


# Supported spatial file extensions
_GEO_EXTENSIONS = {'.geojson', '.topojson', '.json'}

# GeoJSON type values that identify spatial content
_GEOJSON_TYPES = {'FeatureCollection', 'Feature', 'Point', 'MultiPoint',
                  'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon',
                  'GeometryCollection'}


def detect_geo_sources(visualizations):
    """Detect GeoJSON / spatial data references in Qlik visualizations.

    Scans visualization metadata for embedded or referenced GeoJSON
    data — inline ``features`` arrays, file path references, or URL
    references.

    Args:
        visualizations: List of visualization dicts from Qlik extraction.

    Returns:
        list[dict]: Detected geo sources, each with keys:
            - ``type``: ``'inline'`` | ``'file'`` | ``'url'``
            - ``data``: GeoJSON dict (for inline) or path/URL string
            - ``visual_id``: ID of the referencing visual
            - ``name``: Suggested resource name
    """
    if not visualizations:
        return []

    sources = []

    for viz in visualizations:
        viz_id = viz.get('id', '') or viz.get('name', '')
        viz_type = (viz.get('type') or viz.get('chart_type') or '').lower()

        # Check for map-like visuals
        if viz_type not in ('map', 'geomap', 'shapemap', 'geojson', 'geodata',
                            'polygon', 'multipolygon', 'filledmap', 'choropleth',
                            'density', 'heatmapgeo', 'densitymap'):
            # Still scan properties for embedded geo data
            pass

        properties = viz.get('properties', {})
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except (json.JSONDecodeError, TypeError):
                properties = {}

        # Check for inline GeoJSON in visualization properties
        _scan_for_geojson(properties, viz_id, sources)

        # Check for file references in layers or data sources
        layers = viz.get('layers', [])
        for i, layer in enumerate(layers):
            layer_data = layer if isinstance(layer, dict) else {}
            geo_file = layer_data.get('geoFile') or layer_data.get('file') or ''
            if geo_file and _is_geo_file(geo_file):
                sources.append({
                    'type': 'file',
                    'data': geo_file,
                    'visual_id': viz_id,
                    'name': f'geo_{viz_id}_{i}',
                })

            geo_url = layer_data.get('url') or layer_data.get('geoUrl') or ''
            if geo_url and _is_geo_url(geo_url):
                sources.append({
                    'type': 'url',
                    'data': geo_url,
                    'visual_id': viz_id,
                    'name': f'geo_{viz_id}_{i}',
                })

            _scan_for_geojson(layer_data, viz_id, sources, suffix=f'_layer{i}')

    return sources


def _scan_for_geojson(data, viz_id, sources, suffix=''):
    """Recursively scan a dict for inline GeoJSON content."""
    if not isinstance(data, dict):
        return

    # Direct GeoJSON object
    geo_type = data.get('type', '')
    if geo_type in _GEOJSON_TYPES and ('features' in data or 'coordinates' in data
                                        or 'geometries' in data):
        sources.append({
            'type': 'inline',
            'data': data,
            'visual_id': viz_id,
            'name': f'geo_{viz_id}{suffix}',
        })
        return

    # Scan nested keys
    for key, value in data.items():
        if isinstance(value, dict):
            _scan_for_geojson(value, viz_id, sources, suffix=f'_{key}')
        elif isinstance(value, str) and len(value) > 50:
            # Try parsing string values that look like GeoJSON
            stripped = value.strip()
            if stripped.startswith('{') and '"type"' in stripped[:100]:
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict) and parsed.get('type') in _GEOJSON_TYPES:
                        sources.append({
                            'type': 'inline',
                            'data': parsed,
                            'visual_id': viz_id,
                            'name': f'geo_{viz_id}_{key}',
                        })
                except (json.JSONDecodeError, TypeError):
                    pass


def _is_geo_file(path):
    """Check if a file path has a spatial file extension."""
    _, ext = os.path.splitext(path.lower())
    return ext in _GEO_EXTENSIONS


def _is_geo_url(url):
    """Check if a URL likely references spatial data."""
    lower = url.lower()
    return any(lower.endswith(ext) for ext in _GEO_EXTENSIONS) or 'geojson' in lower


def copy_geo_resources(geo_sources, project_dir, report_name='Report'):
    """Copy or write geo resources into the PBIP project.

    Places GeoJSON files in ``{report_name}.Report/definition/RegisteredResources/``
    so that shape map visuals can reference them.

    Args:
        geo_sources: List of geo source dicts from ``detect_geo_sources()``.
        project_dir: Root of the .pbip project directory.
        report_name: Name of the report (for folder path).

    Returns:
        list[str]: Paths of created resource files (relative to project_dir).
    """
    if not geo_sources:
        return []

    resources_dir = os.path.join(
        project_dir, f'{report_name}.Report', 'definition', 'RegisteredResources')
    os.makedirs(resources_dir, exist_ok=True)

    created = []

    for source in geo_sources:
        safe_name = re.sub(r'[^\w\-]', '_', source.get('name', 'geo'))
        dest_filename = f'{safe_name}.geojson'
        dest_path = os.path.join(resources_dir, dest_filename)

        if source['type'] == 'inline':
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(source['data'], f, ensure_ascii=False)
            created.append(dest_filename)
            logger.info("Wrote inline GeoJSON: %s", dest_filename)

        elif source['type'] == 'file':
            src_path = source['data']
            if os.path.isfile(src_path):
                shutil.copy2(src_path, dest_path)
                created.append(dest_filename)
                logger.info("Copied GeoJSON file: %s → %s", src_path, dest_filename)
            else:
                logger.warning("GeoJSON file not found: %s", src_path)

        elif source['type'] == 'url':
            # Write a placeholder with the URL reference
            placeholder = {
                "type": "FeatureCollection",
                "features": [],
                "_source_url": source['data'],
                "_note": "Download this GeoJSON from the URL and replace this placeholder"
            }
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(placeholder, f, ensure_ascii=False, indent=2)
            created.append(dest_filename)
            logger.info("Created GeoJSON placeholder for URL: %s", source['data'])

    return created


def build_shape_map_config(geo_sources, resource_names=None):
    """Build shape map visual configuration referencing bundled GeoJSON.

    Args:
        geo_sources: List of geo source dicts.
        resource_names: Optional list of resource filenames (from ``copy_geo_resources``).

    Returns:
        dict: Shape map configuration for visual.json.
    """
    if not geo_sources:
        return {}

    config = {
        "shape": {
            "projections": [],
            "customShapes": [],
        }
    }

    for i, source in enumerate(geo_sources):
        name = source.get('name', f'geo_{i}')
        filename = (resource_names[i] if resource_names and i < len(resource_names)
                    else f'{name}.geojson')
        config["shape"]["customShapes"].append({
            "name": name,
            "path": f"RegisteredResources/{filename}",
        })

    return config


def extract_geo_properties(visualization):
    """Extract geographic properties from a single Qlik visualization.

    Returns a dict with location-relevant field mappings suitable for
    Power BI map visuals:
    - ``latitude_field``: Field name for latitude
    - ``longitude_field``: Field name for longitude
    - ``location_field``: Field name for geographic location (country, state, etc.)
    - ``geo_role``: Detected geographic role (Country, State, City, PostalCode, etc.)

    Args:
        visualization: Single visualization dict.

    Returns:
        dict: Geographic property mappings, or empty dict if not a geo visual.
    """
    props = {}
    dimensions = visualization.get('dimensions', [])
    measures = visualization.get('measures', [])

    for dim in dimensions:
        field = dim.get('field', '') or dim.get('name', '')
        label = (dim.get('label') or field or '').lower()

        if any(kw in label for kw in ('latitude', 'lat')):
            props['latitude_field'] = field
        elif any(kw in label for kw in ('longitude', 'lng', 'lon', 'long')):
            props['longitude_field'] = field
        elif any(kw in label for kw in ('country', 'nation')):
            props['location_field'] = field
            props['geo_role'] = 'Country'
        elif any(kw in label for kw in ('state', 'province', 'region')):
            props['location_field'] = field
            props['geo_role'] = 'StateOrProvince'
        elif any(kw in label for kw in ('city', 'town')):
            props['location_field'] = field
            props['geo_role'] = 'City'
        elif any(kw in label for kw in ('zip', 'postal', 'postcode')):
            props['location_field'] = field
            props['geo_role'] = 'PostalCode'
        elif any(kw in label for kw in ('address', 'street')):
            props['location_field'] = field
            props['geo_role'] = 'Address'

    return props
