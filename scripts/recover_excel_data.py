"""Recover source data files from TWBX archives in examples/real_world."""
import zipfile
import sqlite3
import csv
import os
import sys

REAL_WORLD = os.path.join(os.path.dirname(__file__), '..', 'examples', 'real_world')

def extract_from_twbx(twbx_path, out_dir):
    """Extract data files (.xlsx, .xls, .csv, .hyper) from a TWBX ZIP."""
    extracted = []
    with zipfile.ZipFile(twbx_path) as z:
        for info in z.infolist():
            ext = os.path.splitext(info.filename)[1].lower()
            if ext in ('.xls', '.xlsx', '.csv'):
                basename = os.path.basename(info.filename)
                out_path = os.path.join(out_dir, basename)
                data = z.read(info.filename)
                with open(out_path, 'wb') as f:
                    f.write(data)
                extracted.append((out_path, len(data), 'direct'))
                print(f"  Extracted: {basename} ({len(data):,} bytes)")
            elif ext in ('.hyper', '.tde'):
                # Try to convert hyper/tde to CSV
                data = z.read(info.filename)
                # Write directly to final name to avoid lock issues with temp files
                raw_name = os.path.splitext(os.path.basename(twbx_path))[0] + ext
                raw_path = os.path.join(out_dir, raw_name)
                with open(raw_path, 'wb') as f:
                    f.write(data)
                csv_files = hyper_to_csv(raw_path, out_dir, os.path.splitext(os.path.basename(twbx_path))[0])
                if csv_files:
                    extracted.extend(csv_files)
                    # Remove raw file if CSV export succeeded
                    try:
                        import time; time.sleep(1)
                        os.remove(raw_path)
                    except OSError:
                        pass
                else:
                    # Keep the raw file as fallback
                    extracted.append((raw_path, len(data), f'raw-{ext[1:]}'))
                    print(f"  Extracted raw: {raw_name} ({len(data):,} bytes)")
    return extracted


def hyper_to_csv(hyper_path, out_dir, prefix):
    """Try to read a Hyper file and export tables to CSV."""
    results = []
    
    # Tier 1: try Qlikhyperapi
    try:
        from Qlikhyperapi import HyperProcess, Telemetry, Connection
        hyper = HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_Qlik)
        try:
            conn = Connection(hyper.endpoint, hyper_path)
            try:
                schemas = conn.catalog.get_schema_names()
                for schema in schemas:
                    tables = conn.catalog.get_table_names(schema)
                    for table in tables:
                        cols = conn.catalog.get_table_definition(table).columns
                        col_names = [c.name.unescaped for c in cols]
                        rows = conn.execute_list_query(f"SELECT * FROM {table}")
                        csv_name = f"{prefix}_{table.name.unescaped}.csv"
                        csv_path = os.path.join(out_dir, csv_name)
                        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(col_names)
                            writer.writerows(rows)
                        results.append((csv_path, os.path.getsize(csv_path), 'hyper-api'))
                        print(f"  Exported (hyper-api): {csv_name} ({len(rows)} rows)")
            finally:
                conn.close()
        finally:
            hyper.close()
            import time; time.sleep(0.5)  # let Hyper release file locks
        return results
    except ImportError:
        pass
    except Exception as e:
        print(f"  hyper-api failed: {e}")
        try:
            hyper.close()
            import time; time.sleep(0.5)
        except Exception:
            pass

    # Tier 2: try sqlite3
    try:
        conn = sqlite3.connect(hyper_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        for tname in tables:
            cur.execute(f'PRAGMA table_info("{tname}")')
            col_info = cur.fetchall()
            col_names = [c[1] for c in col_info]
            cur.execute(f'SELECT * FROM "{tname}"')
            rows = cur.fetchall()
            if rows:
                csv_name = f"{prefix}_{tname}.csv"
                csv_path = os.path.join(out_dir, csv_name)
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(col_names)
                    writer.writerows(rows)
                results.append((csv_path, os.path.getsize(csv_path), 'sqlite'))
                print(f"  Exported (sqlite): {csv_name} ({len(rows)} rows)")
        conn.close()
        return results
    except Exception as e:
        print(f"  sqlite3 failed: {e}")

    # Tier 3: try hyper_reader from project
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from qlik_export.hyper_reader import read_hyper, export_hyper_to_csv
        result = read_hyper(hyper_path, max_rows=100000)
        tbls = result.get('tables', []) if isinstance(result, dict) else []
        for tbl in tbls:
            rows = tbl.get('sample_rows', [])
            if rows:
                name = tbl.get('table', 'data')
                csv_path = export_hyper_to_csv(tbl, out_dir, csv_filename=f"{prefix}_{name}.csv")
                if csv_path:
                    results.append((csv_path, os.path.getsize(csv_path), 'hyper_reader'))
                    print(f"  Exported (hyper_reader): {os.path.basename(csv_path)}")
    except Exception as e:
        print(f"  hyper_reader failed: {e}")

    if not results:
        print(f"  WARNING: Could not read hyper file (install Qlikhyperapi for full support)")

    return results


def main():
    out_dir = REAL_WORLD
    os.makedirs(out_dir, exist_ok=True)

    twbx_files = sorted(f for f in os.listdir(REAL_WORLD) if f.endswith('.qvf'))
    all_extracted = []

    for twbx in twbx_files:
        twbx_path = os.path.join(REAL_WORLD, twbx)
        print(f"\n=== {twbx} ===")
        extracted = extract_from_twbx(twbx_path, out_dir)
        all_extracted.extend(extracted)

    print(f"\n{'='*60}")
    print(f"Total files recovered: {len(all_extracted)}")
    for path, size, method in all_extracted:
        print(f"  {os.path.basename(path)} ({size:,} bytes) [{method}]")


if __name__ == '__main__':
    main()
