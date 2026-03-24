# 🔧 LoanTracker Troubleshooting Guide

## Quick Fixes for Common Issues

---

## ❌ Issue: Docker Build Fails with npm Error

### Error Message:
```
failed to solve: process "/bin/sh -c npm ci" did not complete successfully: exit code: 1
```

### Solution 1: Use Development Mode (No Docker)

Instead of using Docker, run the application directly:

```bash
./start-dev.sh
```

This will:
- Create a Python virtual environment
- Install dependencies
- Start the backend server
- No Docker required!

### Solution 2: Rebuild Docker Image

If you want to use Docker:

```bash
# Clean up old images
docker-compose down
docker system prune -f

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up -d
```

### Solution 3: Use Pre-built Backend Only

Since the frontend is just static files, you can build it separately:

```bash
# Build frontend locally
cd frontend
npm install --legacy-peer-deps
npm run build
cd ..

# Then start backend with Docker (it will serve the frontend)
docker-compose up -d backend
```

---

## ❌ Issue: Port 8000 Already in Use

### Error Message:
```
Error starting userland proxy: listen tcp4 0.0.0.0:8000: bind: address already in use
```

### Solution 1: Kill Process on Port 8000

**Mac/Linux:**
```bash
lsof -ti:8000 | xargs kill -9
```

**Windows:**
```cmd
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Solution 2: Change Port

Edit `.env` file:
```env
BACKEND_PORT=8001
```

Then access at http://localhost:8001

---

## ❌ Issue: Docker Daemon Not Running

### Error Message:
```
Cannot connect to the Docker daemon
```

### Solution:

1. **Start Docker Desktop**:
   - Mac: Open Docker from Applications
   - Windows: Search for "Docker Desktop" in Start Menu

2. **Wait for Docker to fully start** (icon should not be animated)

3. **Verify Docker is running**:
   ```bash
   docker ps
   ```

---

## ❌ Issue: Permission Denied

### Error Message:
```
Permission denied while trying to connect to Docker daemon
```

### Solution 1: Add User to Docker Group (Linux)

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Solution 2: Run with Sudo (Not Recommended)

```bash
sudo docker-compose up -d
```

### Solution 3: Use Development Mode

```bash
./start-dev.sh  # No Docker, no permission issues
```

---

## ❌ Issue: Frontend Not Loading

### Error Message:
Browser shows blank page or "Cannot GET /"

### Solution 1: Check if Backend is Running

```bash
# Check if service is up
curl http://localhost:8000/health

# Should return:
# {"status":"healthy","app":"LoanTracker",...}
```

### Solution 2: Check Frontend Build

```bash
# Verify frontend build exists
ls -la frontend/dist/

# If not, build it:
cd frontend
npm install --legacy-peer-deps
npm run build
```

### Solution 3: Access Backend Directly

If frontend build isn't working, you can still use the API:

- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Create Loan: POST http://localhost:8000/api/v1/loans/

---

## ❌ Issue: Data Not Appearing

### Symptoms:
- Created loans don't show in table
- Reports show 0 loans
- CSV file is empty

### Solution 1: Check CSV File

```bash
# Verify CSV exists
ls -la engine_output/loan_records.csv

# Check contents
cat engine_output/loan_records.csv
```

### Solution 2: Check File Permissions

```bash
# Fix permissions
chmod 755 engine_output
chmod 644 engine_output/*.csv
```

### Solution 3: Check Logs

```bash
# View logs
tail -f logs/loantracker.log

# Or with Docker
docker-compose logs -f
```

### Solution 4: Restart Application

```bash
# With Docker
docker-compose restart

# Without Docker
# Press Ctrl+C and run ./start-dev.sh again
```

---

## ❌ Issue: Encryption Errors

### Error Message:
```
EncryptionException: Decryption failed
```

### Solution 1: Check Encryption Key

Ensure `ENCRYPTION_KEY` in `.env` is:
- Exactly the same as when data was encrypted
- Case-sensitive
- Not empty if you encrypted data

### Solution 2: Start Fresh (Development Only)

```bash
# Backup old data
cp engine_output/loan_records.csv engine_output/loan_records.backup.csv

# Remove encrypted data
rm engine_output/loan_records.csv

# Restart application
./start-dev.sh
```

### Solution 3: Disable Encryption

Edit `.env`:
```env
ENCRYPTION_KEY=
```

**Warning**: This only works with new data. Previously encrypted data will remain encrypted.

---

## ❌ Issue: Module Not Found (Python)

### Error Message:
```
ModuleNotFoundError: No module named 'fastapi'
```

### Solution 1: Install Dependencies

```bash
cd backend
pip3 install -r requirements.txt
```

### Solution 2: Use Virtual Environment

```bash
# Create venv
python3 -m venv venv

# Activate
source venv/bin/activate  # Mac/Linux
# or
venv\Scripts\activate     # Windows

# Install
pip install -r backend/requirements.txt
```

### Solution 3: Use Development Script

```bash
./start-dev.sh  # Handles everything automatically
```

---

## ❌ Issue: npm Install Fails

### Error Message:
```
npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
```

### Solution:

Use `--legacy-peer-deps` flag:

```bash
cd frontend
npm install --legacy-peer-deps
npm run build
```

---

## 🚀 Quick Start Alternatives

If all else fails, here are 3 ways to run LoanTracker:

### Method 1: Development Mode (Easiest)
```bash
./start-dev.sh
```
- No Docker needed
- Handles dependencies automatically
- Access at http://localhost:8000

### Method 2: Docker Compose (Production)
```bash
docker-compose up -d
```
- Requires Docker Desktop
- Fully containerized
- Access at http://localhost:8000

### Method 3: Manual (Full Control)
```bash
# Terminal 1: Backend
cd backend
pip3 install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Access at http://localhost:8000
```

---

## 📊 Diagnostic Commands

### Check System Status

```bash
# Docker status
docker ps
docker-compose ps

# Backend health
curl http://localhost:8000/health

# View logs
tail -f logs/loantracker.log
docker-compose logs -f

# Check processes
ps aux | grep uvicorn
ps aux | grep python

# Check ports
lsof -i:8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows
```

### Verify Installation

```bash
# Python version
python3 --version  # Should be 3.11+

# Node version
node --version     # Should be 20+

# Docker version
docker --version
docker-compose --version

# Pip packages
pip3 list | grep fastapi
pip3 list | grep uvicorn
```

---

## 🔄 Complete Reset

If nothing works, start fresh:

```bash
# Stop everything
docker-compose down
pkill -f uvicorn

# Clean Docker
docker system prune -af
docker volume prune -f

# Backup data
cp -r engine_output engine_output.backup

# Remove build artifacts
rm -rf frontend/node_modules frontend/dist
rm -rf venv
rm -rf backend/__pycache__ backend/app/__pycache__

# Start fresh
./start-dev.sh
```

---

## 📞 Getting Help

### Log Files to Check

1. **Application logs**: `logs/loantracker.log`
2. **Docker logs**: `docker-compose logs`
3. **Browser console**: Press F12 in browser

### Information to Collect

When reporting issues:

```bash
# System info
uname -a
python3 --version
node --version
docker --version

# Application status
docker-compose ps
curl http://localhost:8000/health

# Recent logs
tail -50 logs/loantracker.log
```

---

## ✅ Success Checklist

After fixing issues, verify:

- [ ] Backend accessible at http://localhost:8000/health
- [ ] Frontend loads at http://localhost:8000
- [ ] Can create a loan record
- [ ] Loan appears in "View Loans" tab
- [ ] CSV file created: `engine_output/loan_records.csv`
- [ ] Reports show statistics
- [ ] Can change themes
- [ ] Can update loan status
- [ ] Can delete loan

---

## 🎯 Recommended Approach for Demo

**Fastest, Most Reliable Method**:

```bash
./start-dev.sh
```

This:
- ✅ Requires only Python 3.11+
- ✅ No Docker complexity
- ✅ Automatic dependency management
- ✅ Works on Mac, Linux, Windows (with Git Bash)
- ✅ Takes 30 seconds to start
- ✅ Perfect for demos

---

**Last Updated**: March 2026
**For**: LoanTracker v1.0.0
