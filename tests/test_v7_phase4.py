"""Tests for v7 Phase 4 – Section Access enhancements (OMIT, wildcard, REDUCE)."""
import pytest
from qlik_export.format_adapter import _parse_section_access
from powerbi_import.tmdl_generator import _create_rls_roles


# ─── _parse_section_access ───────────────────────────────────────────────

class TestParseSectionAccess:
    """Tests for OMIT, wildcard, and REDUCE column parsing."""

    def test_basic_userid(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID
            USER, alice@contoso.com
            USER, bob@contoso.com
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert len(roles) == 2
        assert roles[0]['name'] == 'RLS_alice'
        assert 'USERPRINCIPALNAME()' in roles[0]['filter_expression']

    def test_wildcard_star_generates_true(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID
            ADMIN, *
            USER, alice@contoso.com
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert len(roles) == 2
        wildcard_role = roles[0]
        assert wildcard_role['name'] == 'RLS_AllUsers'
        assert wildcard_role['filter_expression'] == 'TRUE()'

    def test_omit_column_parsed(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID, OMIT
            USER, alice@contoso.com, Salary
            USER, bob@contoso.com, Salary;Bonus
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert len(roles) == 2
        assert roles[0].get('omit_fields') == ['Salary']
        assert roles[1].get('omit_fields') == ['Salary', 'Bonus']

    def test_no_omit_no_key(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID
            USER, alice@contoso.com
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert 'omit_fields' not in roles[0]

    def test_reduction_column_parsed(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID, REDUCTION
            USER, alice@contoso.com, US;Canada
            USER, bob@contoso.com, France
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert roles[0].get('reduce_values') == ['US', 'Canada']
        assert roles[1].get('reduce_values') == ['France']

    def test_empty_omit_field_not_included(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID, OMIT
            USER, alice@contoso.com,
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert 'omit_fields' not in roles[0]

    def test_ntname_fallback(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, NTNAME
            USER, DOMAIN\\alice
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert len(roles) == 1
        assert 'DOMAIN' in roles[0]['filter_expression']

    def test_type_always_user_filter(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID
            USER, alice@contoso.com
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert roles[0]['type'] == 'user_filter'

    def test_empty_script_returns_empty(self):
        assert _parse_section_access('') == []
        assert _parse_section_access(None) == []
        assert _parse_section_access({}) == []

    def test_no_section_access_block(self):
        assert _parse_section_access('LET vYear = 2024;') == []

    def test_dict_input_with_script_key(self):
        script = {
            'script': """
            SECTION ACCESS;
            LOAD * INLINE [
                ACCESS, USERID
                USER, test@example.com
            ];
            SECTION APPLICATION;
            """
        }
        roles = _parse_section_access(script)
        assert len(roles) == 1


# ─── _create_rls_roles with new fields ──────────────────────────────────

class TestCreateRlsRolesEnhanced:
    """Tests for _create_rls_roles handling OMIT, wildcard, reduce."""

    def _make_model(self):
        return {
            'model': {
                'tables': [{'name': 'Sales', 'columns': []}],
            }
        }

    def test_filter_expression_passthrough(self):
        """Pre-built filter_expression from _parse_section_access is used directly."""
        model = self._make_model()
        filters = [{
            'type': 'user_filter',
            'name': 'RLS_alice',
            'filter_expression': 'USERPRINCIPALNAME() = "alice@contoso.com"',
            'tables': [],
        }]
        _create_rls_roles(model, filters, 'Sales', {})
        roles = model['model']['roles']
        assert len(roles) == 1
        assert roles[0]['tablePermissions'][0]['filterExpression'] == 'USERPRINCIPALNAME() = "alice@contoso.com"'

    def test_wildcard_true_passthrough(self):
        """Wildcard * → TRUE() passes through correctly."""
        model = self._make_model()
        filters = [{
            'type': 'user_filter',
            'name': 'RLS_AllUsers',
            'filter_expression': 'TRUE()',
            'tables': [],
        }]
        _create_rls_roles(model, filters, 'Sales', {})
        roles = model['model']['roles']
        assert roles[0]['tablePermissions'][0]['filterExpression'] == 'TRUE()'

    def test_omit_fields_in_role(self):
        """OMIT fields are stored and noted in migration note."""
        model = self._make_model()
        filters = [{
            'type': 'user_filter',
            'name': 'RLS_alice',
            'filter_expression': 'USERPRINCIPALNAME() = "alice@contoso.com"',
            'tables': [],
            'omit_fields': ['Salary', 'Bonus'],
        }]
        _create_rls_roles(model, filters, 'Sales', {})
        role = model['model']['roles'][0]
        assert role.get('_omit_fields') == ['Salary', 'Bonus']
        assert 'Object-Level Security' in role.get('_migration_note', '')

    def test_reduce_values_stored(self):
        """Reduce values are stored in role entry."""
        model = self._make_model()
        filters = [{
            'type': 'user_filter',
            'name': 'RLS_alice',
            'filter_expression': 'USERPRINCIPALNAME() = "alice@contoso.com"',
            'tables': [],
            'reduce_values': ['US', 'Canada'],
        }]
        _create_rls_roles(model, filters, 'Sales', {})
        role = model['model']['roles'][0]
        assert role.get('_reduce_values') == ['US', 'Canada']

    def test_existing_user_mappings_still_work(self):
        """Existing user_mappings path is not broken."""
        model = self._make_model()
        filters = [{
            'type': 'user_filter',
            'name': 'RegionFilter',
            'column': 'Region',
            'user_mappings': [
                {'user': 'alice@contoso.com', 'value': 'US'},
                {'user': 'bob@contoso.com', 'value': 'EU'},
            ],
        }]
        _create_rls_roles(model, filters, 'Sales', {})
        roles = model['model']['roles']
        assert len(roles) == 1
        filt = roles[0]['tablePermissions'][0]['filterExpression']
        assert 'USERPRINCIPALNAME()' in filt
        assert 'US' in filt

    def test_column_only_path_still_works(self):
        """Column-only filter (no user_mappings) still works."""
        model = self._make_model()
        filters = [{
            'type': 'user_filter',
            'name': 'EmailFilter',
            'column': 'UserEmail',
        }]
        _create_rls_roles(model, filters, 'Sales', {})
        roles = model['model']['roles']
        assert '[UserEmail] = USERPRINCIPALNAME()' in roles[0]['tablePermissions'][0]['filterExpression']

    def test_calculated_security_still_works(self):
        """Calculated security path is unchanged."""
        model = self._make_model()
        filters = [{
            'type': 'calculated_security',
            'name': 'GroupSecurity',
            'formula': 'ISMEMBEROF("Managers")',
            'functions_used': [],
            'ismemberof_groups': ['Managers'],
        }]
        _create_rls_roles(model, filters, 'Sales', {})
        roles = model['model']['roles']
        assert len(roles) == 1
        assert 'Managers' in roles[0]['name']

    def test_empty_filters_no_roles(self):
        """Empty filter list does nothing."""
        model = self._make_model()
        _create_rls_roles(model, [], 'Sales', {})
        assert 'roles' not in model['model']

    def test_none_filters_no_roles(self):
        """None filter list does nothing."""
        model = self._make_model()
        _create_rls_roles(model, None, 'Sales', {})
        assert 'roles' not in model['model']


# ─── End-to-end: parse → create ─────────────────────────────────────────

class TestSectionAccessEndToEnd:
    """Integration: _parse_section_access → _create_rls_roles."""

    def test_full_pipeline_with_omit(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID, OMIT
            ADMIN, *, 
            USER, alice@contoso.com, Salary
            USER, bob@contoso.com, Salary;Bonus
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert len(roles) == 3

        model = {'model': {'tables': [{'name': 'HR', 'columns': []}]}}
        _create_rls_roles(model, roles, 'HR', {})

        created = model['model']['roles']
        assert len(created) == 3

        # Admin wildcard
        assert created[0]['tablePermissions'][0]['filterExpression'] == 'TRUE()'

        # Alice with OMIT
        assert created[1].get('_omit_fields') == ['Salary']

        # Bob with multiple OMIT
        assert created[2].get('_omit_fields') == ['Salary', 'Bonus']

    def test_full_pipeline_basic(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID
            USER, john@example.com
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        model = {'model': {'tables': [{'name': 'Data', 'columns': []}]}}
        _create_rls_roles(model, roles, 'Data', {})
        created = model['model']['roles']
        assert len(created) == 1
        assert 'john@example.com' in created[0]['tablePermissions'][0]['filterExpression']
