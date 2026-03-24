# LoanTracker - Windows User Guide

## 🎯 Quick Start Guide for Windows Users

Welcome to LoanTracker! This guide will help you get started with the Loan Tracker System on your Windows machine.

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

1. **Docker Desktop for Windows** (Recommended for easiest setup)
   - Download from: https://www.docker.com/products/docker-desktop
   - Install and start Docker Desktop
   - Ensure Docker is running (you'll see the Docker icon in your system tray)

**OR (Alternative)**

2. **Python 3.11+** and **Node.js 20+** (For manual installation)
   - Python: https://www.python.org/downloads/
   - Node.js: https://nodejs.org/

---

## 🚀 Option 1: Quick Start with Docker (Recommended)

### Step 1: Download the Project

1. Download the LoanTracker folder to your computer
2. Extract the ZIP file if needed
3. Open **Command Prompt** or **PowerShell** as Administrator

### Step 2: Navigate to Project Directory

```cmd
cd C:\path\to\LoanTracker
```

### Step 3: Configure Your Settings (Optional)

Open the `.env` file in Notepad to customize:

```
STORAGE_TYPE=csv
ENCRYPTION_KEY=
```

- **STORAGE_TYPE**: Keep as `csv` for simple file-based storage
- **ENCRYPTION_KEY**: Leave empty for no encryption, or add a password like `my_secret_key_123` to encrypt your data

### Step 4: Start the Application

```cmd
docker-compose up -d
```

This will:
- Build the Docker image
- Start the LoanTracker application
- Make it available at http://localhost:8000

### Step 5: Access the Application

1. Open your web browser (Chrome, Edge, Firefox)
2. Go to: **http://localhost:8000**
3. You should see the LoanTracker interface!

### Step 6: Stop the Application

When you're done, stop the application:

```cmd
docker-compose down
```

---

## 🛠️ Option 2: Manual Installation (Without Docker)

### Step 1: Install Backend Dependencies

Open Command Prompt and navigate to the backend folder:

```cmd
cd C:\path\to\LoanTracker\backend
pip install -r requirements.txt
```

### Step 2: Install Frontend Dependencies

Open a **new** Command Prompt and navigate to the frontend folder:

```cmd
cd C:\path\to\LoanTracker\frontend
npm install
npm run build
```

### Step 3: Configure Settings

Edit the `.env` file in the root LoanTracker directory (see Step 3 in Docker method above).

### Step 4: Start the Backend Server

In the backend folder:

```cmd
cd C:\path\to\LoanTracker\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Keep this window open!

### Step 5: Access the Application

1. Open your browser
2. Go to: **http://localhost:8000**
3. The application is now running!

### Step 6: Stop the Application

Press `Ctrl+C` in the Command Prompt window where the server is running.

---

## 📖 Using LoanTracker

### Data Entry Tab

1. Click on **"📝 Data Entry"** tab
2. Fill in the loan information:
   - **Borrower Name**: Person/entity borrowing money
   - **Amount**: Loan amount in dollars
   - **Depositor Name**: Person/entity lending money
   - **Giving Date**: When the loan was given
   - **Due Date**: When the loan should be repaid
   - **Borrower Group** (Optional): Category like "Family", "Friends"
   - **Depositor Group** (Optional): Category like "Bank", "Personal"
3. Click **"Create Loan"**
4. You'll see a success message!

### View Loans Tab

1. Click on **"📊 View Loans"** tab
2. See all your loan records in a table
3. You can:
   - **Change Status**: Use the dropdown to mark loans as "Active", "Paid Off", or "Overdue"
   - **Delete**: Click "Delete" button to remove a loan (you'll be asked to confirm)

### Reports Tab

1. Click on **"📈 Reports"** tab
2. View statistics:
   - Total number of loans
   - Total amount across all loans
   - Active, Paid Off, and Overdue counts
   - Summary by Borrower
   - Summary by Depositor

### Changing Themes

- At the top right, you can switch between 4 themes:
  - **Modern**: Clean, contemporary design (default)
  - **Classic**: Traditional blue theme
  - **Dark**: Dark mode for low-light environments
  - **Minimal**: Minimalist black & white design

---

## 📁 Where is My Data Stored?

Your loan data is stored in the `engine_output` folder:

```
C:\path\to\LoanTracker\engine_output\loan_records.csv
```

This CSV file can be opened with:
- **Microsoft Excel**
- **Google Sheets**
- **LibreOffice Calc**
- Any text editor

### Data Format

The CSV contains these columns:
- id
- borrower_name
- amount
- depositor_name
- giving_date
- due_date
- borrower_group
- depositor_group
- status
- created_at
- updated_at

**Note**: If you enabled encryption, the borrower_name and depositor_name columns will be encrypted in the CSV file.

---

## 🔒 Security Features

### Encryption

To enable encryption:

1. Edit `.env` file
2. Set: `ENCRYPTION_KEY=your_strong_password_here`
3. Restart the application
4. Your borrower and depositor names will now be encrypted in the CSV file

**Important**:
- Don't lose your encryption key! You won't be able to read your data without it.
- The encryption key is case-sensitive.

### Backup Your Data

**Recommended**: Regularly backup the `engine_output` folder:

1. Copy `engine_output` folder to a safe location
2. Consider cloud backup (OneDrive, Google Drive, Dropbox)
3. Keep multiple versions (weekly backups)

---

## 🐛 Troubleshooting

### Problem: "Docker is not running"

**Solution**: Start Docker Desktop from the Start Menu

### Problem: "Port 8000 is already in use"

**Solution**: Another application is using port 8000. Either:
1. Stop that application
2. OR change the port in `.env` file: `BACKEND_PORT=8001`

### Problem: "Cannot access http://localhost:8000"

**Solution**:
1. Check if the application is running (`docker ps` in Command Prompt)
2. Try http://127.0.0.1:8000 instead
3. Check Windows Firewall settings

### Problem: "Data not showing up"

**Solution**:
1. Check `engine_output/loan_records.csv` exists
2. Look for errors in logs: `logs/loantracker.log`
3. Try refreshing the browser (F5)

### Problem: "ModuleNotFoundError" or "Package not found"

**Solution**:
1. Reinstall dependencies: `pip install -r backend/requirements.txt`
2. For frontend: `cd frontend && npm install`

---

## 📞 Need Help?

1. Check the log file: `logs/loantracker.log`
2. Review the error messages in the browser console (F12)
3. Ensure all prerequisites are installed correctly

---

## 🎓 Best Practices

1. **Regular Backups**: Backup `engine_output` folder weekly
2. **Use Encryption**: If handling sensitive data, always enable encryption
3. **Descriptive Groups**: Use borrower/depositor groups for better reporting
4. **Status Updates**: Keep loan statuses updated (Active → Paid Off)
5. **Date Accuracy**: Ensure giving and due dates are accurate for proper tracking

---

## 🔄 Updating LoanTracker

When a new version is released:

**With Docker:**
```cmd
docker-compose down
docker-compose pull
docker-compose up -d
```

**Manual Installation:**
```cmd
cd C:\path\to\LoanTracker\backend
pip install -r requirements.txt --upgrade

cd C:\path\to\LoanTracker\frontend
npm install
npm run build
```

---

## 📊 Exporting Data

Your data is already in CSV format in `engine_output/loan_records.csv`!

To analyze in Excel:
1. Open Microsoft Excel
2. File → Open → Navigate to `engine_output/loan_records.csv`
3. The data will be imported as a table
4. You can now create charts, pivot tables, etc.

---

**Version**: 1.0.0
**Last Updated**: March 2026
**Support**: See main README.md for contact information
