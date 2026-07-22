FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY python/ ./python
COPY tests/ ./tests
COPY pytest.ini .

ENV PYTHONPATH=/app/python

EXPOSE 5000

HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

CMD ["gunicorn", "--chdir", "python", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
