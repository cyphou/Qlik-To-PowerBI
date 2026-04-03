FROM python:3.12-slim

WORKDIR /app

COPY qlik_export/ qlik_export/
COPY powerbi_import/ powerbi_import/
COPY migrate.py .
COPY pyproject.toml .

# No external dependencies needed for core migration
# Install optional deps only if requirements.txt has them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true

EXPOSE 8000

CMD ["python", "-m", "powerbi_import.api_server", "--host", "0.0.0.0", "--port", "8000"]
