FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk curl xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    flask flask-cors waitress requests \
    playwright cryptography openpyxl \
    firebase-admin google-cloud-firestore \
    apscheduler anthropic paramiko

RUN playwright install --with-deps chromium

ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY sourcing/ /app/sourcing/
COPY logistics/ /app/logistics/
COPY hub/ /app/hub/

EXPOSE 8080 8082 8090
