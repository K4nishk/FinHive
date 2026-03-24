# 🚀 LoanTracker - Quick Start Guide

**Version**: 1.0.1
**Last Updated**: March 8, 2026

---

## ⚡ Quick Start (3 Steps)

### 1. Prerequisites

- **Python 3.8+** installed
- **Terminal/Command Prompt** access

### 2. Run the Application

**On Mac/Linux**:
```bash
./start-dev.sh
```

**On Windows**:
```batch
start-windows.bat
```

### 3. Access the Application

Open your browser and go to:
```
http://localhost:8000
```

**That's it!** 🎉 LoanTracker is now running.

---

## 📝 Basic Usage

### Create Your First Loan

1. Click **"Data Entry"** tab
2. Fill in the form:
   - Borrower Name *
   - Amount (in ₹) *
   - Depositor Name *
   - Giving Date *
   - Due Date (optional)
3. Click **"Add Loan"**

### View All Loans

1. Click **"View Loans"** tab
2. See all your loans in a table
3. Update status or delete as needed

### Calculate Interest

1. Click **"Interest Calculator"** tab
2. Select borrower/group
3. Enter interest rate and commission rate
4. Enter number of months
5. Click **"Calculate Interest"**

---

## 📚 Additional Resources

- **Full Documentation**: See `docs/` folder
- **User Guides**: See `guides/` folder
  - [Mac User Guide](guides/USER_GUIDE_MAC.md)
  - [Windows User Guide](guides/USER_GUIDE_WINDOWS.md)
  - [Demo Guide](guides/DEMO_GUIDE.md)
  - [Troubleshooting](guides/TROUBLESHOOTING.md)
- **Version Updates**: See `references/mvp1/updates/` folder
- **Testing**: See `testing/` folder

---

## 🔧 Troubleshooting

### Application won't start?

**Check Python version**:
```bash
python3 --version  # Should be 3.8 or higher
```

**Port already in use?**:
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9  # Mac/Linux
netstat -ano | findstr :8000   # Windows
```

### Can't create loans (422 error)?

- Clear browser cache: Ctrl+Shift+Delete (Cmd+Shift+Delete on Mac)
- Hard refresh: Ctrl+F5 (Cmd+Shift+R on Mac)
- Restart the application

### More help?

See [Troubleshooting Guide](guides/TROUBLESHOOTING.md) for detailed solutions.

---

## 🎯 Key Features

- ✅ **Loan Management**: Create, view, update, delete loans
- ✅ **Interest Calculator**: Calculate interest and commission by borrower/group
- ✅ **Reports**: Statistics dashboard and detailed reports
- ✅ **CSV Import/Export**: Bulk import and export loan data
- ✅ **Status Tracking**: Auto-calculate loan status (active/overdue/paid_off)
- ✅ **Indian Currency**: All amounts in INR (₹) with proper formatting

---

## 📦 What's New in v1.0.1

- Fixed 422 error when creating loans
- All currency now INR only (₹)
- Added Serial Number (SNo) in YYYY/xxx format
- Renamed "Commission" to "Interest Calculator"
- Enhanced Interest Calculator report format
- Improved documentation organization

See [Latest Changes](references/mvp1/updates/LATEST_CHANGES.md) for details.

---

## ⚠️ Important Notes

- **No Docker required**: Use start-dev.sh or start-windows.bat
- **Data stored in**: `backend/engine_output/loan_records.csv`
- **Backup recommended**: Copy `loan_records.csv` regularly
- **Currency**: All amounts are in INR (₹) only

---

## 🆘 Need Help?

- **Technical Issues**: See [Troubleshooting Guide](guides/TROUBLESHOOTING.md)
- **Feature Questions**: See [Business Requirements](docs/04-business-requirements.md)
- **Demo Guide**: See [Demo Guide](guides/DEMO_GUIDE.md)

---

**Happy Tracking!** 💰
