#!/bin/sh
# Generates deploy/prometheus/alertmanager.rendered.yml from the template + .env
set -e

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: .env file not found."
  exit 1
fi

SMTP_PASSWORD=$(grep '^SMTP_PASSWORD=' "$ENV_FILE" | cut -d '=' -f2-)
ALERT_EMAIL=$(grep '^ALERT_EMAIL=' "$ENV_FILE" | cut -d '=' -f2-)

if [ -z "$SMTP_PASSWORD" ]; then
  echo "Error: SMTP_PASSWORD is not set in .env"
  exit 1
fi

if [ -z "$ALERT_EMAIL" ]; then
  echo "Error: ALERT_EMAIL is not set in .env"
  exit 1
fi

sed \
  -e "s|\${SMTP_PASSWORD}|$SMTP_PASSWORD|g" \
  -e "s|\${ALERT_EMAIL}|$ALERT_EMAIL|g" \
  deploy/prometheus/alertmanager.yml \
  > deploy/prometheus/alertmanager.rendered.yml

echo "Generated deploy/prometheus/alertmanager.rendered.yml"
