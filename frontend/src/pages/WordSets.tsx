import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Snackbar from '@mui/material/Snackbar';
import Stack from '@mui/material/Stack';

import { ApiError } from '../api/client';
import {
  useCreateWordSet,
  useDeleteWordSet,
  usePublishWordSet,
  useWordSets,
} from '../api/wordSets';
import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';
import WordSetCard, { wordSetGridSx } from '../components/WordSetCard';
import WordSetFormDialog from '../components/WordSetFormDialog';
import { BookIcon } from '../components/icons';
import type { WordSet, WordSetInput } from '../types/wordSet';

function PublishButton({ wordSet, onError }: { wordSet: WordSet; onError: (msg: string) => void }) {
  const publish = usePublishWordSet(wordSet.id);
  const handleClick = () => {
    publish.mutate(!wordSet.is_public, {
      onError: (error) => {
        onError(error instanceof ApiError ? error.message : 'Không đổi được trạng thái.');
      },
    });
  };
  return (
    <Button size="small" onClick={handleClick} disabled={publish.isPending}>
      {wordSet.is_public ? 'Ẩn' : 'Công khai'}
    </Button>
  );
}

function WordSets() {
  const navigate = useNavigate();
  const listQuery = useWordSets();
  const createMutation = useCreateWordSet();
  const deleteMutation = useDeleteWordSet();

  const [createOpen, setCreateOpen] = useState(false);
  const [snack, setSnack] = useState<string | null>(null);

  const handleCreate = (data: WordSetInput, onError: (error: unknown) => void) => {
    createMutation.mutate(data, {
      onSuccess: () => {
        setCreateOpen(false);
        setSnack('Đã tạo bộ từ vựng.');
      },
      onError,
    });
  };

  return (
    <>
      <PageHeader
        title="Bộ từ vựng của tôi"
        subtitle="Bộ từ bạn đang học."
        actions={
          <>
            {/* UC-87 — lối vào duy nhất của luồng cắt bộ từ từ tài liệu PDF */}
            <Button variant="outlined" onClick={() => navigate('/word-sets/from-pdf')}>
              Tạo từ PDF
            </Button>
            <Button variant="contained" onClick={() => setCreateOpen(true)}>
              Tạo bộ từ vựng
            </Button>
          </>
        }
      />

      {listQuery.isLoading && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {listQuery.isError && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => listQuery.refetch()}>
              Thử lại
            </Button>
          }
        >
          Không tải được danh sách bộ từ vựng.
        </Alert>
      )}

      {listQuery.data && listQuery.data.length === 0 && (
        <EmptyState
          icon={<BookIcon size={24} />}
          title="Thư viện còn trống"
          description="Tạo bộ từ đầu tiên hoặc tải một bộ ở Khám phá."
          action={
            <Button variant="contained" onClick={() => setCreateOpen(true)}>Tạo bộ từ vựng</Button>
          }
        />
      )}

      {listQuery.data && listQuery.data.length > 0 && (
        <Box sx={wordSetGridSx}>
          {listQuery.data.map((ws) => (
              <WordSetCard
                key={ws.id}
                id={ws.id}
                name={ws.name}
                coverImageUrl={ws.cover_image_url}
                description={ws.description}
                itemCount={ws.item_count}
                masteredCount={ws.mastered_count}
                learningCount={ws.learning_count}
                category={ws.category}
                difficulty={ws.difficulty}
                isPublic={ws.is_public}
                onOpen={() => navigate(`/word-sets/${ws.id}`)}
                actions={
                  <Stack direction="row" spacing={1}>
                    <Button size="small" onClick={() => navigate(`/word-sets/${ws.id}`)}>
                      Mở
                    </Button>
                    <PublishButton wordSet={ws} onError={setSnack} />
                    <Button
                      size="small"
                      color="error"
                      onClick={() =>
                        deleteMutation.mutate(ws.id, { onSuccess: () => setSnack('Đã xóa bộ từ vựng.') })
                      }
                    >
                      Xóa
                    </Button>
                  </Stack>
                }
              />
            ))}
          </Box>
        )}

      <WordSetFormDialog
        open={createOpen}
        pending={createMutation.isPending}
        onClose={() => setCreateOpen(false)}
        onSubmit={handleCreate}
      />

      <Snackbar
        open={snack !== null}
        autoHideDuration={3000}
        onClose={() => setSnack(null)}
        message={snack ?? ''}
      />
    </>
  );
}

export default WordSets;
