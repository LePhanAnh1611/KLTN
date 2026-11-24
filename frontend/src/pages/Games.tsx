import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { useGameLeaderboard, useGames, useSubmitScore } from '../api/games';
import { formatLabel } from '../types/labels';
import type { GameDefinition } from '../api/games';
import { getMatching, getTyping } from '../api/sessions';
import { useWordSets } from '../api/wordSets';
import type { MatchingRound, TypingQuestion } from '../types/session';
import PageHeader from '../components/PageHeader';
import SectionCard from '../components/SectionCard';
import SpellingBee from '../components/games/SpellingBee';
import WordMatch from '../components/games/WordMatch';
import WordRain from '../components/games/WordRain';
import { TrophyIcon } from '../components/icons';
import type { ReactNode } from 'react';
import { BulbArt, CardsArt, GameArt } from '../components/FlatArt';
import type { FlatArtProps } from '../components/FlatArt';
import { CARD_SX } from '../theme/theme';

/** UC-94 — trò chơi từ vựng.
 *
 * Trang này nói rõ trò chơi không nằm ngoài việc học: mỗi lượt trả lời vẫn ghi
 * INTERACTION và vẫn cập nhật mastery, chỉ khác cách trình bày và có tính giờ.
 * Người học cần biết điều đó để không nghĩ "chơi thì không được tính".
 */

const QUESTION_COUNT = 12;
const MIN_ITEMS = 4;

type Stage = 'idle' | 'loading' | 'playing' | 'done';

function GameCard({ game, onPlay }: { game: GameDefinition; onPlay: () => void }) {
  const look = GAME_LOOK[game.key] ?? GAME_LOOK.rain;
  const Art = look.art;
  return (
    <Box
      sx={{
        ...CARD_SX, flex: '1 1 280px', minWidth: { xs: 0, sm: 260 }, p: 1.25,
        display: 'flex', flexDirection: 'column', boxSizing: 'border-box',
      }}
    >
      <Box sx={{ position: 'relative', height: 140, borderRadius: '16px', bgcolor: look.tint, display: 'grid', placeItems: 'center' }}>
        <Art size={104} />
        <Box sx={{ position: 'absolute', left: 10, bottom: 10, px: 1.25, borderRadius: 999, bgcolor: 'rgba(255,255,255,0.92)', fontWeight: 900, fontSize: 13, lineHeight: 1.8 }}>
          {game.plays > 0 ? `${game.plays} ván` : 'Chưa chơi'}
        </Box>
      </Box>
      <Box sx={{ px: 0.75, pt: 1.5, display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
        <Typography component="h3" sx={{ fontWeight: 900, fontSize: 19, lineHeight: 1.3 }}>
          {game.name}
        </Typography>
        <Typography sx={{ mt: 0.5, fontSize: 14, fontWeight: 600, color: 'text.secondary', flexGrow: 1 }}>{game.description}</Typography>

        <Stack direction="row" sx={{ mt: 1.25, flexWrap: 'wrap', gap: 0.75 }}>
          <Chip size="small" label={`Dạng bài: ${formatLabel(game.exercise_format) || game.exercise_format}`} />
          {game.best_score != null && (
            <Chip size="small" color="secondary" label={`★ Kỷ lục ${game.best_score}`} />
          )}
        </Stack>

        <Button variant="contained" sx={{ mt: 1.75, mb: 0.5 }} onClick={onPlay}>Chơi ngay</Button>
      </Box>
    </Box>
  );
}

/** Màu nền + minh hoạ phẳng riêng cho từng trò. */
const GAME_LOOK: Record<string, { tint: string; art: (p: FlatArtProps) => ReactNode }> = {
  rain: { tint: '#E6E7FC', art: GameArt },
  spelling: { tint: '#FDF0CC', art: BulbArt },
  match: { tint: '#EFE4FB', art: CardsArt },
};

function Leaderboard({ game }: { game: GameDefinition }) {
  const rows = useGameLeaderboard(game.key);
  if (rows.isLoading) return <CircularProgress size={20} />;
  if (!rows.data || rows.data.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Chưa ai lập kỷ lục ở “{game.name}”. Bạn có thể là người đầu tiên.
      </Typography>
    );
  }
  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>#</TableCell>
          <TableCell>Người chơi</TableCell>
          <TableCell align="right">Điểm</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.data.map((r) => (
          <TableRow key={r.user_id}>
            <TableCell>{r.rank}</TableCell>
            <TableCell>{r.display_name}</TableCell>
            <TableCell align="right">{r.best_score.toLocaleString('vi-VN')}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function Games() {
  const games = useGames();
  const wordSets = useWordSets();
  const [active, setActive] = useState<GameDefinition | null>(null);
  const [wordSetId, setWordSetId] = useState<number | ''>('');
  const [stage, setStage] = useState<Stage>('idle');
  const [questions, setQuestions] = useState<TypingQuestion[]>([]);
  const [round, setRound] = useState<MatchingRound | null>(null);
  const [finalScore, setFinalScore] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [board, setBoard] = useState<GameDefinition | null>(null);

  const submit = useSubmitScore(active?.key ?? 'rain');

  const playable = (wordSets.data ?? []).filter((ws) => ws.item_count >= MIN_ITEMS);

  const close = () => {
    setActive(null);
    setStage('idle');
    setQuestions([]);
    setRound(null);
    setError(null);
  };

  const begin = async () => {
    if (!active || wordSetId === '') return;
    setStage('loading');
    setError(null);
    try {
      if (active.source === 'matching') {
        setRound(await getMatching(Number(wordSetId)));
      } else {
        setQuestions(await getTyping(Number(wordSetId), QUESTION_COUNT));
      }
      setStage('playing');
    } catch {
      setError('Không tải được đề. Bộ từ vựng có thể chưa đủ từ.');
      setStage('idle');
    }
  };

  const finish = (score: number) => {
    setFinalScore(score);
    setStage('done');
    submit.mutate(score);
  };

  return (
    <Box>
      <PageHeader
        title="Trò chơi từ vựng"
        subtitle="Chơi mà vẫn học: kết quả tính như bài học."
      />

      {games.isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}
      {games.isError && <Alert severity="error">Không tải được danh sách trò chơi.</Alert>}

      {games.data && (
        <>
          <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 2, mb: 3 }}>
            {games.data.map((g) => (
              <GameCard key={g.key} game={g} onPlay={() => { setActive(g); setStage('idle'); }} />
            ))}
          </Stack>

          <SectionCard
            title="Bảng xếp hạng"
            icon={<TrophyIcon size={18} />}
            caption="Điểm cao nhất của mỗi người ở từng trò."
          >
            <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap' }}>
              {games.data.map((g) => (
                <Chip
                  key={g.key} label={g.name}
                  color={(board ?? games.data[0]).key === g.key ? 'primary' : 'default'}
                  onClick={() => setBoard(g)}
                />
              ))}
            </Stack>
            <Leaderboard game={board ?? games.data[0]} />
          </SectionCard>
        </>
      )}

      <Dialog open={active !== null} onClose={stage === 'playing' ? undefined : close}
              maxWidth="sm" fullWidth>
        <DialogTitle>{active?.name}</DialogTitle>
        <DialogContent dividers>
          {stage === 'idle' && active && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {active.description}
              </Typography>
              {playable.length === 0 ? (
                <Alert severity="info">
                  Cần một bộ từ vựng có ít nhất {MIN_ITEMS} từ để chơi. Hãy tạo hoặc tải một bộ về
                  trước.
                </Alert>
              ) : (
                <TextField
                  select fullWidth label="Chơi với bộ từ vựng"
                  value={wordSetId} onChange={(e) => setWordSetId(Number(e.target.value))}
                >
                  {playable.map((ws) => (
                    <MenuItem key={ws.id} value={ws.id}>
                      {ws.name} ({ws.item_count} từ)
                    </MenuItem>
                  ))}
                </TextField>
              )}
              {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
            </Box>
          )}

          {stage === 'loading' && <Box sx={{ textAlign: 'center', py: 4 }}><CircularProgress /></Box>}

          {stage === 'playing' && active?.key === 'rain' && (
            <WordRain questions={questions} wordSetId={Number(wordSetId)} onFinish={finish} />
          )}
          {stage === 'playing' && active?.key === 'spelling' && (
            <SpellingBee questions={questions} wordSetId={Number(wordSetId)} onFinish={finish} />
          )}
          {stage === 'playing' && active?.key === 'match' && round && (
            <WordMatch round={round} wordSetId={Number(wordSetId)} onFinish={finish} />
          )}

          {stage === 'done' && (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <Typography variant="h3" sx={{ fontWeight: 800 }}>{finalScore}</Typography>
              <Typography variant="body2" color="text.secondary">điểm</Typography>
              {submit.data?.is_new_best && (
                <Chip color="success" label="Kỷ lục mới!" sx={{ mt: 1.5 }} />
              )}
              {submit.data && !submit.data.is_new_best && (
                <Typography variant="body2" sx={{ mt: 1.5 }}>
                  Kỷ lục của bạn: {submit.data.best_score} · hạng {submit.data.rank}
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                Các lượt trả lời trong ván này đã được ghi lại và đã cập nhật mức độ nắm vững.
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {stage === 'idle' && (
            <>
              <Button onClick={close}>Đóng</Button>
              <Button variant="contained" disabled={wordSetId === ''} onClick={begin}>
                Bắt đầu
              </Button>
            </>
          )}
          {stage === 'done' && (
            <>
              <Button onClick={close}>Đóng</Button>
              <Button variant="contained" onClick={() => setStage('idle')}>Chơi lại</Button>
            </>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default Games;
