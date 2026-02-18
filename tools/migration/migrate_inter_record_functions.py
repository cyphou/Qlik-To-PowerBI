"""Migration - Inter-Record Functions (Peek, Previous, RowNo) vers DAX"""
import json; from pathlib import Path
def gen_guide(output_dir: Path) -> str:
    path = output_dir / "INTER_RECORD_FUNCTIONS_MIGRATION_GUIDE.md"
    content = """# 📊 Guide Migration - Inter-Record Functions vers DAX

**Date :** 13 février 2026

## 📋 Mapping Qlik → DAX

| Qlik | DAX Equivalent |
|---|---|
| **Peek()** | LAG() / OFFSET() |
| **Previous()** | LAG() in same sort context |
| **RowNo()** | ROW_NUMBER() in calculated column |
| **Above()** | LAG() with offset |
| **Below()** | LEAD() |

## Peek() → LAG()

### Qlik
```qlik
Sales, Peek(Sales) as PrevSales
```

### Power BI DAX
```dax
PrevSales = VAR CurrentRow = ROW()
RETURN
  CALCULATE(
    SUM(Sales[Amount]),
    ALL(Date),
    FILTER(
      Date,
      ROW_NUMBER() = CurrentRow - 1
    )
  )
```

## RowNo() → ROW_NUMBER()

### Calculated Column
```dax
RowNumber = ROW_NUMBER(
  ALL('Sales'),
  ORDER BY Sales[Date] ASC
)
```

## Previous() → LAG()

```dax
PriorYearSales = 
CALCULATE(
  SUM(Sales[Amount]),
  DATEADD(Dates[Date], -1, YEAR)
)
```

## 🚀 Steps

1. Identify inter-record functions
2. Map to DAX equivalents
3. Create calculated columns/measures
4. Test with data
5. Optimize performance

---

**Effort :** 1-2 semaines | **Complexité :** Élevée (DAX avancé)
"""
    with open(path, 'w') as f: f.write(content)
    return str(path)

def main():
    output_dir = Path("output/inter_record_functions")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ Inter-Record Functions: {gen_guide(output_dir)}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
