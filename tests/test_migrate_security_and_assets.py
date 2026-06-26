import os

from migrate import _parse_roles_tmdl, _scan_image_values, export_power_query_folder


def test_parse_roles_tmdl_extracts_rows(tmp_path):
    roles = tmp_path / 'roles.tmdl'
    roles.write_text(
        """
role 'RLS_Sales'
	modelPermission: read
	tablePermission 'Orders'
		filterExpression = [Region] = \"EMEA\"

role 'RLS_All'
	modelPermission: read
	tablePermission 'Customers'
""".strip() + "\n",
        encoding='utf-8',
    )

    rows = _parse_roles_tmdl(str(roles))
    assert len(rows) == 2
    assert rows[0]['role_name'] == 'RLS_Sales'
    assert rows[0]['table'] == 'Orders'
    assert rows[0]['filter_expression'] == '[Region] = "EMEA"'
    assert rows[1]['role_name'] == 'RLS_All'
    assert rows[1]['table'] == 'Customers'


def test_scan_image_values_finds_data_uri_and_urls():
    payload = {
        'backgroundImage': {'url': 'https://example.com/bg.png'},
        'items': [
            {'source': 'data:image/png;base64,Zm9v'},
            {'source': 'assets/logo.svg'},
        ],
    }

    refs = _scan_image_values(payload)
    kinds = {k for _, _, k in refs}
    assert 'data_uri' in kinds
    assert 'url' in kinds
    assert 'path' in kinds


def test_export_power_query_folder_copies_queries(tmp_path):
    report = 'Demo'
    project = tmp_path / report
    def_dir = project / f'{report}.SemanticModel' / 'definition'
    expr_dir = def_dir / 'expressions'
    expr_dir.mkdir(parents=True)
    (expr_dir / 'Orders.pq').write_text('let Source = 1 in Source\n', encoding='utf-8')
    (def_dir / 'expressions.tmdl').write_text('expression DataFolder = "C:\\\\Data"\n', encoding='utf-8')

    info = export_power_query_folder(report, output_dir=str(tmp_path))
    assert info is not None
    assert info['query_files'] == 1
    pq_dir = project / 'power_query'
    assert (pq_dir / 'Orders.pq').exists()
    assert (pq_dir / 'expressions.tmdl').exists()
