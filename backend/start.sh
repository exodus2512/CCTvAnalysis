#!/bin/bash
# SentinelAI Backend Start Script for Render

# Default to port 10000 for Render
PORT=${PORT:-10000}

echo "Starting SentinelAI Backend on port $PORT..."
uvicorn main:app --host 0.0.0.0 --port $PORT
