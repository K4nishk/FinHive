# 🎬 LoanTracker Demo Guide

**Quick demonstration of all features in 10 minutes**

---

## 📋 Prerequisites

- LoanTracker running on http://localhost:8000
- Sample data file: `sample_loans.csv` (included in project)

**Not started yet?** See [USER_GUIDE_MAC.md](USER_GUIDE_MAC.md) or [USER_GUIDE_WINDOWS.md](USER_GUIDE_WINDOWS.md)

---

## 🚀 Demo Flow (10 Minutes)

### Step 1: Overview & UI Themes (1 minute)

1. **Open browser**: http://localhost:8000
2. **Show 6 tabs**: Data Entry, View Loans, Reports, Commission, Import CSV, Config
3. **Demo themes**: Click theme buttons in header
   - Modern (default - blue gradient)
   - Classic (green/professional)
   - Dark (dark mode)
   - Minimal (clean white)

---

### Step 2: Import Sample Data (2 minutes)

1. **Click "📥 Import CSV" tab**
2. **Upload file**: Click "Select CSV File" → Choose `sample_loans.csv`
3. **Preview data**: Shows first 5 rows
   - 10 sample loans
   - Mix of businesses and individuals
   - Various due dates and groups
4. **Click "Import Data"** button
5. **Wait for confirmation**: "Import complete! 10 loans imported, 0 failed."

**Result**: Database now has 10 test loans to work with

---

### Step 3: View All Loans (1 minute)

1. **Click "📊 View Loans" tab**
2. **Show table features**:
   - All 10 imported loans displayed
   - Sortable columns
   - Status indicators (active/overdue/paid_off)
   - Due dates (some show "No due date" for 1970-01-01)
3. **Change loan status**:
   - Select dropdown next to any loan
   - Change status to "Paid Off"
   - Click "Update" button
   - Notice status badge updates immediately

---

### Step 4: Create New Loan (2 minutes)

1. **Click "📝 Data Entry" tab**
2. **Fill out form**:
   ```
   Borrower Name: Demo User
   Amount: 5000
   Depositor Name: Your Bank
   Giving Date: (auto-filled to today)
   Due Date: (leave empty - optional!)
   Borrower Group: Demo
   Depositor Group: Bank
   ```
3. **Click "Create Loan"** button
4. **Verify success**: Green success message appears
5. **Check View Loans** tab: New loan appears in table

**Key Point**: Show that due_date is optional - defaults to 1970-01-01

---

### Step 5: Reports & Statistics (2 minutes)

1. **Click "📈 Reports" tab**
2. **Click "🔄 Refresh"** button
3. **Show statistics cards**:
   - Total Loans: 11 (10 imported + 1 created)
   - Total Amount: ~$293,000
   - Active Loans, Paid Off, Overdue counts
4. **Show breakdown tables**:
   - By Borrower: Shows counts and totals
   - By Depositor: Shows funding sources
5. **Export Report**:
   - Click "📥 Export Report as CSV" button
   - File downloads: `loantracker_report_YYYY-MM-DD.csv`
   - Open in Excel: Shows all data formatted nicely

---

### Step 6: Commission Calculator (3 minutes)

1. **Click "💰 Commission" tab**
2. **Show dropdown populated**:
   - Notice dropdown has borrower names from imported data
   - Organized in sections: "By Borrower Name" and "By Borrower Group"
3. **Calculate commission for individual**:
   ```
   Select Borrower/Group: John Doe
   Interest Rate: 12 (12% per annum)
   Commission Rate: 10 (10% of interest)
   Number of Months: 12
   ```
4. **Click "Calculate Commission"**
5. **Show results table**:
   - Individual loan breakdown
   - Loan ID, Amount, Monthly Interest, Commission/Month
   - Summary totals at bottom
   - **Total Commission highlighted in green**
6. **Export commission report**:
   - Click "📥 Export Commission Report as CSV"
   - File downloads with borrower name in filename
   - Open to show calculation details

**Business Value**: Show how this helps track broker earnings

---

### Step 7: Calculate Group Commission (1 minute)

1. **Still in Commission tab**
2. **Select by group**:
   ```
   Select Borrower/Group: Business (Group)
   Interest Rate: 15
   Commission Rate: 8
   Number of Months: 6
   ```
3. **Calculate**: Shows all loans in "Business" group aggregated
4. **Highlight**: Total commission for entire group

**Key Point**: One calculation covers multiple borrowers in same category

---

### Step 8: System Configuration (30 seconds)

1. **Click "⚙️ Config" tab**
2. **Show settings**:
   - Storage Type: CSV
   - Encryption: Enabled/Disabled status
   - CSV Output Directory location
   - App Version
3. **Show data locations**: Where files are stored

---

## 🎯 Key Features to Emphasize

### 1. **Zero-Friction Setup**
- No complex configuration
- Works without optional dependencies
- Clear error messages if issues occur

### 2. **Flexible Data Entry**
- Due date is optional (defaults to 1970-01-01)
- Groups are optional for categorization
- Excel-compatible CSV storage

### 3. **Business Value**
- **Commission Calculator**: Track broker earnings automatically
- **5 Report Types**: Filter by name, group, date range
- **CSV Export**: One-click exports for accounting

### 4. **User Experience**
- 4 beautiful themes
- Real-time updates
- Smooth tab navigation (auto-scrolls to content)
- Clear success/error messages

### 5. **Production-Ready**
- Graceful dependency handling
- Audit logging
- Optional encryption
- Docker deployment ready

---

## 📊 Sample Commission Calculation (Talking Points)

**Scenario**: John Doe has 1 loan of $10,000

```
Interest Rate: 12% per annum
Commission Rate: 10%
Period: 12 months

Monthly Interest = $10,000 × (12% / 12) = $100/month
Commission = $100 × 10% = $10/month
Total for 12 months = $10 × 12 = $120

Result: You earn $120 in commissions over 1 year on this loan
```

**For Business Group**: Aggregate all business loans and calculate total commission across entire portfolio.

---

## 🔄 Demo Reset (If Needed)

To reset and start fresh demo:

```bash
# Stop server (Ctrl+C)

# Delete data file
rm backend/engine_output/loan_records.csv

# Restart server
./start-dev.sh

# Re-import sample_loans.csv
```

---

## 💡 Demo Tips

### Opening
- "LoanTracker is a complete loan management system for small businesses and individuals"
- "Let me show you how easy it is to manage loans and calculate commissions"

### During Import
- "Notice it handles missing due dates gracefully - perfect for perpetual loans"
- "You can import years of historical data in seconds"

### During Commission Calc
- "This is especially valuable for brokers who need to track commission earnings"
- "Calculate for individuals or entire groups with one click"

### Closing
- "Everything is stored locally - your data stays private"
- "Export to CSV anytime for accounting or analysis"
- "Production-ready with Docker deployment included"

---

## 📸 Screenshot Checklist

For documentation or presentations, capture:

- [ ] Home page with Modern theme
- [ ] All 4 themes displayed
- [ ] Import CSV preview screen
- [ ] View Loans table with data
- [ ] Reports with statistics
- [ ] Commission calculator results
- [ ] Export buttons and CSV download

---

## ❓ Common Demo Questions

### Q: "What if I don't know the due date?"
**A**: Leave it empty! The system defaults to 1970-01-01, which displays as "No due date". Perfect for on-demand loans.

### Q: "Can I export data for my accountant?"
**A**: Yes! Two export types:
1. Complete report with all loans
2. Commission report with detailed calculations

### Q: "What happens if cryptography isn't installed?"
**A**: System works perfectly! Encryption is optional and gracefully disabled with clear messaging.

### Q: "How do I track commissions for multiple borrowers?"
**A**: Use groups! Assign borrowers to groups (Family, Business, etc.), then calculate commission for entire group.

### Q: "Is my data safe?"
**A**: Yes! All data stored locally on your machine. Optional AES-256 encryption available.

---

## 🎬 Quick 2-Minute Speed Demo

If short on time:

1. **Show themes** (20 seconds)
2. **Import sample_loans.csv** (30 seconds)
3. **View Reports** with statistics (30 seconds)
4. **Calculate commission** for one borrower (40 seconds)

Total: 2 minutes to show core value

---

## ✅ Demo Checklist

Before starting demo:

- [ ] Server running on http://localhost:8000
- [ ] sample_loans.csv file ready
- [ ] Browser open and ready
- [ ] Screen sharing/projection working
- [ ] Backup plan if internet needed (it's not!)

During demo:

- [ ] Show all 6 tabs
- [ ] Demo at least 2 themes
- [ ] Import sample data
- [ ] Create 1 new loan
- [ ] Calculate commission for individual
- [ ] Export at least one report
- [ ] Show configuration

After demo:

- [ ] Offer to send documentation links
- [ ] Explain deployment options (Docker, standalone)
- [ ] Answer questions about customization

---

**Demo Duration**: 10 minutes (full) | 2 minutes (speed demo)

**Audience**: Business owners, brokers, financial managers, individual lenders

**Key Takeaway**: "Manage loans and calculate commissions with zero complexity"
