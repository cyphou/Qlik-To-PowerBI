"""Streamlit Web UI — browser-based migration wizard.

A 6-step interactive wizard for non-CLI users:
1. Upload — Upload .qvf/.qvf file(s)
2. Configure — Set migration options (culture, mode, output format)
3. Assess — Pre-migration readiness assessment
4. Migrate — Run extraction + generation with progress
5. Validate — Artifact validation summary
6. Download — Download .pbip project as ZIP

Requires optional `streamlit` package:
    pip install streamlit
    streamlit run web/app.py

If streamlit is not installed, a fallback mode launches the stdlib
http.server-based wizard (no external deps).
"""

import os
import sys
import json
import shutil
import tempfile
import logging
import zipfile
from datetime import datetime

logger = logging.getLogger('qlik_to_powerbi.web')

# ════════════════════════════════════════════════════════════════════
#  STREAMLIT APP
# ════════════════════════════════════════════════════════════════════

_HAS_STREAMLIT = False
try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    st = None


def _zip_directory(source_dir, zip_path):
    """Create a ZIP archive of a directory."""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            for f in files:
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, source_dir)
                zf.write(full, arcname)


def _save_uploaded_file(uploaded, tmp_dir):
    """Save a Streamlit uploaded file to a temp directory, return path."""
    path = os.path.join(tmp_dir, uploaded.name)
    with open(path, 'wb') as f:
        f.write(uploaded.getbuffer())
    return path


def _run_migration_pipeline(file_path, options, progress_callback=None):
    """Run the migration pipeline and return results dict.

    Args:
        file_path: Path to .qvf/.qvf file
        options: dict with migration options
        progress_callback: optional callable(step, total, message)

    Returns:
        dict with keys: success, output_dir, stats, errors, assessment
    """
    # Add project root to path
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    result = {
        'success': False,
        'output_dir': options.get('output_dir', ''),
        'stats': {},
        'errors': [],
        'assessment': None,
    }

    try:
        if progress_callback:
            progress_callback(1, 4, "Extracting Qlik objects...")

        # Step 1: Extraction
        sys.path.insert(0, os.path.join(root, 'qlik_export'))
        from extract_Qlik_data import QlikExtractor
        extractor = QlikExtractor(file_path)
        if not extractor.extract_all():
            result['errors'].append("Extraction failed")
            return result

        if progress_callback:
            progress_callback(2, 4, "Generating Power BI project...")

        # Step 2: Generation
        from powerbi_import.import_to_powerbi import PowerBIImporter
        importer = PowerBIImporter(
            json_dir=os.path.join(root, 'qlik_export'),
            output_dir=result['output_dir'],
        )
        gen_result = importer.import_all(
            report_name=os.path.splitext(os.path.basename(file_path))[0],
            culture=options.get('culture', 'en-US'),
            model_mode=options.get('mode', 'import'),
            output_format=options.get('output_format', 'pbip'),
        )
        result['stats'] = gen_result if isinstance(gen_result, dict) else {}
        result['success'] = True

        if progress_callback:
            progress_callback(3, 4, "Validating artifacts...")

        # Step 3: Validation (optional)
        try:
            from powerbi_import.validator import ArtifactValidator
            validator = ArtifactValidator()
            val_result = validator.validate_project(result['output_dir'])
            result['validation'] = val_result
        except Exception as e:
            result['validation'] = {'error': str(e)}

        if progress_callback:
            progress_callback(4, 4, "Done!")

    except Exception as e:
        result['errors'].append(str(e))
        logger.exception("Migration pipeline error")

    return result


def _run_assessment(file_path):
    """Run pre-migration assessment, return assessment dict."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        sys.path.insert(0, os.path.join(root, 'qlik_export'))
        from extract_Qlik_data import QlikExtractor
        extractor = QlikExtractor(file_path)
        if not extractor.extract_all():
            return {'error': 'Extraction failed'}

        from powerbi_import.assessment import AssessmentEngine
        engine = AssessmentEngine()
        return engine.assess(os.path.join(root, 'qlik_export'))
    except Exception as e:
        return {'error': str(e)}


# ════════════════════════════════════════════════════════════════════
#  STREAMLIT UI
# ════════════════════════════════════════════════════════════════════

def run_streamlit_app():
    """Launch the Streamlit migration wizard."""
    if not _HAS_STREAMLIT:
        print("Streamlit is not installed. Install with: pip install streamlit")
        print("Falling back to CLI wizard...")
        return False

    st.set_page_config(
        page_title="Qlik → Power BI Migration",
        page_icon="📊",
        layout="wide",
    )

    st.title("📊 Qlik → Power BI Migration Wizard")
    st.markdown("Migrate your Qlik apps to Power BI in seconds.")

    # ── Session State ──
    if 'step' not in st.session_state:
        st.session_state.step = 1
    if 'tmp_dir' not in st.session_state:
        st.session_state.tmp_dir = tempfile.mkdtemp(prefix='Qlik_migrate_')
    if 'file_paths' not in st.session_state:
        st.session_state.file_paths = []
    if 'assessment' not in st.session_state:
        st.session_state.assessment = None
    if 'migration_result' not in st.session_state:
        st.session_state.migration_result = None

    # ── Navigation ──
    steps = ["Upload", "Configure", "Assess", "Migrate", "Validate", "Download"]
    cols = st.columns(len(steps))
    for i, (col, name) in enumerate(zip(cols, steps)):
        step_num = i + 1
        if step_num == st.session_state.step:
            col.markdown(f"**{step_num}. {name}** ◀")
        elif step_num < st.session_state.step:
            col.markdown(f"~~{step_num}. {name}~~ ✓")
        else:
            col.markdown(f"{step_num}. {name}")

    st.divider()

    # ── Step 1: Upload ──
    if st.session_state.step == 1:
        st.header("Step 1: Upload Qlik app")
        uploaded = st.file_uploader(
            "Choose .qvf or .qvf file(s)",
            type=['twb', 'twbx', 'tds', 'tdsx'],
            accept_multiple_files=True,
        )
        if uploaded:
            paths = []
            for f in uploaded:
                path = _save_uploaded_file(f, st.session_state.tmp_dir)
                paths.append(path)
                st.success(f"Uploaded: {f.name} ({f.size / 1024:.1f} KB)")
            st.session_state.file_paths = paths

            if st.button("Next →", type="primary"):
                st.session_state.step = 2
                st.rerun()

    # ── Step 2: Configure ──
    elif st.session_state.step == 2:
        st.header("Step 2: Configure Migration")

        col1, col2 = st.columns(2)
        with col1:
            culture = st.selectbox("Culture", [
                'en-US', 'fr-FR', 'de-DE', 'es-ES', 'pt-BR',
                'ja-JP', 'zh-CN', 'ko-KR', 'it-IT', 'nl-NL',
            ])
            mode = st.selectbox("Storage Mode", ['import', 'directquery', 'composite'])

        with col2:
            output_format = st.selectbox("Output Format", ['pbip', 'fabric'])
            optimize = st.checkbox("Optimize DAX", value=True)
            time_intel = st.selectbox("Time Intelligence", ['none', 'auto', 'full'])

        if 'options' not in st.session_state:
            st.session_state.options = {}

        st.session_state.options = {
            'culture': culture,
            'mode': mode,
            'output_format': output_format,
            'optimize_dax': optimize,
            'time_intelligence': time_intel,
            'output_dir': os.path.join(st.session_state.tmp_dir, 'output'),
        }

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Back"):
                st.session_state.step = 1
                st.rerun()
        with c2:
            if st.button("Next →", type="primary"):
                st.session_state.step = 3
                st.rerun()

    # ── Step 3: Assess ──
    elif st.session_state.step == 3:
        st.header("Step 3: Pre-Migration Assessment")

        if st.session_state.assessment is None:
            with st.spinner("Running assessment..."):
                if st.session_state.file_paths:
                    result = _run_assessment(st.session_state.file_paths[0])
                    st.session_state.assessment = result

        assessment = st.session_state.assessment
        if assessment:
            if 'error' in assessment:
                st.error(f"Assessment error: {assessment['error']}")
            else:
                overall = assessment.get('overall_score', 0)
                verdict = assessment.get('verdict', 'unknown')
                color = {'pass': 'green', 'warn': 'orange', 'fail': 'red'}.get(verdict, 'gray')
                st.markdown(f"### Overall Score: :{color}[{overall}%] ({verdict.upper()})")

                categories = assessment.get('categories', {})
                for cat, info in categories.items():
                    score = info.get('score', 0) if isinstance(info, dict) else 0
                    st.progress(score / 100, text=f"{cat}: {score}%")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Back"):
                st.session_state.step = 2
                st.rerun()
        with c2:
            if st.button("Migrate →", type="primary"):
                st.session_state.step = 4
                st.rerun()

    # ── Step 4: Migrate ──
    elif st.session_state.step == 4:
        st.header("Step 4: Migration")

        if st.session_state.migration_result is None:
            progress = st.progress(0, text="Starting migration...")
            status = st.empty()

            def _progress(step, total, msg):
                progress.progress(step / total, text=msg)
                status.info(msg)

            result = _run_migration_pipeline(
                st.session_state.file_paths[0],
                st.session_state.options,
                progress_callback=_progress,
            )
            st.session_state.migration_result = result

        result = st.session_state.migration_result
        if result['success']:
            st.success("Migration completed successfully!")
            stats = result.get('stats', {})
            if stats:
                cols = st.columns(4)
                cols[0].metric("Tables", stats.get('tables', 0))
                cols[1].metric("Measures", stats.get('measures', 0))
                cols[2].metric("Visuals", stats.get('visuals', 0))
                cols[3].metric("Pages", stats.get('pages', 0))
        else:
            st.error("Migration failed")
            for err in result.get('errors', []):
                st.error(err)

        if st.button("Next →", type="primary"):
            st.session_state.step = 5
            st.rerun()

    # ── Step 5: Validate ──
    elif st.session_state.step == 5:
        st.header("Step 5: Validation")

        result = st.session_state.migration_result
        validation = result.get('validation', {}) if result else {}

        if 'error' in validation:
            st.warning(f"Validation: {validation['error']}")
        else:
            is_valid = validation.get('valid', False)
            if is_valid:
                st.success("All validation checks passed!")
            else:
                st.warning("Some validation issues found:")
                for issue in validation.get('issues', []):
                    st.warning(f"  - {issue}")

        if st.button("Download →", type="primary"):
            st.session_state.step = 6
            st.rerun()

    # ── Step 6: Download ──
    elif st.session_state.step == 6:
        st.header("Step 6: Download")

        result = st.session_state.migration_result
        if result and result['success']:
            output_dir = result['output_dir']
            zip_path = os.path.join(st.session_state.tmp_dir, 'migration_output.zip')

            if not os.path.exists(zip_path) and os.path.isdir(output_dir):
                _zip_directory(output_dir, zip_path)

            if os.path.exists(zip_path):
                with open(zip_path, 'rb') as f:
                    st.download_button(
                        label="Download .pbip Project (ZIP)",
                        data=f.read(),
                        file_name="migration_output.zip",
                        mime="application/zip",
                        type="primary",
                    )

            st.info("Open the extracted .pbip file in Power BI Desktop (December 2025+).")
        else:
            st.error("No migration output available. Please run the migration first.")

        if st.button("Start Over"):
            # Cleanup
            tmp = st.session_state.tmp_dir
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.session_state.step = 1
            st.session_state.tmp_dir = tempfile.mkdtemp(prefix='Qlik_migrate_')
            st.rerun()


# ════════════════════════════════════════════════════════════════════
#  FALLBACK: STDLIB HTTP SERVER
# ════════════════════════════════════════════════════════════════════

def _generate_upload_html():
    """Generate a simple HTML upload form."""
    return """<!DOCTYPE html>
<html>
<head>
<title>Qlik to Power BI Migration</title>
<style>
  body { font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
  h1 { color: #0078D4; }
  .upload-area { border: 2px dashed #0078D4; padding: 40px; text-align: center;
                 border-radius: 8px; margin: 20px 0; background: #f8f9fa; }
  input[type=file] { margin: 10px; }
  button { background: #0078D4; color: white; padding: 12px 24px; border: none;
           border-radius: 4px; font-size: 16px; cursor: pointer; }
  button:hover { background: #005a9e; }
</style>
</head>
<body>
<h1>Qlik → Power BI Migration</h1>
<p>Upload a .qvf or .qvf file to migrate.</p>
<form method="POST" enctype="multipart/form-data" action="/migrate">
  <div class="upload-area">
    <input type="file" name="file" accept=".qvf,.qvf,.tds,.tdsx" required>
  </div>
  <button type="submit">Migrate</button>
</form>
</body>
</html>"""


def run_fallback_server(port=8501):
    """Run a minimal stdlib-based web UI (no Streamlit dependency)."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import cgi

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(_generate_upload_html().encode('utf-8'))

        def do_POST(self):
            if self.path != '/migrate':
                self.send_error(404)
                return

            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_error(400, "Expected multipart/form-data")
                return

            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST',
                         'CONTENT_TYPE': content_type},
            )

            file_item = form['file']
            if not file_item.file:
                self.send_error(400, "No file uploaded")
                return

            ext = os.path.splitext(file_item.filename)[1].lower()
            if ext not in ('.qvf', '.qvf', '.tds', '.tdsx'):
                self.send_error(400, f"Unsupported file type: {ext}")
                return

            tmp_dir = tempfile.mkdtemp(prefix='Qlik_migrate_')
            file_path = os.path.join(tmp_dir, os.path.basename(file_item.filename))
            with open(file_path, 'wb') as f:
                f.write(file_item.file.read())

            output_dir = os.path.join(tmp_dir, 'output')
            result = _run_migration_pipeline(file_path, {'output_dir': output_dir})

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            response = {
                'success': result['success'],
                'errors': result.get('errors', []),
                'stats': result.get('stats', {}),
            }
            self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))

        def log_message(self, fmt, *args):
            logger.info(fmt, *args)

    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f"Migration Web UI running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def launch_web_ui(port=8501):
    """Launch the web UI — Streamlit if available, fallback otherwise."""
    if _HAS_STREAMLIT:
        run_streamlit_app()
    else:
        run_fallback_server(port)


if __name__ == '__main__':
    if _HAS_STREAMLIT:
        run_streamlit_app()
    else:
        run_fallback_server()
