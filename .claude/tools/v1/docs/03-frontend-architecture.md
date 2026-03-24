# Frontend Architecture and Patterns

## Technology Stack

### Core Framework
- **React 18+**: Modern React with hooks, concurrent features
- **TypeScript 5+**: Type safety, better IDE support, fewer runtime errors
- **Vite**: Fast build tool, HMR (Hot Module Replacement)

### UI Framework
- **Material-UI (MUI) v5**: Recommended for professional, accessible components
  - Alternative: Ant Design (more opinionated, feature-rich)
  - Rationale: MUI has excellent TypeScript support, customization, accessibility

### State Management
- **React Query (TanStack Query)**: Server state management, caching, synchronization
- **Context API + useReducer**: Local UI state (theme, user preferences)
- **React Hook Form**: Form state management

### Additional Libraries
- **Axios**: HTTP client with interceptors for auth, error handling
- **Yup**: Schema validation for forms
- **date-fns**: Date manipulation (lighter than moment.js)
- **recharts**: Charts and data visualization
- **react-router-dom v6**: Client-side routing
- **react-toastify**: User notifications/alerts

## Project Structure

```
frontend/
├── public/
│   ├── index.html
│   └── favicon.ico
│
├── src/
│   ├── main.tsx                # Entry point
│   ├── App.tsx                 # Root component
│   ├── vite-env.d.ts
│   │
│   ├── api/                    # API client layer
│   │   ├── client.ts           # Axios instance configuration
│   │   ├── loans.ts            # Loan API methods
│   │   ├── reports.ts          # Report API methods
│   │   └── types.ts            # API request/response types
│   │
│   ├── components/             # Reusable components
│   │   ├── common/
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── DatePicker.tsx
│   │   │   ├── LoadingSpinner.tsx
│   │   │   └── ErrorBoundary.tsx
│   │   │
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Footer.tsx
│   │   │   └── Layout.tsx
│   │   │
│   │   └── loans/
│   │       ├── LoanTable.tsx
│   │       ├── LoanForm.tsx
│   │       ├── LoanCard.tsx
│   │       └── LoanFilters.tsx
│   │
│   ├── pages/                  # Page components (routes)
│   │   ├── Dashboard.tsx
│   │   ├── LoansPage.tsx
│   │   ├── ReportsPage.tsx
│   │   ├── SettingsPage.tsx
│   │   └── NotFound.tsx
│   │
│   ├── hooks/                  # Custom React hooks
│   │   ├── useLoans.ts
│   │   ├── useReports.ts
│   │   ├── useAuth.ts
│   │   └── useDebounce.ts
│   │
│   ├── context/                # React Context providers
│   │   ├── AuthContext.tsx
│   │   └── ThemeContext.tsx
│   │
│   ├── utils/                  # Utility functions
│   │   ├── formatters.ts       # Date, currency formatters
│   │   ├── validators.ts       # Custom validation functions
│   │   └── constants.ts        # App constants
│   │
│   ├── types/                  # TypeScript type definitions
│   │   ├── loan.ts
│   │   ├── report.ts
│   │   └── common.ts
│   │
│   ├── styles/                 # Global styles
│   │   ├── theme.ts            # MUI theme configuration
│   │   └── global.css
│   │
│   └── tests/
│       ├── setup.ts
│       └── components/
│
├── .env.development
├── .env.production
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

## Core Patterns

### 1. API Client Layer

```typescript
// src/api/client.ts
import axios, { AxiosInstance, AxiosError } from 'axios';
import { toast } from 'react-toastify';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: Add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle errors globally
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail: string }>) => {
    const message = error.response?.data?.detail || 'An unexpected error occurred';

    // Handle specific error codes
    if (error.response?.status === 401) {
      toast.error('Session expired. Please log in again.');
      // Redirect to login
      window.location.href = '/login';
    } else if (error.response?.status === 403) {
      toast.error('You do not have permission to perform this action.');
    } else if (error.response?.status >= 500) {
      toast.error('Server error. Please try again later.');
    } else {
      toast.error(message);
    }

    return Promise.reject(error);
  }
);
```

```typescript
// src/api/loans.ts
import { apiClient } from './client';
import type { Loan, LoanCreate, LoanUpdate, LoanFilters } from '@/types/loan';

export const loansApi = {
  /**
   * Fetch all loans with optional filters
   */
  getAll: async (filters?: LoanFilters): Promise<Loan[]> => {
    const { data } = await apiClient.get<Loan[]>('/loans', { params: filters });
    return data;
  },

  /**
   * Fetch single loan by ID
   */
  getById: async (id: string): Promise<Loan> => {
    const { data } = await apiClient.get<Loan>(`/loans/${id}`);
    return data;
  },

  /**
   * Create new loan
   */
  create: async (loan: LoanCreate): Promise<Loan> => {
    const { data } = await apiClient.post<Loan>('/loans', loan);
    return data;
  },

  /**
   * Update existing loan
   */
  update: async (id: string, loan: LoanUpdate): Promise<Loan> => {
    const { data } = await apiClient.patch<Loan>(`/loans/${id}`, loan);
    return data;
  },

  /**
   * Soft delete loan
   */
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/loans/${id}`);
  },

  /**
   * Export loans to CSV
   */
  exportToCsv: async (filters?: LoanFilters): Promise<Blob> => {
    const { data } = await apiClient.get('/loans/export', {
      params: filters,
      responseType: 'blob',
    });
    return data;
  },
};
```

### 2. React Query Hooks (Server State)

```typescript
// src/hooks/useLoans.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { loansApi } from '@/api/loans';
import type { LoanCreate, LoanUpdate, LoanFilters } from '@/types/loan';
import { toast } from 'react-toastify';

const QUERY_KEYS = {
  loans: ['loans'] as const,
  loan: (id: string) => ['loans', id] as const,
};

/**
 * Fetch all loans with filters
 */
export const useLoans = (filters?: LoanFilters) => {
  return useQuery({
    queryKey: [...QUERY_KEYS.loans, filters],
    queryFn: () => loansApi.getAll(filters),
    staleTime: 30000, // 30 seconds
  });
};

/**
 * Fetch single loan
 */
export const useLoan = (id: string) => {
  return useQuery({
    queryKey: QUERY_KEYS.loan(id),
    queryFn: () => loansApi.getById(id),
    enabled: !!id, // Only fetch if ID exists
  });
};

/**
 * Create loan mutation
 */
export const useCreateLoan = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (loan: LoanCreate) => loansApi.create(loan),
    onSuccess: () => {
      // Invalidate and refetch loans
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.loans });
      toast.success('Loan created successfully!');
    },
  });
};

/**
 * Update loan mutation
 */
export const useUpdateLoan = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: LoanUpdate }) =>
      loansApi.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.loans });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.loan(id) });
      toast.success('Loan updated successfully!');
    },
  });
};

/**
 * Delete loan mutation
 */
export const useDeleteLoan = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => loansApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.loans });
      toast.success('Loan deleted successfully!');
    },
  });
};
```

### 3. Form Management (React Hook Form + Yup)

```typescript
// src/components/loans/LoanForm.tsx
import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import {
  TextField,
  Button,
  Box,
  Grid,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers';
import type { LoanCreate } from '@/types/loan';
import { useCreateLoan } from '@/hooks/useLoans';

// Validation schema
const loanSchema = yup.object({
  borrower_name: yup
    .string()
    .required('Borrower name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name cannot exceed 100 characters'),

  amount: yup
    .number()
    .required('Amount is required')
    .positive('Amount must be positive')
    .max(999999999.99, 'Amount too large'),

  depositor_name: yup
    .string()
    .required('Depositor name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name cannot exceed 100 characters'),

  giving_date: yup
    .date()
    .required('Giving date is required')
    .max(new Date(), 'Giving date cannot be in the future'),

  due_date: yup
    .date()
    .required('Due date is required')
    .min(yup.ref('giving_date'), 'Due date must be after giving date'),

  borrower_group: yup.string().max(50).optional(),
  depositor_group: yup.string().max(50).optional(),
});

interface LoanFormProps {
  onSuccess?: () => void;
}

export const LoanForm: React.FC<LoanFormProps> = ({ onSuccess }) => {
  const createLoan = useCreateLoan();

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<LoanCreate>({
    resolver: yupResolver(loanSchema),
    defaultValues: {
      borrower_name: '',
      amount: 0,
      depositor_name: '',
      giving_date: new Date(),
      due_date: new Date(),
      borrower_group: '',
      depositor_group: '',
    },
  });

  const onSubmit = async (data: LoanCreate) => {
    await createLoan.mutateAsync(data);
    reset();
    onSuccess?.();
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6}>
          <Controller
            name="borrower_name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Borrower Name"
                fullWidth
                required
                error={!!errors.borrower_name}
                helperText={errors.borrower_name?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="amount"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Amount"
                type="number"
                fullWidth
                required
                error={!!errors.amount}
                helperText={errors.amount?.message}
                InputProps={{ startAdornment: '$' }}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="depositor_name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Depositor Name"
                fullWidth
                required
                error={!!errors.depositor_name}
                helperText={errors.depositor_name?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="giving_date"
            control={control}
            render={({ field }) => (
              <DatePicker
                {...field}
                label="Giving Date"
                slotProps={{
                  textField: {
                    fullWidth: true,
                    required: true,
                    error: !!errors.giving_date,
                    helperText: errors.giving_date?.message,
                  },
                }}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="due_date"
            control={control}
            render={({ field }) => (
              <DatePicker
                {...field}
                label="Due Date"
                slotProps={{
                  textField: {
                    fullWidth: true,
                    required: true,
                    error: !!errors.due_date,
                    helperText: errors.due_date?.message,
                  },
                }}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="borrower_group"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Borrower Group (Optional)"
                fullWidth
                error={!!errors.borrower_group}
                helperText={errors.borrower_group?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="depositor_group"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="Depositor Group (Optional)"
                fullWidth
                error={!!errors.depositor_group}
                helperText={errors.depositor_group?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            fullWidth
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Creating...' : 'Create Loan'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
};
```

### 4. Data Table Component

```typescript
// src/components/loans/LoanTable.tsx
import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Paper,
  IconButton,
  Chip,
} from '@mui/material';
import { Edit, Delete } from '@mui/icons-material';
import type { Loan } from '@/types/loan';
import { formatCurrency, formatDate } from '@/utils/formatters';

interface LoanTableProps {
  loans: Loan[];
  onEdit: (loan: Loan) => void;
  onDelete: (id: string) => void;
}

export const LoanTable: React.FC<LoanTableProps> = ({ loans, onEdit, onDelete }) => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'primary';
      case 'paid_off':
        return 'success';
      case 'overdue':
        return 'error';
      default:
        return 'default';
    }
  };

  const paginatedLoans = loans.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage
  );

  return (
    <Paper>
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Borrower</TableCell>
              <TableCell align="right">Amount</TableCell>
              <TableCell>Depositor</TableCell>
              <TableCell>Giving Date</TableCell>
              <TableCell>Due Date</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {paginatedLoans.map((loan) => (
              <TableRow key={loan.id} hover>
                <TableCell>{loan.borrower_name}</TableCell>
                <TableCell align="right">{formatCurrency(loan.amount)}</TableCell>
                <TableCell>{loan.depositor_name}</TableCell>
                <TableCell>{formatDate(loan.giving_date)}</TableCell>
                <TableCell>{formatDate(loan.due_date)}</TableCell>
                <TableCell>
                  <Chip
                    label={loan.status.toUpperCase()}
                    color={getStatusColor(loan.status)}
                    size="small"
                  />
                </TableCell>
                <TableCell align="center">
                  <IconButton
                    size="small"
                    onClick={() => onEdit(loan)}
                    aria-label="edit"
                  >
                    <Edit />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={() => onDelete(loan.id)}
                    aria-label="delete"
                    color="error"
                  >
                    <Delete />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={loans.length}
        page={page}
        onPageChange={handleChangePage}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={handleChangeRowsPerPage}
      />
    </Paper>
  );
};
```

### 5. Custom Hooks

```typescript
// src/hooks/useDebounce.ts
import { useEffect, useState } from 'react';

/**
 * Debounce a value to reduce API calls during typing
 */
export function useDebounce<T>(value: T, delay: number = 500): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// Usage in search component
const SearchLoans = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearchTerm = useDebounce(searchTerm, 300);

  const { data: loans } = useLoans({ search: debouncedSearchTerm });

  return (
    <TextField
      value={searchTerm}
      onChange={(e) => setSearchTerm(e.target.value)}
      placeholder="Search loans..."
    />
  );
};
```

### 6. Type Definitions

```typescript
// src/types/loan.ts
export interface Loan {
  id: string;
  borrower_name: string;
  amount: number;
  depositor_name: string;
  giving_date: string; // ISO date string
  due_date: string;
  borrower_group?: string;
  depositor_group?: string;
  status: LoanStatus;
  created_at: string;
  updated_at: string;
}

export type LoanStatus = 'active' | 'paid_off' | 'overdue';

export interface LoanCreate {
  borrower_name: string;
  amount: number;
  depositor_name: string;
  giving_date: Date;
  due_date: Date;
  borrower_group?: string;
  depositor_group?: string;
}

export interface LoanUpdate {
  amount?: number;
  due_date?: Date;
  status?: LoanStatus;
}

export interface LoanFilters {
  borrower_name?: string;
  depositor_name?: string;
  status?: LoanStatus;
  date_from?: string;
  date_to?: string;
  search?: string;
}
```

### 7. Utility Functions

```typescript
// src/utils/formatters.ts
import { format, parseISO } from 'date-fns';

/**
 * Format number as currency (USD)
 */
export const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
};

/**
 * Format ISO date string to readable format
 */
export const formatDate = (dateString: string): string => {
  return format(parseISO(dateString), 'MMM dd, yyyy');
};

/**
 * Calculate days until due date
 */
export const daysUntilDue = (dueDateString: string): number => {
  const dueDate = parseISO(dueDateString);
  const today = new Date();
  const diffTime = dueDate.getTime() - today.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};
```

## Security Best Practices

### 1. XSS Prevention
```typescript
// React automatically escapes values in JSX
// ✅ SAFE: React auto-escapes
<div>{userInput}</div>

// ⚠️ DANGEROUS: Using dangerouslySetInnerHTML (avoid unless sanitized)
<div dangerouslySetInnerHTML={{ __html: sanitizedHtml }} />

// Use DOMPurify if you must render HTML
import DOMPurify from 'dompurify';
const cleanHtml = DOMPurify.sanitize(dirtyHtml);
```

### 2. Content Security Policy
```html
<!-- public/index.html -->
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self';
               script-src 'self' 'unsafe-inline';
               style-src 'self' 'unsafe-inline';
               img-src 'self' data: https:;">
```

### 3. Secure Token Storage
```typescript
// ✅ GOOD: Use httpOnly cookies for sensitive tokens (backend sets)
// ⚠️ ACCEPTABLE: localStorage for less sensitive data with short expiry
const setAuthToken = (token: string, expiresIn: number) => {
  const expiry = Date.now() + expiresIn * 1000;
  localStorage.setItem('auth_token', token);
  localStorage.setItem('token_expiry', expiry.toString());
};

const getAuthToken = (): string | null => {
  const token = localStorage.getItem('auth_token');
  const expiry = localStorage.getItem('token_expiry');

  if (token && expiry && Date.now() < parseInt(expiry)) {
    return token;
  }

  // Token expired, clear storage
  localStorage.removeItem('auth_token');
  localStorage.removeItem('token_expiry');
  return null;
};
```

## Performance Optimization

### 1. Code Splitting
```typescript
// Lazy load routes
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const LoansPage = lazy(() => import('./pages/LoansPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/loans" element={<LoansPage />} />
          <Route path="/reports" element={<ReportsPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
```

### 2. Memoization
```typescript
import { memo, useMemo } from 'react';

// Memoize expensive calculations
const ExpensiveComponent = memo(({ loans }: { loans: Loan[] }) => {
  const totalAmount = useMemo(() => {
    return loans.reduce((sum, loan) => sum + loan.amount, 0);
  }, [loans]);

  return <div>Total: {formatCurrency(totalAmount)}</div>;
});
```

### 3. Virtual Scrolling (for large lists)
```typescript
import { FixedSizeList } from 'react-window';

const LoanList = ({ loans }: { loans: Loan[] }) => (
  <FixedSizeList
    height={600}
    itemCount={loans.length}
    itemSize={50}
    width="100%"
  >
    {({ index, style }) => (
      <div style={style}>
        <LoanCard loan={loans[index]} />
      </div>
    )}
  </FixedSizeList>
);
```

## Testing Strategy

### Unit Tests (Vitest + React Testing Library)
```typescript
// src/components/loans/LoanForm.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LoanForm } from './LoanForm';

const queryClient = new QueryClient();

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
};

describe('LoanForm', () => {
  it('should render all form fields', () => {
    renderWithProviders(<LoanForm />);

    expect(screen.getByLabelText(/borrower name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/amount/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/depositor name/i)).toBeInTheDocument();
  });

  it('should show validation errors for invalid input', async () => {
    renderWithProviders(<LoanForm />);
    const user = userEvent.setup();

    // Submit without filling required fields
    await user.click(screen.getByRole('button', { name: /create loan/i }));

    await waitFor(() => {
      expect(screen.getByText(/borrower name is required/i)).toBeInTheDocument();
    });
  });

  it('should submit form with valid data', async () => {
    const onSuccess = vi.fn();
    renderWithProviders(<LoanForm onSuccess={onSuccess} />);
    const user = userEvent.setup();

    // Fill form
    await user.type(screen.getByLabelText(/borrower name/i), 'John Doe');
    await user.type(screen.getByLabelText(/amount/i), '1000');
    await user.type(screen.getByLabelText(/depositor name/i), 'Jane Smith');

    // Submit
    await user.click(screen.getByRole('button', { name: /create loan/i }));

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });
});
```

## Styling Approach

### MUI Theme Customization
```typescript
// src/styles/theme.ts
import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    error: {
      main: '#f44336',
    },
    warning: {
      main: '#ff9800',
    },
    success: {
      main: '#4caf50',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 600,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none', // Disable uppercase
          borderRadius: 8,
        },
      },
    },
  },
});
```

## Accessibility (a11y)

### Best Practices
```typescript
// ✅ Proper semantic HTML
<button onClick={handleClick}>Submit</button>

// ✅ ARIA labels for icon buttons
<IconButton aria-label="delete loan" onClick={handleDelete}>
  <DeleteIcon />
</IconButton>

// ✅ Keyboard navigation support
<div
  role="button"
  tabIndex={0}
  onClick={handleClick}
  onKeyPress={(e) => e.key === 'Enter' && handleClick()}
>
  Custom Button
</div>

// ✅ Form labels
<label htmlFor="borrower-name">Borrower Name</label>
<input id="borrower-name" type="text" />
```

## Build and Deployment

### Environment Variables
```env
# .env.development
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_NAME=Loan Tracker
VITE_LOG_LEVEL=debug

# .env.production
VITE_API_BASE_URL=https://api.loantracker.com
VITE_APP_NAME=Loan Tracker
VITE_LOG_LEVEL=error
```

### Vite Configuration
```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          mui: ['@mui/material', '@mui/icons-material'],
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

### Docker Build
```dockerfile
# Frontend Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

## Code Quality

### ESLint Configuration
```json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended"
  ],
  "rules": {
    "react/react-in-jsx-scope": "off",
    "@typescript-eslint/no-unused-vars": "error",
    "@typescript-eslint/explicit-function-return-type": "warn"
  }
}
```

### Pre-commit Hooks
```json
// package.json
{
  "lint-staged": {
    "*.{ts,tsx}": [
      "eslint --fix",
      "prettier --write"
    ]
  },
  "husky": {
    "hooks": {
      "pre-commit": "lint-staged"
    }
  }
}
```

---

**Last Updated**: 2026-03-07
**Status**: Draft - Awaiting Review
