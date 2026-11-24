import { useQuery } from '@tanstack/react-query';

import type { DashboardData } from '../types/dashboard';
import { apiGet } from './client';

function fetchDashboard(): Promise<DashboardData> {
  return apiGet<DashboardData>('/api/v1/dashboard');
}

export function useDashboard() {
  return useQuery({ queryKey: ['dashboard'], queryFn: fetchDashboard });
}
