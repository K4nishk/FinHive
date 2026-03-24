export interface Loan {
  id: string
  borrower_name: string
  amount: number
  depositor_name: string
  giving_date: string
  due_date: string
  borrower_group?: string
  depositor_group?: string
  status: LoanStatus
  created_at: string
  updated_at: string
}

export type LoanStatus = 'active' | 'paid_off' | 'overdue'

export interface LoanCreate {
  borrower_name: string
  amount: number
  depositor_name: string
  giving_date: string
  due_date: string
  borrower_group?: string
  depositor_group?: string
}

export interface LoanUpdate {
  amount?: number
  due_date?: string
  status?: LoanStatus
  borrower_group?: string
  depositor_group?: string
}

export interface Statistics {
  total_loans: number
  total_amount: number
  active_loans: number
  paid_off_loans: number
  overdue_loans: number
  by_borrower: Record<string, { count: number; sum: number }>
  by_depositor: Record<string, { count: number; sum: number }>
}

export interface SystemConfig {
  storage_type: string
  encryption_enabled: boolean
  csv_output_dir: string
  app_version: string
}
