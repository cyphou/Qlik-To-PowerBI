"""
Drift Detector for Qlik-to-Power BI Migration

Detects schema changes, formula modifications, and data anomalies.
Used for regression detection and migration integrity validation.
"""

import json
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class DriftType(Enum):
    """Types of detected drift."""
    COLUMN_ADDED = "column_added"
    COLUMN_REMOVED = "column_removed"
    COLUMN_RENAMED = "column_renamed"
    COLUMN_TYPE_CHANGED = "column_type_changed"
    MEASURE_ADDED = "measure_added"
    MEASURE_REMOVED = "measure_removed"
    MEASURE_FORMULA_CHANGED = "measure_formula_changed"
    TABLE_ADDED = "table_added"
    TABLE_REMOVED = "table_removed"
    RELATIONSHIP_CHANGED = "relationship_changed"
    DATA_QUALITY_DEGRADED = "data_quality_degraded"
    PERFORMANCE_DEGRADED = "performance_degraded"


@dataclass
class DriftItem:
    """Single detected drift."""
    drift_type: DriftType
    entity: str  # Table/column/measure name
    severity: str  # "critical", "high", "medium", "low"
    message: str
    before_state: Optional[Dict] = None
    after_state: Optional[Dict] = None
    impact: Optional[str] = None


@dataclass
class DriftReport:
    """Complete drift analysis report."""
    reference_version: str  # Baseline version
    current_version: str  # Current version
    total_drifts: int
    critical_drifts: List[DriftItem] = field(default_factory=list)
    high_drifts: List[DriftItem] = field(default_factory=list)
    medium_drifts: List[DriftItem] = field(default_factory=list)
    low_drifts: List[DriftItem] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "reference_version": self.reference_version,
            "current_version": self.current_version,
            "total_drifts": self.total_drifts,
            "critical_count": len(self.critical_drifts),
            "high_count": len(self.high_drifts),
            "medium_count": len(self.medium_drifts),
            "low_count": len(self.low_drifts),
            "drifts": {
                "critical": [
                    {
                        "type": d.drift_type.value,
                        "entity": d.entity,
                        "message": d.message,
                        "impact": d.impact
                    }
                    for d in self.critical_drifts
                ],
                "high": [
                    {
                        "type": d.drift_type.value,
                        "entity": d.entity,
                        "message": d.message,
                        "impact": d.impact
                    }
                    for d in self.high_drifts
                ],
                "medium": [
                    {
                        "type": d.drift_type.value,
                        "entity": d.entity,
                        "message": d.message
                    }
                    for d in self.medium_drifts
                ],
                "low": [
                    {
                        "type": d.drift_type.value,
                        "entity": d.entity,
                        "message": d.message
                    }
                    for d in self.low_drifts
                ]
            }
        }


class DriftDetector:
    """Detects schema and data drift between baseline and current states."""
    
    # Severity mappings for drift types
    SEVERITY_MAP = {
        DriftType.COLUMN_REMOVED: "critical",
        DriftType.TABLE_REMOVED: "critical",
        DriftType.MEASURE_REMOVED: "high",
        DriftType.MEASURE_FORMULA_CHANGED: "high",
        DriftType.COLUMN_TYPE_CHANGED: "high",
        DriftType.RELATIONSHIP_CHANGED: "high",
        DriftType.COLUMN_ADDED: "low",
        DriftType.MEASURE_ADDED: "low",
        DriftType.TABLE_ADDED: "low",
        DriftType.COLUMN_RENAMED: "medium",
        DriftType.DATA_QUALITY_DEGRADED: "high",
        DriftType.PERFORMANCE_DEGRADED: "medium"
    }
    
    def __init__(self):
        """Initialize drift detector."""
        self.logger = logging.getLogger(__name__)
    
    def detect_schema_drift(
        self,
        baseline_model: Dict,
        current_model: Dict
    ) -> DriftReport:
        """
        Detect schema drift between baseline and current models.
        
        Args:
            baseline_model: Baseline semantic model snapshot
            current_model: Current semantic model snapshot
        
        Returns:
            DriftReport with all detected changes
        """
        report = DriftReport(
            reference_version=baseline_model.get("version", "unknown"),
            current_version=current_model.get("version", "unknown"),
            total_drifts=0
        )
        
        # Compare tables
        self._compare_tables(baseline_model, current_model, report)
        
        # Compare columns
        self._compare_columns(baseline_model, current_model, report)
        
        # Compare measures
        self._compare_measures(baseline_model, current_model, report)
        
        # Compare relationships
        self._compare_relationships(baseline_model, current_model, report)
        
        report.total_drifts = (
            len(report.critical_drifts) + len(report.high_drifts) +
            len(report.medium_drifts) + len(report.low_drifts)
        )
        
        self.logger.info(
            f"Drift detection complete: {report.total_drifts} changes found "
            f"({len(report.critical_drifts)} critical)"
        )
        
        return report
    
    def _compare_tables(
        self,
        baseline: Dict,
        current: Dict,
        report: DriftReport
    ) -> None:
        """Compare table definitions."""
        baseline_tables = {t.get("name"): t for t in baseline.get("tables", [])}
        current_tables = {t.get("name"): t for t in current.get("tables", [])}
        
        # Find removed tables
        for table_name in baseline_tables:
            if table_name not in current_tables:
                drift = DriftItem(
                    drift_type=DriftType.TABLE_REMOVED,
                    entity=table_name,
                    severity=self.SEVERITY_MAP[DriftType.TABLE_REMOVED],
                    message=f"Table '{table_name}' removed",
                    before_state=baseline_tables[table_name],
                    impact="All dependent measures and visuals affected"
                )
                report.critical_drifts.append(drift)
        
        # Find added tables
        for table_name in current_tables:
            if table_name not in baseline_tables:
                drift = DriftItem(
                    drift_type=DriftType.TABLE_ADDED,
                    entity=table_name,
                    severity=self.SEVERITY_MAP[DriftType.TABLE_ADDED],
                    message=f"Table '{table_name}' added",
                    after_state=current_tables[table_name]
                )
                report.low_drifts.append(drift)
    
    def _compare_columns(
        self,
        baseline: Dict,
        current: Dict,
        report: DriftReport
    ) -> None:
        """Compare column definitions."""
        baseline_tables = {t.get("name"): t for t in baseline.get("tables", [])}
        current_tables = {t.get("name"): t for t in current.get("tables", [])}
        
        for table_name, baseline_table in baseline_tables.items():
            if table_name not in current_tables:
                continue  # Table removed (already detected)
            
            current_table = current_tables[table_name]
            baseline_cols = {
                c.get("name"): c for c in baseline_table.get("columns", [])
            }
            current_cols = {
                c.get("name"): c for c in current_table.get("columns", [])
            }
            
            # Find removed/renamed/type-changed columns
            for col_name, baseline_col in baseline_cols.items():
                if col_name not in current_cols:
                    # Check if renamed
                    renamed = False
                    for curr_col_name, curr_col in current_cols.items():
                        # Simple heuristic: if same data type and table, likely renamed
                        if (curr_col.get("dataType") == baseline_col.get("dataType") and
                            curr_col_name not in baseline_cols):
                            drift = DriftItem(
                                drift_type=DriftType.COLUMN_RENAMED,
                                entity=f"{table_name}.{col_name}",
                                severity=self.SEVERITY_MAP[DriftType.COLUMN_RENAMED],
                                message=f"Column '{col_name}' likely renamed to '{curr_col_name}'",
                                before_state={"name": col_name, "type": baseline_col.get("dataType")},
                                after_state={"name": curr_col_name, "type": curr_col.get("dataType")},
                                impact="References in measures/visuals may break"
                            )
                            report.medium_drifts.append(drift)
                            renamed = True
                            break
                    
                    if not renamed:
                        drift = DriftItem(
                            drift_type=DriftType.COLUMN_REMOVED,
                            entity=f"{table_name}.{col_name}",
                            severity=self.SEVERITY_MAP[DriftType.COLUMN_REMOVED],
                            message=f"Column '{col_name}' removed from table '{table_name}'",
                            before_state=baseline_col,
                            impact="Measures/visuals using this column will fail"
                        )
                        report.critical_drifts.append(drift)
                
                else:
                    # Check for type changes
                    baseline_type = baseline_col.get("dataType")
                    current_type = current_cols[col_name].get("dataType")
                    
                    if baseline_type != current_type:
                        drift = DriftItem(
                            drift_type=DriftType.COLUMN_TYPE_CHANGED,
                            entity=f"{table_name}.{col_name}",
                            severity=self.SEVERITY_MAP[DriftType.COLUMN_TYPE_CHANGED],
                            message=f"Column type changed from '{baseline_type}' to '{current_type}'",
                            before_state={"type": baseline_type},
                            after_state={"type": current_type},
                            impact="May affect measure calculations or aggregations"
                        )
                        report.high_drifts.append(drift)
            
            # Find added columns
            for col_name in current_cols:
                if col_name not in baseline_cols:
                    drift = DriftItem(
                        drift_type=DriftType.COLUMN_ADDED,
                        entity=f"{table_name}.{col_name}",
                        severity=self.SEVERITY_MAP[DriftType.COLUMN_ADDED],
                        message=f"Column '{col_name}' added to table '{table_name}'",
                        after_state=current_cols[col_name]
                    )
                    report.low_drifts.append(drift)
    
    def _compare_measures(
        self,
        baseline: Dict,
        current: Dict,
        report: DriftReport
    ) -> None:
        """Compare measure definitions."""
        baseline_tables = {t.get("name"): t for t in baseline.get("tables", [])}
        current_tables = {t.get("name"): t for t in current.get("tables", [])}
        
        for table_name, baseline_table in baseline_tables.items():
            if table_name not in current_tables:
                continue
            
            current_table = current_tables[table_name]
            baseline_measures = {
                m.get("name"): m for m in baseline_table.get("measures", [])
            }
            current_measures = {
                m.get("name"): m for m in current_table.get("measures", [])
            }
            
            # Find removed measures
            for msr_name in baseline_measures:
                if msr_name not in current_measures:
                    drift = DriftItem(
                        drift_type=DriftType.MEASURE_REMOVED,
                        entity=f"{table_name}.{msr_name}",
                        severity=self.SEVERITY_MAP[DriftType.MEASURE_REMOVED],
                        message=f"Measure '{msr_name}' removed",
                        before_state=baseline_measures[msr_name],
                        impact="Visuals using this measure will break"
                    )
                    report.high_drifts.append(drift)
            
            # Find changed formulas
            for msr_name in baseline_measures:
                if msr_name in current_measures:
                    baseline_expr = baseline_measures[msr_name].get("expression", "")
                    current_expr = current_measures[msr_name].get("expression", "")
                    
                    if baseline_expr != current_expr:
                        drift = DriftItem(
                            drift_type=DriftType.MEASURE_FORMULA_CHANGED,
                            entity=f"{table_name}.{msr_name}",
                            severity=self.SEVERITY_MAP[DriftType.MEASURE_FORMULA_CHANGED],
                            message=f"Measure formula changed",
                            before_state={"formula": baseline_expr[:100]},
                            after_state={"formula": current_expr[:100]},
                            impact="Results may differ from baseline"
                        )
                        report.high_drifts.append(drift)
            
            # Find added measures
            for msr_name in current_measures:
                if msr_name not in baseline_measures:
                    drift = DriftItem(
                        drift_type=DriftType.MEASURE_ADDED,
                        entity=f"{table_name}.{msr_name}",
                        severity=self.SEVERITY_MAP[DriftType.MEASURE_ADDED],
                        message=f"Measure '{msr_name}' added",
                        after_state=current_measures[msr_name]
                    )
                    report.low_drifts.append(drift)
    
    def _compare_relationships(
        self,
        baseline: Dict,
        current: Dict,
        report: DriftReport
    ) -> None:
        """Compare relationship definitions."""
        baseline_rels = baseline.get("relationships", [])
        current_rels = current.get("relationships", [])
        
        # Create comparable keys
        def rel_key(rel: Dict) -> str:
            from_table = rel.get("from_table", "")
            from_col = rel.get("from_column", "")
            to_table = rel.get("to_table", "")
            to_col = rel.get("to_column", "")
            return f"{from_table}.{from_col}->{to_table}.{to_col}"
        
        baseline_keys = {rel_key(r): r for r in baseline_rels}
        current_keys = {rel_key(r): r for r in current_rels}
        
        # Find removed relationships
        for key in baseline_keys:
            if key not in current_keys:
                drift = DriftItem(
                    drift_type=DriftType.RELATIONSHIP_CHANGED,
                    entity=key,
                    severity=self.SEVERITY_MAP[DriftType.RELATIONSHIP_CHANGED],
                    message=f"Relationship removed: {key}",
                    before_state=baseline_keys[key],
                    impact="Cross-table calculations may break"
                )
                report.high_drifts.append(drift)
        
        # Find added/changed relationships
        for key in current_keys:
            if key not in baseline_keys:
                drift = DriftItem(
                    drift_type=DriftType.RELATIONSHIP_CHANGED,
                    entity=key,
                    severity="medium",
                    message=f"Relationship added: {key}",
                    after_state=current_keys[key]
                )
                report.medium_drifts.append(drift)


# Example usage
if __name__ == "__main__":
    detector = DriftDetector()
    
    baseline = {
        "version": "1.0",
        "tables": [
            {
                "name": "Sales",
                "columns": [
                    {"name": "SalesID", "dataType": "int"},
                    {"name": "Amount", "dataType": "decimal"}
                ],
                "measures": [
                    {"name": "TotalSales", "expression": "SUM(Sales[Amount])"}
                ]
            }
        ],
        "relationships": [
            {
                "from_table": "Sales",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID"
            }
        ]
    }
    
    current = {
        "version": "1.1",
        "tables": [
            {
                "name": "Sales",
                "columns": [
                    {"name": "SalesID", "dataType": "int"},
                    {"name": "Amount", "dataType": "currency"}  # Type changed
                ],
                "measures": [
                    {"name": "TotalSales", "expression": "SUM(Sales[Amount]) * 1.1"}  # Formula changed
                ]
            }
        ],
        "relationships": [
            {
                "from_table": "Sales",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID"
            }
        ]
    }
    
    report = detector.detect_schema_drift(baseline, current)
    print(json.dumps(report.to_dict(), indent=2))
