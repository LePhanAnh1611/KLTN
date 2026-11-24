import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from './client';

/** UC-72 — chỉ số tổng quan. */
export interface AdminOverview {
  total_users: number;
  active_users: number;
  dau: number;
  mau: number;
  total_sessions: number;
  total_interactions: number;
  total_word_sets: number;
  public_word_sets: number;
  total_items: number;
  total_posts: number;
  pending_reports: number;
}

export function useAdminOverview() {
  return useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: () => apiGet<AdminOverview>('/api/v1/admin/overview'),
  });
}

/** UC-73 — quản lý người dùng. */
export type UserRole = 'learner' | 'content' | 'admin';

export interface AdminUserRow {
  id: number;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  xp: number;
  is_me: boolean;
}

export interface AdminUserListResponse {
  items: AdminUserRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUserParams {
  q?: string;
  role?: UserRole | '';
  page?: number;
}

export function useAdminUsers(params: AdminUserParams) {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.role) sp.set('role', params.role);
  if (params.page) sp.set('page', String(params.page));
  const qs = sp.toString();

  return useQuery({
    queryKey: ['admin', 'users', params],
    queryFn: () => apiGet<AdminUserListResponse>(`/api/v1/admin/users${qs ? `?${qs}` : ''}`),
  });
}

export function useSetUserRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, role }: { id: number; role: UserRole }) =>
      apiPatch<AdminUserRow>(`/api/v1/admin/users/${id}/role`, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin'] }),
  });
}

export function useSetUserActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isActive, reason }: { id: number; isActive: boolean; reason?: string }) =>
      apiPatch<AdminUserRow>(`/api/v1/admin/users/${id}/active`, {
        is_active: isActive, reason: reason ?? null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin'] }),
  });
}

/** UC-75 — kho bộ từ. */
export interface AdminWordSetRow {
  id: number;
  name: string;
  owner_id: number;
  owner_name: string;
  category: string | null;
  difficulty: string | null;
  is_public: boolean;
  is_featured: boolean;
  download_count: number;
  item_count: number;
  created_at: string;
}

export interface AdminWordSetListResponse {
  items: AdminWordSetRow[];
  total: number;
  page: number;
  page_size: number;
}

export function useAdminWordSets(q: string, page: number) {
  const sp = new URLSearchParams();
  if (q) sp.set('q', q);
  sp.set('page', String(page));

  return useQuery({
    queryKey: ['admin', 'word-sets', q, page],
    queryFn: () => apiGet<AdminWordSetListResponse>(`/api/v1/admin/word-sets?${sp}`),
  });
}

export function useUpdateAdminWordSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; is_featured?: boolean; is_public?: boolean }) =>
      apiPatch<AdminWordSetRow>(`/api/v1/admin/word-sets/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'word-sets'] }),
  });
}

export function useDeleteAdminWordSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/admin/word-sets/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'word-sets'] }),
  });
}

/** UC-81 — cấu hình hệ thống. */
export interface SystemConfigItem {
  key: string;
  value: number | boolean;
  value_type: 'float' | 'int' | 'bool';
  label: string;
  description: string;
  minimum: number | null;
  maximum: number | null;
  default: number | boolean;
}

export function useSystemConfig() {
  return useQuery({
    queryKey: ['admin', 'config'],
    queryFn: () => apiGet<SystemConfigItem[]>('/api/v1/admin/config'),
  });
}

export function useUpdateSystemConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (values: Record<string, number | boolean>) =>
      apiPut<SystemConfigItem[]>('/api/v1/admin/config', { values }),
    onSuccess: (data) => {
      qc.setQueryData(['admin', 'config'], data);
      qc.invalidateQueries({ queryKey: ['admin', 'audit-logs'] });
    },
  });
}

/** UC-77 — kiểm duyệt bài viết. */
export interface ModerationPost {
  id: number;
  post_type: string;
  content: string;
  image_url: string | null;
  status: string;
  created_at: string;
  author_id: number;
  author_name: string;
}

export function useModerationQueue(status: string) {
  return useQuery({
    queryKey: ['admin', 'moderation', status],
    queryFn: () =>
      apiGet<{ items: ModerationPost[]; total: number }>(`/api/v1/admin/posts?status=${status}`),
  });
}

export function useModeratePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision, reason }:
      { id: number; decision: 'approve' | 'reject' | 'remove'; reason?: string }) =>
      apiPatch<ModerationPost>(`/api/v1/admin/posts/${id}`, { decision, reason: reason ?? null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'moderation'] }),
  });
}

/** UC-78 — xử lý báo cáo. */
export interface ReportRow {
  id: number;
  target_type: string;
  target_id: number;
  reason: string;
  description: string | null;
  status: string;
  created_at: string;
  resolved_at: string | null;
  reporter_id: number;
  reporter_name: string;
  target_preview: string | null;
  target_exists: boolean;
}

export function useReports(status: string) {
  return useQuery({
    queryKey: ['admin', 'reports', status],
    queryFn: () =>
      apiGet<{ items: ReportRow[]; total: number }>(`/api/v1/admin/reports?status=${status}`),
  });
}

export function useResolveReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision, note }:
      { id: number; decision: 'dismiss' | 'remove_content'; note?: string }) =>
      apiPatch<ReportRow>(`/api/v1/admin/reports/${id}`, { decision, note: note ?? null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'reports'] });
      qc.invalidateQueries({ queryKey: ['admin', 'overview'] });
    },
  });
}

/** UC-82 — gửi thông báo hàng loạt. */
export interface BroadcastResult {
  recipients: number;
  notifications_created: number;
  emails_queued: number;
}

export function useSendBroadcast() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      title: string; body?: string | null; link?: string | null;
      audience: 'all' | 'role'; role?: UserRole | null; send_email: boolean;
    }) => apiPost<BroadcastResult>('/api/v1/admin/broadcast', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'emails'] }),
  });
}

/** UC-80 — hàng đợi email. */
export interface EmailQueueRow {
  id: number;
  to_email: string;
  subject: string;
  template: string | null;
  status: string;
  attempts: number;
  last_error: string | null;
  scheduled_at: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface EmailQueueListResponse {
  items: EmailQueueRow[];
  total: number;
  page: number;
  page_size: number;
  counts: Record<string, number>;
}

export function useEmailQueue(status: string, page: number) {
  const sp = new URLSearchParams();
  if (status) sp.set('status', status);
  sp.set('page', String(page));

  return useQuery({
    queryKey: ['admin', 'emails', status, page],
    queryFn: () => apiGet<EmailQueueListResponse>(`/api/v1/admin/emails?${sp}`),
  });
}

export function useRetryEmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiPost<EmailQueueRow>(`/api/v1/admin/emails/${id}/retry`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'emails'] }),
  });
}

export function useDeleteEmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/admin/emails/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'emails'] }),
  });
}

/** UC-76 — danh mục bộ từ. */
export interface Category {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface CategoryAdminRow extends Category {
  word_set_count: number;
}

export function useAdminCategories() {
  return useQuery({
    queryKey: ['admin', 'categories'],
    queryFn: () => apiGet<CategoryAdminRow[]>('/api/v1/admin/categories'),
  });
}

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string | null }) =>
      apiPost<Category>('/api/v1/admin/categories', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'categories'] }),
  });
}

export function useUpdateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; name?: string; is_active?: boolean }) =>
      apiPatch<Category>(`/api/v1/admin/categories/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'categories'] }),
  });
}

export function useDeleteCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/admin/categories/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'categories'] }),
  });
}

/** UC-79 — định nghĩa huy hiệu. */
export type ConditionKey = 'sessions_completed' | 'xp' | 'streak' | 'mastered';

export interface AchievementDefinition {
  id: number;
  code: string;
  name: string;
  description: string;
  condition_key: ConditionKey;
  threshold: number;
  icon: string | null;
  is_active: boolean;
  sort_order: number;
}

export function useAchievementDefinitions() {
  return useQuery({
    queryKey: ['admin', 'achievements'],
    queryFn: () => apiGet<AchievementDefinition[]>('/api/v1/admin/achievements'),
  });
}

export function useCreateAchievement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      code: string; name: string; description: string;
      condition_key: ConditionKey; threshold: number;
    }) => apiPost<AchievementDefinition>('/api/v1/admin/achievements', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'achievements'] }),
  });
}

export function useUpdateAchievement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; threshold?: number; is_active?: boolean }) =>
      apiPatch<AchievementDefinition>(`/api/v1/admin/achievements/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'achievements'] }),
  });
}

export function useDeleteAchievement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/admin/achievements/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'achievements'] }),
  });
}

/** UC-74 — vai trò & phân quyền. */
export interface PermissionInfo {
  key: string;
  label: string;
  description: string;
}

export interface RolePermissionMatrix {
  permissions: PermissionInfo[];
  roles: string[];
  matrix: Record<string, string[]>;
}

/** Quyền của chính người đang đăng nhập — quyết định hiện mục/tab nào. */
export function useMyPermissions() {
  return useQuery({
    queryKey: ['admin', 'my-permissions'],
    queryFn: () => apiGet<string[]>('/api/v1/admin/my-permissions'),
  });
}

export function usePermissionMatrix(enabled = true) {
  return useQuery({
    queryKey: ['admin', 'permissions'],
    queryFn: () => apiGet<RolePermissionMatrix>('/api/v1/admin/permissions'),
    enabled,
    retry: false,
  });
}

export function useSetRolePermissions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ role, permissions }: { role: string; permissions: string[] }) =>
      apiPut<RolePermissionMatrix>(`/api/v1/admin/permissions/${role}`, { permissions }),
    onSuccess: (data) => qc.setQueryData(['admin', 'permissions'], data),
  });
}

/** UC-83 — nhật ký hệ thống. */
export interface AuditLogEntry {
  id: number;
  action: string;
  target_type: string | null;
  target_id: number | null;
  detail: string | null;
  actor_id: number | null;
  actor_name: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export function useAuditLogs(page: number) {
  return useQuery({
    queryKey: ['admin', 'audit-logs', page],
    queryFn: () => apiGet<AuditLogListResponse>(`/api/v1/admin/audit-logs?page=${page}`),
  });
}

/** UC-62/UC-63 — chạy tay tác vụ nền (bình thường do scheduler gọi). */
export function useRunJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (job: 'send-emails' | 'run-reminders') =>
      apiPost<Record<string, number>>(`/api/v1/admin/jobs/${job}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin'] }),
  });
}

/** UC-11 — ngân hàng câu hỏi kiểm tra đầu vào (Admin, quyền admin.content). */
export interface PlacementQuestionRow {
  id: number;
  cefr_level: string;
  word: string;
  correct_meaning: string;
  distractors: string[];
  is_active: boolean;
}

export interface PlacementQuestionInput {
  cefr_level: string;
  word: string;
  correct_meaning: string;
  distractors: string[];
  is_active?: boolean;
}

export interface PlacementBankStat {
  cefr_level: string;
  active_count: number;
  total_count: number;
}

const PQ_KEY = ['admin', 'placement-questions'];

export function usePlacementQuestions(cefrLevel: string) {
  return useQuery({
    queryKey: [...PQ_KEY, cefrLevel],
    queryFn: () => apiGet<PlacementQuestionRow[]>(
      `/api/v1/admin/placement-questions${cefrLevel ? `?cefr_level=${cefrLevel}` : ''}`,
    ),
  });
}

export function usePlacementBankStats() {
  return useQuery({
    queryKey: [...PQ_KEY, 'stats'],
    queryFn: () => apiGet<PlacementBankStat[]>('/api/v1/admin/placement-questions/stats'),
  });
}

export function useCreatePlacementQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PlacementQuestionInput) =>
      apiPost<PlacementQuestionRow>('/api/v1/admin/placement-questions', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: PQ_KEY }),
  });
}

export function useUpdatePlacementQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<PlacementQuestionInput> & { id: number }) =>
      apiPatch<PlacementQuestionRow>(`/api/v1/admin/placement-questions/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: PQ_KEY }),
  });
}

export function useDeletePlacementQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/admin/placement-questions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: PQ_KEY }),
  });
}

/** UC-70 — giám sát hiệu năng mô hình trên dữ liệu hệ thống. */
export interface ModelHealth {
  model_name: string;
  sample_size: number;
  lookback_days: number;
  /** null = mẫu chưa đủ để kết luận (khác với "bằng 0"). */
  accuracy: number | null;
  brier: number | null;
  /** Tỉ lệ trả lời đúng thực tế — bộ "đoán theo lớp đa số". Mô hình không vượt
   *  được số này thì accuracy cao cũng không nói lên điều gì. */
  baseline_accuracy: number | null;
  /** Tỉ lệ state ĐÃ có tương tác mà mô hình chấm được (không tính từ chưa học). */
  coverage: number;
  covered_states: number;
  answered_states: number;
  /** Tỉ lệ từ trong thư viện mà service phục vụ biết. null = service không sẵn sàng. */
  vocab_coverage: number | null;
  reliable: boolean;
  note: string;
}

export interface MetricPoint {
  metric: string;
  value: number;
  sample_size: number;
  recorded_at: string;
}

export function useModelHealth(days: number) {
  return useQuery({
    queryKey: ['admin', 'model-health', days],
    queryFn: () => apiGet<ModelHealth>(`/api/v1/admin/model-health?days=${days}`),
  });
}

export function useModelHealthHistory() {
  return useQuery({
    queryKey: ['admin', 'model-health', 'history'],
    queryFn: () => apiGet<MetricPoint[]>('/api/v1/admin/model-health/history'),
  });
}

export function useSnapshotModelHealth() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (days: number) =>
      apiPost<ModelHealth>(`/api/v1/admin/model-health/snapshot?days=${days}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'model-health'] }),
  });
}

// --- UC-93 · So sánh định lượng lịch ôn DKT vs SM-2 -------------------------

export interface SchedulerArm {
  scheduler: 'sm2' | 'dkt' | 'dkt_hl' | 'fixed';
  budget: number;
  pool: number;
  introduced: number;
  reviews: number;
  recall_end: number;
  recall_delayed: number;
  mastered_delayed: number;
  recall_per_100_reviews: number;
  wasted_pct: number;
  late_pct: number;
  mean_gap_days: number;
  mean_p_at_review: number;
  daily_recall: number[];
}

export interface SchedulerGap {
  key: string;
  mean_diff: number;
  ci_low: number;
  ci_high: number;
  win_rate: number;
  n_learners: number;
}

export interface SchedulerComparison {
  generated_at: string;
  setup: {
    learners: number;
    horizon_days: number;
    delay_days: number;
    budgets: number[];
    main_budget: number;
    pools: number[];
    main_pool: number;
    mastered_threshold: number;
    n_words: number;
    model: string;
    seconds: number;
  };
  memory_model: Record<string, unknown>;
  arms: SchedulerArm[];
  gaps: SchedulerGap[];
}

export function useSchedulerComparison() {
  return useQuery({
    queryKey: ['admin', 'scheduler-comparison'],
    queryFn: () => apiGet<SchedulerComparison>('/api/v1/admin/scheduler-comparison'),
    retry: false,   // thiếu file thí nghiệm là 404 hợp lệ, thử lại vô ích
  });
}
