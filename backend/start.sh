#!/bin/bash
# Start script for Render deployment
# Render automatically sets PORT environment variable

PORT=${PORT:-8000}

echo "Starting Routecast backend on port $PORT"
uvicorn server:app --host 0.0.0.0 --port $PORT
