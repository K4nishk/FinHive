# 🪟 LoanTracker - Windows Setup Guide

Quick setup guide for Windows users.

---

## 📋 Prerequisites

### 1. Install Python

1. **Download Python 3.11+** from https://www.python.org/downloads/
2. **During installation**:
   - ✅ **CHECK** "Add Python to PATH" (IMPORTANT!)
   - ✅ **CHECK** "Install pip"
   - Click "Install Now"

3. **Verify installation**:
   ```cmd
   python --version
   ```
   Should show: `Python 3.11` or higher

---

## 🚀 Quick Start (30 seconds)

### Option 1: Double-Click Launch (Easiest)

1. **Extract** the LoanTracker ZIP file
2. **Double-click** `start-windows.bat`
3. **Wait** for setup to complete (first run: 2-3 minutes)
4. **Open browser**: http://localhost:8000

Done! 🎉

---

### Option 2: Command Line

1. **Open Command Prompt** or PowerShell
2. **Navigate** to LoanTracker folder:
   ```cmd
   cd C:\Path\To\LoanTracker
   ```
3. **Run**:
   ```cmd
   start-windows.bat
   ```
4. **Open browser**: http://localhost:8000

---

## 📂 What Gets Installed

### Core Packages (Always Installed):
- **FastAPI** - Web framework
- **Uvicorn** - Web server
- **Pydantic** - Data validation

### Optional Packages (Auto-attempted):
- **Cryptography** - For data encryption (optional)
- **Pandas** - For better CSV performance (optional)

**Note**: If optional packages fail to install, the system works fine without them!

---

## 🗂️ Folder Structure

```
LoanTracker/
├── start-windows.bat         ← Double-click this to start
├── backend/
│   ├── venv/                 ← Virtual environment (created on first run)
│   ├── engine_output/        ← Your loan data stored here
│   │   └── loan_records.csv
│   ├── logs/                 ← Application logs
│   └── .env                  ← Configuration (created on first run)
├── sample_loans.csv          ← Test data (10 sample loans)
└── README.md                 ← Documentation
```

---

## ⚙️ Configuration

Configuration file: `backend/.env`

**Default settings** (created automatically):
```env
STORAGE_TYPE=csv
ENCRYPTION_KEY=                  # Empty = encryption disabled
CSV_OUTPUT_DIR=./engine_output
CSV_FILENAME=loan_records.csv
BACKEND_PORT=8000
LOG_LEVEL=INFO
```

**To enable encryption** (optional):
1. Make sure cryptography installed successfully
2. Edit `backend\.env`
3. Set: `ENCRYPTION_KEY=your-secret-key-here`
4. Restart server

---

## 🔧 Troubleshooting

### Issue: "Python is not installed or not in PATH"

**Solution**:
1. Reinstall Python from https://www.python.org/downloads/
2. **IMPORTANT**: Check "Add Python to PATH" during installation
3. Restart Command Prompt
4. Try again

---

### Issue: Port 8000 already in use

**Solution 1** - Kill process on port 8000:
```cmd
netstat -ano | findstr :8000
taskkill /PID <PID_NUMBER> /F
```

**Solution 2** - Use different port:
1. Edit `backend\.env`
2. Change: `BACKEND_PORT=8001`
3. Restart server
4. Access at: http://localhost:8001

---

### Issue: "Failed to install core dependencies"

**Solution**:
1. **Check internet connection**
2. **Update pip**:
   ```cmd
   python -m pip install --upgrade pip
   ```
3. **Try manual install**:
   ```cmd
   cd backend
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements-minimal.txt
   ```

---

### Issue: Cryptography or Pandas won't install

**This is OK!** The system works without them.

**What you lose**:
- No cryptography = No encryption (data stored unencrypted)
- No pandas = Slightly slower for large datasets (>5,000 loans)

**If you really want them**:
- Install Microsoft Visual C++ Build Tools
- Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
- Then re-run `start-windows.bat`

---

## 📊 Using the Application

### 1. Import Sample Data
1. Click "📥 Import CSV" tab
2. Click "Select CSV File"
3. Choose `sample_loans.csv`
4. Click "Import Data"
5. Success! 10 test loans imported

### 2. Create New Loan
1. Click "📝 Data Entry" tab
2. Fill in:
   - **Borrower Name**: e.g., "John Doe"
   - **Amount**: e.g., 100000
   - **Currency**: INR or CAD
   - **Depositor Name**: e.g., "Jane Smith"
   - **Giving Date**: Auto-filled to today
   - **Due Date**: Optional (leave empty for perpetual loan)
3. Click "Create Loan"

### 3. Calculate Commission
1. Click "💰 Commission" tab
2. Select borrower from dropdown
3. Enter:
   - **Interest Rate**: e.g., 12 (for 12% per annum)
   - **Commission Rate**: e.g., 10 (for 10%)
   - **Months**: e.g., 12
4. Click "Calculate Commission"
5. View detailed breakdown
6. Click "Export Commission Report as CSV" to save

### 4. View Reports
1. Click "📈 Reports" tab
2. Click "🔄 Refresh"
3. View statistics and breakdowns
4. Click "Export Report as CSV" to save

---

## 🛑 Stopping the Server

**Method 1**: Press `Ctrl+C` in the command window

**Method 2**: Close the command window

---

## 💾 Backing Up Your Data

Your loan data is stored in:
```
backend\engine_output\loan_records.csv
```

**To backup**:
1. Copy `loan_records.csv` to safe location
2. Or use Windows Backup/OneDrive
3. Recommended: Weekly backups

**To restore**:
1. Copy backed-up `loan_records.csv` to `backend\engine_output\`
2. Restart server

---

## 🔄 Updating LoanTracker

1. **Backup your data** (see above)
2. **Download new version**
3. **Replace files** (keep `backend\engine_output\` folder)
4. **Run** `start-windows.bat`

---

## 📞 Getting Help

### Check Logs
```cmd
type backend\logs\loantracker.log
```

### Common Solutions
1. **Restart server**: Close and re-run `start-windows.bat`
2. **Clear browser cache**: Ctrl+Shift+Delete
3. **Try different browser**: Chrome, Firefox, Edge

### More Help
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- See [README.md](README.md)

---

## ✅ System Requirements

- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.11 or higher
- **RAM**: 512 MB minimum
- **Disk**: 100 MB for application + data
- **Browser**: Chrome, Firefox, or Edge (latest)

---

## 🎯 Quick Reference

| Task | Command/Action |
|------|----------------|
| Start server | Double-click `start-windows.bat` |
| Stop server | Press `Ctrl+C` |
| Access app | http://localhost:8000 |
| View data | Open `backend\engine_output\loan_records.csv` in Excel |
| Check logs | Open `backend\logs\loantracker.log` in Notepad |
| Backup data | Copy `loan_records.csv` |

---

## 🔐 Security Notes

### Data Storage
- Data stored locally on your PC
- Location: `backend\engine_output\`
- Not sent to any external server

### Encryption (Optional)
- Enable by setting `ENCRYPTION_KEY` in `.env`
- Requires cryptography package
- Protects data at rest

### Network Access
- Server binds to `0.0.0.0:8000`
- Accessible from local network
- **For home use**: No action needed
- **For office use**: Check with IT department

---

**Version**: 1.0.0
**Last Updated**: March 2026
**Status**: Production Ready ✅
