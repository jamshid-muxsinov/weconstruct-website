#!/bin/bash

echo "=== Docker Compose Status ==="
docker-compose ps

echo -e "\n=== Checking Site Container Logs (Last 20 lines) ==="
docker-compose logs --tail=20 site

echo -e "\n=== Checking Admin Container Logs (Last 20 lines) ==="
docker-compose logs --tail=20 admin

echo -e "\n=== Testing Site App Directly ==="
curl -v http://localhost:8001/uz 2>&1 | head -30

echo -e "\n=== Testing Admin App Directly ==="
curl -v http://localhost:8000/login 2>&1 | head -30

echo -e "\n=== Checking if APP_TO_RUN is set ==="
docker-compose exec -T site env | grep APP_TO_RUN
docker-compose exec -T admin env | grep APP_TO_RUN
