# start_all.ps1
# Unified script to start all components for the Xtreme Federated Learning project

Write-Host "Starting Docker containers (RabbitMQ, etc.)..." -ForegroundColor Green
docker-compose up -d

Write-Host "Starting Dashboard Backend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd dashboard-backend; node server.js"

Write-Host "Starting Dashboard Frontend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd dashboard-frontend; npm run dev"

Write-Host "Starting XFL Server..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\activate; cd xtreme_federated_learning; python server_xfl.py"

# Wait a couple of seconds to ensure RabbitMQ is up before the consumer starts
Start-Sleep -Seconds 5

Write-Host "Starting Consumer (server.py)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\activate; python server.py"

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "All services started! Separate windows have been opened." -ForegroundColor Cyan
Write-Host "Dashboard available at: http://localhost:5173" -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Cyan
