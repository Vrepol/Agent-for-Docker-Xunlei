FROM docker.1ms.run/python:3.9-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive


ARG HTTP_PROXY
ARG HTTPS_PROXY

ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      chromium \
      chromium-driver \
      xvfb \
      fonts-liberation \
      && rm -rf /var/lib/apt/lists/*

COPY . /app
WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7861

CMD ["python", "app.py"]
