import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Pagination from '@mui/material/Pagination';
import Paper from '@mui/material/Paper';
import Snackbar from '@mui/material/Snackbar';
import Switch from '@mui/material/Switch';
import Tab from '@mui/material/Tab';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import PageHeader from '../components/PageHeader';
import SchedulerComparison from '../components/SchedulerComparison';
import PilotMonitor from '../components/PilotMonitor';
import {
  useAchievementDefinitions,
  useAdminCategories,
  useAdminOverview,
  useAdminUsers,
  useAdminWordSets,
  useAuditLogs,
  useCreateAchievement,
  useCreateCategory,
  useCreatePlacementQuestion,
  useModelHealth,
  useModelHealthHistory,
  useSnapshotModelHealth,
  useDeletePlacementQuestion,
  usePlacementBankStats,
  usePlacementQuestions,
  useUpdatePlacementQuestion,
  useDeleteAchievement,
  useDeleteAdminWordSet,
  useDeleteCategory,
  useDeleteEmail,
  useEmailQueue,
  useModeratePost,
  useModerationQueue,
  useReports,
  useResolveReport,
  useRetryEmail,
  useRunJob,
  useSendBroadcast,
  useSetUserActive,
  useSetUserRole,
  useMyPermissions,
  usePermissionMatrix,
  useSetRolePermissions,
  useSystemConfig,
  useUpdateAchievement,
  useUpdateAdminWordSet,
  useUpdateCategory,
  useUpdateSystemConfig,
  type ConditionKey,
  type UserRole,
} from '../api/admin';
import { ApiError } from '../api/client';
import StatCard from '../components/StatCard';
import ShadowingAdminTab from '../components/ShadowingAdminTab';

const ROLES: UserRole[] = ['learner', 'content', 'admin'];

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

/** UC-72 — chỉ số tổng quan + nút chạy tay tác vụ nền (UC-62/63). */
function OverviewTab({ onResult }: { onResult: (msg: string) => void }) {
  const { data, isLoading } = useAdminOverview();
  const runJob = useRunJob();

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (!data) return <Alert severity="error">Không tải được chỉ số.</Alert>;

  const run = (job: 'send-emails' | 'run-reminders', label: string) => () =>
    runJob.mutate(job, {
      onSuccess: (res) => onResult(`${label}: ${JSON.stringify(res)}`),
      onError: (e) => onResult(e instanceof ApiError ? e.message : 'Chạy tác vụ thất bại.'),
    });

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <StatCard label="Người dùng" value={data.total_users} />
        <StatCard label="Đang hoạt động" value={data.active_users} />
        <StatCard label="DAU" value={data.dau} />
        <StatCard label="MAU (30 ngày)" value={data.mau} />
        <StatCard label="Phiên học" value={data.total_sessions} />
        <StatCard label="Lượt trả lời" value={data.total_interactions} />
        <StatCard label="Bộ từ vựng" value={data.total_word_sets} />
        <StatCard label="Bộ công khai" value={data.public_word_sets} />
        <StatCard label="Số từ" value={data.total_items} />
        <StatCard label="Bài viết" value={data.total_posts} />
        <StatCard label="Báo cáo chờ xử lý" value={data.pending_reports} />
      </Box>

      <Typography variant="h6" gutterBottom>Tác vụ nền</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Bình thường do bộ lập lịch chạy tự động; các nút dưới đây để chạy ngay khi demo.
      </Typography>
      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
        <Button variant="outlined" disabled={runJob.isPending}
                onClick={run('run-reminders', 'Nhắc ôn')}>
          Chạy quét nhắc ôn (UC-63)
        </Button>
        <Button variant="outlined" disabled={runJob.isPending}
                onClick={run('send-emails', 'Gửi email')}>
          Đẩy hàng đợi email (UC-62)
        </Button>
      </Box>
    </Box>
  );
}

/** UC-73 — tìm/lọc, đổi vai trò, khóa/mở khóa. */
function UsersTab({ onResult }: { onResult: (msg: string) => void }) {
  const [q, setQ] = useState('');
  const [role, setRole] = useState<UserRole | ''>('');
  const [page, setPage] = useState(1);
  const { data, isLoading } = useAdminUsers({ q: q || undefined, role, page });
  const setUserRole = useSetUserRole();
  const setUserActive = useSetUserActive();

  const onError = (e: unknown) =>
    onResult(e instanceof ApiError ? e.message : 'Thao tác thất bại.');
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <TextField size="small" label="Tìm email / tên" value={q}
                   onChange={(e) => { setQ(e.target.value); setPage(1); }} sx={{ minWidth: 240 }} />
        <TextField size="small" select label="Vai trò" value={role} sx={{ minWidth: 150 }}
                   onChange={(e) => { setRole(e.target.value as UserRole | ''); setPage(1); }}>
          <MenuItem value="">Tất cả</MenuItem>
          {ROLES.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
        </TextField>
      </Box>

      {isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}

      <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Email</TableCell>
              <TableCell>Tên</TableCell>
              <TableCell>XP</TableCell>
              <TableCell>Vai trò</TableCell>
              <TableCell>Trạng thái</TableCell>
              <TableCell align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data?.items.map((u) => (
              <TableRow key={u.id}>
                <TableCell>{u.email}{u.is_me ? ' (bạn)' : ''}</TableCell>
                <TableCell>{u.display_name}</TableCell>
                <TableCell>{u.xp}</TableCell>
                <TableCell>
                  <TextField
                    select size="small" value={u.role} disabled={u.is_me} sx={{ minWidth: 120 }}
                    onChange={(e) =>
                      setUserRole.mutate(
                        { id: u.id, role: e.target.value as UserRole },
                        { onSuccess: () => onResult('Đã đổi vai trò.'), onError },
                      )
                    }
                  >
                    {ROLES.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
                  </TextField>
                </TableCell>
                <TableCell>
                  <Chip size="small" color={u.is_active ? 'success' : 'default'}
                        label={u.is_active ? 'Hoạt động' : 'Đã khóa'} />
                </TableCell>
                <TableCell align="right">
                  <Button
                    size="small" color={u.is_active ? 'error' : 'primary'} disabled={u.is_me}
                    onClick={() =>
                      setUserActive.mutate(
                        { id: u.id, isActive: !u.is_active },
                        {
                          onSuccess: () => onResult(u.is_active ? 'Đã khóa tài khoản.' : 'Đã mở khóa.'),
                          onError,
                        },
                      )
                    }
                  >
                    {u.is_active ? 'Khóa' : 'Mở khóa'}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {pageCount > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" />
        </Box>
      )}
    </Box>
  );
}

/** UC-75 — kho bộ từ: gắn nổi bật (khép UC-22), gỡ công khai, xóa mềm. */
function WordSetsTab({ onResult }: { onResult: (msg: string) => void }) {
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const { data, isLoading } = useAdminWordSets(q, page);
  const update = useUpdateAdminWordSet();
  const remove = useDeleteAdminWordSet();

  const onError = (e: unknown) =>
    onResult(e instanceof ApiError ? e.message : 'Thao tác thất bại.');
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <Box>
      <TextField size="small" label="Tìm theo tên" value={q} sx={{ mb: 2, minWidth: 260 }}
                 onChange={(e) => { setQ(e.target.value); setPage(1); }} />

      {isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}

      <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Tên</TableCell>
              <TableCell>Chủ sở hữu</TableCell>
              <TableCell>Số từ</TableCell>
              <TableCell>Lượt tải</TableCell>
              <TableCell>Công khai</TableCell>
              <TableCell>Nổi bật</TableCell>
              <TableCell align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data?.items.map((ws) => (
              <TableRow key={ws.id}>
                <TableCell>{ws.name}</TableCell>
                <TableCell>{ws.owner_name}</TableCell>
                <TableCell>{ws.item_count}</TableCell>
                <TableCell>{ws.download_count}</TableCell>
                <TableCell>
                  <Switch
                    size="small" checked={ws.is_public}
                    onChange={(e) =>
                      update.mutate(
                        { id: ws.id, is_public: e.target.checked },
                        { onSuccess: () => onResult('Đã cập nhật trạng thái công khai.'), onError },
                      )
                    }
                  />
                </TableCell>
                <TableCell>
                  <Switch
                    size="small" checked={ws.is_featured}
                    onChange={(e) =>
                      update.mutate(
                        { id: ws.id, is_featured: e.target.checked },
                        { onSuccess: () => onResult('Đã cập nhật cờ nổi bật.'), onError },
                      )
                    }
                  />
                </TableCell>
                <TableCell align="right">
                  <Button
                    size="small" color="error"
                    onClick={() =>
                      remove.mutate(ws.id, {
                        onSuccess: () => onResult('Đã xóa mềm bộ từ vựng.'),
                        onError,
                      })
                    }
                  >
                    Xóa
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {pageCount > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" />
        </Box>
      )}
    </Box>
  );
}

/** UC-81 — chỉnh tham số vận hành (θ_review, vùng vừa sức, quy đổi XP...). */
function ConfigTab({ onResult }: { onResult: (msg: string) => void }) {
  const { data } = useSystemConfig();
  const update = useUpdateSystemConfig();
  const [draft, setDraft] = useState<Record<string, string>>({});

  if (!data) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;

  const save = (key: string, value: number | boolean) =>
    update.mutate(
      { [key]: value },
      {
        onSuccess: () => { onResult('Đã lưu cấu hình.'); setDraft((d) => ({ ...d, [key]: '' })); },
        onError: (e) => onResult(e instanceof ApiError ? e.message : 'Lưu cấu hình thất bại.'),
      },
    );

  return (
    <Box sx={{ maxWidth: 760, mx: 'auto' }}>
      <Alert severity="info" sx={{ mb: 2 }}>
        Tham số áp dụng ngay cho tính XP (UC-46), gợi ý vừa sức (UC-65) và lịch ôn (UC-66).
        Giá trị ngoài khoảng an toàn sẽ bị từ chối.
      </Alert>

      {data.map((c) => (
        <Paper key={c.key} sx={{ p: 2, mb: 1.5 }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <Box sx={{ flexGrow: 1, minWidth: 220 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{c.label}</Typography>
              <Typography variant="caption" color="text.secondary">
                {c.description}
                {c.minimum != null && ` · khoảng cho phép ${c.minimum}-${c.maximum}`}
              </Typography>
            </Box>

            {c.value_type === 'bool' ? (
              <Switch
                checked={Boolean(c.value)} disabled={update.isPending}
                onChange={(e) => save(c.key, e.target.checked)}
              />
            ) : (
              <>
                <TextField
                  size="small" type="number" sx={{ width: 120 }}
                  value={draft[c.key] ?? String(c.value)}
                  onChange={(e) => setDraft((d) => ({ ...d, [c.key]: e.target.value }))}
                  slotProps={{ htmlInput: {
                    step: c.value_type === 'float' ? 0.05 : 1,
                    min: c.minimum ?? undefined, max: c.maximum ?? undefined,
                  } }}
                />
                <Button
                  size="small" variant="outlined" disabled={update.isPending}
                  onClick={() => save(c.key, Number(draft[c.key] ?? c.value))}
                >
                  Lưu
                </Button>
              </>
            )}
          </Box>
        </Paper>
      ))}
    </Box>
  );
}

/** UC-77 — duyệt / từ chối bài chờ, gỡ bài đã hiển thị. */
function ModerationTab({ onResult }: { onResult: (msg: string) => void }) {
  const [status, setStatus] = useState('pending');
  const { data, isLoading } = useModerationQueue(status);
  const moderate = useModeratePost();

  const act = (id: number, decision: 'approve' | 'reject' | 'remove', label: string) => () =>
    moderate.mutate(
      { id, decision },
      {
        onSuccess: () => onResult(label),
        onError: (e) => onResult(e instanceof ApiError ? e.message : 'Thao tác thất bại.'),
      },
    );

  return (
    <Box>
      <TextField select size="small" label="Trạng thái" value={status} sx={{ minWidth: 180, mb: 2 }}
                 onChange={(e) => setStatus(e.target.value)}>
        <MenuItem value="pending">Chờ duyệt</MenuItem>
        <MenuItem value="approved">Đã hiển thị</MenuItem>
        <MenuItem value="rejected">Đã từ chối</MenuItem>
      </TextField>

      {isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}
      {data?.total === 0 && (
        <Alert severity="info">
          {status === 'pending'
            ? 'Không có bài nào chờ duyệt. (Bật "Duyệt bài trước khi hiển thị" ở tab Cấu hình để dùng hàng đợi này.)'
            : 'Không có bài nào ở trạng thái này.'}
        </Alert>
      )}

      {data?.items.map((p) => (
        <Paper key={p.id} sx={{ p: 2, mb: 1.5 }}>
          <Typography variant="caption" color="text.secondary">
            {p.author_name} · {formatTime(p.created_at)} · {p.post_type}
          </Typography>
          <Typography variant="body2" sx={{ my: 1, whiteSpace: 'pre-wrap' }}>{p.content}</Typography>
          {p.image_url && (
            <Box component="img" src={p.image_url} alt=""
                 sx={{ maxWidth: 240, borderRadius: 1, display: 'block', mb: 1 }} />
          )}
          <Box sx={{ display: 'flex', gap: 1 }}>
            {p.status === 'pending' && (
              <>
                <Button size="small" variant="contained" disabled={moderate.isPending}
                        onClick={act(p.id, 'approve', 'Đã duyệt bài.')}>
                  Duyệt
                </Button>
                <Button size="small" color="warning" disabled={moderate.isPending}
                        onClick={act(p.id, 'reject', 'Đã từ chối bài.')}>
                  Từ chối
                </Button>
              </>
            )}
            {p.status === 'approved' && (
              <Button size="small" color="error" disabled={moderate.isPending}
                      onClick={act(p.id, 'remove', 'Đã gỡ bài.')}>
                Gỡ bài
              </Button>
            )}
          </Box>
        </Paper>
      ))}
    </Box>
  );
}

/** UC-78 — xử lý báo cáo từ UC-24 (bộ từ) và UC-53 (bài viết). */
function ReportsTab({ onResult }: { onResult: (msg: string) => void }) {
  const [status, setStatus] = useState('pending');
  const { data, isLoading } = useReports(status);
  const resolve = useResolveReport();

  const act = (id: number, decision: 'dismiss' | 'remove_content', label: string) => () =>
    resolve.mutate(
      { id, decision },
      {
        onSuccess: () => onResult(label),
        onError: (e) => onResult(e instanceof ApiError ? e.message : 'Thao tác thất bại.'),
      },
    );

  return (
    <Box>
      <TextField select size="small" label="Trạng thái" value={status} sx={{ minWidth: 180, mb: 2 }}
                 onChange={(e) => setStatus(e.target.value)}>
        <MenuItem value="pending">Chờ xử lý</MenuItem>
        <MenuItem value="resolved">Đã gỡ nội dung</MenuItem>
        <MenuItem value="dismissed">Đã bỏ qua</MenuItem>
      </TextField>

      {isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}
      {data?.total === 0 && <Alert severity="info">Không có báo cáo nào ở trạng thái này.</Alert>}

      {data?.items.map((r) => (
        <Paper key={r.id} sx={{ p: 2, mb: 1.5 }}>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
            <Chip size="small" label={r.target_type === 'word_set' ? 'Bộ từ vựng' : 'Bài viết'} />
            <Chip size="small" color="warning" label={r.reason} />
            {!r.target_exists && <Chip size="small" label="Nội dung đã bị gỡ" />}
            <Typography variant="caption" color="text.secondary">
              {r.reporter_name} báo cáo · {formatTime(r.created_at)}
            </Typography>
          </Box>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {r.target_preview ?? '(nội dung không còn)'}
          </Typography>
          {r.description && (
            <Typography variant="body2" color="text.secondary">{r.description}</Typography>
          )}

          {r.status === 'pending' && (
            <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
              <Button size="small" disabled={resolve.isPending}
                      onClick={act(r.id, 'dismiss', 'Đã bỏ qua báo cáo.')}>
                Bỏ qua
              </Button>
              <Button size="small" variant="contained" color="error" disabled={resolve.isPending}
                      onClick={act(r.id, 'remove_content', 'Đã gỡ nội dung vi phạm.')}>
                Gỡ nội dung
              </Button>
            </Box>
          )}
        </Paper>
      ))}
    </Box>
  );
}

/** UC-82 soạn & gửi broadcast · UC-80 theo dõi hàng đợi email. */
function EmailsTab({ onResult }: { onResult: (msg: string) => void }) {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [audience, setAudience] = useState<'all' | 'role'>('all');
  const [role, setRole] = useState<UserRole>('learner');
  const [sendEmail, setSendEmail] = useState(false);
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);

  const broadcast = useSendBroadcast();
  const { data } = useEmailQueue(status, page);
  const retry = useRetryEmail();
  const remove = useDeleteEmail();

  const onError = (e: unknown) =>
    onResult(e instanceof ApiError ? e.message : 'Thao tác thất bại.');
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Gửi thông báo hàng loạt</Typography>
      <Paper sx={{ p: 2, mb: 3, maxWidth: 720 }}>
        <TextField fullWidth size="small" label="Tiêu đề" value={title} sx={{ mb: 1.5 }}
                   onChange={(e) => setTitle(e.target.value)} />
        <TextField fullWidth size="small" label="Nội dung" multiline minRows={2} value={body}
                   sx={{ mb: 1.5 }} onChange={(e) => setBody(e.target.value)} />
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField select size="small" label="Đối tượng" value={audience} sx={{ minWidth: 150 }}
                     onChange={(e) => setAudience(e.target.value as 'all' | 'role')}>
            <MenuItem value="all">Tất cả</MenuItem>
            <MenuItem value="role">Theo vai trò</MenuItem>
          </TextField>
          {audience === 'role' && (
            <TextField select size="small" label="Vai trò" value={role} sx={{ minWidth: 140 }}
                       onChange={(e) => setRole(e.target.value as UserRole)}>
              {ROLES.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
            </TextField>
          )}
          <FormControlLabel
            control={<Switch checked={sendEmail} onChange={(e) => setSendEmail(e.target.checked)} />}
            label="Gửi kèm email"
          />
          <Button
            variant="contained" disabled={!title.trim() || broadcast.isPending}
            onClick={() =>
              broadcast.mutate(
                {
                  title: title.trim(), body: body.trim() || null,
                  audience, role: audience === 'role' ? role : null, send_email: sendEmail,
                },
                {
                  onSuccess: (res) => {
                    onResult(`Đã gửi tới ${res.recipients} người (${res.emails_queued} email xếp hàng).`);
                    setTitle(''); setBody('');
                  },
                  onError,
                },
              )
            }
          >
            Gửi
          </Button>
        </Box>
      </Paper>

      <Typography variant="h6" gutterBottom>Hàng đợi email</Typography>
      <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <TextField select size="small" label="Trạng thái" value={status} sx={{ minWidth: 160 }}
                   onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <MenuItem value="">Tất cả</MenuItem>
          <MenuItem value="pending">Chờ gửi</MenuItem>
          <MenuItem value="sent">Đã gửi</MenuItem>
          <MenuItem value="failed">Thất bại</MenuItem>
        </TextField>
        {Object.entries(data?.counts ?? {}).map(([key, n]) => (
          <Chip key={key} size="small" label={`${key}: ${n}`} />
        ))}
      </Box>

      <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Người nhận</TableCell>
              <TableCell>Tiêu đề</TableCell>
              <TableCell>Trạng thái</TableCell>
              <TableCell>Số lần thử</TableCell>
              <TableCell>Lỗi gần nhất</TableCell>
              <TableCell align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data?.items.map((e) => (
              <TableRow key={e.id}>
                <TableCell>{e.to_email}</TableCell>
                <TableCell>{e.subject}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color={e.status === 'sent' ? 'success' : e.status === 'failed' ? 'error' : 'default'}
                    label={e.status}
                  />
                </TableCell>
                <TableCell>{e.attempts}</TableCell>
                <TableCell sx={{ maxWidth: 220 }}>{e.last_error ?? '-'}</TableCell>
                <TableCell align="right">
                  {e.status !== 'sent' && (
                    <Button size="small" disabled={retry.isPending}
                            onClick={() => retry.mutate(e.id, {
                              onSuccess: () => onResult('Đã đưa email về hàng đợi.'), onError,
                            })}>
                      Thử lại
                    </Button>
                  )}
                  <Button size="small" color="error" disabled={remove.isPending}
                          onClick={() => remove.mutate(e.id, {
                            onSuccess: () => onResult('Đã xóa email.'), onError,
                          })}>
                    Xóa
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {pageCount > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" />
        </Box>
      )}
    </Box>
  );
}

const CEFR = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

const EMPTY_QUESTION = {
  cefr_level: 'A1', word: '', correct_meaning: '', distractors: ['', '', ''],
};

/** UC-11 — ngân hàng câu hỏi kiểm tra đầu vào.
 *
 * Trước đây chỉ nạp được bằng script seed; đây là chỗ Admin thêm/sửa/tắt câu hỏi.
 * Bảng thống kê phía trên cho thấy mức nào còn mỏng — mức không có câu nào thì
 * bài kiểm tra bỏ qua mức đó và kết quả ước lượng kém tin cậy đi.
 */
function PlacementBankSection({ onResult }: { onResult: (msg: string) => void }) {
  const [level, setLevel] = useState('');
  const [draft, setDraft] = useState(EMPTY_QUESTION);

  const stats = usePlacementBankStats();
  const questions = usePlacementQuestions(level);
  const create = useCreatePlacementQuestion();
  const update = useUpdatePlacementQuestion();
  const remove = useDeletePlacementQuestion();

  const onError = (e: unknown) =>
    onResult(e instanceof ApiError ? e.message : 'Thao tác thất bại.');

  const canSubmit =
    draft.word.trim() && draft.correct_meaning.trim()
    && draft.distractors.every((d) => d.trim());

  const setDistractor = (index: number, value: string) =>
    setDraft({
      ...draft,
      distractors: draft.distractors.map((d, i) => (i === index ? value : d)),
    });

  return (
    <Box sx={{ mt: 4 }}>
      <Typography variant="h6" gutterBottom>Ngân hàng câu hỏi đầu vào</Typography>

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
        {stats.data?.map((s) => (
          <Chip
            key={s.cefr_level}
            label={`${s.cefr_level}: ${s.active_count}/${s.total_count}`}
            color={s.active_count === 0 ? 'warning' : 'default'}
            variant={s.active_count === 0 ? 'filled' : 'outlined'}
          />
        ))}
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 3 }}>
        Số câu đang bật / tổng số. Mức đang tô vàng chưa có câu nào nên bài kiểm tra sẽ bỏ qua.
      </Typography>

      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>Thêm câu hỏi</Typography>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <TextField
            select size="small" label="Mức" sx={{ width: 100 }} value={draft.cefr_level}
            onChange={(e) => setDraft({ ...draft, cefr_level: e.target.value })}
          >
            {CEFR.map((lv) => <MenuItem key={lv} value={lv}>{lv}</MenuItem>)}
          </TextField>
          <TextField
            size="small" label="Từ" sx={{ width: 170 }} value={draft.word}
            onChange={(e) => setDraft({ ...draft, word: e.target.value })}
          />
          <TextField
            size="small" label="Nghĩa đúng" sx={{ width: 190 }} value={draft.correct_meaning}
            onChange={(e) => setDraft({ ...draft, correct_meaning: e.target.value })}
          />
          {draft.distractors.map((d, i) => (
            <TextField
              key={i} size="small" label={`Nhiễu ${i + 1}`} sx={{ width: 160 }} value={d}
              onChange={(e) => setDistractor(i, e.target.value)}
            />
          ))}
          <Button
            variant="contained" disabled={!canSubmit || create.isPending} sx={{ mt: 0.5 }}
            onClick={() => create.mutate(draft, {
              onSuccess: () => { setDraft(EMPTY_QUESTION); onResult('Đã thêm câu hỏi.'); },
              onError,
            })}
          >
            Thêm
          </Button>
        </Box>
      </Paper>

      <TextField
        select size="small" label="Lọc theo mức" sx={{ width: 160, mb: 2 }}
        value={level} onChange={(e) => setLevel(e.target.value)}
      >
        <MenuItem value="">Tất cả</MenuItem>
        {CEFR.map((lv) => <MenuItem key={lv} value={lv}>{lv}</MenuItem>)}
      </TextField>

      <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Mức</TableCell>
              <TableCell>Từ</TableCell>
              <TableCell>Nghĩa đúng</TableCell>
              <TableCell>Nhiễu</TableCell>
              <TableCell>Ra đề</TableCell>
              <TableCell align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {questions.data?.map((q) => (
              <TableRow key={q.id}>
                <TableCell>{q.cefr_level}</TableCell>
                <TableCell>{q.word}</TableCell>
                <TableCell>{q.correct_meaning}</TableCell>
                <TableCell sx={{ color: 'text.secondary' }}>
                  {q.distractors.join(' · ')}
                </TableCell>
                <TableCell>
                  {/* Tắt = giữ câu lại nhưng không đưa vào đề, khác hẳn với xóa */}
                  <Switch
                    size="small" checked={q.is_active}
                    onChange={(e) => update.mutate(
                      { id: q.id, is_active: e.target.checked },
                      { onSuccess: () => onResult('Đã cập nhật câu hỏi.'), onError },
                    )}
                  />
                </TableCell>
                <TableCell align="right">
                  <Button size="small" color="error"
                          onClick={() => remove.mutate(q.id, {
                            onSuccess: () => onResult('Đã xóa câu hỏi.'), onError,
                          })}>
                    Xóa
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

/** UC-76 danh mục · UC-79 định nghĩa huy hiệu — hai bảng nội dung dùng chung 1 tab. */
function ContentTab({ onResult }: { onResult: (msg: string) => void }) {
  const categories = useAdminCategories();
  const createCategory = useCreateCategory();
  const updateCategory = useUpdateCategory();
  const deleteCategory = useDeleteCategory();
  const [newCategory, setNewCategory] = useState('');

  const achievements = useAchievementDefinitions();
  const createAchievement = useCreateAchievement();
  const updateAchievement = useUpdateAchievement();
  const deleteAchievement = useDeleteAchievement();
  const [draft, setDraft] = useState({
    code: '', name: '', description: '',
    condition_key: 'xp' as ConditionKey, threshold: 100,
  });

  const onError = (e: unknown) =>
    onResult(e instanceof ApiError ? e.message : 'Thao tác thất bại.');

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Danh mục bộ từ vựng</Typography>
      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <TextField size="small" label="Tên danh mục mới" value={newCategory}
                   onChange={(e) => setNewCategory(e.target.value)} sx={{ minWidth: 240 }} />
        <Button
          variant="contained" disabled={!newCategory.trim() || createCategory.isPending}
          onClick={() =>
            createCategory.mutate({ name: newCategory.trim() }, {
              onSuccess: () => { setNewCategory(''); onResult('Đã thêm danh mục.'); },
              onError,
            })
          }
        >
          Thêm
        </Button>
      </Box>

      <TableContainer component={Paper} sx={{ mb: 4, overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Tên</TableCell>
              <TableCell>Số bộ từ vựng</TableCell>
              <TableCell>Đang bật</TableCell>
              <TableCell align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {categories.data?.map((c) => (
              <TableRow key={c.id}>
                <TableCell>{c.name}</TableCell>
                <TableCell>{c.word_set_count}</TableCell>
                <TableCell>
                  <Switch size="small" checked={c.is_active}
                          onChange={(e) => updateCategory.mutate(
                            { id: c.id, is_active: e.target.checked },
                            { onSuccess: () => onResult('Đã cập nhật danh mục.'), onError },
                          )} />
                </TableCell>
                <TableCell align="right">
                  <Button size="small" color="error"
                          onClick={() => deleteCategory.mutate(c.id, {
                            onSuccess: () => onResult('Đã xóa danh mục.'), onError,
                          })}>
                    Xóa
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Typography variant="h6" gutterBottom>Định nghĩa huy hiệu</Typography>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField size="small" label="Mã (a-z, _)" value={draft.code} sx={{ width: 150 }}
                     onChange={(e) => setDraft({ ...draft, code: e.target.value })} />
          <TextField size="small" label="Tên" value={draft.name} sx={{ width: 160 }}
                     onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          <TextField size="small" label="Mô tả" value={draft.description} sx={{ flexGrow: 1, minWidth: 180 }}
                     onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
          <TextField select size="small" label="Điều kiện" value={draft.condition_key} sx={{ width: 180 }}
                     onChange={(e) => setDraft({ ...draft, condition_key: e.target.value as ConditionKey })}>
            <MenuItem value="xp">Tổng XP</MenuItem>
            <MenuItem value="streak">Chuỗi ngày</MenuItem>
            <MenuItem value="mastered">Từ đã thuộc</MenuItem>
            <MenuItem value="sessions_completed">Phiên hoàn thành</MenuItem>
          </TextField>
          <TextField size="small" type="number" label="Ngưỡng" value={draft.threshold} sx={{ width: 110 }}
                     onChange={(e) => setDraft({ ...draft, threshold: Number(e.target.value) })} />
          <Button
            variant="contained" disabled={!draft.code || !draft.name || !draft.description}
            onClick={() =>
              createAchievement.mutate(draft, {
                onSuccess: () => {
                  setDraft({ code: '', name: '', description: '', condition_key: 'xp', threshold: 100 });
                  onResult('Đã thêm huy hiệu.');
                },
                onError,
              })
            }
          >
            Thêm
          </Button>
        </Box>
      </Paper>

      <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Mã</TableCell>
              <TableCell>Tên</TableCell>
              <TableCell>Điều kiện</TableCell>
              <TableCell>Ngưỡng</TableCell>
              <TableCell>Đang bật</TableCell>
              <TableCell align="right">Thao tác</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {achievements.data?.map((a) => (
              <TableRow key={a.id}>
                <TableCell>{a.code}</TableCell>
                <TableCell>{a.name}</TableCell>
                <TableCell>{a.condition_key}</TableCell>
                <TableCell>
                  <TextField
                    size="small" type="number" defaultValue={a.threshold} sx={{ width: 100 }}
                    onBlur={(e) => {
                      const value = Number(e.target.value);
                      if (value !== a.threshold) {
                        updateAchievement.mutate({ id: a.id, threshold: value }, {
                          onSuccess: () => onResult('Đã cập nhật ngưỡng.'), onError,
                        });
                      }
                    }}
                  />
                </TableCell>
                <TableCell>
                  <Switch size="small" checked={a.is_active}
                          onChange={(e) => updateAchievement.mutate(
                            { id: a.id, is_active: e.target.checked },
                            { onSuccess: () => onResult('Đã cập nhật huy hiệu.'), onError },
                          )} />
                </TableCell>
                <TableCell align="right">
                  <Button size="small" color="error"
                          onClick={() => deleteAchievement.mutate(a.id, {
                            onSuccess: () => onResult('Đã xóa định nghĩa huy hiệu.'), onError,
                          })}>
                    Xóa
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <PlacementBankSection onResult={onResult} />
    </Box>
  );
}

/** UC-70 — sức khỏe mô hình đo trên dữ liệu thật của hệ thống.
 *
 * Khác AUC báo cáo trong chương 4 (đo trên tập test SLAM cố định). Nhãn trên
 * màn hình phải nói rõ điều đó, nếu không hai con số sẽ bị so sánh nhầm với nhau.
 */
function ModelHealthTab({ onResult }: { onResult: (msg: string) => void }) {
  const [days, setDays] = useState(7);
  const health = useModelHealth(days);
  const history = useModelHealthHistory();
  const snapshot = useSnapshotModelHealth();

  if (health.isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (!health.data) return <Alert severity="error">Không tải được chỉ số mô hình.</Alert>;

  const d = health.data;
  const pct = (v: number | null) => (v == null ? '-' : `${Math.round(v * 100)}%`);

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
        <TextField
          select size="small" label="Khoảng thời gian" sx={{ width: 160 }}
          value={days} onChange={(e) => setDays(Number(e.target.value))}
        >
          {[7, 14, 30, 90].map((n) => (
            <MenuItem key={n} value={n}>{n} ngày gần nhất</MenuItem>
          ))}
        </TextField>
        <Button
          variant="contained" disabled={snapshot.isPending}
          onClick={() => snapshot.mutate(days, {
            onSuccess: () => onResult('Đã chốt số đo.'),
            onError: (e) => onResult(
              e instanceof ApiError ? e.message : 'Chốt số đo thất bại.',
            ),
          })}
        >
          Chốt số đo hiện tại
        </Button>
      </Box>

      <Alert severity={d.reliable ? 'info' : 'warning'} sx={{ mb: 3 }}>{d.note}</Alert>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <Paper variant="outlined" sx={{ p: 2, minWidth: 170 }}>
          <Typography variant="caption" color="text.secondary">Dự đoán khớp thực tế</Typography>
          <Typography variant="h5" sx={{ fontWeight: 800 }}>{pct(d.accuracy)}</Typography>
          <Typography variant="caption" color="text.secondary">
            trên {d.sample_size} lượt trả lời
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2, minWidth: 170 }}>
          <Typography variant="caption" color="text.secondary">Sai số Brier</Typography>
          <Typography variant="h5" sx={{ fontWeight: 800 }}>
            {d.brier == null ? '-' : d.brier.toFixed(3)}
          </Typography>
          <Typography variant="caption" color="text.secondary">càng thấp càng tốt</Typography>
        </Paper>
        {/* Baseline đặt ngay cạnh accuracy: một mô hình không vượt được bộ đoán
            theo lớp đa số thì con số accuracy đứng một mình chỉ gây hiểu nhầm. */}
        <Paper variant="outlined" sx={{ p: 2, minWidth: 170 }}>
          <Typography variant="caption" color="text.secondary">Baseline (đoán bừa)</Typography>
          <Typography variant="h5" sx={{ fontWeight: 800 }}>{pct(d.baseline_accuracy)}</Typography>
          <Typography variant="caption" color="text.secondary">
            mô hình phải VƯỢT số này mới có giá trị
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2, minWidth: 170 }}>
          <Typography variant="caption" color="text.secondary">Độ phủ trên từ đã học</Typography>
          <Typography variant="h5" sx={{ fontWeight: 800 }}>{pct(d.coverage)}</Typography>
          <Typography variant="caption" color="text.secondary">
            {d.covered_states}/{d.answered_states} từ đã học được DKT chấm
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2, minWidth: 170 }}>
          <Typography variant="caption" color="text.secondary">Độ phủ vocab</Typography>
          <Typography variant="h5" sx={{ fontWeight: 800 }}>
            {d.vocab_coverage == null ? '-' : pct(d.vocab_coverage)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            từ trong thư viện mà mô hình biết mặt
          </Typography>
        </Paper>
      </Box>

      <Typography variant="h6" gutterBottom>Diễn biến theo thời gian</Typography>
      {(history.data?.length ?? 0) === 0 ? (
        <Alert severity="info">
          Chưa có số đo nào được chốt. Bấm &quot;Chốt số đo hiện tại&quot; để bắt đầu ghi mốc.
        </Alert>
      ) : (
        <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Thời điểm</TableCell>
                <TableCell>Chỉ số</TableCell>
                <TableCell align="right">Giá trị</TableCell>
                <TableCell align="right">Cỡ mẫu</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.data!.map((p, i) => (
                <TableRow key={`${p.metric}-${p.recorded_at}-${i}`}>
                  <TableCell>{new Date(p.recorded_at).toLocaleString('vi-VN')}</TableCell>
                  <TableCell>{p.metric}</TableCell>
                  <TableCell align="right">{p.value.toFixed(4)}</TableCell>
                  <TableCell align="right">{p.sample_size}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}

/** UC-74 — ma trận vai trò ↔ quyền; đổi ô là đổi quyền truy cập thật. */
function PermissionsTab({ onResult }: { onResult: (msg: string) => void }) {
  const { data, isLoading } = usePermissionMatrix();
  const save = useSetRolePermissions();

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (!data) return <Alert severity="error">Không tải được ma trận phân quyền.</Alert>;

  const toggle = (role: string, key: string, checked: boolean) => {
    const current = data.matrix[role] ?? [];
    const next = checked ? [...current, key] : current.filter((k) => k !== key);
    save.mutate({ role, permissions: next }, {
      onSuccess: () => onResult(`Đã cập nhật quyền của vai trò ${role}.`),
      onError: (e) => onResult(e instanceof ApiError ? e.message : 'Không lưu được phân quyền.'),
    });
  };

  return (
    <Box>
      <Alert severity="info" sx={{ mb: 2 }}>
        Bỏ tick là chặn truy cập thật ở backend, không chỉ ẩn giao diện.
        Vai trò <strong>admin</strong> luôn giữ quyền &quot;Quản lý phân quyền&quot; để không tự khóa mình.
      </Alert>

      <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Quyền</TableCell>
              {data.roles.map((r) => <TableCell key={r} align="center">{r}</TableCell>)}
            </TableRow>
          </TableHead>
          <TableBody>
            {data.permissions.map((p) => (
              <TableRow key={p.key}>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{p.label}</Typography>
                  <Typography variant="caption" color="text.secondary">{p.description}</Typography>
                </TableCell>
                {data.roles.map((role) => (
                  <TableCell key={role} align="center">
                    <Switch
                      size="small" disabled={save.isPending}
                      checked={(data.matrix[role] ?? []).includes(p.key)}
                      onChange={(e) => toggle(role, p.key, e.target.checked)}
                    />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

/** UC-83 — nhật ký thao tác quản trị. */
function AuditTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useAuditLogs(page);
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (!data || data.items.length === 0) return <Alert severity="info">Chưa có thao tác nào được ghi.</Alert>;

  return (
    <Box>
      <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Thời điểm</TableCell>
              <TableCell>Người thực hiện</TableCell>
              <TableCell>Thao tác</TableCell>
              <TableCell>Đối tượng</TableCell>
              <TableCell>Chi tiết</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.items.map((e) => (
              <TableRow key={e.id}>
                <TableCell>{formatTime(e.created_at)}</TableCell>
                <TableCell>{e.actor_name ?? '-'}</TableCell>
                <TableCell><Chip size="small" label={e.action} /></TableCell>
                <TableCell>{e.target_type ? `${e.target_type} #${e.target_id}` : '-'}</TableCell>
                <TableCell>{e.detail ?? '-'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {pageCount > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" />
        </Box>
      )}
    </Box>
  );
}

/** Khu vực vận hành — tab hiện theo QUYỀN của người dùng (UC-74), không theo vai
 * trò cứng; backend vẫn chặn độc lập bằng require_permission. */
function Admin() {
  const [tab, setTab] = useState(0);
  const [snack, setSnack] = useState<string | null>(null);
  const { data: permissions, isLoading } = useMyPermissions();

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (!permissions || permissions.length === 0) return <Navigate to="/" replace />;

  const allTabs = [
    { permission: 'admin.overview', label: 'Thử nghiệm', render: () => <PilotMonitor onResult={setSnack} /> },
    { permission: 'admin.overview', label: 'Tổng quan', render: () => <OverviewTab onResult={setSnack} /> },
    { permission: 'admin.users', label: 'Người dùng', render: () => <UsersTab onResult={setSnack} /> },
    { permission: 'admin.roles', label: 'Phân quyền', render: () => <PermissionsTab onResult={setSnack} /> },
    { permission: 'admin.word_sets', label: 'Bộ từ vựng', render: () => <WordSetsTab onResult={setSnack} /> },
    { permission: 'admin.moderation', label: 'Kiểm duyệt', render: () => <ModerationTab onResult={setSnack} /> },
    { permission: 'admin.reports', label: 'Báo cáo', render: () => <ReportsTab onResult={setSnack} /> },
    { permission: 'admin.emails', label: 'Thông báo & Email', render: () => <EmailsTab onResult={setSnack} /> },
    { permission: 'admin.content', label: 'Nội dung', render: () => <ContentTab onResult={setSnack} /> },
    // UC-97 — kho video shadowing
    { permission: 'admin.content', label: 'Shadowing', render: () => <ShadowingAdminTab onResult={setSnack} /> },
    { permission: 'admin.config', label: 'Cấu hình', render: () => <ConfigTab onResult={setSnack} /> },
    { permission: 'admin.overview', label: 'Mô hình',
      render: () => <ModelHealthTab onResult={setSnack} /> },
    // UC-93 — số liệu cho chương thực nghiệm, cố ý KHÔNG hiện ở giao diện người học
    { permission: 'admin.overview', label: 'Lịch ôn: DKT vs SM-2',
      render: () => <SchedulerComparison /> },
    { permission: 'admin.audit', label: 'Nhật ký', render: () => <AuditTab /> },
  ];
  const tabs = allTabs.filter((t) => permissions.includes(t.permission));
  const active = tabs[Math.min(tab, tabs.length - 1)];

  return (
    <Box>
      <PageHeader
        title="Vận hành"
        subtitle="Chỉ hiện các mục bạn có quyền. Mọi thao tác đều được backend kiểm tra quyền độc lập."
      />

      <Tabs value={Math.min(tab, tabs.length - 1)} onChange={(_, v) => setTab(v)}
            sx={{ mb: 3 }} variant="scrollable">
        {tabs.map((t) => <Tab key={t.label} label={t.label} />)}
      </Tabs>

      {active?.render()}

      <Snackbar open={snack !== null} autoHideDuration={4000}
                onClose={() => setSnack(null)} message={snack ?? ''} />
    </Box>
  );
}

export default Admin;
