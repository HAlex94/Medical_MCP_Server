#!/bin/bash

# Check Python version - we need 3.9.x
PYTHON_VERSION=$(python -c 'import sys; print("{}.{}".format(sys.version_info.major, sys.version_info.minor))')

if [[ "$PYTHON_VERSION" == "3.13" ]]; then
  echo "ERROR: Python 3.13 is not supported. Please use Python 3.9"
  exit 1
fi

# Force Python version if environment variable exists
if [[ -z "$PYTHON_VERSION" ]]; then
  export PYTHON_VERSION="3.9.18"
fi

# Create cache directory if it doesn't exist
mkdir -p app/cache

# Print directory structure for troubleshooting
echo "Directory structure for app/routes:"
find ./app/routes -type d | sort
echo "Python files in app/routes:"
find ./app/routes -name "*.py" | sort

# Fix Python path to ensure all modules are discoverable
PROJECT_DIR=$(pwd)
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
echo "PYTHONPATH set to: $PYTHONPATH"

# Start the application with explicit Python version check
echo "Starting application with Python $PYTHON_VERSION"
uvicorn app.main:app --host 0.0.0.0 --port $PORT
