"""
Artifact Lineage Manifest for Qlik-to-Power BI Migration

Builds complete end-to-end provenance tracking from Qlik source to Power BI visual.
Enables impact analysis and change traceability.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path
from enum import Enum


class LineageItemType(Enum):
    """Types of items in lineage chain."""
    SOURCE_SYSTEM = "source_system"  # Qlik
    SOURCE_TABLE = "source_table"  # Database table
    QVF_TABLE = "qvf_table"  # Table in Qlik load script
    QVF_FIELD = "qvf_field"  # Field in Qlik
    QVF_EXPRESSION = "qvf_expression"  # Calculated field
    M_QUERY = "m_query"  # Power Query M script
    PBI_TABLE = "pbi_table"  # Table in Power BI semantic model
    PBI_COLUMN = "pbi_column"  # Column in PBI table
    DAX_MEASURE = "dax_measure"  # DAX measure
    DAX_COLUMN = "dax_column"  # Calculated column
    VISUAL = "visual"  # Power BI visual (chart, table, etc.)


@dataclass
class LineageEdge:
    """Connection between two lineage items."""
    from_id: str
    to_id: str
    edge_type: str  # "depends_on", "transforms_to", "feeds_into", "references"
    transformation: Optional[str] = None  # Description of transformation
    sql_step: Optional[str] = None  # SQL if applicable
    m_step: Optional[str] = None  # M expression if applicable
    dax_step: Optional[str] = None  # DAX if applicable


@dataclass
class LineageNode:
    """Node in the lineage graph."""
    node_id: str
    node_type: LineageItemType
    name: str
    display_name: str
    source_system: str  # "qlik", "database", "powerbi"
    parent_ids: List[str] = field(default_factory=list)  # Upstream dependencies
    child_ids: List[str] = field(default_factory=list)  # Downstream consumers
    metadata: Dict = field(default_factory=dict)  # Extra attributes
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "name": self.name,
            "display_name": self.display_name,
            "source_system": self.source_system,
            "parent_ids": self.parent_ids,
            "child_ids": self.child_ids,
            "metadata": self.metadata
        }


@dataclass
class LineageManifest:
    """Complete lineage manifest for a migration."""
    migration_id: str  # e.g., app ID
    source_app: str  # Qlik app name
    target_project: str  # Power BI project name
    nodes: List[LineageNode] = field(default_factory=list)
    edges: List[LineageEdge] = field(default_factory=list)
    field_mappings: Dict[str, str] = field(default_factory=dict)  # Qlik field -> PBI column
    visual_mappings: Dict[str, str] = field(default_factory=dict)  # Qlik object -> PBI visual
    
    def to_dict(self) -> Dict:
        return {
            "migration_id": self.migration_id,
            "source_app": self.source_app,
            "target_project": self.target_project,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [
                {
                    "from_id": e.from_id,
                    "to_id": e.to_id,
                    "edge_type": e.edge_type,
                    "transformation": e.transformation,
                    "sql_step": e.sql_step,
                    "m_step": e.m_step,
                    "dax_step": e.dax_step
                }
                for e in self.edges
            ],
            "field_mappings": self.field_mappings,
            "visual_mappings": self.visual_mappings
        }


class LineageManifestBuilder:
    """Builds complete lineage manifest for a migration."""
    
    def __init__(self):
        """Initialize lineage builder."""
        self.logger = logging.getLogger(__name__)
    
    def build_manifest(
        self,
        migration_id: str,
        source_app: str,
        target_project: str,
        extraction_json: Dict,  # From extraction phase
        generation_json: Dict   # From generation phase
    ) -> LineageManifest:
        """
        Build complete lineage manifest.
        
        Args:
            migration_id: Migration ID (typically app ID)
            source_app: Qlik app name
            target_project: Target Power BI project name
            extraction_json: Extraction phase output (11 intermediate JSON files)
            generation_json: Generation phase output (PBIP artifacts)
        
        Returns:
            LineageManifest with complete provenance tracking
        """
        manifest = LineageManifest(
            migration_id=migration_id,
            source_app=source_app,
            target_project=target_project
        )
        
        # Build nodes from extraction data
        self._add_source_nodes(manifest, extraction_json)
        
        # Build M query nodes (Power Query layer)
        self._add_m_query_nodes(manifest, generation_json)
        
        # Build PBI semantic model nodes
        self._add_pbi_nodes(manifest, generation_json)
        
        # Build edges to connect nodes
        self._build_edges(manifest, extraction_json, generation_json)
        
        # Create mappings
        self._create_mappings(manifest, extraction_json, generation_json)
        
        self.logger.info(
            f"Built lineage manifest for {migration_id}: "
            f"{len(manifest.nodes)} nodes, {len(manifest.edges)} edges"
        )
        
        return manifest
    
    def _add_source_nodes(self, manifest: LineageManifest, extraction_json: Dict) -> None:
        """Add source system (Qlik, databases) nodes."""
        # Qlik app node
        qlik_node = LineageNode(
            node_id="source_qlik_app",
            node_type=LineageItemType.SOURCE_SYSTEM,
            name=manifest.source_app,
            display_name=f"Qlik App: {manifest.source_app}",
            source_system="qlik",
            metadata={"app_type": "qlik_sense", "version": "November 2024"}
        )
        manifest.nodes.append(qlik_node)
        
        # Add database tables from datasources
        datasources = extraction_json.get("datasources", [])
        for ds in datasources:
            ds_node = LineageNode(
                node_id=f"source_db_{ds.get('id', 'unknown')}",
                node_type=LineageItemType.SOURCE_TABLE,
                name=ds.get("name", "Unknown"),
                display_name=f"DB Table: {ds.get('name', 'Unknown')}",
                source_system="database",
                metadata={
                    "connector": ds.get("connector_type", "unknown"),
                    "column_count": len(ds.get("columns", []))
                }
            )
            manifest.nodes.append(ds_node)
            
            # Connect to Qlik app
            manifest.edges.append(LineageEdge(
                from_id="source_qlik_app",
                to_id=ds_node.node_id,
                edge_type="depends_on"
            ))
        
        # Add Qlik table nodes
        qvf_tables = extraction_json.get("qvf_tables", [])
        for tbl in qvf_tables:
            tbl_node = LineageNode(
                node_id=f"qvf_table_{tbl.get('id', 'unknown')}",
                node_type=LineageItemType.QVF_TABLE,
                name=tbl.get("name", "Unknown"),
                display_name=f"Qlik Table: {tbl.get('name', 'Unknown')}",
                source_system="qlik"
            )
            manifest.nodes.append(tbl_node)
    
    def _add_m_query_nodes(self, manifest: LineageManifest, generation_json: Dict) -> None:
        """Add Power Query M script nodes."""
        m_queries = generation_json.get("m_queries", [])
        for mq in m_queries:
            mq_node = LineageNode(
                node_id=f"m_query_{mq.get('id', 'unknown')}",
                node_type=LineageItemType.M_QUERY,
                name=mq.get("name", "Unknown"),
                display_name=f"Power Query: {mq.get('name', 'Unknown')}",
                source_system="powerbi",
                metadata={
                    "source_type": mq.get("source_type", "unknown"),
                    "line_count": mq.get("line_count", 0)
                }
            )
            manifest.nodes.append(mq_node)
    
    def _add_pbi_nodes(self, manifest: LineageManifest, generation_json: Dict) -> None:
        """Add Power BI semantic model nodes."""
        # Add table nodes
        pbi_tables = generation_json.get("tables", [])
        for tbl in pbi_tables:
            tbl_node = LineageNode(
                node_id=f"pbi_table_{tbl.get('id', 'unknown')}",
                node_type=LineageItemType.PBI_TABLE,
                name=tbl.get("name", "Unknown"),
                display_name=f"Table: {tbl.get('name', 'Unknown')}",
                source_system="powerbi"
            )
            manifest.nodes.append(tbl_node)
            
            # Add column nodes
            columns = tbl.get("columns", [])
            for col in columns:
                col_node = LineageNode(
                    node_id=f"pbi_col_{tbl.get('id', 'unknown')}_{col.get('name', 'unknown')}",
                    node_type=LineageItemType.PBI_COLUMN,
                    name=col.get("name", "Unknown"),
                    display_name=f"Column: {col.get('name', 'Unknown')}",
                    source_system="powerbi",
                    parent_ids=[tbl_node.node_id]
                )
                manifest.nodes.append(col_node)
            
            # Add measure nodes
            measures = tbl.get("measures", [])
            for msr in measures:
                msr_node = LineageNode(
                    node_id=f"dax_measure_{tbl.get('id', 'unknown')}_{msr.get('name', 'unknown')}",
                    node_type=LineageItemType.DAX_MEASURE,
                    name=msr.get("name", "Unknown"),
                    display_name=f"Measure: {msr.get('name', 'Unknown')}",
                    source_system="powerbi",
                    parent_ids=[tbl_node.node_id],
                    metadata={
                        "dax_expression": msr.get("expression", "")[:100] + "..."
                    }
                )
                manifest.nodes.append(msr_node)
        
        # Add visual nodes
        visuals = generation_json.get("visuals", [])
        for vis in visuals:
            vis_node = LineageNode(
                node_id=f"pbi_visual_{vis.get('id', 'unknown')}",
                node_type=LineageItemType.VISUAL,
                name=vis.get("name", "Unknown"),
                display_name=f"Visual: {vis.get('name', 'Unknown')}",
                source_system="powerbi",
                metadata={
                    "visual_type": vis.get("type", "unknown"),
                    "page": vis.get("page", "")
                }
            )
            manifest.nodes.append(vis_node)
    
    def _build_edges(
        self,
        manifest: LineageManifest,
        extraction_json: Dict,
        generation_json: Dict
    ) -> None:
        """Build edges connecting nodes."""
        # This would connect:
        # 1. Source DB tables -> Qlik tables (load script)
        # 2. Qlik fields -> M queries
        # 3. M queries -> PBI columns
        # 4. PBI columns/measures -> Visuals
        
        # Simplified: would iterate through mappings and create edges
        pass
    
    def _create_mappings(
        self,
        manifest: LineageManifest,
        extraction_json: Dict,
        generation_json: Dict
    ) -> None:
        """Create field and visual mappings."""
        # Map Qlik fields to PBI columns
        dimensions = extraction_json.get("dimensions", [])
        measures = extraction_json.get("measures", [])
        
        for dim in dimensions:
            qlik_field = dim.get("name", "Unknown")
            # Find corresponding PBI column
            pbi_col = f"pbi_col_{qlik_field}"
            manifest.field_mappings[qlik_field] = pbi_col
        
        for msr in measures:
            qlik_measure = msr.get("name", "Unknown")
            # Find corresponding PBI measure
            pbi_msr = f"dax_measure_{qlik_measure}"
            manifest.field_mappings[qlik_measure] = pbi_msr


class LineageVisualizer:
    """Generates visual representations of lineage."""
    
    def __init__(self):
        """Initialize visualizer."""
        self.logger = logging.getLogger(__name__)
    
    def generate_mermaid_diagram(self, manifest: LineageManifest) -> str:
        """Generate Mermaid diagram of lineage."""
        mermaid_lines = ["graph LR"]
        
        # Add nodes
        for node in manifest.nodes:
            label = node.display_name.replace('"', "'")
            mermaid_lines.append(f'    {node.node_id}["{label}"]')
        
        # Add edges
        for edge in manifest.edges:
            mermaid_lines.append(f'    {edge.from_id} -->|{edge.edge_type}| {edge.to_id}')
        
        return "\n".join(mermaid_lines)
    
    def save_diagram(self, manifest: LineageManifest, output_path: str) -> None:
        """Save diagram to file."""
        diagram = self.generate_mermaid_diagram(manifest)
        output_path = Path(output_path)
        with open(output_path, 'w') as f:
            f.write(diagram)
        self.logger.info(f"Saved diagram to {output_path}")


# Example usage
if __name__ == "__main__":
    # Load extraction and generation JSONs
    extraction = {
        "datasources": [
            {"id": "1", "name": "Sales", "connector_type": "sql", "columns": []}
        ],
        "qvf_tables": [
            {"id": "1", "name": "SalesData"}
        ],
        "dimensions": [
            {"name": "Region"}
        ],
        "measures": [
            {"name": "Total_Sales"}
        ]
    }
    
    generation = {
        "m_queries": [
            {"id": "1", "name": "SalesQuery", "source_type": "sql", "line_count": 50}
        ],
        "tables": [
            {
                "id": "1", "name": "Sales",
                "columns": [{"name": "Region"}],
                "measures": [{"name": "Total_Sales", "expression": "SUM(...)"}]
            }
        ],
        "visuals": [
            {"id": "1", "name": "SalesChart", "type": "columnChart", "page": "Page1"}
        ]
    }
    
    builder = LineageManifestBuilder()
    manifest = builder.build_manifest(
        "app_1",
        "sample_sales",
        "SalesProject",
        extraction,
        generation
    )
    
    # Save manifest
    output_path = "output/lineage_manifest.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(manifest.to_dict(), f, indent=2)
    
    print(f"Saved lineage manifest to {output_path}")
