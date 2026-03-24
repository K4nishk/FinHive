# LoanTracker - macOS User Guide

## 🎯 Quick Start Guide for Mac Users

Welcome to LoanTracker! This guide will help you get started with the Loan Tracker System on your Mac.

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

1. **Docker Desktop for Mac** (Recommended for easiest setup)
   - Download from: https://www.docker.com/products/docker-desktop
   - Install and start Docker Desktop
   - Ensure Docker is running (you'll see the Docker icon in your menu bar)

**OR (Alternative)**

2. **Python 3.11+** and **Node.js 20+** (For manual installation)
   - Python: `brew install python@3.11` (if you have Homebrew)
   - Node.js: `brew install node@20`
   - Or download from official websites

---

## 🚀 Option 1: Quick Start with Docker (Recommended)

### Step 1: Download the Project

1. Download the LoanTracker folder to your computer
2. Extract the ZIP file if needed
3. Open **Terminal** (Applications → Utilities → Terminal)

### Step 2: Navigate to Project Directory

```bash
cd ~/Downloads/LoanTracker
# Or wherever you extracted the folder
```

### Step 3: Configure Your Settings (Optional)

Open the `.env` file in a text editor:

```bash
open -a TextEdit .env
```

Customize these settings:

```
STORAGE_TYPE=csv
ENCRYPTION_KEY=
```

- **STORAGE_TYPE**: Keep as `csv` for simple file-based storage
- **ENCRYPTION_KEY**: Leave empty for no encryption, or add a password like `my_secret_key_123` to encrypt your data

### Step 4: Start the Application

```bash
docker-compose up -d
```

This will:
- Build the Docker image (first time may take a few minutes)
- Start the LoanTracker application
- Make it available at http://localhost:8000

You'll see output like:
```
Creating loantracker ... done
```

### Step 5: Access the Application

1. Open your web browser (Safari, Chrome, Firefox)
2. Go to: **http://localhost:8000**
3. You should see the LoanTracker interface!

### Step 6: Check Status

To verify the application is running:

```bash
docker-compose ps
```

You should see:
```
    Name                  Command             State           Ports
---------------------------------------------------------------------------
loantracker   python -m uvicorn ...         Up      0.0.0.0:8000->8000/tcp
```

### Step 7: View Logs (if needed)

```bash
docker-compose logs -f
```

Press `Ctrl+C` to stop viewing logs.

### Step 8: Stop the Application

When you're done:

```bash
docker-compose down
```

---

## 🛠️ Option 2: Manual Installation (Without Docker)

### Step 1: Install Backend Dependencies

Open Terminal and navigate to the backend folder:

```bash
cd ~/Downloads/LoanTracker/backend
pip3 install -r requirements.txt
```

If you get permission errors, try:
```bash
pip3 install --user -r requirements.txt
```

### Step 2: Install Frontend Dependencies

Open a **new** Terminal tab (⌘+T) and navigate to the frontend folder:

```bash
cd ~/Downloads/LoanTracker/frontend
npm install
npm run build
```

### Step 3: Configure Settings

Edit the `.env` file in the root LoanTracker directory:

```bash
cd ~/Downloads/LoanTracker
nano .env
```

Or use TextEdit:
```bash
open -a TextEdit .env
```

### Step 4: Start the Backend Server

In the backend Terminal tab:

```bash
cd ~/Downloads/LoanTracker/backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Keep this terminal window open!

### Step 5: Access the Application

1. Open your browser
2. Go to: **http://localhost:8000**
3. The application is now running!

### Step 6: Stop the Application

Press `Ctrl+C` in the Terminal window where the server is running.

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
~/Downloads/LoanTracker/engine_output/loan_records.csv
```

### Finding Your Data

In Finder:
1. Open Finder
2. Navigate to LoanTracker folder
3. Open `engine_output` folder
4. You'll see `loan_records.csv`

In Terminal:
```bash
open ~/Downloads/LoanTracker/engine_output
```

This CSV file can be opened with:
- **Microsoft Excel** for Mac
- **Numbers** (Apple's spreadsheet app)
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

1. Edit `.env` file:
   ```bash
   nano .env
   ```
   Or:
   ```bash
   open -a TextEdit .env
   ```

2. Set: `ENCRYPTION_KEY=your_strong_password_here`

3. Restart the application:
   ```bash
   docker-compose restart
   ```
   Or stop/start the Python server if running manually

4. Your borrower and depositor names will now be encrypted in the CSV file

**Important**:
- Don't lose your encryption key! You won't be able to read your data without it.
- The encryption key is case-sensitive.
- Store your key in a secure password manager (1Password, LastPass, etc.)

### Backup Your Data

**Recommended**: Regularly backup the `engine_output` folder:

1. Copy `engine_output` folder to a safe location:
   ```bash
   cp -r ~/Downloads/LoanTracker/engine_output ~/Documents/LoanTracker_Backup_$(date +%Y%m%d)
   ```

2. Consider cloud backup (iCloud Drive, Google Drive, Dropbox)

3. Time Machine will automatically backup the folder

---

## 🐛 Troubleshooting

### Problem: "Docker is not running"

**Solution**:
1. Open Docker Desktop from Applications
2. Wait for Docker to fully start (icon in menu bar should not be animated)

### Problem: "Permission denied"

**Solution**:
```bash
sudo chown -R $USER ~/Downloads/LoanTracker
chmod -R 755 ~/Downloads/LoanTracker
```

### Problem: "Port 8000 is already in use"

**Solution**: Find and stop the process using port 8000:

```bash
lsof -ti:8000 | xargs kill -9
```

Or change the port in `.env` file: `BACKEND_PORT=8001`

### Problem: "Cannot access http://localhost:8000"

**Solution**:
1. Check if the application is running:
   ```bash
   docker-compose ps
   ```
   Or check if Python is running:
   ```bash
   ps aux | grep uvicorn
   ```

2. Try http://127.0.0.1:8000 instead

3. Check firewall settings in System Preferences → Security & Privacy → Firewall

### Problem: "Data not showing up"

**Solution**:
1. Check if CSV file exists:
   ```bash
   ls -la ~/Downloads/LoanTracker/engine_output/
   ```

2. Look for errors in logs:
   ```bash
   tail -f ~/Downloads/LoanTracker/logs/loantracker.log
   ```

3. Try refreshing the browser (⌘+R)

### Problem: "ModuleNotFoundError" or "Package not found"

**Solution**:
1. Reinstall Python dependencies:
   ```bash
   pip3 install --user -r backend/requirements.txt
   ```

2. For frontend:
   ```bash
   cd frontend && npm install
   ```

### Problem: "command not found: docker-compose"

**Solution**:
Docker Desktop includes docker-compose. Ensure Docker Desktop is:
1. Installed
2. Running
3. Try `docker compose` (without hyphen) instead - newer Docker Desktop versions use this

---

## 📞 Need Help?

1. Check the log file:
   ```bash
   tail -f logs/loantracker.log
   ```

2. Review browser console errors:
   - Safari: Develop → Show JavaScript Console
   - Chrome: View → Developer → JavaScript Console (⌥⌘J)

3. Ensure all prerequisites are installed correctly

---

## 🎓 Best Practices

1. **Regular Backups**: Create weekly backups using Time Machine or manual copies
2. **Use Encryption**: If handling sensitive data, always enable encryption
3. **Descriptive Groups**: Use borrower/depositor groups for better reporting
4. **Status Updates**: Keep loan statuses updated (Active → Paid Off)
5. **Date Accuracy**: Ensure giving and due dates are accurate for proper tracking

---

## 🔄 Updating LoanTracker

When a new version is released:

**With Docker:**
```bash
docker-compose down
docker-compose pull
docker-compose up -d
```

**Manual Installation:**
```bash
cd ~/Downloads/LoanTracker/backend
pip3 install -r requirements.txt --upgrade

cd ~/Downloads/LoanTracker/frontend
npm install
npm run build
```

---

## 📊 Exporting and Analyzing Data

Your data is already in CSV format in `engine_output/loan_records.csv`!

### Open in Excel (Mac)

1. Open Microsoft Excel
2. File → Open → Navigate to `engine_output/loan_records.csv`
3. The data will be imported as a table
4. You can now create charts, pivot tables, etc.

### Open in Numbers (Apple)

1. Right-click on `loan_records.csv` in Finder
2. Open With → Numbers
3. The data will be imported
4. Create charts and analyze your data

### Import to Google Sheets

1. Open Google Sheets
2. File → Import → Upload
3. Select `loan_records.csv`
4. Choose import options and click "Import data"

---

## 🚀 Advanced: Running on Startup (Optional)

To automatically start LoanTracker when you log in:

### Create a LaunchAgent

1. Create a plist file:
   ```bash
   nano ~/Library/LaunchAgents/com.loantracker.app.plist
   ```

2. Add this content:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.loantracker.app</string>
       <key>ProgramArguments</key>
       <array>
           <string>/usr/local/bin/docker-compose</string>
           <string>-f</string>
           <string>/Users/YOUR_USERNAME/Downloads/LoanTracker/docker-compose.yml</string>
           <string>up</string>
           <string>-d</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
   </dict>
   </plist>
   ```

3. Replace `YOUR_USERNAME` with your Mac username

4. Load the agent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.loantracker.app.plist
   ```

---

## 🎬 Quick Demo Walkthrough

### 5-Minute Test Run

1. **Start the app**: `docker-compose up -d`
2. **Open browser**: Go to http://localhost:8000
3. **Create a loan**:
   - Tab: Data Entry
   - Borrower: "John Doe"
   - Amount: 5000
   - Depositor: "Jane Smith"
   - Giving Date: Today
   - Due Date: 30 days from now
   - Click "Create Loan"
4. **View the loan**: Switch to "View Loans" tab
5. **Check CSV**: Open `engine_output/loan_records.csv` in Excel/Numbers
6. **View reports**: Click "Reports" tab to see statistics
7. **Try themes**: Change theme at the top right
8. **Stop the app**: `docker-compose down`

---

**Version**: 1.0.0
**Last Updated**: March 2026
**Platform**: macOS Monterey and later recommended
**Support**: See main README.md for contact information
