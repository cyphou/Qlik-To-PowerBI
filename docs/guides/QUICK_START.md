# Quick Start — Qlik to Power BI Migration

**Automated hybrid migration (95% automatic)**

---

## In 30 Seconds

```bash
# 1. Migrate your QVF or JSON export
python migrate.py "YourApp.qvf"

# or use compact argument aliases
python migrate.py --source "YourApp.qvf" --preset balanced

# 2. Open the generated .pbip project in Power BI Desktop
#    File → Open → Browse → select the .pbip file

# ✅ Migration complete!
```

**Total time: ~5 minutes**

---

## Full Command

### Windows PowerShell

```powershell
cd "C:\path\to\QlikToPowerBI"

# From a QVF file
python migrate.py "C:\Data\Sales.qvf"

# Source alias
python migrate.py --source "C:\Data\Sales.qvf"

# From a JSON export
python migrate.py "C:\Data\Sales_export.json"

# Custom output directory
python migrate.py "C:\Data\Sales.qvf" --output-dir "C:\Output\Sales"

# Alias form for output directory
python migrate.py --source "C:\Data\Sales.qvf" --out "C:\Output\Sales"

# JSON output for CI/CD pipelines
python migrate.py "C:\Data\Sales.qvf" --json

```

### Output Structure

```
artifacts/powerbi_projects/Sales/
  ├── Sales.pbip                          # Project entry point
  ├── Sales.SemanticModel/
  │   ├── definition.tmdl                 # Model definition
  │   ├── tables/                         # Table definitions (TMDL)
  │   ├── relationships.tmdl             # Table relationships
  │   └── expressions.tmdl               # Power Query M expressions
  └── Sales.Report/
      ├── report.json                     # Report layout & visuals
      └── definition.pbir                 # Report reference
```

---

## Open in Power BI Desktop

1. **Open** Power BI Desktop (April 2024+)
2. **File → Open → Browse** → select the `.pbip` file
3. Tables, measures, relationships, and visuals are imported automatically
4. **Save** as `.pbix` when ready

> **Note**: PBIP (Power BI Project) is the modern Git-friendly format. Power BI Desktop opens it natively.

---

## What Gets Migrated

| Category | Coverage |
|----------|----------|
| Data model (tables, columns, types) | ✅ Full |
| Relationships | ✅ Full |
| DAX measures (175+ functions) | ✅ Full |
| Calculated columns | ✅ Full |
| Hierarchies | ✅ Full |
| Power Query M (25 connector types) | ✅ Full |
| Visuals (75+ types) | ✅ Full |
| RLS / Section Access | ✅ Full |
| Bookmarks & variables | ✅ Full |

---

## Next Steps

- **[Migration Guide](MIGRATION_GUIDE.md)** — Detailed technical walkthrough
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** — Deploy to Azure Fabric
- **[Plugin Development](PLUGIN_DEVELOPMENT.md)** — Create custom migration plugins

### v9 Enterprise Options

```bash
# Generate Fabric-native artifacts (Lakehouse + Dataflow + Notebook + Pipeline)
python migrate.py "YourApp.json" --output-format fabric

# Merge multiple apps into a shared semantic model
python migrate.py --merge app1.json app2.json

# Portfolio-level assessment
python migrate.py --assess-server exports/
```

---

## Start Now!

1. Open PowerShell
2. Navigate to the project folder
3. Run: `python migrate.py "YourApp.qvf"`
4. Open the `.pbip` file in Power BI Desktop
5. Done!
