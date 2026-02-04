FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /var/lib/webdav/data/zotero

COPY server.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "server.py"]