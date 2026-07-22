FROM python:3.11-slim

WORKDIR /app

# System deps for pypdf / building small wheels if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# torch is pulled in by sentence-transformers/transformers. Installed
# explicitly first, from the CPU-only wheel index -- the default PyPI
# build drags in multi-gigabyte CUDA libraries this machine has no GPU
# to use.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY python/ ./python
COPY scripts/ ./scripts
COPY tests/ ./tests
COPY pytest.ini .

ENV PYTHONPATH=/app/python:/app
# Model/tokenizer caches -- /app/.cache is mounted as a named volume in
# docker-compose.yml so models survive container rebuilds instead of
# re-downloading every time.
ENV HF_HOME=/app/.cache/huggingface
ENV TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken

EXPOSE 5000

HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

CMD ["uvicorn", "app:app", "--app-dir", "python", "--host", "0.0.0.0", "--port", "5000"]
