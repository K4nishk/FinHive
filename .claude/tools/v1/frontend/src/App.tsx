import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { loansApi } from './api/loans'
import type { Loan, LoanCreate, Statistics, SystemConfig } from './types/loan'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

type Theme = 'modern' | 'classic' | 'dark' | 'minimal'
type Tab = 'entry' | 'view' | 'reports'

function LoanTrackerApp() {
  const [theme, setTheme] = useState<Theme>('modern')
  const [activeTab, setActiveTab] = useState<Tab>('entry')
  const queryClient = useQueryClient()

  // Fetch loans
  const { data: loans = [], isLoading: loansLoading, error: loansError } = useQuery({
    queryKey: ['loans'],
    queryFn: loansApi.getAll,
  })

  // Fetch statistics
  const { data: statistics } = useQuery({
    queryKey: ['statistics'],
    queryFn: loansApi.getStatistics,
  })

  // Fetch system config
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: loansApi.getSystemConfig,
  })

  // Create loan mutation
  const createMutation = useMutation({
    mutationFn: loansApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loans'] })
      queryClient.invalidateQueries({ queryKey: ['statistics'] })
      alert('Loan created successfully!')
    },
    onError: (error: any) => {
      alert(`Error: ${error.response?.data?.detail || 'Failed to create loan'}`)
    },
  })

  // Delete loan mutation
  const deleteMutation = useMutation({
    mutationFn: loansApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loans'] })
      queryClient.invalidateQueries({ queryKey: ['statistics'] })
      alert('Loan deleted successfully!')
    },
    onError: (error: any) => {
      alert(`Error: ${error.response?.data?.detail || 'Failed to delete loan'}`)
    },
  })

  // Update loan status mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'active' | 'paid_off' | 'overdue' }) =>
      loansApi.update(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loans'] })
      queryClient.invalidateQueries({ queryKey: ['statistics'] })
      alert('Loan status updated!')
    },
  })

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)

    const loanData: LoanCreate = {
      borrower_name: formData.get('borrower_name') as string,
      amount: parseFloat(formData.get('amount') as string),
      depositor_name: formData.get('depositor_name') as string,
      giving_date: formData.get('giving_date') as string,
      due_date: formData.get('due_date') as string,
      borrower_group: formData.get('borrower_group') as string || undefined,
      depositor_group: formData.get('depositor_group') as string || undefined,
    }

    createMutation.mutate(loanData)
    e.currentTarget.reset()
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <div className={`app theme-${theme}`}>
      <header className="header">
        <div className="header-content">
          <div>
            <h1>🏦 LoanTracker</h1>
            {config && (
              <div style={{ marginTop: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>
                Storage: <span className="info-badge">{config.storage_type.toUpperCase()}</span>
                Encryption: <span className="info-badge">{config.encryption_enabled ? 'Enabled' : 'Disabled'}</span>
                Output: <span className="info-badge">{config.csv_output_dir}</span>
              </div>
            )}
          </div>
          <div className="theme-selector">
            <span style={{ marginRight: '10px', color: 'var(--text-secondary)' }}>Theme:</span>
            {(['modern', 'classic', 'dark', 'minimal'] as Theme[]).map((t) => (
              <button
                key={t}
                className={`theme-button ${theme === t ? 'active' : ''}`}
                onClick={() => setTheme(t)}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="container">
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'entry' ? 'active' : ''}`}
            onClick={() => setActiveTab('entry')}
          >
            📝 Data Entry
          </button>
          <button
            className={`tab ${activeTab === 'view' ? 'active' : ''}`}
            onClick={() => setActiveTab('view')}
          >
            📊 View Loans
          </button>
          <button
            className={`tab ${activeTab === 'reports' ? 'active' : ''}`}
            onClick={() => setActiveTab('reports')}
          >
            📈 Reports
          </button>
        </div>

        {activeTab === 'entry' && (
          <div className="card">
            <h2>Create New Loan Record</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="borrower_name">Borrower Name *</label>
                  <input
                    type="text"
                    id="borrower_name"
                    name="borrower_name"
                    required
                    placeholder="Enter borrower name"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="amount">Amount *</label>
                  <input
                    type="number"
                    id="amount"
                    name="amount"
                    required
                    step="0.01"
                    min="0.01"
                    placeholder="0.00"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="depositor_name">Depositor Name *</label>
                  <input
                    type="text"
                    id="depositor_name"
                    name="depositor_name"
                    required
                    placeholder="Enter depositor/lender name"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="giving_date">Giving Date *</label>
                  <input
                    type="date"
                    id="giving_date"
                    name="giving_date"
                    required
                    defaultValue={new Date().toISOString().split('T')[0]}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="due_date">Due Date *</label>
                  <input
                    type="date"
                    id="due_date"
                    name="due_date"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="borrower_group">Borrower Group (Optional)</label>
                  <input
                    type="text"
                    id="borrower_group"
                    name="borrower_group"
                    placeholder="e.g., Family, Friends, Business"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="depositor_group">Depositor Group (Optional)</label>
                  <input
                    type="text"
                    id="depositor_group"
                    name="depositor_group"
                    placeholder="e.g., Bank, Personal, Institution"
                  />
                </div>
              </div>

              <div className="action-buttons">
                <button type="submit" className="button button-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Creating...' : 'Create Loan'}
                </button>
              </div>
            </form>
          </div>
        )}

        {activeTab === 'view' && (
          <div className="card">
            <h2>All Loan Records ({loans.length})</h2>
            {loansLoading && <div className="loading">Loading loans...</div>}
            {loansError && <div className="error">Failed to load loans</div>}
            {!loansLoading && loans.length === 0 && (
              <div className="empty-state">
                <h3>No loans yet</h3>
                <p>Create your first loan record in the Data Entry tab</p>
              </div>
            )}
            {!loansLoading && loans.length > 0 && (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Borrower</th>
                      <th>Amount</th>
                      <th>Depositor</th>
                      <th>Giving Date</th>
                      <th>Due Date</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loans.map((loan) => (
                      <tr key={loan.id}>
                        <td>
                          {loan.borrower_name}
                          {loan.borrower_group && (
                            <span className="info-badge">{loan.borrower_group}</span>
                          )}
                        </td>
                        <td>{formatCurrency(loan.amount)}</td>
                        <td>
                          {loan.depositor_name}
                          {loan.depositor_group && (
                            <span className="info-badge">{loan.depositor_group}</span>
                          )}
                        </td>
                        <td>{formatDate(loan.giving_date)}</td>
                        <td>{formatDate(loan.due_date)}</td>
                        <td>
                          <select
                            className={`status-badge status-${loan.status}`}
                            value={loan.status}
                            onChange={(e) =>
                              updateMutation.mutate({
                                id: loan.id,
                                status: e.target.value as any,
                              })
                            }
                            style={{
                              border: 'none',
                              background: 'transparent',
                              cursor: 'pointer',
                            }}
                          >
                            <option value="active">Active</option>
                            <option value="paid_off">Paid Off</option>
                            <option value="overdue">Overdue</option>
                          </select>
                        </td>
                        <td>
                          <button
                            className="icon-button button-danger"
                            onClick={() => {
                              if (confirm('Are you sure you want to delete this loan?')) {
                                deleteMutation.mutate(loan.id)
                              }
                            }}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'reports' && statistics && (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Total Loans</div>
                <div className="stat-value">{statistics.total_loans}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Total Amount</div>
                <div className="stat-value">{formatCurrency(statistics.total_amount)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Active Loans</div>
                <div className="stat-value" style={{ color: '#1e40af' }}>
                  {statistics.active_loans}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Paid Off</div>
                <div className="stat-value" style={{ color: '#065f46' }}>
                  {statistics.paid_off_loans}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Overdue</div>
                <div className="stat-value" style={{ color: '#991b1b' }}>
                  {statistics.overdue_loans}
                </div>
              </div>
            </div>

            <div className="card">
              <h2>By Borrower</h2>
              {Object.keys(statistics.by_borrower).length === 0 ? (
                <div className="empty-state">No borrower data available</div>
              ) : (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Borrower Name</th>
                        <th>Number of Loans</th>
                        <th>Total Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(statistics.by_borrower).map(([name, data]) => (
                        <tr key={name}>
                          <td>{name}</td>
                          <td>{data.count}</td>
                          <td>{formatCurrency(data.sum)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="card">
              <h2>By Depositor</h2>
              {Object.keys(statistics.by_depositor).length === 0 ? (
                <div className="empty-state">No depositor data available</div>
              ) : (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Depositor Name</th>
                        <th>Number of Loans</th>
                        <th>Total Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(statistics.by_depositor).map(([name, data]) => (
                        <tr key={name}>
                          <td>{name}</td>
                          <td>{data.count}</td>
                          <td>{formatCurrency(data.sum)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LoanTrackerApp />
    </QueryClientProvider>
  )
}
