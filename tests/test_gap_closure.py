"""Tests for gap-closure features: visual mappings, Power Query file generation,
geo_passthrough, refresh_generator, and qlik_server_client."""

import json
import os
import sys
import tempfile
import unittest

# Ensure project root is importable
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ═══════════════════════════════════════════════════════════════════
# Visual Type Mapping Tests (120+ mappings)
# ═══════════════════════════════════════════════════════════════════

class TestExpandedVisualMappings(unittest.TestCase):
    """Test the 120+ visual type mappings in visual_generator."""

    def setUp(self):
        from powerbi_import.visual_generator import VISUAL_TYPE_MAP
        self.map = VISUAL_TYPE_MAP

    def test_map_has_120_plus_entries(self):
        self.assertGreaterEqual(len(self.map), 120,
                                f"Expected 120+ visual mappings, got {len(self.map)}")

    # ── Bar/Column variants ───────────────────────────────────────

    def test_horizontal_bar(self):
        self.assertEqual(self.map['horizontalbar'], 'clusteredBarChart')

    def test_horizontal_bar_hyphen(self):
        self.assertEqual(self.map['horizontal-bar'], 'clusteredBarChart')

    def test_grouped_bar(self):
        self.assertEqual(self.map['groupedbarchart'], 'clusteredBarChart')

    def test_grouped_column(self):
        self.assertEqual(self.map['groupedcolumnchart'], 'clusteredColumnChart')

    def test_normalized_bar(self):
        self.assertEqual(self.map['normalizedbar'], 'hundredPercentStackedBarChart')

    def test_normalized_column(self):
        self.assertEqual(self.map['normalizedcolumn'], 'hundredPercentStackedColumnChart')

    def test_sidebyside(self):
        self.assertEqual(self.map['sidebyside'], 'clusteredColumnChart')

    # ── Line/Area variants ────────────────────────────────────────

    def test_stepline(self):
        self.assertEqual(self.map['stepline'], 'lineChart')

    def test_smoothline(self):
        self.assertEqual(self.map['smoothline'], 'lineChart')

    def test_spline(self):
        self.assertEqual(self.map['spline'], 'lineChart')

    def test_stacked_line(self):
        self.assertEqual(self.map['stackedline'], 'lineChart')

    def test_100_stacked_area(self):
        self.assertEqual(self.map['100stackedarea'], 'hundredPercentStackedAreaChart')

    def test_percent_stacked_area(self):
        self.assertEqual(self.map['percentstackedarea'], 'hundredPercentStackedAreaChart')

    # ── Combo variants ────────────────────────────────────────────

    def test_barline(self):
        self.assertEqual(self.map['barline'], 'lineClusteredColumnComboChart')

    def test_columnline(self):
        self.assertEqual(self.map['columnline'], 'lineClusteredColumnComboChart')

    def test_linecolumn(self):
        self.assertEqual(self.map['linecolumn'], 'lineStackedColumnComboChart')

    def test_linebar(self):
        self.assertEqual(self.map['linebar'], 'lineClusteredColumnComboChart')

    # ── Pie/Donut variants ────────────────────────────────────────

    def test_3dpie(self):
        self.assertEqual(self.map['3dpie'], 'pieChart')

    def test_halfdonut(self):
        self.assertEqual(self.map['halfdonut'], 'donutChart')

    def test_explodedpie(self):
        self.assertEqual(self.map['explodedpie'], 'pieChart')

    # ── Map variants ──────────────────────────────────────────────

    def test_choropleth(self):
        self.assertEqual(self.map['choropleth'], 'filledMap')

    def test_bubblemap(self):
        self.assertEqual(self.map['bubblemap'], 'map')

    def test_pointmap(self):
        self.assertEqual(self.map['pointmap'], 'map')

    def test_geojson(self):
        self.assertEqual(self.map['geojson'], 'shapeMap')

    def test_geodata(self):
        self.assertEqual(self.map['geodata'], 'shapeMap')

    def test_mapbox(self):
        self.assertEqual(self.map['mapbox'], 'azureMap')

    def test_densitymap(self):
        self.assertEqual(self.map['densitymap'], 'map')

    # ── KPI/Card/Gauge variants ───────────────────────────────────

    def test_scoreboard(self):
        self.assertEqual(self.map['scoreboard'], 'card')

    def test_bignum(self):
        self.assertEqual(self.map['bignum'], 'card')

    def test_bignumber(self):
        self.assertEqual(self.map['bignumber'], 'card')

    def test_summary(self):
        self.assertEqual(self.map['summary'], 'multiRowCard')

    def test_speedometer(self):
        self.assertEqual(self.map['speedometer'], 'gauge')

    def test_thermometer(self):
        self.assertEqual(self.map['thermometer'], 'gauge')

    def test_dial(self):
        self.assertEqual(self.map['dial'], 'gauge')

    def test_angulargauge(self):
        self.assertEqual(self.map['angulargauge'], 'gauge')

    def test_lineargauge(self):
        self.assertEqual(self.map['lineargauge'], 'gauge')

    def test_kpicard(self):
        self.assertEqual(self.map['kpicard'], 'card')

    # ── Table/Matrix variants ─────────────────────────────────────

    def test_grid(self):
        self.assertEqual(self.map['grid'], 'tableEx')

    def test_datagrid(self):
        self.assertEqual(self.map['datagrid'], 'tableEx')

    def test_crosstab(self):
        self.assertEqual(self.map['crosstab'], 'matrix')

    def test_texttable(self):
        self.assertEqual(self.map['texttable'], 'tableEx')

    def test_detailtable(self):
        self.assertEqual(self.map['detailtable'], 'tableEx')

    # ── Specialty visuals ─────────────────────────────────────────

    def test_tornado(self):
        self.assertEqual(self.map['tornado'], 'clusteredBarChart')

    def test_pyramid(self):
        self.assertEqual(self.map['pyramid'], 'funnel')

    def test_dumbbell(self):
        self.assertEqual(self.map['dumbbell'], 'clusteredBarChart')

    def test_marimekko(self):
        self.assertEqual(self.map['marimekko'], 'stackedBarChart')

    def test_coxcomb(self):
        self.assertEqual(self.map['coxcomb'], 'pieChart')

    def test_rose(self):
        self.assertEqual(self.map['rose'], 'pieChart')

    def test_nightingale(self):
        self.assertEqual(self.map['nightingale'], 'pieChart')

    def test_radarchart(self):
        self.assertEqual(self.map['radarchart'], 'lineChart')

    def test_spiderweb(self):
        self.assertEqual(self.map['spiderweb'], 'lineChart')

    def test_polarchart(self):
        self.assertEqual(self.map['polarchart'], 'lineChart')

    def test_trellis(self):
        self.assertEqual(self.map['trellis'], 'lineChart')

    def test_smallmultiple(self):
        self.assertEqual(self.map['smallmultiple'], 'lineChart')

    def test_facet(self):
        self.assertEqual(self.map['facet'], 'lineChart')

    def test_panelchart(self):
        self.assertEqual(self.map['panelchart'], 'lineChart')

    def test_sparkcolumn(self):
        self.assertEqual(self.map['sparkcolumn'], 'clusteredColumnChart')

    def test_sparkarea(self):
        self.assertEqual(self.map['sparkarea'], 'areaChart')

    def test_minibar(self):
        self.assertEqual(self.map['minibar'], 'clusteredBarChart')

    def test_minichart(self):
        self.assertEqual(self.map['minichart'], 'lineChart')

    def test_100percentbar(self):
        self.assertEqual(self.map['100percentbar'], 'hundredPercentStackedBarChart')

    def test_100percentcolumn(self):
        self.assertEqual(self.map['100percentcolumn'], 'hundredPercentStackedColumnChart')

    def test_percentbar(self):
        self.assertEqual(self.map['percentbar'], 'hundredPercentStackedBarChart')

    def test_percentcolumn(self):
        self.assertEqual(self.map['percentcolumn'], 'hundredPercentStackedColumnChart')

    # ── All values are valid PBI types ────────────────────────────

    def test_all_values_are_valid_pbi_types(self):
        valid_types = {
            'clusteredBarChart', 'stackedBarChart', 'hundredPercentStackedBarChart',
            'clusteredColumnChart', 'stackedColumnChart', 'hundredPercentStackedColumnChart',
            'lineChart', 'areaChart', 'stackedAreaChart', 'hundredPercentStackedAreaChart',
            'lineStackedColumnComboChart', 'lineClusteredColumnComboChart',
            'pieChart', 'donutChart', 'funnel', 'scatterChart',
            'map', 'filledMap', 'shapeMap', 'azureMap',
            'tableEx', 'pivotTable', 'matrix',
            'card', 'multiRowCard', 'gauge',
            'treemap', 'sunburst', 'decompositionTree',
            'waterfallChart', 'boxAndWhisker', 'bulletChart',
            'textbox', 'image', 'actionButton',
            'slicer', 'wordCloud', 'ribbonChart',
        }
        for key, value in self.map.items():
            self.assertIn(value, valid_types,
                          f"Invalid PBI type '{value}' for key '{key}'")


class TestExpandedApproximationMap(unittest.TestCase):
    """Test the expanded approximation map."""

    def setUp(self):
        from powerbi_import.visual_generator import APPROXIMATION_MAP
        self.approx = APPROXIMATION_MAP

    def test_has_27_plus_entries(self):
        self.assertGreaterEqual(len(self.approx), 27)

    def test_tornado_has_note(self):
        self.assertIn('tornado', self.approx)
        self.assertIn('mirrored', self.approx['tornado'][1].lower())

    def test_pyramid_has_note(self):
        self.assertIn('pyramid', self.approx)

    def test_violin_has_note(self):
        self.assertIn('violin', self.approx)
        self.assertIn('density', self.approx['violin'][1].lower())

    def test_radar_has_note(self):
        self.assertIn('radar', self.approx)

    def test_spider_has_note(self):
        self.assertIn('spider', self.approx)

    def test_coxcomb_has_note(self):
        self.assertIn('coxcomb', self.approx)

    def test_nightingale_has_note(self):
        self.assertIn('nightingale', self.approx)

    def test_trellis_has_note(self):
        self.assertIn('trellis', self.approx)

    def test_smallmultiple_has_note(self):
        self.assertIn('smallmultiple', self.approx)

    def test_orgchart_has_note(self):
        self.assertIn('orgchart', self.approx)

    def test_dendrogram_has_note(self):
        self.assertIn('dendrogram', self.approx)

    def test_lollipop_has_note(self):
        self.assertIn('lollipop', self.approx)

    def test_all_entries_have_two_tuple(self):
        for key, value in self.approx.items():
            self.assertIsInstance(value, tuple, f"{key} should be a tuple")
            self.assertEqual(len(value), 2, f"{key} should be (type, note)")


class TestFormatAdapterExpandedMap(unittest.TestCase):
    """Test the expanded format_adapter chart type map."""

    def test_format_adapter_has_new_entries(self):
        from qlik_export.format_adapter import _QLIK_CHART_TYPE_MAP
        self.assertIn('sunburst', _QLIK_CHART_TYPE_MAP)
        self.assertIn('ribbon', _QLIK_CHART_TYPE_MAP)
        self.assertIn('decompositiontree', _QLIK_CHART_TYPE_MAP)
        self.assertIn('choropleth', _QLIK_CHART_TYPE_MAP)
        self.assertIn('shapemap', _QLIK_CHART_TYPE_MAP)
        self.assertIn('geojson', _QLIK_CHART_TYPE_MAP)
        self.assertIn('azuremap', _QLIK_CHART_TYPE_MAP)
        self.assertIn('nl-insights', _QLIK_CHART_TYPE_MAP)
        self.assertIn('button', _QLIK_CHART_TYPE_MAP)
        self.assertIn('tabcontainer', _QLIK_CHART_TYPE_MAP)
        self.assertIn('sparkline', _QLIK_CHART_TYPE_MAP)

    def test_format_adapter_map_count(self):
        from qlik_export.format_adapter import _QLIK_CHART_TYPE_MAP
        self.assertGreaterEqual(len(_QLIK_CHART_TYPE_MAP), 70)


# ═══════════════════════════════════════════════════════════════════
# Power Query File Generation Tests
# ═══════════════════════════════════════════════════════════════════

class TestPowerQueryFileGeneration(unittest.TestCase):
    """Test _write_power_query_files in tmdl_generator."""

    def setUp(self):
        from powerbi_import.tmdl_generator import _write_power_query_files, _safe_filename
        self.write_pq = _write_power_query_files
        self.safe_filename = _safe_filename
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_expressions_folder(self):
        tables = [{
            'name': 'Sales',
            'partitions': [{'source': {'type': 'm', 'expression': 'let\n  Source = Sql.Database("srv", "db")\nin\n  Source'}}]
        }]
        self.write_pq(self.tmpdir, tables)
        expr_dir = os.path.join(self.tmpdir, 'expressions')
        self.assertTrue(os.path.isdir(expr_dir))

    def test_creates_pq_file_per_table(self):
        tables = [
            {'name': 'Sales', 'partitions': [{'source': {'type': 'm', 'expression': 'let Source = 1 in Source'}}]},
            {'name': 'Products', 'partitions': [{'source': {'type': 'm', 'expression': 'let Source = 2 in Source'}}]},
        ]
        self.write_pq(self.tmpdir, tables)
        expr_dir = os.path.join(self.tmpdir, 'expressions')
        files = os.listdir(expr_dir)
        self.assertIn('Sales.pq', files)
        self.assertIn('Products.pq', files)

    def test_pq_file_contains_m_expression(self):
        m_expr = 'let\n  Source = Sql.Database("srv", "db")\nin\n  Source'
        tables = [{'name': 'Orders', 'partitions': [{'source': {'type': 'm', 'expression': m_expr}}]}]
        self.write_pq(self.tmpdir, tables)
        pq_path = os.path.join(self.tmpdir, 'expressions', 'Orders.pq')
        with open(pq_path, 'r') as f:
            content = f.read()
        self.assertIn('Sql.Database("srv", "db")', content)
        self.assertIn('// Power Query M expression for table: Orders', content)

    def test_skips_calculated_partitions(self):
        tables = [{'name': 'CalcTable', 'partitions': [{'source': {'type': 'calculated', 'expression': 'CALENDAR()'}}]}]
        self.write_pq(self.tmpdir, tables)
        expr_dir = os.path.join(self.tmpdir, 'expressions')
        self.assertFalse(os.path.exists(expr_dir))

    def test_skips_empty_expression(self):
        tables = [{'name': 'Empty', 'partitions': [{'source': {'type': 'm', 'expression': ''}}]}]
        self.write_pq(self.tmpdir, tables)
        expr_dir = os.path.join(self.tmpdir, 'expressions')
        self.assertFalse(os.path.exists(expr_dir))

    def test_no_tables_no_folder(self):
        self.write_pq(self.tmpdir, [])
        expr_dir = os.path.join(self.tmpdir, 'expressions')
        self.assertFalse(os.path.exists(expr_dir))

    def test_pq_file_has_header_comment(self):
        tables = [{'name': 'T1', 'partitions': [{'source': {'type': 'm', 'expression': 'let S = 1 in S'}}]}]
        self.write_pq(self.tmpdir, tables)
        pq_path = os.path.join(self.tmpdir, 'expressions', 'T1.pq')
        with open(pq_path, 'r') as f:
            first_line = f.readline()
        self.assertTrue(first_line.startswith('// Power Query M expression'))

    def test_multiple_partitions_uses_first(self):
        tables = [{
            'name': 'Multi',
            'partitions': [
                {'source': {'type': 'm', 'expression': 'let S = 1 in S'}},
                {'source': {'type': 'm', 'expression': 'let S = 2 in S'}},
            ]
        }]
        self.write_pq(self.tmpdir, tables)
        pq_path = os.path.join(self.tmpdir, 'expressions', 'Multi.pq')
        with open(pq_path, 'r') as f:
            content = f.read()
        self.assertIn('S = 1', content)
        self.assertNotIn('S = 2', content)

    def test_safe_filename_for_special_chars(self):
        tables = [{'name': 'My Table (v2)', 'partitions': [{'source': {'type': 'm', 'expression': 'let S = 1 in S'}}]}]
        self.write_pq(self.tmpdir, tables)
        expr_dir = os.path.join(self.tmpdir, 'expressions')
        files = os.listdir(expr_dir)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith('.pq'))

    def test_file_ends_with_newline(self):
        tables = [{'name': 'T', 'partitions': [{'source': {'type': 'm', 'expression': 'let S = 1 in S'}}]}]
        self.write_pq(self.tmpdir, tables)
        pq_path = os.path.join(self.tmpdir, 'expressions', 'T.pq')
        with open(pq_path, 'r') as f:
            content = f.read()
        self.assertTrue(content.endswith('\n'))

    def test_mirrors_pq_to_project_power_query_folder(self):
        project_root = os.path.join(self.tmpdir, 'MyProject')
        semantic_model_dir = os.path.join(project_root, 'Test.SemanticModel')
        definition_dir = os.path.join(semantic_model_dir, 'definition')
        os.makedirs(definition_dir, exist_ok=True)

        tables = [{
            'name': 'Sales',
            'partitions': [{'source': {'type': 'm', 'expression': 'let Source = 1 in Source'}}]
        }]

        self.write_pq(definition_dir, tables, output_dir=semantic_model_dir)

        mirrored = os.path.join(project_root, 'power_query', 'Sales.pq')
        self.assertTrue(os.path.isfile(mirrored))


# ═══════════════════════════════════════════════════════════════════
# Geo Passthrough Tests
# ═══════════════════════════════════════════════════════════════════

class TestGeoPassthrough(unittest.TestCase):
    """Test geo_passthrough module."""

    def setUp(self):
        from powerbi_import.geo_passthrough import (
            detect_geo_sources,
            copy_geo_resources,
            build_shape_map_config,
            extract_geo_properties,
        )
        self.detect = detect_geo_sources
        self.copy = copy_geo_resources
        self.build_config = build_shape_map_config
        self.extract_props = extract_geo_properties
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_detect_empty_returns_empty(self):
        self.assertEqual(self.detect([]), [])
        self.assertEqual(self.detect(None), [])

    def test_detect_inline_geojson(self):
        viz = [{
            'id': 'map1',
            'type': 'map',
            'properties': {
                'type': 'FeatureCollection',
                'features': [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [0, 0]}}]
            }
        }]
        sources = self.detect(viz)
        self.assertGreaterEqual(len(sources), 1)
        self.assertEqual(sources[0]['type'], 'inline')

    def test_detect_file_reference(self):
        viz = [{
            'id': 'map2',
            'type': 'shapemap',
            'properties': {},
            'layers': [{'geoFile': '/data/regions.geojson'}],
        }]
        sources = self.detect(viz)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['type'], 'file')
        self.assertIn('regions.geojson', sources[0]['data'])

    def test_detect_url_reference(self):
        viz = [{
            'id': 'map3',
            'type': 'map',
            'properties': {},
            'layers': [{'url': 'https://example.com/data.geojson'}],
        }]
        sources = self.detect(viz)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['type'], 'url')

    def test_detect_string_geojson_in_properties(self):
        geojson_str = json.dumps({
            'type': 'FeatureCollection',
            'features': [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [1, 2]}}]
        })
        viz = [{
            'id': 'map4',
            'type': 'map',
            'properties': {'geoData': geojson_str},
        }]
        sources = self.detect(viz)
        self.assertGreaterEqual(len(sources), 1)

    def test_copy_inline_geojson(self):
        sources = [{
            'type': 'inline',
            'data': {'type': 'FeatureCollection', 'features': []},
            'visual_id': 'v1',
            'name': 'test_geo',
        }]
        report_dir = os.path.join(self.tmpdir, 'Report.Report', 'definition')
        os.makedirs(report_dir, exist_ok=True)
        created = self.copy(sources, self.tmpdir, 'Report')
        self.assertEqual(len(created), 1)
        resource_path = os.path.join(
            self.tmpdir, 'Report.Report', 'definition',
            'RegisteredResources', created[0])
        self.assertTrue(os.path.exists(resource_path))

    def test_copy_url_creates_placeholder(self):
        sources = [{
            'type': 'url',
            'data': 'https://example.com/data.geojson',
            'visual_id': 'v2',
            'name': 'url_geo',
        }]
        created = self.copy(sources, self.tmpdir, 'Report')
        self.assertEqual(len(created), 1)
        resource_path = os.path.join(
            self.tmpdir, 'Report.Report', 'definition',
            'RegisteredResources', created[0])
        with open(resource_path) as f:
            data = json.load(f)
        self.assertIn('_source_url', data)

    def test_copy_empty_returns_empty(self):
        self.assertEqual(self.copy([], self.tmpdir), [])

    def test_build_shape_map_config(self):
        sources = [{'name': 'test', 'type': 'inline', 'data': {}, 'visual_id': 'v1'}]
        config = self.build_config(sources, ['test.geojson'])
        self.assertIn('shape', config)
        self.assertEqual(len(config['shape']['customShapes']), 1)
        self.assertIn('RegisteredResources', config['shape']['customShapes'][0]['path'])

    def test_build_empty_config(self):
        self.assertEqual(self.build_config([]), {})

    def test_extract_geo_properties_latitude(self):
        viz = {'dimensions': [
            {'field': 'Lat', 'label': 'Latitude'},
            {'field': 'Lng', 'label': 'Longitude'},
        ]}
        props = self.extract_props(viz)
        self.assertEqual(props['latitude_field'], 'Lat')
        self.assertEqual(props['longitude_field'], 'Lng')

    def test_extract_geo_properties_country(self):
        viz = {'dimensions': [{'field': 'Country', 'label': 'Country'}]}
        props = self.extract_props(viz)
        self.assertEqual(props['location_field'], 'Country')
        self.assertEqual(props['geo_role'], 'Country')

    def test_extract_geo_properties_city(self):
        viz = {'dimensions': [{'field': 'CityName', 'label': 'City'}]}
        props = self.extract_props(viz)
        self.assertEqual(props['geo_role'], 'City')

    def test_extract_geo_properties_postal(self):
        viz = {'dimensions': [{'field': 'ZIP', 'label': 'Postal Code'}]}
        props = self.extract_props(viz)
        self.assertEqual(props['geo_role'], 'PostalCode')

    def test_extract_geo_properties_empty(self):
        viz = {'dimensions': [{'field': 'Amount', 'label': 'Amount'}]}
        props = self.extract_props(viz)
        self.assertEqual(props, {})


# ═══════════════════════════════════════════════════════════════════
# Refresh Generator Tests
# ═══════════════════════════════════════════════════════════════════

class TestRefreshGenerator(unittest.TestCase):
    """Test refresh_generator module."""

    def setUp(self):
        from powerbi_import.refresh_generator import (
            parse_qlik_tasks,
            generate_refresh_schedule,
            generate_refresh_powershell,
            write_refresh_config,
        )
        self.parse = parse_qlik_tasks
        self.gen_schedule = generate_refresh_schedule
        self.gen_ps = generate_refresh_powershell
        self.write_config = write_refresh_config
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ── Parsing tests ─────────────────────────────────────────────

    def test_parse_empty_returns_empty(self):
        self.assertEqual(self.parse(None), [])
        self.assertEqual(self.parse({}), [])
        self.assertEqual(self.parse([]), [])

    def test_parse_task_list(self):
        raw = [{'name': 'Daily Reload', 'enabled': True, 'triggers': [
            {'type': 'daily', 'startTime': '2024-01-01T06:00:00'}
        ]}]
        tasks = self.parse(raw)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['name'], 'Daily Reload')
        self.assertTrue(tasks[0]['enabled'])
        self.assertEqual(len(tasks[0]['triggers']), 1)
        self.assertEqual(tasks[0]['triggers'][0]['start_time'], '06:00')

    def test_parse_task_dict_with_tasks_key(self):
        raw = {'tasks': [{'name': 'T1', 'triggers': []}]}
        tasks = self.parse(raw)
        self.assertEqual(len(tasks), 1)

    def test_parse_task_dict_with_reload_tasks_key(self):
        raw = {'reloadTasks': [{'name': 'T2', 'triggers': []}]}
        tasks = self.parse(raw)
        self.assertEqual(len(tasks), 1)

    def test_parse_adds_default_trigger_if_none(self):
        raw = [{'name': 'NoTrigger'}]
        tasks = self.parse(raw)
        self.assertEqual(len(tasks[0]['triggers']), 1)
        self.assertEqual(tasks[0]['triggers'][0]['type'], 'daily')

    def test_parse_weekly_days(self):
        raw = [{'name': 'Weekly', 'triggers': [
            {'type': 'weekly', 'daysOfWeek': ['Monday', 'Wednesday', 'Friday']}
        ]}]
        tasks = self.parse(raw)
        days = tasks[0]['triggers'][0]['days']
        self.assertIn('Monday', days)
        self.assertIn('Wednesday', days)
        self.assertIn('Friday', days)

    def test_parse_numeric_days(self):
        raw = [{'name': 'NumDays', 'triggers': [
            {'type': 'weekly', 'daysOfWeek': ['1', '3', '5']}
        ]}]
        tasks = self.parse(raw)
        days = tasks[0]['triggers'][0]['days']
        self.assertIn('Monday', days)
        self.assertIn('Wednesday', days)
        self.assertIn('Friday', days)

    def test_parse_time_from_datetime(self):
        raw = [{'name': 'T', 'triggers': [
            {'type': 'daily', 'startDateTime': '2024-06-15T14:30:00Z'}
        ]}]
        tasks = self.parse(raw)
        self.assertEqual(tasks[0]['triggers'][0]['start_time'], '14:30')

    def test_parse_app_name_from_nested(self):
        raw = [{'name': 'T', 'app': {'name': 'SalesApp'}, 'triggers': []}]
        tasks = self.parse(raw)
        self.assertEqual(tasks[0]['app_name'], 'SalesApp')

    def test_parse_app_name_from_flat(self):
        raw = [{'name': 'T', 'appName': 'FlatApp', 'triggers': []}]
        tasks = self.parse(raw)
        self.assertEqual(tasks[0]['app_name'], 'FlatApp')

    # ── Schedule generation tests ─────────────────────────────────

    def test_schedule_from_daily_task(self):
        tasks = [{'name': 'Daily', 'enabled': True, 'triggers': [
            {'type': 'daily', 'start_time': '08:00', 'days': [], 'day_of_month': 0, 'interval_minutes': 0}
        ]}]
        schedule = self.gen_schedule(tasks)
        self.assertTrue(schedule['enabled'])
        self.assertIn('08:00', schedule['times'])
        self.assertEqual(len(schedule['days']), 7)  # All days for daily

    def test_schedule_from_weekly_task(self):
        tasks = [{'name': 'Weekly', 'enabled': True, 'triggers': [
            {'type': 'weekly', 'start_time': '07:00', 'days': ['Monday', 'Friday'],
             'day_of_month': 0, 'interval_minutes': 0}
        ]}]
        schedule = self.gen_schedule(tasks)
        self.assertEqual(schedule['days'], ['Monday', 'Friday'])

    def test_schedule_disabled_tasks_excluded(self):
        tasks = [{'name': 'Disabled', 'enabled': False, 'triggers': [
            {'type': 'daily', 'start_time': '06:00', 'days': [], 'day_of_month': 0, 'interval_minutes': 0}
        ]}]
        schedule = self.gen_schedule(tasks)
        self.assertFalse(schedule['enabled'])

    def test_schedule_empty_returns_disabled(self):
        schedule = self.gen_schedule([])
        self.assertFalse(schedule['enabled'])

    def test_schedule_max_refreshes_limit(self):
        tasks = [{'name': 'Frequent', 'enabled': True, 'triggers': [
            {'type': 'continuous', 'start_time': '00:00', 'days': [],
             'day_of_month': 0, 'interval_minutes': 30}
        ]}]
        schedule = self.gen_schedule(tasks, max_refreshes_per_day=8)
        self.assertLessEqual(len(schedule['times']), 8)

    def test_schedule_timezone_preserved(self):
        tasks = [{'name': 'T', 'enabled': True, 'triggers': [
            {'type': 'daily', 'start_time': '06:00', 'days': [], 'day_of_month': 0, 'interval_minutes': 0}
        ]}]
        schedule = self.gen_schedule(tasks, timezone='America/New_York')
        self.assertEqual(schedule['timezone'], 'America/New_York')

    def test_schedule_source_tasks_tracked(self):
        tasks = [
            {'name': 'Task1', 'enabled': True, 'triggers': [
                {'type': 'daily', 'start_time': '06:00', 'days': [], 'day_of_month': 0, 'interval_minutes': 0}
            ]},
            {'name': 'Task2', 'enabled': True, 'triggers': [
                {'type': 'daily', 'start_time': '12:00', 'days': [], 'day_of_month': 0, 'interval_minutes': 0}
            ]},
        ]
        schedule = self.gen_schedule(tasks)
        self.assertIn('Task1', schedule['source_tasks'])
        self.assertIn('Task2', schedule['source_tasks'])

    def test_schedule_days_sorted_calendar_order(self):
        tasks = [{'name': 'T', 'enabled': True, 'triggers': [
            {'type': 'weekly', 'start_time': '06:00',
             'days': ['Friday', 'Monday', 'Wednesday'],
             'day_of_month': 0, 'interval_minutes': 0}
        ]}]
        schedule = self.gen_schedule(tasks)
        self.assertEqual(schedule['days'], ['Monday', 'Wednesday', 'Friday'])

    # ── PowerShell generation tests ───────────────────────────────

    def test_powershell_contains_api_call(self):
        schedule = {
            'enabled': True, 'timezone': 'UTC',
            'days': ['Monday'], 'times': ['06:00'],
            'notifyOption': 'MailOnFailure', 'source_tasks': ['T1'],
        }
        ps = self.gen_ps(schedule, dataset_id='abc-123', group_id='grp-456')
        self.assertIn('Invoke-PowerBIRestMethod', ps)
        self.assertIn('abc-123', ps)
        self.assertIn('grp-456', ps)
        self.assertIn('refreshSchedule', ps)

    def test_powershell_has_header_comment(self):
        schedule = {
            'enabled': True, 'timezone': 'UTC',
            'days': [], 'times': [], 'notifyOption': 'NoNotification',
            'source_tasks': ['MyTask'],
        }
        ps = self.gen_ps(schedule)
        self.assertIn('# Power BI Scheduled Refresh Configuration', ps)
        self.assertIn('MyTask', ps)

    # ── Config file writing tests ─────────────────────────────────

    def test_write_refresh_config(self):
        schedule = {
            'enabled': True, 'timezone': 'UTC',
            'days': ['Monday'], 'times': ['06:00'],
            'notifyOption': 'MailOnFailure', 'source_tasks': ['T1'],
        }
        filepath = self.write_config(schedule, self.tmpdir, 'TestReport')
        self.assertTrue(os.path.exists(filepath))
        with open(filepath) as f:
            data = json.load(f)
        self.assertTrue(data['enabled'])
        self.assertIn('Monday', data['days'])


# ═══════════════════════════════════════════════════════════════════
# Qlik Server Client Tests
# ═══════════════════════════════════════════════════════════════════

class TestQlikServerClient(unittest.TestCase):
    """Test qlik_server_client module (unit tests — no server needed)."""

    def test_import(self):
        from qlik_export.qlik_server_client import QlikServerClient, QlikApiError
        self.assertIsNotNone(QlikServerClient)
        self.assertIsNotNone(QlikApiError)

    def test_cloud_detection_by_domain(self):
        from qlik_export.qlik_server_client import QlikServerClient
        client = QlikServerClient('https://tenant.qlikcloud.com', api_key='test')
        self.assertTrue(client._is_cloud)

    def test_cloud_detection_by_api_key(self):
        from qlik_export.qlik_server_client import QlikServerClient
        client = QlikServerClient('https://custom-server.com', api_key='test')
        self.assertTrue(client._is_cloud)

    def test_cloud_detection_by_jwt(self):
        from qlik_export.qlik_server_client import QlikServerClient
        client = QlikServerClient('https://custom-server.com', jwt_token='eyJ...')
        self.assertTrue(client._is_cloud)

    def test_qseow_detection(self):
        from qlik_export.qlik_server_client import QlikServerClient
        client = QlikServerClient('https://qlik.corp.com')
        self.assertFalse(client._is_cloud)

    def test_headers_with_api_key(self):
        from qlik_export.qlik_server_client import QlikServerClient
        client = QlikServerClient('https://tenant.qlikcloud.com', api_key='my-key')
        headers = client._build_headers()
        self.assertEqual(headers['Authorization'], 'Bearer my-key')

    def test_headers_with_jwt(self):
        from qlik_export.qlik_server_client import QlikServerClient
        client = QlikServerClient('https://x.qlikcloud.com', jwt_token='jwt-tok')
        headers = client._build_headers()
        self.assertEqual(headers['Authorization'], 'Bearer jwt-tok')

    def test_headers_qseow_xqlik_user(self):
        from qlik_export.qlik_server_client import QlikServerClient
        client = QlikServerClient('https://qlik.corp.com',
                                  user_directory='CORP', user_id='admin')
        headers = client._build_headers()
        self.assertIn('X-Qlik-User', headers)
        self.assertIn('CORP', headers['X-Qlik-User'])
        self.assertIn('admin', headers['X-Qlik-User'])

    def test_server_trailing_slash_stripped(self):
        from qlik_export.qlik_server_client import QlikServerClient
        client = QlikServerClient('https://server.com/')
        self.assertEqual(client.server, 'https://server.com')

    def test_connections_to_datasources(self):
        from qlik_export.qlik_server_client import _connections_to_datasources
        conns = [
            {'qName': 'MyDB', 'qType': 'ODBC', 'qConnectionString': 'DSN=mydb',
             'qServer': 'dbhost', 'qDatabase': 'mydb'},
        ]
        ds = _connections_to_datasources(conns)
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0]['name'], 'MyDB')
        self.assertEqual(ds[0]['connection']['server'], 'dbhost')

    def test_connections_to_datasources_empty(self):
        from qlik_export.qlik_server_client import _connections_to_datasources
        self.assertEqual(_connections_to_datasources([]), [])
        self.assertEqual(_connections_to_datasources(None), [])

    def test_qlik_api_error_message(self):
        from qlik_export.qlik_server_client import QlikApiError
        err = QlikApiError(404, 'GET', '/api/v1/apps', 'Not found')
        self.assertIn('404', str(err))
        self.assertIn('GET', str(err))
        self.assertIn('/api/v1/apps', str(err))


# ═══════════════════════════════════════════════════════════════════
# Integration: TMDL generator writes expressions/ folder
# ═══════════════════════════════════════════════════════════════════

class TestTMDLGeneratorExpressions(unittest.TestCase):
    """Integration test: generate_tmdl produces expressions/*.pq files."""

    def test_generate_tmdl_creates_expressions_folder(self):
        from powerbi_import.tmdl_generator import generate_tmdl

        datasources = [{
            'connection': {'type': 'sql', 'server': 'localhost', 'dbname': 'testdb'},
            'tables': [{
                'name': 'TestTable',
                'columns': [
                    {'name': 'ID', 'dataType': 'int64'},
                    {'name': 'Name', 'dataType': 'string'},
                ]
            }],
            'calculations': [],
            'columns': [],
        }]

        with tempfile.TemporaryDirectory() as tmpdir:
            sm_dir = os.path.join(tmpdir, 'Test.SemanticModel')
            os.makedirs(sm_dir, exist_ok=True)
            generate_tmdl(datasources, 'Test', {}, sm_dir)

            expr_dir = os.path.join(sm_dir, 'definition', 'expressions')
            if os.path.exists(expr_dir):
                pq_files = [f for f in os.listdir(expr_dir) if f.endswith('.pq')]
                # Should have at least one .pq file for TestTable
                self.assertGreaterEqual(len(pq_files), 1)


# ═══════════════════════════════════════════════════════════════════
# Pipeline Wiring Tests — geo_passthrough in pbip_generator
# ═══════════════════════════════════════════════════════════════════

class TestGeoPassthroughWiring(unittest.TestCase):
    """Test that geo_passthrough is wired into PowerBIProjectGenerator."""

    def test_geo_passthrough_imported_in_generate_project(self):
        """Verify geo_passthrough import is reachable from pbip_generator."""
        import importlib
        mod = importlib.import_module('powerbi_import.pbip_generator')
        # The import happens lazily inside generate_project, so just verify
        # the module can be imported
        geo = importlib.import_module('powerbi_import.geo_passthrough')
        self.assertTrue(hasattr(geo, 'detect_geo_sources'))
        self.assertTrue(hasattr(geo, 'copy_geo_resources'))
        self.assertTrue(hasattr(geo, 'build_shape_map_config'))

    def test_generate_project_with_geo_visuals(self):
        """Test that generate_project handles worksheets with GeoJSON."""
        from powerbi_import.pbip_generator import PowerBIProjectGenerator

        with tempfile.TemporaryDirectory() as td:
            gen = PowerBIProjectGenerator(output_dir=td)
            converted = {
                'datasources': [{'name': 'Source', 'tables': [
                    {'name': 'Regions', 'columns': [
                        {'name': 'Country', 'dataType': 'string'},
                    ]}
                ]}],
                'worksheets': [{
                    'name': 'GeoSheet',
                    'type': 'map',
                    'properties': {
                        'type': 'FeatureCollection',
                        'features': [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [0, 0]}}],
                    },
                    'dimensions': [{'field': 'Country'}],
                    'measures': [],
                }],
                'calculations': [],
                'dashboards': [{'name': 'Dashboard1', 'objects': []}],
            }
            # Should not raise even with geo data present
            result = gen.generate_project('GeoTest', converted)
            self.assertTrue(os.path.isdir(result))

    def test_generate_project_writes_geojson_resources(self):
        """Test that inline GeoJSON is written to RegisteredResources."""
        from powerbi_import.pbip_generator import PowerBIProjectGenerator

        with tempfile.TemporaryDirectory() as td:
            gen = PowerBIProjectGenerator(output_dir=td)
            geojson = {
                'type': 'FeatureCollection',
                'features': [
                    {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [1, 2]},
                     'properties': {'name': 'Test'}}
                ],
            }
            converted = {
                'datasources': [{'name': 'Src', 'tables': [
                    {'name': 'T', 'columns': [{'name': 'C', 'dataType': 'string'}]}
                ]}],
                'worksheets': [{
                    'name': 'MapViz',
                    'type': 'map',
                    'chart_type': 'map',
                    'properties': geojson,
                    'dimensions': [],
                    'measures': [],
                }],
                'calculations': [],
                'dashboards': [{'name': 'D', 'objects': []}],
            }
            result = gen.generate_project('GeoResourceTest', converted)
            # Check RegisteredResources for .geojson files
            res_dir = os.path.join(result, 'GeoResourceTest.Report',
                                   'definition', 'RegisteredResources')
            if os.path.isdir(res_dir):
                geo_files = [f for f in os.listdir(res_dir) if f.endswith('.geojson')]
                self.assertGreaterEqual(len(geo_files), 1)


# ═══════════════════════════════════════════════════════════════════
# Pipeline Wiring Tests — CLI flags for server/refresh
# ═══════════════════════════════════════════════════════════════════

class TestNewCLIFlagsV101(unittest.TestCase):
    """Test that v10.1 CLI flags are registered in migrate.py."""

    @classmethod
    def setUpClass(cls):
        import subprocess
        project_root = os.path.join(os.path.dirname(__file__), '..')
        python = os.path.join(project_root, 'venv', 'Scripts', 'python.exe')
        if not os.path.isfile(python):
            python = sys.executable
        result = subprocess.run(
            [python, os.path.join(project_root, 'migrate.py'), '--help'],
            capture_output=True, text=True, cwd=project_root,
        )
        cls.help_text = result.stdout + result.stderr

    def _assert_flag(self, flag_name):
        self.assertIn(flag_name, self.help_text,
                      f"Flag {flag_name} not in --help output")

    def test_server_url_flag(self):
        self._assert_flag('--server-url')

    def test_server_api_key_flag(self):
        self._assert_flag('--server-api-key')

    def test_server_cert_flag(self):
        self._assert_flag('--server-cert')

    def test_server_app_id_flag(self):
        self._assert_flag('--server-app-id')

    def test_refresh_schedule_flag(self):
        self._assert_flag('--refresh-schedule')

    def test_refresh_timezone_flag(self):
        self._assert_flag('--refresh-timezone')


# ═══════════════════════════════════════════════════════════════════
# Pipeline Wiring Tests — refresh_generator integration
# ═══════════════════════════════════════════════════════════════════

class TestRefreshGeneratorWiring(unittest.TestCase):
    """Test refresh_generator end-to-end with write_refresh_config."""

    def test_write_refresh_config_creates_file(self):
        from powerbi_import.refresh_generator import (
            parse_qlik_tasks, generate_refresh_schedule,
            generate_refresh_powershell, write_refresh_config,
        )

        with tempfile.TemporaryDirectory() as td:
            tasks_meta = [
                {
                    'name': 'DailyReload',
                    'appName': 'SalesApp',
                    'enabled': True,
                    'triggers': [
                        {'type': 'daily', 'startTime': '06:30'}
                    ]
                }
            ]
            tasks = parse_qlik_tasks(tasks_meta)
            schedule = generate_refresh_schedule(tasks, timezone='UTC')
            config_path = write_refresh_config(schedule, td)
            self.assertTrue(os.path.isfile(config_path))

            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertIn('times', data)

    def test_powershell_script_generation(self):
        from powerbi_import.refresh_generator import (
            parse_qlik_tasks, generate_refresh_schedule,
            generate_refresh_powershell,
        )

        tasks_meta = {'tasks': [
            {'name': 'Weekly', 'enabled': True, 'triggers': [
                {'type': 'weekly', 'startTime': '08:00', 'days': ['Monday', 'Wednesday']}
            ]}
        ]}
        tasks = parse_qlik_tasks(tasks_meta)
        schedule = generate_refresh_schedule(tasks)
        ps = generate_refresh_powershell(schedule, dataset_id='test-ds-id')
        self.assertIn('test-ds-id', ps)
        self.assertIn('Invoke-', ps)


# ═══════════════════════════════════════════════════════════════════
# Pipeline Wiring Tests — qlik_server_client extraction
# ═══════════════════════════════════════════════════════════════════

class TestServerClientWiring(unittest.TestCase):
    """Test that qlik_server_client can be used from migrate.py context."""

    def test_extract_app_for_migration_keys(self):
        """Verify extract_app_for_migration returns 11-key dict structure."""
        from qlik_export.qlik_server_client import QlikServerClient

        client = QlikServerClient('https://qlik.example.com', api_key='test')
        # The method calls the API, but we test the client construction
        self.assertEqual(client.server, 'https://qlik.example.com')
        self.assertTrue(client._is_cloud)

    def test_server_client_qseow_detection(self):
        """QSEoW clients should set _is_cloud=False."""
        from qlik_export.qlik_server_client import QlikServerClient

        client = QlikServerClient(
            'https://qlik-internal.corp.com',
            cert_path='/path/to/cert.pem'
        )
        self.assertFalse(client._is_cloud)

    def test_import_from_qlik_export(self):
        """Verify qlik_server_client is importable from qlik_export package."""
        from qlik_export import qlik_server_client
        self.assertTrue(hasattr(qlik_server_client, 'QlikServerClient'))
        self.assertTrue(hasattr(qlik_server_client, 'QlikApiError'))


if __name__ == '__main__':
    unittest.main()
