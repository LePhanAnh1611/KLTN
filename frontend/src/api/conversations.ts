import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost, apiPostForm } from './client';

/** UC-39 — hội thoại roleplay với nhân vật AI.
 *
 * Module luyện nói độc lập với lõi DKT: không endpoint nào ở đây đụng tới
 * mastery hay lịch ôn.
 */
export interface Scenario {
  key: string;
  name: string;
  description: string;
  persona: string;
  /** Giới tính giọng đọc của nhân vật (bug #11). */
  voice: 'female' | 'male';
  cefr: string;
  opening: string;
}

export interface ConversationTurn {
  ordinal: number;
  speaker: 'ai' | 'user';
  text: string;
  correction: string | null;
  asr_confidence: number | null;
  created_at: string;
}

export interface ConversationDetail {
  id: number;
  scenario: string;
  scenario_name: string;
  persona: string;
  /** Giới tính giọng đọc của nhân vật (bug #11). */
  voice: 'female' | 'male';
  cefr: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  turns: ConversationTurn[];
}

export interface ConversationRow {
  id: number;
  scenario: string;
  scenario_name: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  turn_count: number;
}

export function useScenarios() {
  return useQuery({
    queryKey: ['conversations', 'scenarios'],
    queryFn: () => apiGet<Scenario[]>('/api/v1/conversations/scenarios'),
  });
}

export function useConversationHistory() {
  return useQuery({
    queryKey: ['conversations', 'history'],
    queryFn: () => apiGet<ConversationRow[]>('/api/v1/conversations'),
  });
}

export function useStartConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scenario: string) =>
      apiPost<ConversationDetail>('/api/v1/conversations', { scenario }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['conversations', 'history'] }),
  });
}

export function useReplyText(conversationId: number | null) {
  return useMutation({
    mutationFn: (text: string) =>
      apiPost<ConversationDetail>(`/api/v1/conversations/${conversationId}/turns`, { text }),
  });
}

export function useReplyAudio(conversationId: number | null) {
  return useMutation({
    mutationFn: (blob: Blob) => {
      const form = new FormData();
      form.append('audio', blob, 'turn.webm');
      form.append('language', 'en');
      return apiPostForm<ConversationDetail>(
        `/api/v1/conversations/${conversationId}/turns/audio`, form,
      );
    },
  });
}

export function useEndConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiPost<ConversationDetail>(`/api/v1/conversations/${id}/end`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['conversations', 'history'] }),
  });
}
