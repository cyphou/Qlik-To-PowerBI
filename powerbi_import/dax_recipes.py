"""
DAX Recipe Overrides — industry-specific KPI measure templates.

Provides curated DAX recipe collections for Healthcare, Finance, and Retail
verticals. Recipes can be loaded into the Migration Marketplace or applied
directly to a set of measures during TMDL generation.

Usage:
    from powerbi_import.dax_recipes import get_industry_recipes, apply_recipes
    recipes = get_industry_recipes("healthcare")
    changes = apply_recipes(measures_dict, recipes)
"""

import logging
import re

logger = logging.getLogger('qlik_to_powerbi.dax_recipes')


# ── Healthcare KPIs ──

HEALTHCARE_RECIPES = [
    {
        'name': 'Average Length of Stay',
        'dax': "DIVIDE(SUM('Encounters'[LOS_Days]), COUNTROWS('Encounters'))",
        'description': 'Average patient length of stay in days',
        'tags': ['healthcare', 'clinical', 'los'],
    },
    {
        'name': 'Readmission Rate',
        'dax': "DIVIDE(CALCULATE(COUNTROWS('Encounters'), 'Encounters'[IsReadmission] = TRUE()), COUNTROWS('Encounters'))",
        'description': '30-day readmission rate',
        'tags': ['healthcare', 'clinical', 'readmission'],
    },
    {
        'name': 'Bed Occupancy Rate',
        'dax': "DIVIDE(SUM('Census'[OccupiedBeds]), SUM('Census'[AvailableBeds]))",
        'description': 'Hospital bed occupancy percentage',
        'tags': ['healthcare', 'operations', 'capacity'],
    },
    {
        'name': 'Patient Satisfaction Score',
        'dax': "AVERAGE('Surveys'[SatisfactionScore])",
        'description': 'Average patient satisfaction (HCAHPS)',
        'tags': ['healthcare', 'quality', 'satisfaction'],
    },
    {
        'name': 'Mortality Rate',
        'dax': "DIVIDE(CALCULATE(COUNTROWS('Encounters'), 'Encounters'[DischargeStatus] = \"Expired\"), COUNTROWS('Encounters'))",
        'description': 'In-hospital mortality rate',
        'tags': ['healthcare', 'clinical', 'mortality'],
    },
    {
        'name': 'ED Wait Time Avg',
        'dax': "AVERAGE('ED_Visits'[WaitMinutes])",
        'description': 'Average emergency department wait time in minutes',
        'tags': ['healthcare', 'operations', 'ed'],
    },
]

# ── Finance KPIs ──

FINANCE_RECIPES = [
    {
        'name': 'Net Revenue',
        'dax': "SUM('Financials'[GrossRevenue]) - SUM('Financials'[Deductions])",
        'description': 'Net revenue after deductions',
        'tags': ['finance', 'revenue'],
    },
    {
        'name': 'Gross Margin %',
        'dax': "DIVIDE(SUM('Financials'[GrossRevenue]) - SUM('Financials'[COGS]), SUM('Financials'[GrossRevenue]))",
        'description': 'Gross margin percentage',
        'tags': ['finance', 'profitability', 'margin'],
    },
    {
        'name': 'Operating Expense Ratio',
        'dax': "DIVIDE(SUM('Financials'[OperatingExpenses]), SUM('Financials'[GrossRevenue]))",
        'description': 'Operating expenses as a ratio of revenue',
        'tags': ['finance', 'efficiency', 'opex'],
    },
    {
        'name': 'Revenue YTD',
        'dax': "TOTALYTD(SUM('Financials'[GrossRevenue]), 'Calendar'[Date])",
        'description': 'Year-to-date gross revenue',
        'tags': ['finance', 'time-intelligence', 'ytd'],
    },
    {
        'name': 'Revenue Prior Year',
        'dax': "CALCULATE(SUM('Financials'[GrossRevenue]), SAMEPERIODLASTYEAR('Calendar'[Date]))",
        'description': 'Prior year revenue for comparison',
        'tags': ['finance', 'time-intelligence', 'comparison'],
    },
    {
        'name': 'Budget Variance',
        'dax': "SUM('Financials'[Actual]) - SUM('Financials'[Budget])",
        'description': 'Actual vs budget variance',
        'tags': ['finance', 'budget', 'variance'],
    },
    {
        'name': 'Budget Variance %',
        'dax': "DIVIDE(SUM('Financials'[Actual]) - SUM('Financials'[Budget]), SUM('Financials'[Budget]))",
        'description': 'Budget variance as percentage',
        'tags': ['finance', 'budget', 'variance'],
    },
    {
        'name': 'Days Sales Outstanding',
        'dax': "DIVIDE(SUM('AR'[AccountsReceivable]), SUM('Financials'[GrossRevenue]) / 365)",
        'description': 'Average days to collect receivables',
        'tags': ['finance', 'ar', 'dso'],
    },
]

# ── Retail KPIs ──

RETAIL_RECIPES = [
    {
        'name': 'Revenue Per Transaction',
        'dax': "DIVIDE(SUM('Sales'[Revenue]), COUNTROWS('Sales'))",
        'description': 'Average revenue per transaction',
        'tags': ['retail', 'revenue', 'basket'],
    },
    {
        'name': 'Items Per Basket',
        'dax': "DIVIDE(SUM('Sales'[Quantity]), DISTINCTCOUNT('Sales'[TransactionID]))",
        'description': 'Average items per shopping basket',
        'tags': ['retail', 'basket', 'upt'],
    },
    {
        'name': 'Conversion Rate',
        'dax': "DIVIDE(DISTINCTCOUNT('Sales'[TransactionID]), SUM('Traffic'[Visits]))",
        'description': 'Store/site conversion rate',
        'tags': ['retail', 'conversion'],
    },
    {
        'name': 'Inventory Turnover',
        'dax': "DIVIDE(SUM('Sales'[COGS]), AVERAGE('Inventory'[Value]))",
        'description': 'Inventory turnover ratio',
        'tags': ['retail', 'inventory', 'turnover'],
    },
    {
        'name': 'Sell-Through Rate',
        'dax': "DIVIDE(SUM('Sales'[Quantity]), SUM('Inventory'[ReceivedQty]))",
        'description': 'Sell-through percentage',
        'tags': ['retail', 'inventory', 'sellthrough'],
    },
    {
        'name': 'Same Store Sales Growth',
        'dax': (
            "VAR _CurrentPeriod = SUM('Sales'[Revenue])\n"
            "VAR _PriorPeriod = CALCULATE(SUM('Sales'[Revenue]), SAMEPERIODLASTYEAR('Calendar'[Date]))\n"
            "RETURN DIVIDE(_CurrentPeriod - _PriorPeriod, _PriorPeriod)"
        ),
        'description': 'Year-over-year same-store sales growth',
        'tags': ['retail', 'growth', 'comp-sales'],
    },
    {
        'name': 'Customer Lifetime Value',
        'dax': "DIVIDE(SUMX(VALUES('Customers'[CustomerID]), CALCULATE(SUM('Sales'[Revenue]))), DISTINCTCOUNT('Customers'[CustomerID]))",
        'description': 'Average customer lifetime value',
        'tags': ['retail', 'customer', 'clv'],
    },
]

# ── Industry registry ──

_INDUSTRY_RECIPES = {
    'healthcare': HEALTHCARE_RECIPES,
    'finance': FINANCE_RECIPES,
    'retail': RETAIL_RECIPES,
}


def get_industry_recipes(industry):
    """Get the recipe list for an industry vertical.

    Args:
        industry: One of 'healthcare', 'finance', 'retail'

    Returns:
        list of recipe dicts, or empty list if unknown industry
    """
    return list(_INDUSTRY_RECIPES.get(industry.lower(), []))


def list_industries():
    """Return available industry verticals."""
    return list(_INDUSTRY_RECIPES.keys())


def get_all_recipes():
    """Return all recipes across all industries."""
    all_recipes = []
    for recipes in _INDUSTRY_RECIPES.values():
        all_recipes.extend(recipes)
    return all_recipes


def apply_recipes(measures, recipes, overwrite=False):
    """Apply a list of DAX recipes to a measures dict.

    Each recipe should have 'name' and 'dax' keys.
    Optionally has 'match' (regex) and 'replacement' for in-place transforms.

    Args:
        measures: dict {measure_name: dax_formula} — modified in place
        recipes: list of recipe dicts
        overwrite: if True, overwrite existing measures with same name

    Returns:
        dict of changes: {name: {'action': 'injected'|'replaced'|'skipped', ...}}
    """
    changes = {}
    for recipe in recipes:
        name = recipe.get('name', '')
        dax = recipe.get('dax', '')
        match_re = recipe.get('match')
        replacement = recipe.get('replacement')

        # In-place replacement mode
        if match_re and replacement:
            for mname, formula in list(measures.items()):
                if re.search(match_re, formula, re.IGNORECASE):
                    measures[mname] = re.sub(match_re, replacement, formula,
                                             flags=re.IGNORECASE)
                    changes[mname] = {'action': 'replaced', 'recipe': name}

        # Injection mode
        elif name and dax:
            if name in measures and not overwrite:
                changes[name] = {'action': 'skipped', 'reason': 'exists'}
            else:
                measures[name] = dax
                changes[name] = {'action': 'injected', 'recipe': name}

    return changes


def recipes_to_marketplace_format(industry):
    """Convert industry recipes to marketplace-compatible pattern dicts.

    Returns list of dicts suitable for ``PatternRegistry.register()``.
    """
    recipes = get_industry_recipes(industry)
    patterns = []
    for recipe in recipes:
        pattern = {
            'metadata': {
                'name': recipe['name'].lower().replace(' ', '_'),
                'version': '1.0.0',
                'author': f'{industry.title()} Template Library',
                'description': recipe.get('description', ''),
                'tags': recipe.get('tags', [industry]),
                'category': 'dax_recipe',
                'created': '2026-03-22',
            },
            'payload': {
                'inject': {
                    'name': recipe['name'],
                    'dax': recipe['dax'],
                }
            },
        }
        if recipe.get('match'):
            pattern['payload']['match'] = recipe['match']
            pattern['payload']['replacement'] = recipe.get('replacement', '')
        patterns.append(pattern)
    return patterns
