#!/bin/bash
# LoanTracker Quick Start Script for Mac/Linux
# Usage: ./start.sh

set -e

echo "🏦 LoanTracker - Starting Application"
echo "======================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running!"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"

# Check if .env file exists, if not create from example
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env 2>/dev/null || touch .env
    echo "✅ Created .env file - you can customize it later"
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p engine_output logs
echo "✅ Directories created"

# Start the application
echo "🚀 Starting LoanTracker with Docker Compose..."
docker-compose up -d

# Wait for service to be ready
echo "⏳ Waiting for service to start..."
sleep 5

# Check if service is running
if docker-compose ps | grep -q "Up"; then
    echo "✅ LoanTracker is running!"
    echo ""
    echo "🌐 Open your browser and go to:"
    echo "   http://localhost:8000"
    echo ""
    echo "📊 Your data will be stored in:"
    echo "   engine_output/loan_records.csv"
    echo ""
    echo "🛑 To stop the application, run:"
    echo "   docker-compose down"
    echo ""
    echo "📖 For more information, see README.md or USER_GUIDE_MAC.md"
else
    echo "❌ Failed to start LoanTracker"
    echo "Check logs with: docker-compose logs"
    exit 1
fi
