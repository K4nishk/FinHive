// LoanTracker Frontend JavaScript
const API_BASE = '/api/v1';
let allLoans = []; // Cache for commission calculator

// Generate Serial Number in YYYY/xxx format
function generateSNo(index, givingDate) {
    const year = new Date(givingDate).getFullYear();
    const counter = String(index + 1).padStart(3, '0');
    return `${year}/${counter}`;
}

// Initialize application
window.addEventListener('DOMContentLoaded', () => {
    // Set today's date as default for giving_date
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('giving_date').value = today;

    // Set today's date as default for month_filter (date picker) in Interest Calculator
    const monthFilterInput = document.getElementById('month_filter');
    if (monthFilterInput) {
        monthFilterInput.value = today; // Use same 'today' variable from above
    }

    // Load initial data
    loadLoans();
    loadStatistics();
    loadConfig();
    loadBorrowerOptions(); // For commission calculator

    // Initialize action button handlers (one-time setup)
    initializeActionHandlers();
});

// Tab Management - FIXED: Proper tab switching
function showTab(tabName) {
    // Close any open modals when switching tabs
    closeModal();

    // Hide all tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });

    // Remove active from all tabs
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));

    // Show selected tab content
    const selectedContent = document.getElementById(tabName);
    if (selectedContent) {
        selectedContent.classList.add('active');
        selectedContent.style.display = 'block';

        // Scroll to top of content
        selectedContent.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Mark tab as active
    event.target.classList.add('active');

    // Reload data when switching tabs
    if (tabName === 'view-loans') loadLoans();
    if (tabName === 'reports') loadStatistics();
    if (tabName === 'config') loadConfig();
    if (tabName === 'commission') loadBorrowerOptions();
}

// API Functions
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        }

        return await response.json();
    } catch (error) {
        showError(error.message);
        throw error;
    }
}

// Create Loan - FIXED: Handle optional due_date, currency hardcoded to INR
async function createLoan(event) {
    event.preventDefault();

    const dueDateValue = document.getElementById('due_date').value;

    const formData = {
        borrower_name: document.getElementById('borrower_name').value,
        amount: parseFloat(document.getElementById('amount').value),
        currency: 'INR', // Always INR per business requirements
        depositor_name: document.getElementById('depositor_name').value,
        giving_date: document.getElementById('giving_date').value,
        due_date: dueDateValue || '1970-01-01', // Default to 1970-01-01 if empty
        borrower_group: document.getElementById('borrower_group').value || null,
        depositor_group: document.getElementById('depositor_group').value || null
    };

    try {
        await apiCall('/loans/', {
            method: 'POST',
            body: JSON.stringify(formData)
        });

        showSuccess('Loan created successfully!');
        document.getElementById('loan-form').reset();

        // Reset giving_date to today
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('giving_date').value = today;

        // Reload data
        loadLoans();
        loadBorrowerOptions();
    } catch (error) {
        console.error('Failed to create loan:', error);
    }
}

// Load Loans
async function loadLoans() {
    try {
        const loans = await apiCall('/loans/');
        allLoans = loans; // Cache for commission calculator
        displayLoans(loans);
    } catch (error) {
        console.error('Failed to load loans:', error);
    }
}

// Sort state for View Loans table
let viewLoansSortConfig = {
    key: null,
    direction: 'asc' // 'asc' or 'desc'
};

// Display Loans Table
function displayLoans(loans) {
    const container = document.getElementById('loans-table-container');

    if (loans.length === 0) {
        container.innerHTML = '<div class="empty-state"><h3>No loans found</h3><p>Create your first loan using the Data Entry tab</p></div>';
        return;
    }

    // Apply sorting if sort config is set
    const sortedLoans = sortLoans([...loans], viewLoansSortConfig);

    let html = '<div class="table-container"><table><thead><tr>';
    html += '<th>SNo</th>';
    html += createSortableHeader('borrower_name', 'Borrower Name');
    html += createSortableHeader('borrower_group', 'Borrower Group');
    html += '<th>Amount</th><th>Currency</th>';
    html += createSortableHeader('depositor_name', 'Depositor Name');
    html += createSortableHeader('depositor_group', 'Depositor Group');
    html += createSortableHeader('giving_date', 'Giving Date');
    html += createSortableHeader('due_date', 'Due Date');
    html += '<th>Status</th><th>Actions</th>';
    html += '</tr></thead><tbody>';

    sortedLoans.forEach((loan, index) => {
        const sno = generateSNo(index, loan.giving_date);
        const currencySymbol = '₹'; // Always INR
        const formattedAmount = parseFloat(loan.amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});

        html += '<tr>';
        html += `<td>${sno}</td>`;
        // Editable: Borrower Name
        html += `<td class="editable-cell" onclick="makeEditable(this, '${loan.id}', 'borrower_name', 'text')" title="Click to edit">${loan.borrower_name}</td>`;
        // Editable: Borrower Group
        html += `<td class="editable-cell" onclick="makeEditable(this, '${loan.id}', 'borrower_group', 'text')" title="Click to edit">${loan.borrower_group || '-'}</td>`;
        // Editable: Amount
        html += `<td class="editable-cell" onclick="makeEditable(this, '${loan.id}', 'amount', 'number')" title="Click to edit" data-raw-value="${loan.amount}">${currencySymbol}${formattedAmount}</td>`;
        html += `<td><span class="currency-badge">${loan.currency || 'INR'}</span></td>`;
        // Editable: Depositor Name
        html += `<td class="editable-cell" onclick="makeEditable(this, '${loan.id}', 'depositor_name', 'text')" title="Click to edit">${loan.depositor_name}</td>`;
        // Editable: Depositor Group
        html += `<td class="editable-cell" onclick="makeEditable(this, '${loan.id}', 'depositor_group', 'text')" title="Click to edit">${loan.depositor_group || '-'}</td>`;
        // Editable: Giving Date
        html += `<td class="editable-cell" onclick="makeEditable(this, '${loan.id}', 'giving_date', 'date')" title="Click to edit" data-raw-value="${loan.giving_date}">${formatDate(loan.giving_date)}</td>`;
        // Editable: Due Date
        html += `<td class="editable-cell" onclick="makeEditable(this, '${loan.id}', 'due_date', 'date')" title="Click to edit" data-raw-value="${loan.due_date}">${formatDueDate(loan.due_date)}</td>`;
        html += `<td><span class="status-badge status-${loan.status}">${formatStatus(loan.status)}</span></td>`;
        html += '<td class="actions-cell">';
        html += `<button class="icon-button action-paid-off" data-loan-id="${loan.id}" title="Mark as Paid Off">💰 Paid Off</button> `;
        html += `<button class="icon-button action-extend" data-loan-id="${loan.id}" title="Extend Loan">📅 Extend</button> `;
        html += `<button class="icon-button button-danger action-delete" data-loan-id="${loan.id}" title="Delete Loan">🗑️ Delete</button>`;
        html += '</td>';
        html += '</tr>';
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}

// Initialize action button handlers (called once on page load)
function initializeActionHandlers() {
    const container = document.getElementById('loans-table-container');
    if (!container) return;

    // Use event delegation for action buttons
    container.addEventListener('click', (e) => {
        const target = e.target.closest('button');
        if (!target) return;

        const loanId = target.getAttribute('data-loan-id');
        if (!loanId) return;

        if (target.classList.contains('action-paid-off')) {
            showPaidOffPopup(loanId);
        } else if (target.classList.contains('action-extend')) {
            showExtendPopup(loanId);
        } else if (target.classList.contains('action-delete')) {
            deleteLoan(loanId);
        }
    });
}

// Create sortable table header
function createSortableHeader(key, label) {
    const isActive = viewLoansSortConfig.key === key;
    const direction = isActive ? viewLoansSortConfig.direction : 'asc';
    const arrow = isActive ? (direction === 'asc' ? ' ▲' : ' ▼') : '';

    return `<th class="sortable-header" onclick="handleSort('${key}')">${label}${arrow}</th>`;
}

// Handle sort when column header is clicked
function handleSort(key) {
    if (viewLoansSortConfig.key === key) {
        // Toggle direction if same column
        viewLoansSortConfig.direction = viewLoansSortConfig.direction === 'asc' ? 'desc' : 'asc';
    } else {
        // New column, start with ascending
        viewLoansSortConfig.key = key;
        viewLoansSortConfig.direction = 'asc';
    }

    // Re-render with sorted data
    displayLoans(allLoans);
}

// Sort loans based on sort config
function sortLoans(loans, sortConfig) {
    if (!sortConfig.key) {
        return loans; // No sorting
    }

    return loans.sort((a, b) => {
        let aVal = a[sortConfig.key];
        let bVal = b[sortConfig.key];

        // Handle null/undefined values - push to end
        if (aVal === null || aVal === undefined || aVal === '') {
            return 1;
        }
        if (bVal === null || bVal === undefined || bVal === '') {
            return -1;
        }

        // Date sorting
        if (sortConfig.key === 'giving_date' || sortConfig.key === 'due_date') {
            // Handle special 1970-01-01 date (no due date)
            if (sortConfig.key === 'due_date') {
                if (aVal === '1970-01-01') return 1;
                if (bVal === '1970-01-01') return -1;
            }

            const dateA = new Date(aVal);
            const dateB = new Date(bVal);
            return sortConfig.direction === 'asc'
                ? dateA - dateB
                : dateB - dateA;
        }

        // String sorting (case-insensitive)
        const strA = String(aVal).toLowerCase();
        const strB = String(bVal).toLowerCase();

        if (strA < strB) {
            return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (strA > strB) {
            return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
    });
}

// Inline Editing Functionality
let currentlyEditingCell = null;

function makeEditable(cell, loanId, fieldName, inputType) {
    // Prevent multiple simultaneous edits
    if (currentlyEditingCell && currentlyEditingCell !== cell) {
        return;
    }

    currentlyEditingCell = cell;
    const originalValue = cell.getAttribute('data-raw-value') || cell.textContent.trim();
    const displayValue = cell.textContent.trim();

    // Get the actual value for editing
    let editValue = originalValue;
    if (fieldName === 'amount') {
        // Remove currency symbol and formatting for amount
        editValue = originalValue;
    } else if (fieldName === 'borrower_group' || fieldName === 'depositor_group') {
        // Handle optional fields - convert '-' to empty string
        editValue = displayValue === '-' ? '' : displayValue;
    }

    // Create input element
    const input = document.createElement('input');
    input.type = inputType;
    input.value = editValue;
    input.className = 'inline-edit-input';

    if (inputType === 'number') {
        input.step = '0.01';
        input.min = '0';
    }

    // Replace cell content with input
    cell.textContent = '';
    cell.appendChild(input);
    cell.classList.add('editing');
    input.focus();
    input.select();

    // Save on blur
    input.addEventListener('blur', async () => {
        await saveEdit(cell, loanId, fieldName, input.value, originalValue, displayValue);
    });

    // Save on Enter, cancel on Escape
    input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            await saveEdit(cell, loanId, fieldName, input.value, originalValue, displayValue);
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancelEdit(cell, displayValue);
        }
    });
}

async function saveEdit(cell, loanId, fieldName, newValue, originalValue, displayValue) {
    if (!currentlyEditingCell) return; // Already saved or cancelled

    currentlyEditingCell = null;
    cell.classList.remove('editing');

    // Normalize empty values for optional fields
    if ((fieldName === 'borrower_group' || fieldName === 'depositor_group') && newValue.trim() === '') {
        newValue = null;
    }

    // Validate
    const validation = validateField(fieldName, newValue, loanId);
    if (!validation.valid) {
        showError(validation.error);
        cell.textContent = displayValue;
        return;
    }

    // Check if value actually changed
    const normalizedOldValue = (fieldName === 'borrower_group' || fieldName === 'depositor_group') && displayValue === '-' ? null : originalValue;
    if (newValue === normalizedOldValue || newValue === originalValue) {
        // No change, just restore display
        cell.textContent = displayValue;
        return;
    }

    // Show loading state
    cell.textContent = 'Saving...';
    cell.classList.add('saving');

    try {
        // Prepare update payload
        const updateData = {};
        if (fieldName === 'amount') {
            updateData[fieldName] = parseFloat(newValue);
        } else {
            updateData[fieldName] = newValue;
        }

        // Send PATCH request
        await apiCall(`/loans/${loanId}`, {
            method: 'PATCH',
            body: JSON.stringify(updateData)
        });

        // Update local data
        const loanIndex = allLoans.findIndex(l => l.id === loanId);
        if (loanIndex !== -1) {
            allLoans[loanIndex][fieldName] = newValue;
        }

        // Show success animation
        cell.classList.remove('saving');
        cell.classList.add('save-success');
        setTimeout(() => cell.classList.remove('save-success'), 1000);

        // Reload table to show updated formatting
        displayLoans(allLoans);
        showSuccess(`${fieldName.replace('_', ' ')} updated successfully`);

    } catch (error) {
        console.error('Failed to update loan:', error);
        cell.classList.remove('saving');
        cell.classList.add('save-error');
        showError(`Failed to update ${fieldName.replace('_', ' ')}`);

        // Revert to original value
        setTimeout(() => {
            cell.classList.remove('save-error');
            cell.textContent = displayValue;
        }, 2000);
    }
}

function cancelEdit(cell, originalDisplayValue) {
    currentlyEditingCell = null;
    cell.classList.remove('editing');
    cell.textContent = originalDisplayValue;
}

function validateField(fieldName, value, loanId) {
    // Amount validation
    if (fieldName === 'amount') {
        const amount = parseFloat(value);
        if (isNaN(amount) || amount <= 0) {
            return { valid: false, error: 'Amount must be greater than 0' };
        }
        if (!/^\d+(\.\d{1,2})?$/.test(value)) {
            return { valid: false, error: 'Amount can have maximum 2 decimal places' };
        }
    }

    // Name validation (required fields)
    if (fieldName === 'borrower_name' || fieldName === 'depositor_name') {
        if (!value || value.trim() === '') {
            return { valid: false, error: `${fieldName.replace('_', ' ')} is required` };
        }
        if (value.length > 200) {
            return { valid: false, error: `${fieldName.replace('_', ' ')} must be 200 characters or less` };
        }
    }

    // Group validation (optional fields)
    if (fieldName === 'borrower_group' || fieldName === 'depositor_group') {
        if (value && value.length > 100) {
            return { valid: false, error: `${fieldName.replace('_', ' ')} must be 100 characters or less` };
        }
    }

    // Date validation
    if (fieldName === 'giving_date' || fieldName === 'due_date') {
        if (!value || value === '') {
            return { valid: false, error: 'Date is required' };
        }

        const datePattern = /^\d{4}-\d{2}-\d{2}$/;
        if (!datePattern.test(value)) {
            return { valid: false, error: 'Invalid date format (use YYYY-MM-DD)' };
        }

        // Special case: 1970-01-01 is allowed for due_date (no due date)
        if (fieldName === 'due_date' && value === '1970-01-01') {
            return { valid: true };
        }

        // Validate that due_date >= giving_date (if both are available)
        if (fieldName === 'due_date') {
            const loan = allLoans.find(l => l.id === loanId);
            if (loan && loan.giving_date && value !== '1970-01-01') {
                const givingDate = new Date(loan.giving_date);
                const dueDate = new Date(value);
                if (dueDate < givingDate) {
                    return { valid: false, error: 'Due date cannot be before giving date' };
                }
            }
        }
    }

    return { valid: true };
}

// Update Loan Status
async function updateLoanStatus(loanId, newStatus) {
    try {
        await apiCall(`/loans/${loanId}`, {
            method: 'PATCH',
            body: JSON.stringify({ status: newStatus })
        });
        showSuccess('Loan status updated!');
        loadLoans();
    } catch (error) {
        console.error('Failed to update loan:', error);
    }
}

// Update Loan Due Dates (batch update)
async function updateLoanDueDates(loansToUpdate) {
    let successCount = 0;
    let errorCount = 0;

    for (const loan of loansToUpdate) {
        try {
            await apiCall(`/loans/${loan.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ due_date: loan.due_date })
            });
            successCount++;
        } catch (error) {
            console.error(`Failed to update loan ${loan.id}:`, error);
            errorCount++;
        }
    }

    if (successCount > 0) {
        showSuccess(`Updated ${successCount} loan(s) with calculated due dates`);
    }
    if (errorCount > 0) {
        showError(`Failed to update ${errorCount} loan(s)`);
    }

    // Reload loans to reflect changes
    loadLoans();
    loadBorrowerOptions();
}

// Delete Loan
async function deleteLoan(loanId) {
    if (!confirm('Are you sure you want to delete this loan?')) return;

    try {
        await apiCall(`/loans/${loanId}`, { method: 'DELETE' });
        showSuccess('Loan deleted successfully!');
        loadLoans();
        loadBorrowerOptions(); // Refresh commission dropdown
    } catch (error) {
        console.error('Failed to delete loan:', error);
    }
}

// Show Paid Off Popup
function showPaidOffPopup(loanId) {
    const loan = allLoans.find(l => l.id === loanId);
    if (!loan) {
        showError('Loan not found');
        return;
    }

    const today = new Date().toISOString().split('T')[0];

    const modalHTML = `
        <div class="modal-overlay" id="paidoff-modal" onclick="closeModal(event)">
            <div class="modal-content" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3>Mark Loan as Paid Off</h3>
                </div>
                <div class="modal-body">
                    <div class="modal-info">
                        <strong>Loan Details:</strong><br>
                        Borrower: ${loan.borrower_name}<br>
                        Amount: ₹${parseFloat(loan.amount).toLocaleString('en-IN', {minimumFractionDigits: 2})}<br>
                        Due Date: ${formatDueDate(loan.due_date)}
                    </div>
                    <div class="form-group">
                        <label for="paidoff-date">Paid Off Date *</label>
                        <input type="date" id="paidoff-date" value="${today}" max="${today}" required>
                        <small>Date when the loan was paid off (cannot be in the future)</small>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="button button-secondary" onclick="closeModal()">Cancel</button>
                    <button class="button button-primary" id="confirm-paid-off-btn" data-loan-id="${loanId}">Mark as Paid Off</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Attach event handler to confirm button
    const confirmBtn = document.getElementById('confirm-paid-off-btn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => confirmPaidOff(loanId));
    }
}

async function confirmPaidOff(loanId) {
    const paidoffDateInput = document.getElementById('paidoff-date');
    const paidoffDate = paidoffDateInput.value;

    if (!paidoffDate) {
        showError('Please select a paid off date');
        return;
    }

    const today = new Date().toISOString().split('T')[0];
    if (paidoffDate > today) {
        showError('Paid off date cannot be in the future');
        return;
    }

    const loan = allLoans.find(l => l.id === loanId);

    // Check if should delete (paid on due date)
    if (loan.due_date === today || paidoffDate === loan.due_date) {
        const shouldDelete = confirm(
            'Loan paid on due date. Do you want to delete this record permanently?\n\n' +
            'Click OK to delete, or Cancel to keep the record as paid off.'
        );

        if (shouldDelete) {
            try {
                await apiCall(`/loans/${loanId}`, { method: 'DELETE' });
                showSuccess('Loan deleted successfully!');
                closeModal();
                loadLoans();
                return;
            } catch (error) {
                console.error('Failed to delete loan:', error);
                showError('Failed to delete loan');
                return;
            }
        }
    }

    // Mark as paid off
    try {
        await apiCall(`/loans/${loanId}`, {
            method: 'PATCH',
            body: JSON.stringify({
                status: 'paid_off',
                paidoff_date: paidoffDate
            })
        });
        showSuccess('Loan marked as paid off!');
        closeModal();
        loadLoans();
    } catch (error) {
        console.error('Failed to update loan:', error);
        showError('Failed to mark loan as paid off');
    }
}

// Show Extend Popup
function showExtendPopup(loanId) {
    const loan = allLoans.find(l => l.id === loanId);
    if (!loan) {
        showError('Loan not found');
        return;
    }

    const today = new Date().toISOString().split('T')[0];
    const oldDueDate = loan.due_date;
    const minDate = new Date(oldDueDate);
    minDate.setDate(minDate.getDate() + 1);
    const minDateStr = minDate.toISOString().split('T')[0];

    const modalHTML = `
        <div class="modal-overlay" id="extend-modal" onclick="closeModal(event)">
            <div class="modal-content" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3>Extend Loan</h3>
                </div>
                <div class="modal-body">
                    <div class="modal-info">
                        <strong>Loan Details:</strong><br>
                        Borrower: ${loan.borrower_name}<br>
                        Amount: ₹${parseFloat(loan.amount).toLocaleString('en-IN', {minimumFractionDigits: 2})}<br>
                        Current Due Date: ${formatDueDate(loan.due_date)}<br>
                        Giving Date: ${formatDate(loan.giving_date)}
                    </div>
                    <div class="modal-warning">
                        <strong>Note:</strong> Extending the loan will update the giving date to today's date and set a new due date.
                    </div>
                    <div class="form-group">
                        <label for="new-due-date">New Due Date *</label>
                        <input type="date" id="new-due-date" min="${minDateStr}" required>
                        <small>New due date must be after ${formatDueDate(oldDueDate)}</small>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="button button-secondary" onclick="closeModal()">Cancel</button>
                    <button class="button button-primary" id="confirm-extend-btn" data-loan-id="${loanId}">Extend Loan</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Attach event handler to confirm button
    const confirmBtn = document.getElementById('confirm-extend-btn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => confirmExtend(loanId));
    }
}

async function confirmExtend(loanId) {
    const newDueDateInput = document.getElementById('new-due-date');
    const newDueDate = newDueDateInput.value;

    if (!newDueDate) {
        showError('Please select a new due date');
        return;
    }

    const loan = allLoans.find(l => l.id === loanId);
    const oldDueDate = new Date(loan.due_date);
    const selectedDate = new Date(newDueDate);

    if (selectedDate <= oldDueDate) {
        showError('New due date must be after the current due date');
        return;
    }

    // Set new giving date to today
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const newGivingDateStr = today.toISOString().split('T')[0];

    try {
        await apiCall(`/loans/${loanId}`, {
            method: 'PATCH',
            body: JSON.stringify({
                giving_date: newGivingDateStr,
                due_date: newDueDate,
                status: 'active'
            })
        });
        showSuccess(`Loan extended! New giving date: ${newGivingDateStr}, New due date: ${newDueDate}`);
        closeModal();
        loadLoans();
    } catch (error) {
        console.error('Failed to extend loan:', error);
        showError('Failed to extend loan');
    }
}

// Close Modal
function closeModal(event) {
    // If event is provided and click was on the overlay itself (not the modal content)
    if (event && event.target !== event.currentTarget) {
        return;
    }

    const modals = document.querySelectorAll('.modal-overlay');
    modals.forEach(modal => modal.remove());
}

// Load Statistics
async function loadStatistics() {
    try {
        const stats = await apiCall('/reports/statistics');
        displayStatistics(stats);
    } catch (error) {
        console.error('Failed to load statistics:', error);
    }
}

// Display Statistics - FIXED: Add CSV Export
function displayStatistics(stats) {
    const container = document.getElementById('stats-container');

    let html = '<div class="action-buttons" style="margin-bottom: 20px;">';
    html += '<button class="button button-primary" onclick="exportReportCSV()">📥 Export Report as CSV</button>';
    html += '</div>';

    html += '<div class="stats-grid">';
    html += `<div class="stat-card"><div class="stat-label">Total Loans</div><div class="stat-value">${stats.total_loans}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Total Amount</div><div class="stat-value">$${stats.total_amount.toFixed(2)}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Active Loans</div><div class="stat-value">${stats.active_loans}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Paid Off</div><div class="stat-value">${stats.paid_off_loans}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Overdue</div><div class="stat-value">${stats.overdue_loans}</div></div>`;
    html += '</div>';

    // By Borrower
    html += '<div class="card" style="margin-top: 20px;"><h3>Summary by Borrower</h3>';
    html += '<div class="table-container"><table><thead><tr><th>Borrower</th><th>Loans</th><th>Total Amount</th></tr></thead><tbody>';
    for (const [borrower, data] of Object.entries(stats.by_borrower)) {
        html += `<tr><td>${borrower}</td><td>${data.count}</td><td>$${data.sum.toFixed(2)}</td></tr>`;
    }
    html += '</tbody></table></div></div>';

    // By Depositor
    html += '<div class="card" style="margin-top: 20px;"><h3>Summary by Depositor</h3>';
    html += '<div class="table-container"><table><thead><tr><th>Depositor</th><th>Loans</th><th>Total Amount</th></tr></thead><tbody>';
    for (const [depositor, data] of Object.entries(stats.by_depositor)) {
        html += `<tr><td>${depositor}</td><td>${data.count}</td><td>$${data.sum.toFixed(2)}</td></tr>`;
    }
    html += '</tbody></table></div></div>';

    container.innerHTML = html;
}

// Export Report as CSV
async function exportReportCSV() {
    try {
        const stats = await apiCall('/reports/statistics');
        const loans = allLoans.length > 0 ? allLoans : await apiCall('/loans/');

        let csv = 'LoanTracker Report\n\n';
        csv += 'Summary Statistics\n';
        csv += `Total Loans,${stats.total_loans}\n`;
        csv += `Total Amount,$${stats.total_amount.toFixed(2)}\n`;
        csv += `Active Loans,${stats.active_loans}\n`;
        csv += `Paid Off Loans,${stats.paid_off_loans}\n`;
        csv += `Overdue Loans,${stats.overdue_loans}\n\n`;

        csv += 'Summary by Borrower\n';
        csv += 'Borrower,Loans,Total Amount\n';
        for (const [borrower, data] of Object.entries(stats.by_borrower)) {
            csv += `"${borrower}",${data.count},$${data.sum.toFixed(2)}\n`;
        }

        csv += '\nSummary by Depositor\n';
        csv += 'Depositor,Loans,Total Amount\n';
        for (const [depositor, data] of Object.entries(stats.by_depositor)) {
            csv += `"${depositor}",${data.count},$${data.sum.toFixed(2)}\n`;
        }

        csv += '\nAll Loans Detail\n';
        csv += 'ID,Borrower,Amount,Depositor,Giving Date,Due Date,Status,Borrower Group,Depositor Group\n';
        loans.forEach(loan => {
            csv += `"${loan.id}","${loan.borrower_name}",$${loan.amount},"${loan.depositor_name}",${loan.giving_date},${loan.due_date},${loan.status},"${loan.borrower_group || ''}","${loan.depositor_group || ''}"\n`;
        });

        downloadCSV(csv, `loantracker_report_${new Date().toISOString().split('T')[0]}.csv`);
        showSuccess('Report exported successfully!');
    } catch (error) {
        console.error('Failed to export report:', error);
    }
}

// Load Borrower Options - FIXED: Populate dropdown with actual data
async function loadBorrowerOptions() {
    try {
        const loans = allLoans.length > 0 ? allLoans : await apiCall('/loans/');
        
        // Get unique borrower names and groups
        const borrowerNames = [...new Set(loans.map(l => l.borrower_name))].sort();
        const borrowerGroups = [...new Set(loans.map(l => l.borrower_group).filter(g => g))].sort();

        const select = document.getElementById('comm_borrower');
        select.innerHTML = '<option value="">-- Select --</option>';

        // Add optgroups for better organization
        if (borrowerNames.length > 0) {
            const nameGroup = document.createElement('optgroup');
            nameGroup.label = 'By Borrower Name';
            borrowerNames.forEach(name => {
                const option = document.createElement('option');
                option.value = name;
                option.dataset.type = 'name';
                option.textContent = name;
                nameGroup.appendChild(option);
            });
            select.appendChild(nameGroup);
        }

        if (borrowerGroups.length > 0) {
            const groupGroup = document.createElement('optgroup');
            groupGroup.label = 'By Borrower Group';
            borrowerGroups.forEach(group => {
                const option = document.createElement('option');
                option.value = group;
                option.dataset.type = 'group';
                option.textContent = `${group} (Group)`;
                groupGroup.appendChild(option);
            });
            select.appendChild(groupGroup);
        }

        if (borrowerNames.length === 0 && borrowerGroups.length === 0) {
            select.innerHTML = '<option value="">-- No borrowers found --</option>';
        }
    } catch (error) {
        console.error('Failed to load borrower options:', error);
    }
}

// Update commission type based on selection
function updateCommissionType() {
    const select = document.getElementById('comm_borrower');
    const selectedOption = select.options[select.selectedIndex];
    const typeSelect = document.getElementById('comm_type');
    
    if (selectedOption && selectedOption.dataset.type) {
        typeSelect.value = selectedOption.dataset.type;
    }
}

// ========================================
// NEW INTEREST CALCULATOR (Month-based with per-record rates)
// ========================================

let loansForSelectedMonth = [];

// Load loans for selected month
async function loadLoansForMonth() {
    const dateInput = document.getElementById('month_filter').value;
    if (!dateInput) {
        showError('Please select a date using the date picker');
        return;
    }

    // Validate date format YYYY-MM-DD
    const datePattern = /^\d{4}-\d{2}-\d{2}$/;
    if (!datePattern.test(dateInput)) {
        showError('Invalid date format. Please use the date picker to select a date');
        return;
    }

    try {
        const loans = allLoans.length > 0 ? allLoans : await apiCall('/loans/');

        // Parse selected filter date (no month extraction)
        const filterDate = new Date(dateInput);
        filterDate.setHours(0, 0, 0, 0);

        // Format date for display messages
        const filterDateFormatted = filterDate.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });

        // CORE FILTER LOGIC: Show all loans where due_date > selected filter date
        // Exclude: 1970-01-01 (no due date) and paid_off loans
        const filteredLoans = loans.filter(loan => {
            if (loan.due_date === '1970-01-01') return false;
            if (loan.status === 'paid_off') return false;

            const dueDate = new Date(loan.due_date);
            dueDate.setHours(0, 0, 0, 0);

            // Filter: due_date > filter_date (strictly greater than)
            return dueDate > filterDate;
        });

        if (filteredLoans.length === 0) {
            showError(`No active loans found with due dates greater than ${filterDateFormatted}. Try a different date.`);
            document.getElementById('loans-for-month').style.display = 'none';
            return;
        }

        loansForSelectedMonth = filteredLoans;
        displayLoansForMonthWithRates(filteredLoans, dateInput);
        showSuccess(`Loaded ${filteredLoans.length} loan(s) with due dates greater than ${filterDateFormatted}`);

    } catch (error) {
        console.error('Failed to load loans:', error);
        showError('Failed to load loans for selected month');
    }
}

// Display loans with per-record rate inputs
function displayLoansForMonthWithRates(loans, selectedMonth) {
    const container = document.getElementById('loan-rates-container');
    const loansSection = document.getElementById('loans-for-month');

    let html = '<div class="loans-rate-list">';

    loans.forEach((loan, index) => {
        const amount = parseFloat(loan.amount);
        const givingDate = new Date(loan.giving_date);
        const dueDate = new Date(loan.due_date);
        const daysBetween = Math.ceil((dueDate - givingDate) / (1000 * 60 * 60 * 24));

        html += `
            <div class="loan-rate-row" data-loan-id="${loan.id}">
                <div class="loan-info">
                    <div class="loan-header">
                        <strong>${loan.borrower_name}</strong>
                        <span class="loan-amount">₹${amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                    </div>
                    <div class="loan-details">
                        <span>${formatDate(loan.giving_date)} → ${formatDate(loan.due_date)}</span>
                        <span class="days-badge">${daysBetween} days</span>
                        <span class="depositor-name">Depositor: ${loan.depositor_name}</span>
                    </div>
                </div>
                <div class="rate-inputs">
                    <div class="rate-input-group">
                        <label for="interest_rate_${loan.id}">Interest Rate (%)</label>
                        <input
                            type="number"
                            id="interest_rate_${loan.id}"
                            class="interest-rate-input"
                            min="0.01"
                            max="100"
                            step="0.01"
                            value="12.00"
                            required
                        />
                    </div>
                    <div class="rate-input-group">
                        <label for="commission_rate_${loan.id}">Commission (%) - Optional</label>
                        <input
                            type="number"
                            id="commission_rate_${loan.id}"
                            class="commission-rate-input"
                            min="0"
                            max="100"
                            step="0.01"
                            value="0.00"
                            placeholder="Enter rate or leave 0"
                        />
                    </div>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
    loansSection.style.display = 'block';
}

// Calculate interest for loaded loans with per-record rates
async function calculateInterestForLoadedLoans() {
    if (loansForSelectedMonth.length === 0) {
        showError('No loans loaded. Please load loans for a month first.');
        return;
    }

    const monthInput = document.getElementById('month_filter').value;
    const results = [];
    let totalAmount = 0;
    let totalInterest = 0;
    let totalCommission = 0;

    // Calculate for each loan
    loansForSelectedMonth.forEach((loan, index) => {
        const amount = parseFloat(loan.amount);
        const interestRateInput = document.getElementById(`interest_rate_${loan.id}`);
        const commissionRateInput = document.getElementById(`commission_rate_${loan.id}`);

        if (!interestRateInput) {
            console.error(`Interest rate input not found for loan ${loan.id}`);
            return;
        }

        const annualRate = parseFloat(interestRateInput.value) / 100; // Convert to decimal
        const commissionRate = parseFloat(commissionRateInput.value || '0') / 100;

        // Calculate actual days between dates
        const givingDate = new Date(loan.giving_date);
        const dueDate = new Date(loan.due_date);
        const daysBetween = Math.ceil((dueDate - givingDate) / (1000 * 60 * 60 * 24));

        // CORRECT FORMULA: Interest = Amount × (Annual Rate / 365) × Days
        const interest = amount * (annualRate / 365) * daysBetween;

        // Commission only if commission rate is provided (> 0)
        const commission = commissionRate > 0 ? (interest * commissionRate) : 0;

        results.push({
            sno: generateSNo(index, loan.giving_date),
            borrower: loan.borrower_name,
            depositor: loan.depositor_name,
            amount: amount,
            givingDate: loan.giving_date,
            dueDate: loan.due_date,
            daysBetween: daysBetween,
            annualRate: annualRate * 100,
            commissionRate: commissionRate * 100,
            interest: interest,
            commission: commission,
            hasCommission: commissionRate > 0,
            loanId: loan.id
        });

        totalAmount += amount;
        totalInterest += interest;
        if (commissionRate > 0) {
            totalCommission += commission;
        }
    });

    // Display results
    displayInterestCalculationResults(results, {
        selectedMonth: monthInput,
        totalAmount,
        totalInterest,
        totalCommission
    });

    showSuccess('Interest calculated successfully!');
}

// Display interest calculation results
function displayInterestCalculationResults(results, summary) {
    const container = document.getElementById('commission-results');

    const monthDate = new Date(summary.selectedMonth + '-01');
    const monthName = monthDate.toLocaleDateString('en-US', { year: 'numeric', month: 'long' });

    let html = '<div class="card">';
    html += `<h3>Interest Calculation Results - ${monthName}</h3>`;
    html += `<p class="info-text">Calculated using formula: Amount × (Annual Rate / 365) × Days</p>`;

    html += '<div style="margin: 20px 0;">';
    html += '<button class="button button-primary" onclick="exportInterestCalculationCSV()">📥 Export Interest Report as CSV</button>';
    html += '</div>';

    // Results table
    html += '<div class="table-container"><table>';
    html += '<thead><tr>';
    html += '<th>SNo</th><th>Borrower</th><th>Amount</th><th>Giving Date</th><th>Due Date</th>';
    html += '<th>Days</th><th>Interest Rate</th><th>Interest</th><th>Commission Rate</th><th>Commission</th>';
    html += '</tr></thead>';
    html += '<tbody>';

    results.forEach(r => {
        html += '<tr>';
        html += `<td>${r.sno}</td>`;
        html += `<td>${r.borrower}</td>`;
        html += `<td>₹${r.amount.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>`;
        html += `<td>${formatDate(r.givingDate)}</td>`;
        html += `<td>${formatDate(r.dueDate)}</td>`;
        html += `<td>${r.daysBetween}</td>`;
        html += `<td>${r.annualRate.toFixed(2)}%</td>`;
        html += `<td>₹${r.interest.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>`;
        html += `<td>${r.hasCommission ? r.commissionRate.toFixed(2) + '%' : '-'}</td>`;
        html += `<td>${r.hasCommission ? '₹' + r.commission.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '-'}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table></div>';

    // Summary section
    html += '<div style="margin-top: 30px; padding: 20px; background: var(--card-bg); border-radius: 8px;">';
    html += '<h4>Summary</h4>';
    html += '<div class="stats-grid">';
    html += `<div class="stat-card"><div class="stat-label">Total Loans</div><div class="stat-value">${results.length}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Total Amount</div><div class="stat-value">₹${summary.totalAmount.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Total Interest</div><div class="stat-value">₹${summary.totalInterest.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Total Commission</div><div class="stat-value" style="color: var(--success-color);">₹${summary.totalCommission.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div></div>`;
    html += '</div>';
    html += '</div>';

    html += '</div>';
    container.innerHTML = html;

    // Store for CSV export
    window.lastInterestResults = { results, summary };
}

// Export interest calculation to CSV
function exportInterestCalculationCSV() {
    if (!window.lastInterestResults) {
        showError('No interest results to export');
        return;
    }

    const { results, summary } = window.lastInterestResults;
    const monthDate = new Date(summary.selectedMonth + '-01');
    const monthName = monthDate.toLocaleDateString('en-US', { year: 'numeric', month: 'long' });

    let csv = 'LoanTracker Interest Calculator Report\n\n';
    csv += `Month: ${monthName}\n`;
    csv += `Calculation Formula: Amount × (Annual Rate / 365) × Days\n\n`;

    csv += `SNo,Borrower,Amount,Giving Date,Due Date,Days,Interest Rate (%),Interest,Commission Rate (%),Commission\n`;
    results.forEach(r => {
        csv += `${r.sno},"${r.borrower}",₹${r.amount.toFixed(2)},${r.givingDate},${r.dueDate},${r.daysBetween},${r.annualRate.toFixed(2)},₹${r.interest.toFixed(2)},${r.hasCommission ? r.commissionRate.toFixed(2) : '0'},${r.hasCommission ? '₹' + r.commission.toFixed(2) : '₹0.00'}\n`;
    });

    csv += '\nSummary\n';
    csv += `Total Loans,${results.length}\n`;
    csv += `Total Amount,₹${summary.totalAmount.toFixed(2)}\n`;
    csv += `Total Interest,₹${summary.totalInterest.toFixed(2)}\n`;
    csv += `Total Commission,₹${summary.totalCommission.toFixed(2)}\n`;

    downloadCSV(csv, `interest_calculation_${summary.selectedMonth}_${new Date().toISOString().split('T')[0]}.csv`);
    showSuccess('Interest report exported successfully!');
}

// Backward compatibility function for old Interest Calculator (now deprecated)
function calculateInterestByMonth(event) {
    event.preventDefault();
    loadLoansForMonth();
}

// ========================================
// OLD INTEREST CALCULATOR (DEPRECATED - kept for backward compatibility)
// ========================================

// Calculate Commission (OLD IMPLEMENTATION - will be removed in future version)
async function calculateCommission(event) {
    event.preventDefault();

    const borrowerValue = document.getElementById('comm_borrower').value;
    const filterType = document.getElementById('comm_type').value;
    const interestRate = parseFloat(document.getElementById('interest_rate').value) / 100; // Convert to decimal
    const commissionRate = parseFloat(document.getElementById('commission_rate').value) / 100;
    const periodCount = parseInt(document.getElementById('period_count').value);
    const periodUnit = document.getElementById('period_unit').value; // 'months' or 'days'

    // Validation
    if (commissionRate >= interestRate) {
        showError('Commission rate must be less than interest rate!');
        return;
    }

    try {
        const loans = allLoans.length > 0 ? allLoans : await apiCall('/loans/');
        
        // Filter loans based on selection
        let filteredLoans;
        if (filterType === 'name') {
            filteredLoans = loans.filter(l => l.borrower_name === borrowerValue && l.status !== 'paid_off');
        } else {
            filteredLoans = loans.filter(l => l.borrower_group === borrowerValue && l.status !== 'paid_off');
        }

        if (filteredLoans.length === 0) {
            showError('No active loans found for selected borrower/group');
            return;
        }

        // Track loans that need due_date updates
        const loansToUpdate = [];

        // Calculate commission for each loan
        const results = filteredLoans.map((loan, index) => {
            const amount = parseFloat(loan.amount);

            // Calculate interest based on unit (days or months)
            let periodInterest, totalInterest, totalCommission;
            if (periodUnit === 'days') {
                // Daily interest calculation
                const dailyInterest = amount * (interestRate / 365);
                periodInterest = dailyInterest;
                totalInterest = dailyInterest * periodCount;
                totalCommission = totalInterest * commissionRate;
            } else {
                // Monthly interest calculation (default)
                const monthlyInterest = amount * (interestRate / 12);
                periodInterest = monthlyInterest;
                totalInterest = monthlyInterest * periodCount;
                totalCommission = totalInterest * commissionRate;
            }

            // Calculate or use existing loan period
            let loanPeriodValue, calculatedDueDate, needsUpdate = false;
            const givingDate = new Date(loan.giving_date);

            if (loan.due_date === '1970-01-01') {
                // No due date exists - calculate from period
                loanPeriodValue = periodCount;
                calculatedDueDate = new Date(givingDate);

                if (periodUnit === 'days') {
                    calculatedDueDate.setDate(calculatedDueDate.getDate() + periodCount);
                } else {
                    calculatedDueDate.setMonth(calculatedDueDate.getMonth() + periodCount);
                }
                calculatedDueDate = calculatedDueDate.toISOString().split('T')[0];
                needsUpdate = true;

                // Queue this loan for update
                loansToUpdate.push({
                    id: loan.id,
                    due_date: calculatedDueDate
                });
            } else {
                // Due date exists - calculate actual period
                const loanPeriodDays = calculateLoanPeriodDays(loan.giving_date, loan.due_date);
                if (periodUnit === 'days') {
                    loanPeriodValue = loanPeriodDays;
                } else {
                    // Convert days to approximate months (30 days per month)
                    loanPeriodValue = Math.round(loanPeriodDays / 30);
                }
                calculatedDueDate = loan.due_date;
            }

            return {
                sno: generateSNo(index, loan.giving_date),
                borrower: loan.borrower_name,
                depositor: loan.depositor_name,
                givingDate: loan.giving_date,
                dueDate: calculatedDueDate,
                originalDueDate: loan.due_date,
                amount: amount,
                periodInterest: periodInterest,
                totalInterest: totalInterest,
                totalCommission: totalCommission,
                periodCount: periodCount,
                periodUnit: periodUnit,
                loanPeriodValue: loanPeriodValue,
                needsUpdate: needsUpdate,
                loanId: loan.id
            };
        });

        // Update loan records if needed
        if (loansToUpdate.length > 0) {
            await updateLoanDueDates(loansToUpdate);
        }

        // Calculate totals
        const totalAmount = results.reduce((sum, r) => sum + r.amount, 0);
        const totalInterest = results.reduce((sum, r) => sum + r.totalInterest, 0);
        const totalCommission = results.reduce((sum, r) => sum + r.totalCommission, 0);

        displayCommissionResults(results, {
            borrowerValue,
            filterType,
            interestRate: interestRate * 100,
            commissionRate: commissionRate * 100,
            periodCount,
            periodUnit,
            totalAmount,
            totalInterest,
            totalCommission
        });

    } catch (error) {
        console.error('Failed to calculate commission:', error);
    }
}

// Display Interest Calculator Results
function displayCommissionResults(results, summary) {
    const container = document.getElementById('commission-results');

    let html = '<div class="card">';
    html += '<h3>Interest Calculator Report</h3>';

    // Borrower/Group Header
    html += `<h4>${summary.borrowerValue}</h4>`;

    html += `<p><strong>Interest Rate:</strong> ${summary.interestRate.toFixed(2)}% per annum</p>`;
    html += `<p><strong>Commission Rate:</strong> ${summary.commissionRate.toFixed(2)}%</p>`;
    html += `<p><strong>Period:</strong> ${summary.periodCount} ${summary.periodUnit}</p>`;

    html += '<div style="margin: 20px 0;">';
    html += '<button class="button button-primary" onclick="exportCommissionCSV()">📥 Export Interest Report as CSV</button>';
    html += '</div>';

    // Enhanced table with detailed breakdown
    html += '<div class="table-container"><table>';
    html += '<thead><tr>';
    html += '<th>SNo</th><th>Amount</th><th>Giving Date</th><th>Depositor</th>';
    html += `<th>LoanPeriod(${summary.periodUnit === 'days' ? 'Days' : 'Months'})</th><th>Due Date</th><th>Interest Amount</th><th>Commission</th>`;
    html += '</tr></thead>';
    html += '<tbody>';

    results.forEach(r => {
        const loanPeriodDisplay = r.loanPeriodValue === 'N/A' ? 'N/A' : `${r.loanPeriodValue} ${r.periodUnit}`;
        const dueDateDisplay = r.originalDueDate === '1970-01-01'
            ? `${formatDate(r.dueDate)} <span style="color: var(--success-color); font-size: 0.85em;">✓ updated</span>`
            : formatDueDate(r.dueDate);
        html += '<tr>';
        html += `<td>${r.sno}</td>`;
        html += `<td>₹${r.amount.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>`;
        html += `<td>${formatDate(r.givingDate)}</td>`;
        html += `<td>${r.depositor}</td>`;
        html += `<td>${loanPeriodDisplay}</td>`;
        html += `<td>${dueDateDisplay}</td>`;
        html += `<td>₹${r.totalInterest.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>`;
        html += `<td>₹${r.totalCommission.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table></div>';

    // Summary section
    html += '<div style="margin-top: 30px; padding: 20px; background: var(--card-bg); border-radius: 8px;">';
    html += '<h4>Summary</h4>';
    html += '<div class="stats-grid">';
    html += `<div class="stat-card"><div class="stat-label">Total Loans</div><div class="stat-value">${results.length}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Total Amount</div><div class="stat-value">₹${summary.totalAmount.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Total Interest</div><div class="stat-value">₹${summary.totalInterest.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div></div>`;
    html += `<div class="stat-card"><div class="stat-label">Total Commission</div><div class="stat-value" style="color: var(--success-color);">₹${summary.totalCommission.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div></div>`;
    html += '</div>';
    html += '</div>';

    html += '</div>';
    container.innerHTML = html;

    // Store for CSV export
    window.lastCommissionResults = { results, summary };
}

// Export Commission Report as CSV
function exportCommissionCSV() {
    if (!window.lastCommissionResults) {
        showError('No interest results to export');
        return;
    }

    const { results, summary } = window.lastCommissionResults;

    let csv = 'LoanTracker Interest Calculator Report\n\n';
    csv += `Borrower/Group: ${summary.borrowerValue}\n`;
    csv += `Interest Rate: ${summary.interestRate.toFixed(2)}% per annum\n`;
    csv += `Commission Rate: ${summary.commissionRate.toFixed(2)}%\n`;
    csv += `Period: ${summary.periodCount} ${summary.periodUnit}\n\n`;

    const periodUnitLabel = summary.periodUnit === 'days' ? 'Days' : 'Months';
    csv += `SNo,Amount,Giving Date,Depositor,LoanPeriod(${periodUnitLabel}),Due Date,Interest Amount,Commission\n`;
    results.forEach(r => {
        const loanPeriodDisplay = r.loanPeriodValue === 'N/A' ? 'N/A' : `${r.loanPeriodValue} ${r.periodUnit}`;
        const dueDateDisplay = r.originalDueDate === '1970-01-01' ? `${r.dueDate} (calculated)` : r.dueDate;
        csv += `${r.sno},₹${r.amount.toFixed(2)},${r.givingDate},"${r.depositor}",${loanPeriodDisplay},${dueDateDisplay},₹${r.totalInterest.toFixed(2)},₹${r.totalCommission.toFixed(2)}\n`;
    });

    csv += '\nSummary\n';
    csv += `Total Loans,${results.length}\n`;
    csv += `Total Amount,₹${summary.totalAmount.toFixed(2)}\n`;
    csv += `Total Interest,₹${summary.totalInterest.toFixed(2)}\n`;
    csv += `Total Commission,₹${summary.totalCommission.toFixed(2)}\n`;

    downloadCSV(csv, `interest_report_${summary.borrowerValue}_${new Date().toISOString().split('T')[0]}.csv`);
    showSuccess('Interest report exported successfully!');
}

// CSV Import functions
let csvData = [];

function previewCSV(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const text = e.target.result;
        const lines = text.split('\n').filter(line => line.trim());
        
        if (lines.length < 2) {
            showError('CSV file is empty or invalid');
            return;
        }

        // Parse CSV
        csvData = parseCSV(text);
        
        // Show preview
        const container = document.getElementById('csv-preview');
        let html = '<h4>Preview (first 5 rows)</h4>';
        html += '<div class="table-container"><table><thead><tr>';
        html += '<th>Borrower</th><th>Amount</th><th>Depositor</th><th>Giving Date</th><th>Due Date</th><th>Status</th>';
        html += '</tr></thead><tbody>';

        csvData.slice(0, 5).forEach(row => {
            html += '<tr>';
            html += `<td>${row.borrower_name || ''}</td>`;
            html += `<td>$${row.amount || '0'}</td>`;
            html += `<td>${row.depositor_name || ''}</td>`;
            html += `<td>${row.giving_date || ''}</td>`;
            html += `<td>${row.due_date || '1970-01-01'}</td>`;
            html += `<td><span class="info-badge">Will auto-calculate</span></td>`;
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        html += `<p><strong>Total rows to import:</strong> ${csvData.length}</p>`;
        container.innerHTML = html;

        document.getElementById('import-btn').style.display = 'block';
    };

    reader.readAsText(file);
}

function parseCSV(text) {
    // Remove BOM if present
    text = text.replace(/^\uFEFF/, '');

    const lines = text.split('\n').filter(line => line.trim());
    if (lines.length < 2) return [];

    const headers = parseCSVLine(lines[0]);

    const data = [];
    for (let i = 1; i < lines.length; i++) {
        const values = parseCSVLine(lines[i]);
        if (values.length === 0) continue; // Skip empty lines

        const row = {};
        headers.forEach((header, index) => {
            row[header] = values[index] || '';
        });

        // Handle missing due_date
        if (!row.due_date || row.due_date === '') {
            row.due_date = '1970-01-01';
        }

        // Only add rows with required fields
        if (row.borrower_name && row.amount && row.depositor_name && row.giving_date) {
            data.push(row);
        }
    }

    return data;
}

// Helper function to parse a CSV line properly (handles quoted fields)
function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const char = line[i];
        const nextChar = line[i + 1];

        if (char === '"') {
            if (inQuotes && nextChar === '"') {
                // Escaped quote
                current += '"';
                i++; // Skip next quote
            } else {
                // Toggle quote state
                inQuotes = !inQuotes;
            }
        } else if (char === ',' && !inQuotes) {
            // End of field
            result.push(current.trim());
            current = '';
        } else {
            current += char;
        }
    }

    // Add last field
    result.push(current.trim());

    return result;
}

async function importCSV() {
    if (csvData.length === 0) {
        showError('No data to import');
        return;
    }

    let successCount = 0;
    let errorCount = 0;

    for (const row of csvData) {
        try {
            await apiCall('/loans/', {
                method: 'POST',
                body: JSON.stringify({
                    borrower_name: row.borrower_name,
                    amount: parseFloat(row.amount),
                    depositor_name: row.depositor_name,
                    giving_date: row.giving_date,
                    due_date: row.due_date || '1970-01-01',
                    borrower_group: row.borrower_group || null,
                    depositor_group: row.depositor_group || null
                })
            });
            successCount++;
        } catch (error) {
            errorCount++;
            console.error('Failed to import row:', row, error);
        }
    }

    showSuccess(`Import complete! ${successCount} loans imported, ${errorCount} failed.`);
    loadLoans();
    loadBorrowerOptions();
    document.getElementById('csv_file').value = '';
    document.getElementById('csv-preview').innerHTML = '';
    document.getElementById('import-btn').style.display = 'none';
}

// Load System Config
async function loadConfig() {
    try {
        const config = await apiCall('/config/');
        displayConfig(config);
    } catch (error) {
        console.error('Failed to load config:', error);
    }
}

// Display Config
function displayConfig(config) {
    const container = document.getElementById('config-container');

    let html = '<div class="table-container"><table>';
    html += '<thead><tr><th>Setting</th><th>Value</th></tr></thead><tbody>';
    html += `<tr><td>Storage Type</td><td><span class="info-badge">${config.storage_type}</span></td></tr>`;
    html += `<tr><td>Encryption</td><td><span class="info-badge">${config.encryption_enabled ? 'Enabled ✅' : 'Disabled ⚠️'}</span></td></tr>`;
    html += `<tr><td>CSV Output Directory</td><td>${config.csv_output_dir}</td></tr>`;
    html += `<tr><td>App Version</td><td>${config.app_version}</td></tr>`;
    html += '</tbody></table></div>';

    html += '<div style="margin-top: 20px; padding: 15px; background: var(--bg-primary); border-radius: 8px;">';
    html += '<h3>Data Locations</h3>';
    html += `<p><strong>Historical Data CSV:</strong> ${config.csv_output_dir}/loan_records.csv</p>`;
    html += `<p><strong>Reports Folder:</strong> reports/ (in downloads)</p>`;
    html += '<p>You can open CSV files directly in Excel or any spreadsheet application.</p>';
    html += '</div>';

    container.innerHTML = html;
}

// Utility Functions
function calculateLoanPeriodDays(givingDate, dueDate) {
    // Handle special case: 1970-01-01 means no due date
    if (dueDate === '1970-01-01') {
        return 'N/A';
    }

    const startDate = new Date(givingDate);
    const endDate = new Date(dueDate);

    // Calculate difference in milliseconds, then convert to days
    const diffTime = endDate - startDate;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    return diffDays;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatDueDate(dateString) {
    if (dateString === '1970-01-01') {
        return 'No due date';
    }
    return formatDate(dateString);
}

function formatStatus(status) {
    // Convert status from snake_case to Title Case for display
    // active -> Active
    // paid_off -> Paid Off
    // overdue -> Overdue
    return status
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

function downloadCSV(csvContent, filename) {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function showSuccess(message) {
    showNotification(message, 'success');
}

function showError(message) {
    showNotification(message, 'error');
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = type;
    notification.textContent = message;
    notification.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 1000; padding: 15px 20px; border-radius: 6px; animation: slideIn 0.3s ease;';

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
@keyframes slideIn {
    from { transform: translateX(400px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}
@keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(400px); opacity: 0; }
}
`;
document.head.appendChild(style);
