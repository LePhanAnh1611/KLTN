import { useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import LinearProgress from '@mui/material/LinearProgress';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import FormControlLabel from '@mui/material/FormControlLabel';
import Snackbar from '@mui/material/Snackbar';
import Switch from '@mui/material/Switch';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';

import MasteryCurve from '../components/MasteryCurve';
import SpeakButton from '../components/SpeakButton';
import { StarIcon } from '../components/icons';

import { useMasteryHistory } from '../api/progress';
import { ApiError } from '../api/client';
import {
  useCreateItem,
  useDeleteItem,
  useImportItems,
  useItems,
  useDeleteCover,
  usePublishWordSet,
  useUpdateItem,
  useUpdateWordSet,
  useUploadCover,
  useWordSet,
} from '../api/wordSets';
import ItemFormDialog from '../components/ItemFormDialog';
import { useClearItemFlag, useFlaggedItems, useSetItemFlag } from '../api/extras';
import PageHeader from '../components/PageHeader';
import SectionCard from '../components/SectionCard';
import SetProgress from '../components/SetProgress';
import WordSetCover from '../components/WordSetCover';
import WordSetFormDialog from '../components/WordSetFormDialog';
import MeaningConfidenceMark from '../components/MeaningConfidenceMark';
import { categoryAccent, difficultyAccent } from '../theme/accents';
import type { Item, ItemInput, WordSetInput } from '../types/wordSet';

/** Thao tác trên một từ. Bug #3: trên điện thoại 3 nút chữ không vừa một cột —
 * gom vào menu "⋯"; từ sm trở lên vẫn hiện đủ 3 nút như cũ. */
function ItemActions({ onCurve, onEdit, onDelete }: {
  onCurve: () => void; onEdit: () => void; onDelete: () => void;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const run = (fn: () => void) => () => { setAnchor(null); fn(); };
  return (
    <>
      <Box sx={{ display: { xs: 'none', sm: 'inline-flex' } }}>
        {/* UC-92 — đường cong học tập của chính từ này */}
        <Button size="small" onClick={onCurve}>Mức nhớ</Button>
        <Button size="small" onClick={onEdit}>Sửa</Button>
        <Button size="small" color="error" onClick={onDelete}>Xóa</Button>
      </Box>
      <IconButton size="small" aria-label="Thao tác với từ"
                  sx={{ display: { xs: 'inline-flex', sm: 'none' } }}
                  onClick={(e) => setAnchor(e.currentTarget)}>
        ⋯
      </IconButton>
      <Menu anchorEl={anchor} open={anchor !== null} onClose={() => setAnchor(null)}>
        <MenuItem onClick={run(onCurve)}>Mức nhớ</MenuItem>
        <MenuItem onClick={run(onEdit)}>Sửa</MenuItem>
        <MenuItem onClick={run(onDelete)} sx={{ color: 'error.main' }}>Xóa</MenuItem>
      </Menu>
    </>
  );
}

/** Cột ví dụ chỉ hiện khi đủ rộng; phiên âm và từ loại đã nằm ngay dưới từ (bug #3). */
const HIDE_NARROW = { display: { xs: 'none', lg: 'table-cell' } } as const;

function WordSetDetail() {
  const { id } = useParams();
  const wordSetId = Number(id);
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const coverInputRef = useRef<HTMLInputElement>(null);

  const wordSetQuery = useWordSet(wordSetId);
  const itemsQuery = useItems(wordSetId);
  const createItem = useCreateItem(wordSetId);
  const updateItem = useUpdateItem(wordSetId);
  const deleteItem = useDeleteItem(wordSetId);
  const importItems = useImportItems(wordSetId);
  const updateSet = useUpdateWordSet(wordSetId);
  const publish = usePublishWordSet(wordSetId);
  const uploadCover = useUploadCover(wordSetId);
  const deleteCover = useDeleteCover(wordSetId);

  const [itemDialogOpen, setItemDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<Item | undefined>(undefined);
  const [editSetOpen, setEditSetOpen] = useState(false);
  // UC-35 — luyện lại cho nhớ mà không muốn xê dịch lịch ôn đang có
  const [practiceOnly, setPracticeOnly] = useState(false);

  // UC-32 — tra cứu nhanh từ nào đang được đánh dấu để tô ngôi sao
  const flaggedQuery = useFlaggedItems();
  const flagged = new Set((flaggedQuery.data ?? []).map((f) => f.item_id));
  const setFlag = useSetItemFlag();
  const clearFlag = useClearItemFlag();

  /** Mở màn học; cờ luyện thường đi kèm qua query để Study biết lúc tạo phiên. */
  const go = (mode: string) =>
    navigate(`/word-sets/${wordSetId}/study/${mode}${practiceOnly ? '?practice=1' : ''}`);
  const [snack, setSnack] = useState<string | null>(null);
  const [curveItemId, setCurveItemId] = useState<number | null>(null);

  if (wordSetQuery.isLoading) {
    return (
      <Box sx={{ textAlign: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (wordSetQuery.isError || !wordSetQuery.data) {
    return (
      <Box>
        <Alert severity="error">Không tìm thấy bộ từ vựng.</Alert>
        <Button sx={{ mt: 2 }} onClick={() => navigate('/word-sets')}>
          Về thư viện
        </Button>
      </Box>
    );
  }

  const wordSet = wordSetQuery.data;

  const openCreateItem = () => {
    setEditingItem(undefined);
    setItemDialogOpen(true);
  };
  const openEditItem = (item: Item) => {
    setEditingItem(item);
    setItemDialogOpen(true);
  };

  const handleItemSubmit = (data: ItemInput, onError: (error: unknown) => void) => {
    const opts = {
      onSuccess: () => {
        setItemDialogOpen(false);
        setSnack(editingItem ? 'Đã cập nhật từ.' : 'Đã thêm từ.');
      },
      onError,
    };
    if (editingItem) {
      updateItem.mutate({ itemId: editingItem.id, data }, opts);
    } else {
      createItem.mutate(data, opts);
    }
  };

  const handleEditSet = (data: WordSetInput, onError: (error: unknown) => void) => {
    updateSet.mutate(data, {
      onSuccess: () => {
        setEditSetOpen(false);
        setSnack('Đã cập nhật bộ từ vựng.');
      },
      onError,
    });
  };

  const handlePublish = () => {
    publish.mutate(!wordSet.is_public, {
      onSuccess: () => setSnack(wordSet.is_public ? 'Đã ẩn bộ từ vựng.' : 'Đã công khai bộ từ vựng.'),
      onError: (error) => setSnack(error instanceof ApiError ? error.message : 'Không đổi được trạng thái.'),
    });
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    importItems.mutate(file, {
      onSuccess: (report) => {
        const errPart = report.errors.length > 0 ? `, ${report.errors.length} dòng lỗi` : '';
        setSnack(`Đã nhập ${report.imported} từ${errPart}.`);
      },
      onError: (error) => setSnack(error instanceof Error ? error.message : 'Import thất bại.'),
    });
  };

  const handlePickCover = (file: File | undefined) => {
    if (!file) return;
    uploadCover.mutate(file, {
      onSuccess: () => setSnack('Đã cập nhật ảnh bìa.'),
      onError: (error) =>
        setSnack(error instanceof ApiError ? error.message : 'Tải ảnh bìa thất bại.'),
    });
  };

  const coverBusy = uploadCover.isPending || deleteCover.isPending;

  return (
    <>
      <Button size="small" onClick={() => navigate('/word-sets')} sx={{ mb: 1 }}>
        ← Thư viện
      </Button>

      <PageHeader
        title={wordSet.name}
        subtitle={wordSet.description}
        actions={
          <>
            <Button onClick={() => setEditSetOpen(true)}>Sửa bộ</Button>
            <Button onClick={handlePublish} disabled={publish.isPending}>
              {wordSet.is_public ? 'Ẩn' : 'Công khai'}
            </Button>
          </>
        }
      />

      {/* Trái: thông tin bộ và chọn chế độ học. Phải: danh sách từ cuộn riêng, nên
          nút học luôn trong tầm mắt dù bộ có nhiều từ (2026-11-04). */}
      <Box sx={{
        display: 'grid', gap: 2.5, alignItems: 'start',
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: '340px minmax(0, 1fr)' },
      }}>
        <Box sx={{ display: 'grid', gap: 2.5, minWidth: 0 }}>
          <Card sx={{ p: 2 }}>
            {/* UC-13 — ảnh bìa. Chưa đặt thì đây là bìa sinh tự động, nên khung luôn
                có ảnh chứ không phải ô trống chờ tải lên. */}
            <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
              <WordSetCover
                id={wordSet.id}
                name={wordSet.name}
                coverUrl={wordSet.cover_image_url}
                variant="thumb"
                thumbSize={84}
              />
              <Box sx={{ minWidth: 0 }}>
                <Tooltip title="Ảnh hiển thị ở thư viện, Khám phá và Trang chủ. JPG/PNG/WebP, tối đa 5MB.">
                  <Typography sx={{ fontWeight: 700, mb: 0.5 }}>Ảnh bìa</Typography>
                </Tooltip>
                <Stack direction="row" spacing={0.5}>
                  <Button
                    size="small"
                    disabled={coverBusy}
                    onClick={() => coverInputRef.current?.click()}
                  >
                    {wordSet.cover_image_url ? 'Đổi ảnh' : 'Tải ảnh lên'}
                  </Button>
                  {wordSet.cover_image_url && (
                    <Button
                      size="small"
                      color="error"
                      disabled={coverBusy}
                      onClick={() =>
                        deleteCover.mutate(undefined, {
                          onSuccess: () => setSnack('Đã gỡ ảnh bìa.'),
                          onError: (error) =>
                            setSnack(error instanceof ApiError ? error.message : 'Gỡ ảnh thất bại.'),
                        })
                      }
                    >
                      Gỡ ảnh
                    </Button>
                  )}
                </Stack>
                <input
                  ref={coverInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  hidden
                  onChange={(e) => {
                    handlePickCover(e.target.files?.[0]);
                    e.target.value = '';   // chọn lại đúng file vừa lỗi vẫn phải bắn onChange
                  }}
                />
              </Box>
            </Box>

            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 0.5, mt: 1.5 }}>
              <Chip size="small" label={`${wordSet.item_count} từ`} />
              {wordSet.category && (
                <Chip size="small" label={wordSet.category}
                      sx={{ bgcolor: categoryAccent(wordSet.category).bg, color: categoryAccent(wordSet.category).fg }} />
              )}
              {wordSet.difficulty && (
                <Chip size="small" label={({ beginner: 'Cơ bản', intermediate: 'Trung cấp', advanced: 'Nâng cao' } as Record<string, string>)[wordSet.difficulty.toLowerCase()] ?? wordSet.difficulty}
                      sx={{ bgcolor: difficultyAccent(wordSet.difficulty).bg, color: difficultyAccent(wordSet.difficulty).fg }} />
              )}
              <Chip
                size="small"
                color={wordSet.is_public ? 'success' : 'default'}
                label={wordSet.is_public ? 'Công khai' : 'Riêng tư'}
              />
              {/* UC-96 — gắn nhãn xong mà chỉ thấy ở Khám phá (và chỉ khi đã
                  công khai) thì người dùng tưởng nhãn biến mất. Bấm vào chip mở
                  thẳng bộ lọc tương ứng. */}
              {wordSet.tags.map((t) => (
                <Chip
                  key={t} size="small" variant="outlined" label={`#${t}`}
                  onClick={() => navigate(`/discover?tag=${encodeURIComponent(t)}`)}
                />
              ))}
            </Stack>
            {wordSet.item_count > 0 && (
              <Box sx={{ mt: 1.5 }}>
                <SetProgress
                  total={wordSet.item_count}
                  mastered={wordSet.mastered_count}
                  learning={wordSet.learning_count ?? 0}
                />
              </Box>
            )}
          </Card>

          {/* Khu vực chọn chế độ học tập (Study Mode Selector) */}
          <SectionCard title="Bắt đầu phiên học">
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 1 }}>
              <Button
                variant="contained"
                disabled={wordSet.item_count === 0}
                onClick={() => go('dkt_smart')}
                sx={{ gridColumn: '1 / -1' }}
              >
                ★ Học từ vừa sức
              </Button>
              <Button size="small" variant="outlined" disabled={wordSet.item_count === 0} onClick={() => go('flashcard')}>
                Thẻ lật
              </Button>
              <Button size="small" variant="outlined" disabled={wordSet.item_count < 4} onClick={() => go('quiz')}>
                Trắc nghiệm
              </Button>
              <Button size="small" variant="outlined" disabled={wordSet.item_count === 0} onClick={() => go('cloze')}>
                Điền khuyết
              </Button>
              <Button size="small" variant="outlined" disabled={wordSet.item_count === 0} onClick={() => go('typing')}>
                Gõ từ
              </Button>
              <Button size="small" variant="outlined" disabled={wordSet.item_count === 0} onClick={() => go('dictation')}>
                Nghe viết
              </Button>
              <Button size="small" variant="outlined" disabled={wordSet.item_count < 2} onClick={() => go('matching')}>
                Ghép cặp
              </Button>
              <Button size="small" variant="outlined" disabled={wordSet.item_count < 5} onClick={() => go('mixed')}>
                Phiên trộn
              </Button>
              <Button size="small" variant="outlined" disabled={wordSet.item_count === 0} onClick={() => go('sm2')} sx={{ color: 'text.secondary' }}>
                Ôn kiểu Anki
              </Button>
            </Box>

            <Tooltip title="Vẫn ghi kết quả và cập nhật mức nắm vững, nhưng không đổi ngày ôn đã xếp">
              <FormControlLabel
                sx={{ mt: 1 }}
                control={
                  <Switch size="small" checked={practiceOnly}
                          onChange={(e) => setPracticeOnly(e.target.checked)} />
                }
                label={<Typography variant="caption" sx={{ fontWeight: 600 }}>Luyện thường (không đổi lịch ôn)</Typography>}
              />
            </Tooltip>
          </SectionCard>
        </Box>

        <SectionCard
          title="Danh sách từ"
          action={
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button variant="contained" size="small" onClick={openCreateItem}>
                + Thêm từ
              </Button>
              <Button variant="outlined" size="small" onClick={() => fileInputRef.current?.click()} disabled={importItems.isPending}>
                Import CSV
              </Button>
              <input ref={fileInputRef} type="file" hidden accept=".csv,text/csv" onChange={handleFileChange} />
            </Box>
          }
          sx={{ minWidth: 0 }}
        >
          {itemsQuery.isLoading && <CircularProgress />}
          {itemsQuery.data && itemsQuery.data.length === 0 && (
            <Alert severity="info">Bộ từ vựng chưa có từ nào. Hãy thêm từ hoặc import CSV.</Alert>
          )}
          {itemsQuery.data && itemsQuery.data.length > 0 && (
            // Bug #3: bảng rộng làm cả trang trượt ngang trên điện thoại. Phiên âm và
            // từ loại nằm dưới từ, ví dụ chỉ hiện khi đủ rộng; màn rộng cuộn trong khung.
            <Box sx={{ overflow: 'auto', maxHeight: { md: 'calc(100vh - 370px)' }, minHeight: { md: 260 } }}>
              <Table stickyHeader size="small" sx={{ '& td, & th': { px: { xs: 1, sm: 1.5 } } }}>
                <TableHead>
                  <TableRow>
                    <TableCell>Từ</TableCell>
                    <TableCell>Nghĩa</TableCell>
                    <TableCell sx={HIDE_NARROW}>Ví dụ</TableCell>
                    <TableCell align="right">
                      <Box component="span" sx={{ display: { xs: 'none', sm: 'inline' } }}>Thao tác</Box>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {itemsQuery.data.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          {/* UC-32 — đánh dấu từ khó; đây là cảm nhận của người học,
                              không liên quan tới mastery do mô hình tính */}
                          <Tooltip title={flagged.has(item.id) ? 'Bỏ đánh dấu từ khó' : 'Đánh dấu là từ khó'}>
                            <IconButton
                              size="small"
                              onClick={() => (flagged.has(item.id)
                                ? clearFlag.mutate(item.id)
                                : setFlag.mutate({ itemId: item.id }))}
                              sx={{ color: flagged.has(item.id) ? 'warning.main' : 'action.disabled' }}
                            >
                              <StarIcon size={16} />
                            </IconButton>
                          </Tooltip>
                          {item.word}
                          <SpeakButton text={item.word} size={16} />
                        </Box>
                        {(item.phonetic || item.part_of_speech) && (
                          <Typography variant="caption" color="text.secondary"
                                      sx={{ display: 'block', pl: 4.5 }}>
                            {[item.phonetic, item.part_of_speech].filter(Boolean).join(' · ')}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {item.meaning}
                        <MeaningConfidenceMark confidence={item.meaning_confidence} />
                      </TableCell>
                      <TableCell sx={HIDE_NARROW}>{item.example}</TableCell>
                      <TableCell align="right" sx={{ whiteSpace: 'nowrap', px: { xs: 0.5, sm: 1 } }}>
                        <ItemActions
                          onCurve={() => setCurveItemId(item.id)}
                          onEdit={() => openEditItem(item)}
                          onDelete={() =>
                            deleteItem.mutate(item.id, { onSuccess: () => setSnack('Đã xóa từ.') })
                          }
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          )}
        </SectionCard>
      </Box>

      <ItemFormDialog
        open={itemDialogOpen}
        initial={editingItem}
        pending={createItem.isPending || updateItem.isPending}
        onClose={() => setItemDialogOpen(false)}
        onSubmit={handleItemSubmit}
      />
      <WordSetFormDialog
        open={editSetOpen}
        initial={wordSet}
        pending={updateSet.isPending}
        onClose={() => setEditSetOpen(false)}
        onSubmit={handleEditSet}
      />
      <MasteryCurveDialog itemId={curveItemId} onClose={() => setCurveItemId(null)} />

      <Snackbar
        open={snack !== null}
        autoHideDuration={4000}
        onClose={() => setSnack(null)}
        message={snack ?? ''}
      />
    </>
  );
}

/** UC-92 — hộp thoại đường cong mastery của một từ. */
function MasteryCurveDialog({ itemId, onClose }: {
  itemId: number | null; onClose: () => void;
}) {
  const query = useMasteryHistory(itemId);
  return (
    <Dialog open={itemId !== null} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {query.data ? `Mức nhớ theo thời gian - "${query.data.word}"` : 'Mức nhớ theo thời gian'}
      </DialogTitle>
      <DialogContent>
        {query.isLoading && <LinearProgress />}
        {query.isError && <Alert severity="error">Không tải được đường cong.</Alert>}
        {query.data && <MasteryCurve data={query.data} />}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Đóng</Button>
      </DialogActions>
    </Dialog>
  );
}

export default WordSetDetail;
