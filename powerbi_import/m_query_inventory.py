"""
Power Query M Script Inventory Tool for Qlik-to-Power BI Migration

Analyzes and catalogs Power Query M scripts in generated Power BI projects.
Identifies deduplication opportunities and code quality metrics.
"""

import json
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path


@dataclass
class MQuery:
    """Metadata for a Power Query M script."""
    query_id: str  # Unique identifier
    query_name: str
    content: str  # Full M script
    source_type: str  # "sql", "csv", "excel", "json", "web", etc.
    line_count: int
    complexity_score: int  # 1-10 based on transforms
    uses_filters: bool
    uses_groupby: bool
    uses_pivot: bool
    uses_custom_column: bool
    sha256_hash: str  # For deduplication
    used_by: List[str] = field(default_factory=list)  # List of table names
    error_count: int = 0
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "query_id": self.query_id,
            "query_name": self.query_name,
            "source_type": self.source_type,
            "line_count": self.line_count,
            "complexity_score": self.complexity_score,
            "uses_filters": self.uses_filters,
            "uses_groupby": self.uses_groupby,
            "uses_pivot": self.uses_pivot,
            "uses_custom_column": self.uses_custom_column,
            "sha256_hash": self.sha256_hash,
            "used_by": self.used_by,
            "error_count": self.error_count,
            "warnings": self.warnings
        }


@dataclass
class MQueryInventory:
    """Complete Power Query inventory for a Power BI project."""
    project_path: str
    total_queries: int
    total_lines: int
    queries: List[MQuery] = field(default_factory=list)
    duplicate_queries: List[Dict] = field(default_factory=list)  # Groups of identical queries
    similar_queries: List[Dict] = field(default_factory=list)  # Similar (>80% match) queries
    
    def to_dict(self) -> Dict:
        return {
            "project_path": self.project_path,
            "total_queries": self.total_queries,
            "total_lines": self.total_lines,
            "queries": [q.to_dict() for q in self.queries],
            "duplicate_queries": self.duplicate_queries,
            "similar_queries": self.similar_queries
        }


class MQueryInventoryBuilder:
    """Analyzes Power Query M scripts in PBIP projects."""
    
    # Keywords indicating transformation complexity
    TRANSFORM_KEYWORDS = {
        "filter": 1,
        "where": 1,
        "groupby": 2,
        "pivot": 3,
        "join": 2,
        "merge": 2,
        "append": 1,
        "union": 1,
        "sort": 1,
        "removecols": 1,
        "selectcols": 1,
        "addcol": 1,
        "replacecol": 1,
        "if then": 2,
        "let": 1,
        "in": 1,
        "error": -2,  # Reduces score (suspicious)
    }
    
    def __init__(self):
        """Initialize M query inventory builder."""
        self.logger = logging.getLogger(__name__)
    
    def build_inventory(self, pbip_project_path: str) -> MQueryInventory:
        """
        Analyze Power Query M scripts in PBIP project.
        
        Args:
            pbip_project_path: Path to .pbip project folder
        
        Returns:
            MQueryInventory with all M scripts
        """
        pbip_path = Path(pbip_project_path)
        if not pbip_path.exists():
            raise FileNotFoundError(f"PBIP project not found: {pbip_path}")
        
        queries: List[MQuery] = []
        query_hashes: Dict[str, List[str]] = {}  # hash -> [query_ids]
        
        # Look for M scripts in the project
        # Typical location: project/.queries/ or within model.tmdl
        m_script_paths = list(pbip_path.glob("**/*.m")) + list(pbip_path.glob("**/*.mql"))
        
        for m_path in m_script_paths:
            try:
                with open(m_path, 'r', encoding='utf-8', errors='ignore') as f:
                    m_content = f.read()
                
                query = self._create_m_query(m_content, m_path.name)
                queries.append(query)
                
                # Track for deduplication
                if query.sha256_hash not in query_hashes:
                    query_hashes[query.sha256_hash] = []
                query_hashes[query.sha256_hash].append(query.query_id)
            
            except Exception as e:
                self.logger.error(f"Error processing {m_path}: {e}")
        
        # Also extract M queries from model.tmdl if present
        model_tmdl_path = pbip_path / "model" / "model.tmdl"
        if model_tmdl_path.exists():
            queries.extend(self._extract_m_from_tmdl(model_tmdl_path))
        
        total_lines = sum(q.line_count for q in queries)
        
        # Identify duplicates and similarities
        duplicates = self._identify_duplicates(query_hashes, queries)
        similar = self._identify_similar_queries(queries)
        
        inventory = MQueryInventory(
            project_path=str(pbip_path),
            total_queries=len(queries),
            total_lines=total_lines,
            queries=queries,
            duplicate_queries=duplicates,
            similar_queries=similar
        )
        
        self.logger.info(
            f"Inventory for {pbip_path.name}: {len(queries)} queries, "
            f"{total_lines} total lines, {len(duplicates)} duplicate groups"
        )
        
        return inventory
    
    def _create_m_query(self, m_content: str, query_name: str) -> MQuery:
        """Create MQuery from M script content."""
        lines = m_content.split('\n')
        line_count = len(lines)
        
        # Determine source type
        source_type = self._detect_source_type(m_content)
        
        # Calculate complexity score
        complexity = self._calculate_complexity(m_content)
        
        # Detect features
        uses_filters = "filter" in m_content.lower() or "where" in m_content.lower()
        uses_groupby = "groupby" in m_content.lower()
        uses_pivot = "pivot" in m_content.lower()
        uses_custom_column = "addcolumn" in m_content.lower() or "addcol" in m_content.lower()
        
        # Calculate hash for deduplication
        m_hash = hashlib.sha256(m_content.encode()).hexdigest()
        
        query = MQuery(
            query_id=m_hash[:16],
            query_name=query_name,
            content=m_content,
            source_type=source_type,
            line_count=line_count,
            complexity_score=complexity,
            uses_filters=uses_filters,
            uses_groupby=uses_groupby,
            uses_pivot=uses_pivot,
            uses_custom_column=uses_custom_column,
            sha256_hash=m_hash
        )
        
        return query
    
    def _detect_source_type(self, m_content: str) -> str:
        """Detect data source type from M script."""
        content_lower = m_content.lower()
        
        if "sql.database" in content_lower:
            return "sql_server"
        elif "ole db" in content_lower:
            return "oledb"
        elif "odbc" in content_lower:
            return "odbc"
        elif "csv" in content_lower or "text" in content_lower:
            return "csv"
        elif "excel" in content_lower:
            return "excel"
        elif "json" in content_lower:
            return "json"
        elif "xml" in content_lower:
            return "xml"
        elif "sharepoint" in content_lower:
            return "sharepoint"
        elif "http" in content_lower or "web" in content_lower:
            return "web"
        elif "cosmos" in content_lower:
            return "cosmos_db"
        elif "snowflake" in content_lower:
            return "snowflake"
        elif "bigquery" in content_lower:
            return "bigquery"
        else:
            return "unknown"
    
    def _calculate_complexity(self, m_content: str) -> int:
        """Calculate query complexity score (1-10)."""
        score = 1  # Base score
        content_lower = m_content.lower()
        
        # Count transform keywords
        for keyword, weight in self.TRANSFORM_KEYWORDS.items():
            count = content_lower.count(keyword)
            score += count * weight
        
        # Cap at 10
        score = min(10, score)
        score = max(1, score)
        
        return score
    
    def _extract_m_from_tmdl(self, tmdl_path: Path) -> List[MQuery]:
        """Extract M queries from model.tmdl file."""
        queries = []
        
        try:
            with open(tmdl_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for expression { ... } blocks (M expressions in TMDL)
            # This is a simplified extraction
            import re
            m_blocks = re.findall(r'expression\s*=\s*\{([^}]+)\}', content, re.MULTILINE)
            
            for i, m_block in enumerate(m_blocks):
                query = self._create_m_query(m_block, f"tmdl_expression_{i+1}")
                queries.append(query)
        
        except Exception as e:
            self.logger.debug(f"Could not extract M from TMDL: {e}")
        
        return queries
    
    def _identify_duplicates(
        self,
        query_hashes: Dict[str, List[str]],
        queries: List[MQuery]
    ) -> List[Dict]:
        """Identify completely duplicate queries."""
        duplicates = []
        queries_by_id = {q.query_id: q for q in queries}
        
        for hash_val, query_ids in query_hashes.items():
            if len(query_ids) > 1:
                dup_group = {
                    "hash": hash_val,
                    "count": len(query_ids),
                    "query_ids": query_ids,
                    "query_names": [queries_by_id[qid].query_name for qid in query_ids],
                    "source_types": list(set(queries_by_id[qid].source_type for qid in query_ids))
                }
                duplicates.append(dup_group)
                self.logger.info(
                    f"Found {len(query_ids)} identical queries: "
                    f"{dup_group['query_names']}"
                )
        
        return duplicates
    
    def _identify_similar_queries(self, queries: List[MQuery]) -> List[Dict]:
        """Identify similar queries (>80% content match)."""
        similar = []
        
        # Simplified similarity check: same source type + similar length
        for i, q1 in enumerate(queries):
            for q2 in queries[i+1:]:
                if q1.source_type == q2.source_type:
                    # Calculate similarity based on length ratio
                    min_len = min(len(q1.content), len(q2.content))
                    max_len = max(len(q1.content), len(q2.content))
                    
                    if min_len > 0 and max_len / min_len < 1.3:  # Within 30% size
                        similarity_pct = (min_len / max_len) * 100
                        
                        if similarity_pct > 80:
                            similar.append({
                                "query_ids": [q1.query_id, q2.query_id],
                                "query_names": [q1.query_name, q2.query_name],
                                "similarity": round(similarity_pct, 1),
                                "source_type": q1.source_type,
                                "dedup_suggestion": f"Consider merging {q1.query_name} and {q2.query_name}"
                            })
        
        return similar


class MQueryReporter:
    """Generates reports from M query inventories."""
    
    def __init__(self):
        """Initialize reporter."""
        self.logger = logging.getLogger(__name__)
    
    def generate_summary(self, inventories: List[MQueryInventory]) -> Dict:
        """Generate portfolio-level summary."""
        total_queries = sum(inv.total_queries for inv in inventories)
        total_lines = sum(inv.total_lines for inv in inventories)
        total_duplicates = sum(len(inv.duplicate_queries) for inv in inventories)
        total_similar = sum(len(inv.similar_queries) for inv in inventories)
        
        # Count by source type
        source_types = {}
        for inv in inventories:
            for query in inv.queries:
                source_types[query.source_type] = source_types.get(query.source_type, 0) + 1
        
        # Average complexity
        all_queries = [q for inv in inventories for q in inv.queries]
        avg_complexity = (
            sum(q.complexity_score for q in all_queries) / len(all_queries)
            if all_queries else 0
        )
        
        return {
            "total_projects": len(inventories),
            "total_queries": total_queries,
            "total_lines": total_lines,
            "duplicate_query_groups": total_duplicates,
            "similar_query_pairs": total_similar,
            "average_complexity_score": round(avg_complexity, 1),
            "query_types": source_types
        }
    
    def save_inventory(self, inventory: MQueryInventory, output_path: str) -> None:
        """Save inventory to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(inventory.to_dict(), f, indent=2)
        
        self.logger.info(f"Saved inventory to {output_path}")


# Example usage
if __name__ == "__main__":
    builder = MQueryInventoryBuilder()
    
    # Build inventory for PBIP project
    inventory = builder.build_inventory("output/sample_sales_pbip")
    
    # Save inventory
    reporter = MQueryReporter()
    reporter.save_inventory(
        inventory,
        "output/sample_sales_m_query_inventory.json"
    )
    
    print(json.dumps(inventory.to_dict(), indent=2))
