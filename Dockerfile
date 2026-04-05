FROM node:20-slim AS node-base

FROM python:3.13-slim

# Copy node (needed for Boba CLI)
COPY --from=node-base /usr/local/bin/node /usr/local/bin/node
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
RUN pip install --no-cache-dir \
    google-genai mcp pydantic streamlit streamlit-autorefresh \
    python-dotenv pandas plotly

# Pre-install Boba CLI
RUN npx -y @tradeboba/cli@latest --help 2>/dev/null || true

COPY . .

RUN chmod +x start.sh run.sh

EXPOSE 8501

CMD ["./start.sh"]
