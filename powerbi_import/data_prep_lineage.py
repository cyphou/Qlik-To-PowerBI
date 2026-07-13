"""
Data Preparation Lineage - Interactive visualization for data transformation tracking

Tracks the transformation stages of data from extraction through semantic modeling,
generating an interactive Mermaid diagram showing the data flow.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ===== Enums and DataClasses =====

class TransformStage(Enum):
    """Stages in data preparation pipeline"""
    CONNECTION = "CONNECTION"
    SOURCE = "SOURCE"
    INGESTION = "INGESTION"
    M_QUERY = "M_QUERY"
    M_SOURCE = "M_SOURCE"
    M_PROMOTED_HEADERS = "M_PROMOTED_HEADERS"
    M_CHANGED_TYPE = "M_CHANGED_TYPE"
    M_FILTERED_ROWS = "M_FILTERED_ROWS"
    M_REMOVED_COLUMNS = "M_REMOVED_COLUMNS"
    M_RENAMED_COLUMNS = "M_RENAMED_COLUMNS"
    QLIK_LOAD = "QLIK_LOAD"
    QLIK_RESIDENT = "QLIK_RESIDENT"
    QLIK_JOIN = "QLIK_JOIN"
    QLIK_CONCATENATE = "QLIK_CONCATENATE"
    QLIK_STORE = "QLIK_STORE"
    FABRIC_DATAFLOW = "FABRIC_DATAFLOW"
    FABRIC_NOTEBOOK = "FABRIC_NOTEBOOK"
    SEMANTIC_MODEL = "SEMANTIC_MODEL"
    TMDL_TABLE = "TMDL_TABLE"
    POWER_BI_DATASET = "POWER_BI_DATASET"


class DataPrepEdge:
    """A data flow edge between two nodes"""
    def __init__(self, source_id: str, target_id: str):
        self.source_id = source_id
        self.target_id = target_id


@dataclass
class DataPrepNode:
    """A transformation step in the data prep lineage."""
    id: str
    stage: TransformStage
    label: str
    source_table: Optional[str] = None
    target_table: Optional[str] = None
    transformation_type: Optional[str] = None
    columns_affected: List[str] = field(default_factory=list)
    operation_code: Optional[str] = None
    row_count_estimate: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    layer: str = 'unknown'
    purpose: str = 'generic'
    complexity: str = 'simple'
    source_count: int = 1


class DataPrepLineage:
    """Container for data preparation lineage"""
    
    def __init__(self):
        self.nodes: Dict[str, DataPrepNode] = {}
        self.edges: List[DataPrepEdge] = []
    
    def add_node(self, node_id: str, stage: TransformStage, label: str,
                 source_table: Optional[str] = None,
                 target_table: Optional[str] = None,
                 transformation_type: Optional[str] = None,
                 layer: str = 'unknown',
                 purpose: str = 'generic',
                 complexity: str = 'simple') -> DataPrepNode:
        """Add a node to the lineage"""
        node = DataPrepNode(
            id=node_id,
            stage=stage,
            label=label,
            source_table=source_table,
            target_table=target_table,
            transformation_type=transformation_type,
            layer=layer,
            purpose=purpose,
            complexity=complexity
        )
        self.nodes[node_id] = node
        return node
    
    def add_edge(self, source_id: str, target_id: str) -> DataPrepEdge:
        """Add an edge between two nodes"""
        edge = DataPrepEdge(source_id, target_id)
        self.edges.append(edge)
        return edge

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


def _safe_table_name(value: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9_]+', '_', value or '')
    return cleaned.strip('_') or 'Unknown'


def _truncate_label(value: str, max_length: int = 90) -> str:
    value = (value or '').strip()
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + '…'


def _merge_lineage(target: DataPrepLineage, source: DataPrepLineage, prefix: str) -> None:
    for node_id, node in source.nodes.items():
        merged_id = f'{prefix}{node_id}'
        target.nodes[merged_id] = DataPrepNode(
            id=merged_id,
            stage=node.stage,
            label=node.label,
            source_table=node.source_table,
            target_table=node.target_table,
            transformation_type=node.transformation_type,
            columns_affected=list(node.columns_affected),
            operation_code=node.operation_code,
            row_count_estimate=node.row_count_estimate,
            metadata=dict(node.metadata),
            layer=node.layer,
            purpose=node.purpose,
            complexity=node.complexity,
            source_count=node.source_count,
        )
    for edge in source.edges:
        target.edges.append(DataPrepEdge(f'{prefix}{edge.source_id}', f'{prefix}{edge.target_id}'))


def parse_qlik_script_lineage(script_content: str) -> DataPrepLineage:
    """Build a lightweight lineage graph from Qlik load script text."""
    lineage = DataPrepLineage()
    if not script_content:
        return lineage

    node_index = 0
    previous_node_id: Optional[str] = None
    for raw_line in script_content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('//') or line.startswith('/*'):
            continue

        statement = line.upper()
        stage = None
        if statement.startswith('LOAD '):
            stage = TransformStage.QLIK_LOAD
        elif statement.startswith('SQL '):
            stage = TransformStage.M_QUERY
        elif 'RESIDENT' in statement:
            stage = TransformStage.QLIK_RESIDENT
        elif statement.startswith('CONCATENATE'):
            stage = TransformStage.QLIK_CONCATENATE
        elif statement.startswith('STORE '):
            stage = TransformStage.QLIK_STORE
        elif statement.startswith('JOIN '):
            stage = TransformStage.QLIK_JOIN
        elif 'FROM ' in statement or 'WITH ' in statement:
            stage = TransformStage.SOURCE

        if stage is None:
            continue

        node_index += 1
        node_id = f'qlik_{node_index}'
        source_table = None
        target_table = None
        if stage in (TransformStage.QLIK_LOAD, TransformStage.QLIK_RESIDENT, TransformStage.QLIK_JOIN, TransformStage.QLIK_CONCATENATE):
            match = re.search(r'\bFROM\s+([\w\[\]"\.\-]+)', line, re.IGNORECASE)
            if match:
                source_table = _safe_table_name(match.group(1))
        if stage == TransformStage.QLIK_STORE:
            match = re.search(r'\bSTORE\s+([\w\[\]"\.\-]+)', line, re.IGNORECASE)
            if match:
                target_table = _safe_table_name(match.group(1))

        lineage.add_node(
            node_id=node_id,
            stage=stage,
            label=_truncate_label(line),
            source_table=source_table,
            target_table=target_table,
            transformation_type=stage.value,
            layer='qlik',
            purpose='script',
            complexity='simple',
        )
        if previous_node_id:
            lineage.add_edge(previous_node_id, node_id)
        previous_node_id = node_id

    return lineage


def parse_m_query_lineage(m_query_text: str) -> DataPrepLineage:
    """Build a lightweight lineage graph from Power Query M text."""
    lineage = DataPrepLineage()
    if not m_query_text:
        return lineage

    step_pattern = re.compile(r'^(?:#"([^"]+)"|([A-Za-z_][A-Za-z0-9_]*))\s*=\s*(.+)$')
    node_index = 0
    previous_node_id: Optional[str] = None

    for raw_line in m_query_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('//'):
            continue

        match = step_pattern.match(line)
        if not match:
            continue

        step_name = match.group(1) or match.group(2) or f'Step {node_index + 1}'
        expression = match.group(3)
        node_index += 1
        node_id = f'm_{node_index}'

        expression_upper = expression.upper()
        if 'TABLE.SOURCE' in expression_upper or 'SOURCE' in step_name.upper():
            stage = TransformStage.M_SOURCE
        elif 'PROMOTEHEADERS' in expression_upper:
            stage = TransformStage.M_PROMOTED_HEADERS
        elif 'TRANSFORMCOLUMNTYPES' in expression_upper:
            stage = TransformStage.M_CHANGED_TYPE
        elif 'FILTER' in expression_upper:
            stage = TransformStage.M_FILTERED_ROWS
        elif 'REMOVECOLUMNS' in expression_upper:
            stage = TransformStage.M_REMOVED_COLUMNS
        elif 'RENAMECOLUMNS' in expression_upper:
            stage = TransformStage.M_RENAMED_COLUMNS
        else:
            stage = TransformStage.M_QUERY

        lineage.add_node(
            node_id=node_id,
            stage=stage,
            label=_truncate_label(step_name),
            source_table=None,
            target_table=_safe_table_name(step_name),
            transformation_type=stage.value,
            layer='m_query',
            purpose='query',
            complexity='simple',
        )
        if previous_node_id:
            lineage.add_edge(previous_node_id, node_id)
        previous_node_id = node_id

    return lineage


def build_data_prep_lineage(extract_dir: str, pbip_dir: str) -> DataPrepLineage:
    """Build lineage from extracted Qlik scripts and generated Power Query files."""
    lineage = DataPrepLineage()

    loadscript_path = os.path.join(extract_dir, 'loadscript.json')
    if os.path.exists(loadscript_path):
        try:
            import json
            with open(loadscript_path, 'r', encoding='utf-8') as handle:
                loadscript_data = json.load(handle)
            script_content = loadscript_data.get('script', '')
            if script_content:
                _merge_lineage(lineage, parse_qlik_script_lineage(script_content), 'qlik_')
        except Exception as exc:
            logger.warning('Could not load Qlik script lineage from %s: %s', loadscript_path, exc)

    power_query_dir = os.path.join(pbip_dir, 'power_query')
    if os.path.isdir(power_query_dir):
        for filename in sorted(os.listdir(power_query_dir)):
            if not filename.lower().endswith('.pq'):
                continue
            pq_path = os.path.join(power_query_dir, filename)
            try:
                with open(pq_path, 'r', encoding='utf-8') as handle:
                    pq_text = handle.read()
                if pq_text.strip():
                    prefix = f'{os.path.splitext(filename)[0]}_'
                    _merge_lineage(lineage, parse_m_query_lineage(pq_text), prefix)
            except Exception as exc:
                logger.warning('Could not parse Power Query lineage from %s: %s', pq_path, exc)

    return lineage


# ===== HTML Generation =====

def generate_data_prep_lineage_html(lineage: DataPrepLineage,
                                   title: str = 'Data Preparation Lineage',
                                   output_file: Optional[str] = None) -> str:
    """Generate interactive HTML visualization for data prep lineage.
    
    Creates a left-to-right Mermaid diagram showing:
      - Nodes: transformation steps with labels
      - Edges: data flows between steps
      - Stages: color-coded by transformation stage
    
    Args:
        lineage: DataPrepLineage object with nodes and edges
        title: HTML page title
        output_file: Optional path to write HTML file to
    
    Returns:
        Generated HTML string
    """
    
    # ===== STEP 1: Build Mermaid diagram code FIRST (before HTML) =====
    mermaid_lines = ['graph LR']
    node_mermaid_ids = {}
    
    # Add nodes to Mermaid diagram
    for node_id, node in lineage.nodes.items():
        mermaid_id = f'N_{len(node_mermaid_ids)}'
        node_mermaid_ids[node_id] = mermaid_id
        safe_label = node.label.replace('"', '\\"').replace('\n', '<br/>')
        mermaid_lines.append(f'    {mermaid_id}["{safe_label}"]')
    
    # Add edges (two-pass algorithm for smart inference)
    added_edges = set()
    used_nodes = set()
    
    # Pass 1: semantic edges from source_table/target_table
    for node_id, node in lineage.nodes.items():
        if node.target_table:
            for other_id, other_node in lineage.nodes.items():
                if other_node.source_table == node.target_table:
                    source_mermaid_id = node_mermaid_ids.get(node_id)
                    target_mermaid_id = node_mermaid_ids.get(other_id)
                    if source_mermaid_id and target_mermaid_id:
                        edge_key = (source_mermaid_id, target_mermaid_id)
                        if edge_key not in added_edges:
                            mermaid_lines.append(f'    {source_mermaid_id} --> {target_mermaid_id}')
                            added_edges.add(edge_key)
                            used_nodes.add(node_id)
                            used_nodes.add(other_id)
    
    # Pass 2: explicit edges for unused nodes
    for edge in lineage.edges:
        if edge.source_id not in used_nodes and edge.target_id not in used_nodes:
            source_mermaid_id = node_mermaid_ids.get(edge.source_id)
            target_mermaid_id = node_mermaid_ids.get(edge.target_id)
            if source_mermaid_id and target_mermaid_id:
                edge_key = (source_mermaid_id, target_mermaid_id)
                if edge_key not in added_edges:
                    mermaid_lines.append(f'    {source_mermaid_id} --> {target_mermaid_id}')
                    added_edges.add(edge_key)
    
    # Build mermaid code
    mermaid_code = '\n'.join(mermaid_lines)
    
    # ===== STEP 2: Create HTML template with placeholder =====
    html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            margin: 0;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
        }}
        
        .header h1 {{
            font-size: 28px;
            margin-bottom: 5px;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            padding: 20px 30px;
            background: #f5f5f5;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .stat-card {{
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-label {{
            font-size: 12px;
            color: #999;
            text-transform: uppercase;
        }}
        
        .graph-caption {{
            padding: 20px 30px 5px;
            color: #666;
            font-size: 14px;
        }}
        
        .graph-panel {{
            padding: 20px 30px;
            overflow-x: auto;
            background: #fafafa;
        }}
        
        .mermaid {{
            display: flex;
            justify-content: center;
            min-height: 400px;
        }}
        
        .mermaid svg {{
            max-width: 100%;
            height: auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Data Preparation Lineage</h1>
            <p>End-to-end data preparation transformation tracking</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{node_count}</div>
                <div class="stat-label">Transformation Steps</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{edge_count}</div>
                <div class="stat-label">Data Flows</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stage_count}</div>
                <div class="stat-label">Stages</div>
            </div>
        </div>
        
        <div class="graph-caption">Graph view: left-to-right data flow through transformation stages</div>
        <div class="graph-panel">
            <div id="mermaidDiagram" class="mermaid">
{mermaid_code}
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            securityLevel: 'loose',
            logLevel: 'error',
            flowchart: {{
                htmlLabels: true,
                useMaxWidth: false,
                rankSpacing: 200,
                nodeSpacing: 120,
                padding: 40,
                curve: 'basis'
            }}
        }});
    </script>
</body>
</html>
'''
    
    # ===== STEP 3: Substitute placeholders and return =====
    node_count = len(lineage.nodes)
    edge_count = len(lineage.edges)
    stage_count = len(set(n.stage for n in lineage.nodes.values()))
    
    html_content = html_template.format(
        title=title,
        node_count=node_count,
        edge_count=edge_count,
        stage_count=stage_count,
        mermaid_code=mermaid_code
    )
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f'Data prep lineage HTML generated: {output_file}')
    
    return html_content
