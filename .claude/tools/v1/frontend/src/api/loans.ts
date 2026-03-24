import { apiClient } from './client'
import type { Loan, LoanCreate, LoanUpdate, Statistics, SystemConfig } from '../types/loan'

export const loansApi = {
  getAll: async (): Promise<Loan[]> => {
    const { data } = await apiClient.get<Loan[]>('/loans')
    return data
  },

  getById: async (id: string): Promise<Loan> => {
    const { data } = await apiClient.get<Loan>(`/loans/${id}`)
    return data
  },

  create: async (loan: LoanCreate): Promise<Loan> => {
    const { data } = await apiClient.post<Loan>('/loans/', loan)
    return data
  },

  update: async (id: string, loan: LoanUpdate): Promise<Loan> => {
    const { data } = await apiClient.patch<Loan>(`/loans/${id}`, loan)
    return data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/loans/${id}`)
  },

  getStatistics: async (): Promise<Statistics> => {
    const { data} = await apiClient.get<Statistics>('/reports/statistics')
    return data
  },

  getSystemConfig: async (): Promise<SystemConfig> => {
    const { data } = await apiClient.get<SystemConfig>('/config/')
    return data
  },
}
