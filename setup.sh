#!/bin/bash
# Run this on EC2: bash setup.sh
set -e

EC2_IP="16.148.23.192"
PROJECT_DIR="/home/ubuntu/meeting-bot"

echo "=== Cloning project ==="
git clone https://github.com/YOUR_USERNAME/Meeting_Bot_Agent.git $PROJECT_DIR || \
  (cd $PROJECT_DIR && git pull)

cd $PROJECT_DIR

echo "=== Copying .env ==="
# .env must already exist in $PROJECT_DIR (scp it before running this)
[ -f .env ] || { echo "ERROR: .env file missing. scp it first."; exit 1; }

echo "=== Running Attendee migrations ==="
docker compose run --rm attendee python manage.py migrate

echo "=== Starting all services ==="
docker compose up -d --build

echo "=== Waiting for services ==="
sleep 10

echo "=== Health check ==="
curl -s http://localhost:8000/health && echo ""
curl -s http://localhost:8080/api/v1/bots && echo ""

echo ""
echo "=== Done ==="
echo "FastAPI:  http://$EC2_IP:8000/docs"
echo "Attendee: http://$EC2_IP:8080"
echo "Qdrant:   http://$EC2_IP:6333/dashboard"
