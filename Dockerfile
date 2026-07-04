FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libssl-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY app ./app
COPY gunicorn.conf.py .

# A porta vem de $PORT (lida em Python no gunicorn.conf.py), sem depender de shell.
CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
