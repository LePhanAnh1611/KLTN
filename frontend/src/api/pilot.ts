import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost } from './client';

// --- Theo dõi pilot (Admin) ---------------------------------------------------

export interface PilotCriterion {
  key: string;
  label: string;
  why: string;
  current: number;
  target: number;
  met: boolean;
}

export interface PilotParticipant {
  user_id: number;
  display_name: string;
  email: string;
  registered_at: string;
  placement_done: boolean;
  active_days: number;
  answers_total: number;
  answers_today: number;
  last_active_at: string | null;
  days_inactive: number | null;
  needs_nudge: boolean;
  validation_done: boolean;
}

export interface PilotBin {
  low: number;
  high: number;
  count: number;
  accuracy: number | null;
}

export interface PilotReport {
  generated_at: string;
  pilot_start: string | null;
  pilot_day: number | null;
  registered: number;
  participants: number;
  active_today: number;
  answers_today: number;
  answers_total: number;
  model_share: number | null;
  explore_answers: number;
  validation_done: number;
  criteria: PilotCriterion[];
  ready: boolean;
  bins: PilotBin[];
  people: PilotParticipant[];
}

export function usePilotReport() {
  return useQuery({
    queryKey: ['admin', 'pilot'],
    queryFn: () => apiGet<PilotReport>('/api/v1/admin/pilot'),
    refetchInterval: 60_000,
  });
}

export function useSendPilotReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<PilotReport>('/api/v1/admin/pilot/send-report', {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'pilot'] }),
  });
}

// --- Bài kiểm tra cuối (người học) ---------------------------------------------

export interface ValidationStatus {
  open: boolean;
  done: boolean;
  in_progress_session_id: number | null;
  eligible_items: number;
  size: number;
  min_items: number;
}

export interface ValidationQuestion {
  item_id: number;
  meaning: string;
  part_of_speech: string | null;
  first_letter: string;
  length: number;
}

export interface ValidationStart {
  session_id: number;
  questions: ValidationQuestion[];
}

export function useValidationStatus() {
  return useQuery({
    queryKey: ['validation', 'status'],
    queryFn: () => apiGet<ValidationStatus>('/api/v1/validation/status'),
  });
}

export function startValidation(): Promise<ValidationStart> {
  return apiPost<ValidationStart>('/api/v1/validation/start', {});
}
