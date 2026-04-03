"""LLM-Assisted DAX Correction — AI-powered refinement for approximated DAX formulas.

When the Qlik→DAX converter produces an approximated result (marked with
MigrationNote), this module can optionally send the formula to an LLM (OpenAI
or Anthropic) for refinement.

Features:
- OpenAI and Anthropic client support via stdlib urllib (no external deps)
- Structured prompt with Qlik formula + current DAX + schema context
- Confidence scoring per refinement
- Token counting and cost estimation
- Rate limiting and retry-after logic
- Dry-run mode (preview prompts without calling API)
- Cost report generation

Usage:
    from powerbi_import.llm_client import LLMClient, refine_approximated_measures

    client = LLMClient(provider='openai', api_key='sk-...', model='gpt-4o')
    results = refine_approximated_measures(client, measures, table_context)
"""

import json
import os
import re
import time
import logging
import hashlib
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger('qlik_to_powerbi.llm_client')

# ════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════════

_PROVIDERS = {
    'openai': {
        'url': 'https://api.openai.com/v1/chat/completions',
        'default_model': 'gpt-4o',
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'cost_per_1k_input': 0.0025,
        'cost_per_1k_output': 0.01,
    },
    'anthropic': {
        'url': 'https://api.anthropic.com/v1/messages',
        'default_model': 'claude-sonnet-4-20250514',
        'auth_header': 'x-api-key',
        'auth_prefix': '',
        'cost_per_1k_input': 0.003,
        'cost_per_1k_output': 0.015,
    },
    'azure_openai': {
        'url': '',  # Set via endpoint param
        'default_model': 'gpt-4o',
        'auth_header': 'api-key',
        'auth_prefix': '',
        'cost_per_1k_input': 0.0025,
        'cost_per_1k_output': 0.01,
    },
}

_SYSTEM_PROMPT = """You are an expert in both Qlik calculated fields and Power BI DAX.
Your task is to refine an approximated DAX formula that was auto-converted from Qlik.

Rules:
1. Output ONLY the corrected DAX formula — no explanation, no markdown.
2. The formula must be syntactically valid DAX.
3. Use proper column references: 'TableName'[ColumnName].
4. Preserve the original semantics of the Qlik formula as closely as possible.
5. If the approximation is already correct, return it unchanged.
6. Use modern DAX functions (COALESCE, SELECTEDVALUE, WINDOW, OFFSET) when appropriate.
"""

_USER_PROMPT_TEMPLATE = """Qlik formula:
{Qlik_formula}

Current approximated DAX:
{current_dax}

Migration note (explains the approximation):
{migration_note}

Available tables and columns:
{schema_context}

Return ONLY the corrected DAX formula."""

# ════════════════════════════════════════════════════════════════════
#  TOKEN ESTIMATION
# ════════════════════════════════════════════════════════════════════

def estimate_tokens(text):
    """Rough token count estimation (~4 chars per token for English text)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


# ════════════════════════════════════════════════════════════════════
#  LLM CLIENT
# ════════════════════════════════════════════════════════════════════

class LLMClient:
    """Stateless LLM client using stdlib urllib. No external dependencies."""

    def __init__(self, provider='openai', api_key=None, model=None,
                 endpoint=None, max_calls=100, timeout=30,
                 max_retries=3, dry_run=False):
        """Initialize LLM client.

        Args:
            provider: 'openai', 'anthropic', or 'azure_openai'
            api_key: API key (or set LLM_API_KEY env var)
            model: Model name override
            endpoint: Custom API endpoint (required for azure_openai)
            max_calls: Maximum API calls allowed
            timeout: Request timeout in seconds
            max_retries: Number of retries on rate-limit (429)
            dry_run: If True, build prompts but don't call API
        """
        if provider not in _PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Use: {list(_PROVIDERS)}")

        self.provider = provider
        self.api_key = api_key or os.environ.get('LLM_API_KEY', '')
        self.model = model or _PROVIDERS[provider]['default_model']
        self.endpoint = endpoint
        self.max_calls = max_calls
        self.timeout = timeout
        self.max_retries = max_retries
        self.dry_run = dry_run

        # Stats tracking
        self._call_count = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._results = []

        if provider == 'azure_openai' and not endpoint:
            raise ValueError("endpoint is required for azure_openai provider")

    @property
    def calls_remaining(self):
        return max(0, self.max_calls - self._call_count)

    @property
    def total_cost(self):
        """Estimated total cost in USD."""
        cfg = _PROVIDERS[self.provider]
        input_cost = (self._total_input_tokens / 1000) * cfg['cost_per_1k_input']
        output_cost = (self._total_output_tokens / 1000) * cfg['cost_per_1k_output']
        return round(input_cost + output_cost, 6)

    def _build_url(self):
        if self.provider == 'azure_openai':
            return f"{self.endpoint.rstrip('/')}/openai/deployments/{self.model}/chat/completions?api-version=2024-02-01"
        return _PROVIDERS[self.provider]['url']

    def _build_headers(self):
        cfg = _PROVIDERS[self.provider]
        headers = {'Content-Type': 'application/json'}
        headers[cfg['auth_header']] = f"{cfg['auth_prefix']}{self.api_key}"
        if self.provider == 'anthropic':
            headers['anthropic-version'] = '2023-06-01'
        return headers

    def _build_body(self, system, user_message):
        if self.provider == 'anthropic':
            return json.dumps({
                'model': self.model,
                'max_tokens': 1024,
                'system': system,
                'messages': [{'role': 'user', 'content': user_message}],
            })
        # OpenAI / Azure OpenAI format
        return json.dumps({
            'model': self.model,
            'max_tokens': 1024,
            'temperature': 0.1,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user_message},
            ],
        })

    def _parse_response(self, data):
        """Extract text content from provider response."""
        if self.provider == 'anthropic':
            content = data.get('content', [])
            return content[0]['text'] if content else ''
        # OpenAI / Azure
        choices = data.get('choices', [])
        if choices:
            return choices[0].get('message', {}).get('content', '')
        return ''

    def _parse_usage(self, data):
        """Extract token usage from response."""
        usage = data.get('usage', {})
        if self.provider == 'anthropic':
            return usage.get('input_tokens', 0), usage.get('output_tokens', 0)
        return usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)

    def call(self, system, user_message):
        """Send a request to the LLM API.

        Args:
            system: System prompt
            user_message: User prompt

        Returns:
            dict: {text, input_tokens, output_tokens, cost, cached}
        """
        if self._call_count >= self.max_calls:
            logger.warning("LLM call limit reached (%d)", self.max_calls)
            return {'text': '', 'input_tokens': 0, 'output_tokens': 0,
                    'cost': 0, 'cached': False, 'error': 'call_limit_reached'}

        # Dry-run mode — return prompt without calling API
        if self.dry_run:
            est_in = estimate_tokens(system + user_message)
            self._call_count += 1
            return {
                'text': f'[DRY RUN] Would send {est_in} estimated tokens',
                'input_tokens': est_in,
                'output_tokens': 0,
                'cost': 0,
                'cached': False,
                'dry_run': True,
            }

        url = self._build_url()
        headers = self._build_headers()
        body = self._build_body(system, user_message).encode('utf-8')

        for attempt in range(self.max_retries + 1):
            try:
                req = Request(url, data=body, headers=headers, method='POST')
                with urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode('utf-8'))

                text = self._parse_response(data)
                in_tok, out_tok = self._parse_usage(data)
                self._call_count += 1
                self._total_input_tokens += in_tok
                self._total_output_tokens += out_tok

                cfg = _PROVIDERS[self.provider]
                cost = round(
                    (in_tok / 1000) * cfg['cost_per_1k_input'] +
                    (out_tok / 1000) * cfg['cost_per_1k_output'], 6
                )

                return {
                    'text': text.strip(),
                    'input_tokens': in_tok,
                    'output_tokens': out_tok,
                    'cost': cost,
                    'cached': False,
                }

            except HTTPError as e:
                if e.code == 429 and attempt < self.max_retries:
                    retry_after = int(e.headers.get('Retry-After', 2 ** attempt))
                    logger.warning("Rate limited (429), retrying in %ds", retry_after)
                    time.sleep(retry_after)
                    continue
                logger.error("LLM API error: %d %s", e.code, e.reason)
                return {'text': '', 'input_tokens': 0, 'output_tokens': 0,
                        'cost': 0, 'cached': False, 'error': f'http_{e.code}'}

            except (URLError, OSError) as e:
                logger.error("LLM connection error: %s", e)
                return {'text': '', 'input_tokens': 0, 'output_tokens': 0,
                        'cost': 0, 'cached': False, 'error': str(e)}

        return {'text': '', 'input_tokens': 0, 'output_tokens': 0,
                'cost': 0, 'cached': False, 'error': 'max_retries_exceeded'}


# ════════════════════════════════════════════════════════════════════
#  DAX REFINEMENT PIPELINE
# ════════════════════════════════════════════════════════════════════

def _build_schema_context(tables):
    """Build a compact schema description for the LLM prompt.

    Args:
        tables: list of table dicts with 'name' and 'columns' keys

    Returns:
        str: formatted schema context
    """
    lines = []
    for t in (tables or []):
        name = t.get('name', 'Unknown')
        cols = t.get('columns', [])
        col_strs = []
        for c in cols[:30]:  # Limit per table to control token usage
            cname = c.get('name', c) if isinstance(c, dict) else str(c)
            ctype = c.get('dataType', '') if isinstance(c, dict) else ''
            col_strs.append(f"  [{cname}] {ctype}".strip())
        lines.append(f"'{name}':\n" + "\n".join(col_strs))
    return "\n\n".join(lines) if lines else "(no schema available)"


def _extract_migration_note(dax_or_measure):
    """Extract MigrationNote from a measure dict or DAX string."""
    if isinstance(dax_or_measure, dict):
        for ann in dax_or_measure.get('annotations', []):
            if isinstance(ann, dict) and ann.get('name') == 'MigrationNote':
                return ann.get('value', '')
        return dax_or_measure.get('migration_note', '')
    # Check for inline comment
    m = re.search(r'/\*\s*MigrationNote:\s*(.+?)\s*\*/', str(dax_or_measure))
    return m.group(1) if m else ''


def refine_approximated_measures(client, measures, tables=None, source_formulas=None):
    """Refine all approximated measures using the LLM.

    Args:
        client: LLMClient instance
        measures: list of measure dicts with keys:
            - name: measure name
            - expression: current DAX expression
            - annotations (optional): list including MigrationNote
        tables: list of table dicts for schema context
        source_formulas: dict mapping measure_name → original Qlik formula

    Returns:
        list of result dicts:
            - name: measure name
            - original_dax: before refinement
            - refined_dax: after refinement (or original if unchanged)
            - confidence: float 0–1
            - tokens: {input, output}
            - cost: float
            - status: 'refined' | 'unchanged' | 'skipped' | 'error'
    """
    source_formulas = source_formulas or {}
    schema_ctx = _build_schema_context(tables)
    results = []

    for m in measures:
        name = m.get('name', '')
        expression = m.get('expression', '')
        note = _extract_migration_note(m)

        # Only target approximated measures
        if 'approximat' not in note.lower() and 'approx' not in note.lower():
            results.append({
                'name': name, 'original_dax': expression,
                'refined_dax': expression, 'confidence': 1.0,
                'tokens': {'input': 0, 'output': 0}, 'cost': 0,
                'status': 'skipped',
            })
            continue

        if client.calls_remaining <= 0:
            results.append({
                'name': name, 'original_dax': expression,
                'refined_dax': expression, 'confidence': 0,
                'tokens': {'input': 0, 'output': 0}, 'cost': 0,
                'status': 'error', 'error': 'call_limit_reached',
            })
            continue

        Qlik_formula = source_formulas.get(name, '(not available)')
        user_prompt = _USER_PROMPT_TEMPLATE.format(
            Qlik_formula=Qlik_formula,
            current_dax=expression,
            migration_note=note,
            schema_context=schema_ctx,
        )

        resp = client.call(_SYSTEM_PROMPT, user_prompt)

        if resp.get('error'):
            results.append({
                'name': name, 'original_dax': expression,
                'refined_dax': expression, 'confidence': 0,
                'tokens': {'input': resp['input_tokens'], 'output': resp['output_tokens']},
                'cost': resp['cost'], 'status': 'error', 'error': resp['error'],
            })
            continue

        refined = resp['text'].strip()
        # Strip markdown code fences if present
        if refined.startswith('```'):
            refined = re.sub(r'^```(?:dax)?\s*\n?', '', refined)
            refined = re.sub(r'\n?```\s*$', '', refined)
        refined = refined.strip()

        # Confidence: high if formula changed, low if API returned empty
        if not refined:
            confidence = 0.0
            refined = expression
            status = 'error'
        elif refined == expression:
            confidence = 1.0
            status = 'unchanged'
        else:
            confidence = 0.85
            status = 'refined'

        results.append({
            'name': name,
            'original_dax': expression,
            'refined_dax': refined,
            'confidence': confidence,
            'tokens': {'input': resp['input_tokens'], 'output': resp['output_tokens']},
            'cost': resp['cost'],
            'status': status,
        })
        logger.info("LLM refined '%s': %s (confidence=%.2f)", name, status, confidence)

    return results


# ════════════════════════════════════════════════════════════════════
#  COST / REPORT
# ════════════════════════════════════════════════════════════════════

def generate_llm_report(client, results, output_dir=None):
    """Generate a JSON report of LLM refinement results.

    Args:
        client: LLMClient instance (for aggregate stats)
        results: list of result dicts from refine_approximated_measures
        output_dir: optional directory to write report JSON

    Returns:
        dict: summary report
    """
    refined_count = sum(1 for r in results if r['status'] == 'refined')
    skipped_count = sum(1 for r in results if r['status'] == 'skipped')
    error_count = sum(1 for r in results if r['status'] == 'error')

    report = {
        'timestamp': datetime.now().isoformat(),
        'provider': client.provider,
        'model': client.model,
        'dry_run': client.dry_run,
        'summary': {
            'total_measures': len(results),
            'refined': refined_count,
            'unchanged': sum(1 for r in results if r['status'] == 'unchanged'),
            'skipped': skipped_count,
            'errors': error_count,
            'total_input_tokens': client._total_input_tokens,
            'total_output_tokens': client._total_output_tokens,
            'total_cost_usd': client.total_cost,
            'api_calls': client._call_count,
        },
        'measures': results,
    }

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, 'llm_refinement_report.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("LLM report saved to %s", path)

    return report
