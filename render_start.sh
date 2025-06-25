#!/bin/bash
# Create cache directory if it doesn't exist
mkdir -p app/cache
# Start the application
uvicorn app.main:app --host 0.0.0.0 --port $PORT
