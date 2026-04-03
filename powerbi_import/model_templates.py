"""
Industry Model Templates — pre-built semantic model skeletons for
Healthcare, Finance, and Retail verticals.

Each template defines tables, columns, relationships, measures, and
hierarchies that represent common industry data models. Templates
can be merged with migrated Qlik data to produce a richer,
standards-compliant Power BI semantic model.

Usage:
    from powerbi_import.model_templates import get_template, apply_template
    template = get_template("healthcare")
    enrichment = apply_template(template, existing_tables)
"""

import copy
import logging

logger = logging.getLogger('qlik_to_powerbi.model_templates')


# ── Healthcare Star Schema ──

HEALTHCARE_TEMPLATE = {
    'name': 'Healthcare',
    'description': 'Clinical analytics star schema — encounters, patients, providers, facilities',
    'tables': [
        {
            'name': 'Encounters',
            'columns': [
                {'name': 'EncounterID', 'dataType': 'string', 'isKey': True},
                {'name': 'PatientID', 'dataType': 'string'},
                {'name': 'ProviderID', 'dataType': 'string'},
                {'name': 'FacilityID', 'dataType': 'string'},
                {'name': 'AdmitDate', 'dataType': 'dateTime'},
                {'name': 'DischargeDate', 'dataType': 'dateTime'},
                {'name': 'LOS_Days', 'dataType': 'int64'},
                {'name': 'DischargeStatus', 'dataType': 'string'},
                {'name': 'IsReadmission', 'dataType': 'boolean'},
                {'name': 'DRG_Code', 'dataType': 'string'},
                {'name': 'PrimaryDiagnosis', 'dataType': 'string'},
                {'name': 'TotalCharges', 'dataType': 'double'},
            ],
        },
        {
            'name': 'Patients',
            'columns': [
                {'name': 'PatientID', 'dataType': 'string', 'isKey': True},
                {'name': 'PatientName', 'dataType': 'string'},
                {'name': 'DateOfBirth', 'dataType': 'dateTime'},
                {'name': 'Gender', 'dataType': 'string'},
                {'name': 'ZipCode', 'dataType': 'string', 'dataCategory': 'PostalCode'},
            ],
        },
        {
            'name': 'Providers',
            'columns': [
                {'name': 'ProviderID', 'dataType': 'string', 'isKey': True},
                {'name': 'ProviderName', 'dataType': 'string'},
                {'name': 'Specialty', 'dataType': 'string'},
                {'name': 'Department', 'dataType': 'string'},
            ],
        },
        {
            'name': 'Facilities',
            'columns': [
                {'name': 'FacilityID', 'dataType': 'string', 'isKey': True},
                {'name': 'FacilityName', 'dataType': 'string'},
                {'name': 'City', 'dataType': 'string', 'dataCategory': 'City'},
                {'name': 'State', 'dataType': 'string', 'dataCategory': 'StateOrProvince'},
                {'name': 'BedCount', 'dataType': 'int64'},
            ],
        },
    ],
    'relationships': [
        {'from': 'Encounters.PatientID', 'to': 'Patients.PatientID', 'cardinality': 'manyToOne'},
        {'from': 'Encounters.ProviderID', 'to': 'Providers.ProviderID', 'cardinality': 'manyToOne'},
        {'from': 'Encounters.FacilityID', 'to': 'Facilities.FacilityID', 'cardinality': 'manyToOne'},
    ],
    'measures': [
        {'name': 'Total Encounters', 'dax': "COUNTROWS('Encounters')", 'displayFolder': 'Measures'},
        {'name': 'Avg Length of Stay', 'dax': "AVERAGE('Encounters'[LOS_Days])", 'displayFolder': 'Measures'},
        {'name': 'Readmission Rate', 'dax': "DIVIDE(CALCULATE(COUNTROWS('Encounters'), 'Encounters'[IsReadmission] = TRUE()), COUNTROWS('Encounters'))", 'displayFolder': 'Measures'},
        {'name': 'Total Charges', 'dax': "SUM('Encounters'[TotalCharges])", 'displayFolder': 'Measures'},
    ],
    'hierarchies': [
        {'table': 'Facilities', 'name': 'Geography', 'levels': ['State', 'City', 'FacilityName']},
    ],
}


# ── Finance Star Schema ──

FINANCE_TEMPLATE = {
    'name': 'Finance',
    'description': 'Financial analytics — GL, budget, accounts receivable',
    'tables': [
        {
            'name': 'Financials',
            'columns': [
                {'name': 'TransactionID', 'dataType': 'string', 'isKey': True},
                {'name': 'AccountID', 'dataType': 'string'},
                {'name': 'CostCenterID', 'dataType': 'string'},
                {'name': 'TransactionDate', 'dataType': 'dateTime'},
                {'name': 'GrossRevenue', 'dataType': 'double'},
                {'name': 'Deductions', 'dataType': 'double'},
                {'name': 'COGS', 'dataType': 'double'},
                {'name': 'OperatingExpenses', 'dataType': 'double'},
                {'name': 'Actual', 'dataType': 'double'},
                {'name': 'Budget', 'dataType': 'double'},
            ],
        },
        {
            'name': 'Accounts',
            'columns': [
                {'name': 'AccountID', 'dataType': 'string', 'isKey': True},
                {'name': 'AccountName', 'dataType': 'string'},
                {'name': 'AccountType', 'dataType': 'string'},
                {'name': 'AccountCategory', 'dataType': 'string'},
            ],
        },
        {
            'name': 'CostCenters',
            'columns': [
                {'name': 'CostCenterID', 'dataType': 'string', 'isKey': True},
                {'name': 'CostCenterName', 'dataType': 'string'},
                {'name': 'Division', 'dataType': 'string'},
                {'name': 'Region', 'dataType': 'string'},
            ],
        },
        {
            'name': 'AR',
            'columns': [
                {'name': 'InvoiceID', 'dataType': 'string', 'isKey': True},
                {'name': 'AccountID', 'dataType': 'string'},
                {'name': 'InvoiceDate', 'dataType': 'dateTime'},
                {'name': 'DueDate', 'dataType': 'dateTime'},
                {'name': 'AccountsReceivable', 'dataType': 'double'},
                {'name': 'PaidAmount', 'dataType': 'double'},
            ],
        },
    ],
    'relationships': [
        {'from': 'Financials.AccountID', 'to': 'Accounts.AccountID', 'cardinality': 'manyToOne'},
        {'from': 'Financials.CostCenterID', 'to': 'CostCenters.CostCenterID', 'cardinality': 'manyToOne'},
        {'from': 'AR.AccountID', 'to': 'Accounts.AccountID', 'cardinality': 'manyToOne'},
    ],
    'measures': [
        {'name': 'Net Revenue', 'dax': "SUM('Financials'[GrossRevenue]) - SUM('Financials'[Deductions])", 'displayFolder': 'Revenue'},
        {'name': 'Gross Margin %', 'dax': "DIVIDE(SUM('Financials'[GrossRevenue]) - SUM('Financials'[COGS]), SUM('Financials'[GrossRevenue]))", 'displayFolder': 'Profitability'},
        {'name': 'Budget Variance', 'dax': "SUM('Financials'[Actual]) - SUM('Financials'[Budget])", 'displayFolder': 'Budget'},
        {'name': 'Budget Variance %', 'dax': "DIVIDE(SUM('Financials'[Actual]) - SUM('Financials'[Budget]), SUM('Financials'[Budget]))", 'displayFolder': 'Budget'},
    ],
    'hierarchies': [
        {'table': 'Accounts', 'name': 'Account Hierarchy', 'levels': ['AccountCategory', 'AccountType', 'AccountName']},
        {'table': 'CostCenters', 'name': 'Organization', 'levels': ['Region', 'Division', 'CostCenterName']},
    ],
}


# ── Retail Star Schema ──

RETAIL_TEMPLATE = {
    'name': 'Retail',
    'description': 'Retail analytics — sales, products, stores, customers',
    'tables': [
        {
            'name': 'Sales',
            'columns': [
                {'name': 'TransactionID', 'dataType': 'string'},
                {'name': 'LineItemID', 'dataType': 'string', 'isKey': True},
                {'name': 'ProductID', 'dataType': 'string'},
                {'name': 'StoreID', 'dataType': 'string'},
                {'name': 'CustomerID', 'dataType': 'string'},
                {'name': 'SaleDate', 'dataType': 'dateTime'},
                {'name': 'Quantity', 'dataType': 'int64'},
                {'name': 'Revenue', 'dataType': 'double'},
                {'name': 'COGS', 'dataType': 'double'},
                {'name': 'Discount', 'dataType': 'double'},
            ],
        },
        {
            'name': 'Products',
            'columns': [
                {'name': 'ProductID', 'dataType': 'string', 'isKey': True},
                {'name': 'ProductName', 'dataType': 'string'},
                {'name': 'Category', 'dataType': 'string'},
                {'name': 'SubCategory', 'dataType': 'string'},
                {'name': 'Brand', 'dataType': 'string'},
                {'name': 'UnitPrice', 'dataType': 'double'},
            ],
        },
        {
            'name': 'Stores',
            'columns': [
                {'name': 'StoreID', 'dataType': 'string', 'isKey': True},
                {'name': 'StoreName', 'dataType': 'string'},
                {'name': 'City', 'dataType': 'string', 'dataCategory': 'City'},
                {'name': 'State', 'dataType': 'string', 'dataCategory': 'StateOrProvince'},
                {'name': 'Region', 'dataType': 'string'},
                {'name': 'StoreType', 'dataType': 'string'},
            ],
        },
        {
            'name': 'Customers',
            'columns': [
                {'name': 'CustomerID', 'dataType': 'string', 'isKey': True},
                {'name': 'CustomerName', 'dataType': 'string'},
                {'name': 'Segment', 'dataType': 'string'},
                {'name': 'City', 'dataType': 'string', 'dataCategory': 'City'},
                {'name': 'State', 'dataType': 'string', 'dataCategory': 'StateOrProvince'},
            ],
        },
    ],
    'relationships': [
        {'from': 'Sales.ProductID', 'to': 'Products.ProductID', 'cardinality': 'manyToOne'},
        {'from': 'Sales.StoreID', 'to': 'Stores.StoreID', 'cardinality': 'manyToOne'},
        {'from': 'Sales.CustomerID', 'to': 'Customers.CustomerID', 'cardinality': 'manyToOne'},
    ],
    'measures': [
        {'name': 'Total Revenue', 'dax': "SUM('Sales'[Revenue])", 'displayFolder': 'Revenue'},
        {'name': 'Total Quantity', 'dax': "SUM('Sales'[Quantity])", 'displayFolder': 'Sales Metrics'},
        {'name': 'Avg Revenue Per Transaction', 'dax': "DIVIDE(SUM('Sales'[Revenue]), DISTINCTCOUNT('Sales'[TransactionID]))", 'displayFolder': 'Sales Metrics'},
        {'name': 'Items Per Basket', 'dax': "DIVIDE(SUM('Sales'[Quantity]), DISTINCTCOUNT('Sales'[TransactionID]))", 'displayFolder': 'Sales Metrics'},
        {'name': 'Gross Margin', 'dax': "SUM('Sales'[Revenue]) - SUM('Sales'[COGS])", 'displayFolder': 'Profitability'},
    ],
    'hierarchies': [
        {'table': 'Products', 'name': 'Product Hierarchy', 'levels': ['Category', 'SubCategory', 'ProductName']},
        {'table': 'Stores', 'name': 'Store Geography', 'levels': ['Region', 'State', 'City', 'StoreName']},
    ],
}


# ── Template registry ──

_TEMPLATES = {
    'healthcare': HEALTHCARE_TEMPLATE,
    'finance': FINANCE_TEMPLATE,
    'retail': RETAIL_TEMPLATE,
}


def get_template(industry):
    """Get an industry model template by name.

    Args:
        industry: One of 'healthcare', 'finance', 'retail'

    Returns:
        dict template or None
    """
    tpl = _TEMPLATES.get(industry.lower())
    return copy.deepcopy(tpl) if tpl else None


def list_templates():
    """Return available template names."""
    return list(_TEMPLATES.keys())


def apply_template(template, existing_tables):
    """Merge a template into existing migrated tables.

    Tables that already exist (by name, case-insensitive) get enriched:
    - Missing columns are appended
    - Measures are added if not present
    - Relationships are suggested if endpoints exist

    New tables from the template are included as skeleton tables.

    Args:
        template: dict from ``get_template()``
        existing_tables: list of table dicts from migration output

    Returns:
        dict with keys:
            - 'tables': enriched table list
            - 'measures': list of new measures added
            - 'relationships': list of new relationships suggested
            - 'hierarchies': list of new hierarchies added
            - 'stats': summary counts
    """
    existing_map = {t.get('name', '').lower(): t for t in existing_tables}
    new_measures = []
    new_relationships = []
    new_hierarchies = []
    new_tables_added = 0
    columns_added = 0

    # Merge tables
    for tpl_table in template.get('tables', []):
        tpl_name = tpl_table['name']
        key = tpl_name.lower()
        if key in existing_map:
            # Enrich existing table with missing columns
            existing = existing_map[key]
            existing_cols = {c.get('name', '').lower() for c in existing.get('columns', [])}
            for col in tpl_table.get('columns', []):
                if col['name'].lower() not in existing_cols:
                    existing.setdefault('columns', []).append(col)
                    columns_added += 1
        else:
            # Add skeleton table
            existing_tables.append(copy.deepcopy(tpl_table))
            existing_map[key] = existing_tables[-1]
            new_tables_added += 1

    # Add measures
    for measure in template.get('measures', []):
        new_measures.append(measure)

    # Add relationships where both endpoints exist
    for rel in template.get('relationships', []):
        from_parts = rel['from'].split('.')
        to_parts = rel['to'].split('.')
        if len(from_parts) == 2 and len(to_parts) == 2:
            from_table = from_parts[0].lower()
            to_table = to_parts[0].lower()
            if from_table in existing_map and to_table in existing_map:
                new_relationships.append(rel)

    # Add hierarchies where table exists
    for hier in template.get('hierarchies', []):
        if hier.get('table', '').lower() in existing_map:
            new_hierarchies.append(hier)

    return {
        'tables': existing_tables,
        'measures': new_measures,
        'relationships': new_relationships,
        'hierarchies': new_hierarchies,
        'stats': {
            'new_tables': new_tables_added,
            'columns_added': columns_added,
            'measures_added': len(new_measures),
            'relationships_added': len(new_relationships),
            'hierarchies_added': len(new_hierarchies),
        },
    }
