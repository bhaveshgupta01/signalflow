FROM node:20-slim AS node-base
FROM python:3.13-slim

# Copy node from node image (needed for Boba CLI)
COPY --from=node-base /usr/local/bin/node /usr/local/bin/node
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Install script utility for TTY emulation (boba proxy needs it)
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    google-genai mcp pydantic streamlit streamlit-autorefresh \
    python-dotenv pandas plotly

# Pre-install boba CLI
RUN npx -y @tradeboba/cli@latest --help || true

# Copy application code
COPY . .

# Expose Streamlit port
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import sqlite3; c=sqlite3.connect('/app/signalflow.db'); c.execute('SELECT 1')" || exit 1

CMD ["python", "runner.py"]
