import { useEffect, useRef, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';

import {
  useEndConversation,
  useReplyAudio,
  useReplyText,
  useScenarios,
  useStartConversation,
} from '../api/conversations';
import type { ConversationDetail, ConversationTurn, Scenario } from '../api/conversations';
import { ApiError } from '../api/client';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { useSpeech } from '../hooks/useSpeech';
import PageHeader from '../components/PageHeader';
import RecordingPlayback from '../components/RecordingPlayback';
import { CheckIcon, MicIcon, SpeakerIcon, TrophyIcon } from '../components/icons';
import { ACCENT_FONT, LINE } from '../theme/theme';
import { KidBin, KidNa } from '../components/FlatScene';
import { VendingBox, VendingDots, VendingScreen } from '../components/VendingBox';
import { FLAT, INK, LABEL_FONT, PRIMARY, SECONDARY, SOFT_SHADOW, hardShadow } from '../theme/theme';

/** Bạn hội thoại theo GIỌNG của tình huống: nữ = Na, nam = Bin (thay Mona / Hét của bản retro). */
function NaPersona({ size = 80, bob }: { size?: number; bob?: boolean }) {
  return <KidNa size={size} pose={bob ? 'wave' : 'book'} mood={bob ? 'cheer' : 'happy'} />;
}
function BinPersona({ size = 80, bob }: { size?: number; bob?: boolean }) {
  return <KidBin size={size} pose={bob ? 'wave' : 'book'} mood={bob ? 'cheer' : 'happy'} />;
}
const RETRO_YELLOW = '#FDF0CC';

const MAX_RECORD_SEC = 60;

/** 3 mục tiêu trọng tâm (3 missions) theo chuẩn Hanpeak Speaking Studio */
const SCENARIO_MISSIONS: Record<string, string[]> = {
  airport_checkin: [
    'Xuất trình vé máy bay và giấy tờ tùy thân',
    'Yêu cầu lựa chọn vị trí chỗ ngồi phù hợp',
    'Hỏi về thời gian và cổng lên máy bay (Gate)',
  ],
  coffee_shop: [
    'Gọi món đồ uống theo sở thích (nóng/đá, sữa/đường)',
    'Hỏi mật khẩu Wifi của quán',
    'Thực hiện thanh toán và cảm ơn',
  ],
  job_interview: [
    'Giới thiệu bản thân và kinh nghiệm liên quan',
    'Nêu điểm mạnh và kỹ năng làm việc nhóm',
    'Đặt một câu hỏi làm rõ về vị trí công việc',
  ],
  hotel_reception: [
    'Xác nhận thông tin đặt phòng khách sạn',
    'Hỏi về thời gian bữa sáng và các tiện ích',
    'Yêu cầu nhận chìa khóa hoặc hỗ trợ hành lý',
  ],
  restaurant_order: [
    'Hỏi món ăn gợi ý đặc sắc của nhà hàng',
    'Gọi món chính và ghi chú khẩu vị',
    'Yêu cầu tính tiền và lấy hóa đơn',
  ],
};

function getMissions(key: string, name: string): string[] {
  if (SCENARIO_MISSIONS[key]) return SCENARIO_MISSIONS[key];
  return [
    `Chào hỏi và giới thiệu nhu cầu trong tình huống ${name}`,
    'Lắng nghe phản hồi và đặt câu hỏi làm rõ',
    'Hoàn thành mục tiêu giao tiếp và chào tạm biệt',
  ];
}

/** Soundwave hiệu ứng chuyển động âm thanh tinh tế (Anti-AI Slop) */
function SoundWave({ active, color }: { active: boolean; color: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, height: 28 }}>
      {[0.4, 0.8, 1.2, 0.6, 1.0, 0.5, 0.9].map((delay, idx) => (
        <Box
          key={idx}
          sx={{
            width: 3.5,
            height: active ? '100%' : '20%',
            borderRadius: 2,
            bgcolor: color,
            transition: 'height 0.2s ease',
            ...(active && {
              animation: `soundWavePulse 0.8s ease-in-out ${delay * 0.18}s infinite alternate`,
              '@keyframes soundWavePulse': {
                '0%': { height: '20%' },
                '100%': { height: '95%' },
              },
            }),
          }}
        />
      ))}
    </Box>
  );
}

function Bubble({
  turn,
  onSpeak,
  audioUrl,
}: {
  turn: ConversationTurn;
  onSpeak: (t: string) => void;
  /** Bản thu gốc của lượt người học (chỉ có với lượt nói, trong phiên hiện tại). */
  audioUrl?: string;
}) {
  const isAi = turn.speaker === 'ai';
  return (
    <Box sx={{ display: 'flex', justifyContent: isAi ? 'flex-start' : 'flex-end', mb: 2 }}>
      <Box sx={{ maxWidth: '82%' }}>
        <Box
          sx={{
            px: 2.25,
            py: 1.5,
            // Bong bóng thoại kiểu sticker: AI vàng, người học trắng, viền mực + bóng cứng.
            borderRadius: isAi ? '18px 18px 18px 4px' : '18px 18px 4px 18px',
            border: `1px solid ${LINE}`,
            bgcolor: isAi ? RETRO_YELLOW : '#FFFFFF',
            boxShadow: SOFT_SHADOW,
          }}
        >
          <Typography variant="body1" sx={{ lineHeight: 1.6, fontWeight: 600 }}>
            {turn.text}
          </Typography>
          {!isAi && audioUrl && (
            <Box sx={{ mt: 0.75 }}>
              <RecordingPlayback src={audioUrl} label="Giọng bạn" compact />
            </Box>
          )}
          {isAi && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.75 }}>
              <Button
                size="small"
                startIcon={<SpeakerIcon size={15} />}
                onClick={() => onSpeak(turn.text)}
                sx={{ fontSize: 13, px: 1, py: 0.25, minHeight: 0, textTransform: 'none' }}
              >
                Nghe câu này
              </Button>
            </Box>
          )}
        </Box>

        {turn.correction && (
          <Box
            sx={{
              mt: 1,
              p: 1.25,
              borderRadius: '12px',
              bgcolor: '#FFD2C2',
              border: `1px solid ${LINE}`,
            }}
          >
            <Typography sx={{ display: 'block', fontFamily: LABEL_FONT, fontWeight: 700, fontSize: 13, lineHeight: 1.1 }}>
              ✎ GỢI Ý TỰ NHIÊN HƠN
            </Typography>
            <Typography variant="body2" sx={{ fontStyle: 'italic', fontWeight: 700, color: INK, mt: 0.25 }}>
              “{turn.correction}”
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}

function ScenarioCard({
  scenario,
  onStart,
  pending,
}: {
  scenario: Scenario;
  onStart: () => void;
  pending: boolean;
}) {
  // Nhân vật đại diện theo GIỌNG của tình huống: nữ = Na, nam = Bin.
  const Persona = scenario.voice === 'female' ? NaPersona : BinPersona;
  const face = scenario.voice === 'female' ? '#FFFFFF' : '#FFFFFF';

  return (
    <VendingBox
      face={face}
      sideLabel={`${scenario.cefr} · ${scenario.persona}`}
      depth={44}
      radius={20}
      faceSx={{ p: 1.75, height: '100%', display: 'flex', flexDirection: 'column', boxSizing: 'border-box', color: INK }}
      sx={{ height: '100%' }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.25 }}>
        <Typography component="h3" sx={{ fontWeight: 900, fontSize: 17, flexGrow: 1, minWidth: 0 }}>
          {scenario.name}
        </Typography>
        <Box component="span" sx={{ px: 0.75, bgcolor: FLAT.green, color: '#FFFFFF', borderRadius: '999px', fontFamily: LABEL_FONT, fontWeight: 700, fontSize: 13, lineHeight: 1.3 }}>
          {scenario.cefr}
        </Box>
      </Box>

      {/* Màn hình: nhân vật đại diện + câu mở đầu dạng bong bóng thoại */}
      <VendingScreen color={RETRO_YELLOW} faceColor={face}>
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 0.75, p: 1.25, pb: 0 }}>
          <Persona size={80} bob />
          <Box sx={{ position: 'relative', mb: 3, p: 1.25, bgcolor: '#FFFFFF', border: `1px solid ${LINE}`, borderRadius: '14px',
                     boxShadow: SOFT_SHADOW, flexGrow: 1, minWidth: 0 }}>
            <Typography sx={{ fontSize: 14.5, fontStyle: 'italic', fontWeight: 700, lineHeight: 1.4 }}>
              “{scenario.opening}”
            </Typography>
            <Typography sx={{ fontSize: 12.5, fontWeight: 700, mt: 0.5 }}>- {scenario.persona}</Typography>
          </Box>
        </Box>
      </VendingScreen>

      <Typography sx={{ fontSize: 14, fontWeight: 600, mt: 1.25, mb: 1.25 }}>
        {scenario.description}
      </Typography>

      <Box sx={{ mt: 'auto', display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <VendingDots size={16} />
        <Button variant="contained" color="inherit" disabled={pending} onClick={onStart} sx={{ flexGrow: 1 }}>
          ▶ Bắt đầu
        </Button>
      </Box>
    </VendingBox>
  );
}

/** Post-Call Review / Rubric Screen (Hanpeak Speaking Studio) */
function PostCallReview({
  convo,
  onRetry,
  onClose,
}: {
  convo: ConversationDetail;
  onRetry: () => void;
  onClose: () => void;
}) {
  const theme = useTheme();
  const missions = getMissions(convo.scenario, convo.scenario_name);
  const userTurns = convo.turns.filter((t) => t.speaker === 'user');
  const corrections = convo.turns.filter((t) => t.correction);
  const completedMissions = Math.min(missions.length, Math.max(1, Math.floor(userTurns.length * 0.75)));

  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', py: 2 }}>
      <Paper
        variant="outlined"
        sx={{
          p: { xs: 2.5, sm: 3.5 },
          borderRadius: '16px',
          bgcolor: 'background.paper',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Box
            sx={{
              width: 52,
              height: 52,
              borderRadius: '12px',
              bgcolor: alpha(theme.palette.success.main, 0.12),
              color: theme.palette.success.main,
              display: 'grid',
              placeItems: 'center',
            }}
          >
            <TrophyIcon size={30} />
          </Box>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 800, fontFamily: ACCENT_FONT }}>
              Đánh giá buổi luyện nói
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Tình huống: <strong>{convo.scenario_name}</strong> · Với <strong>{convo.persona}</strong>
            </Typography>
          </Box>
        </Box>

        {/* 3 Metric cards */}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' }, gap: 2, mb: 3 }}>
          <Paper
            variant="outlined"
            sx={{ p: 2, textAlign: 'center', borderRadius: '10px', bgcolor: alpha(theme.palette.primary.main, 0.04) }}
          >
            <Typography variant="caption" color="text.secondary">
              LƯỢT ĐỐI THOẠI
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 800, my: 0.5, color: theme.palette.primary.main }}>
              {userTurns.length}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              câu nói đã phản hồi
            </Typography>
          </Paper>

          <Paper
            variant="outlined"
            sx={{ p: 2, textAlign: 'center', borderRadius: '10px', bgcolor: alpha(theme.palette.success.main, 0.04) }}
          >
            <Typography variant="caption" color="text.secondary">
              MỤC TIÊU ĐẠT ĐƯỢC
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 800, my: 0.5, color: theme.palette.success.main }}>
              {completedMissions}/{missions.length}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              nhiệm vụ giao tiếp
            </Typography>
          </Paper>

          <Paper
            variant="outlined"
            sx={{ p: 2, textAlign: 'center', borderRadius: '10px', bgcolor: alpha(theme.palette.warning.main, 0.04) }}
          >
            <Typography variant="caption" color="text.secondary">
              GỢI Ý TỰ NHIÊN HƠN
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 800, my: 0.5, color: theme.palette.warning.main }}>
              {corrections.length}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              điểm ngữ pháp / từ vựng
            </Typography>
          </Paper>
        </Box>

        {/* Missions summary checklist */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
            Kiểm tra 3 mục tiêu trọng tâm:
          </Typography>
          <Stack spacing={1}>
            {missions.map((m, idx) => {
              const isChecked = idx < completedMissions;
              return (
                <Box
                  key={idx}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    p: 1.5,
                    borderRadius: '8px',
                    bgcolor: isChecked
                      ? alpha(theme.palette.success.main, 0.06)
                      : alpha(theme.palette.text.primary, 0.03),
                    border: `1px solid ${
                      isChecked
                        ? alpha(theme.palette.success.main, 0.25)
                        : theme.palette.divider
                    }`,
                  }}
                >
                  <Box
                    sx={{
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      bgcolor: isChecked ? theme.palette.success.main : theme.palette.action.disabledBackground,
                      color: '#FFFFFF',
                      display: 'grid',
                      placeItems: 'center',
                    }}
                  >
                    <CheckIcon size={14} />
                  </Box>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 600, color: isChecked ? 'text.primary' : 'text.secondary' }}
                  >
                    {m}
                  </Typography>
                </Box>
              );
            })}
          </Stack>
        </Box>

        {/* Key corrections review */}
        {corrections.length > 0 && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
              Tổng hợp điểm cần lưu ý để nói tự nhiên hơn:
            </Typography>
            <Stack spacing={1.5}>
              {corrections.map((turn) => (
                <Paper
                  key={turn.ordinal}
                  variant="outlined"
                  sx={{ p: 2, borderRadius: '8px', bgcolor: alpha(theme.palette.warning.main, 0.03) }}
                >
                  <Typography variant="caption" color="text.secondary">
                    Câu bạn đã nói:
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 1, textDecoration: 'line-through', color: 'text.secondary' }}>
                    “{turn.text}”
                  </Typography>
                  <Typography variant="caption" color="warning.dark" sx={{ fontWeight: 700 }}>
                    Nói tự nhiên như người bản xứ:
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                    “{turn.correction}”
                  </Typography>
                </Paper>
              ))}
            </Stack>
          </Box>
        )}

        <Divider sx={{ my: 3 }} />

        <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <Button variant="outlined" onClick={onClose}>
            Chọn tình huống khác
          </Button>
          <Button variant="contained" onClick={onRetry}>
            Luyện tập lại
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}

function Conversation() {
  const theme = useTheme();
  const scenarios = useScenarios();
  const start = useStartConversation();
  const [convo, setConvo] = useState<ConversationDetail | null>(null);
  // Nhân vật đại diện của cuộc gọi theo giọng đọc: nữ = Na, nam = Bin.
  const Persona = convo?.voice === 'male' ? BinPersona : NaPersona;
  const personaFace = convo?.voice === 'male' ? '#FFFFFF' : '#FFFFFF';
  const [finishedConvo, setFinishedConvo] = useState<ConversationDetail | null>(null);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);

  const replyText = useReplyText(convo?.id ?? null);
  const replyAudio = useReplyAudio(convo?.id ?? null);
  const finish = useEndConversation();
  const recorder = useAudioRecorder(MAX_RECORD_SEC);
  const speech = useSpeech();
  const endRef = useRef<HTMLDivElement | null>(null);

  const busy = replyText.isPending || replyAudio.isPending;

  // Bản thu của từng lượt nói, theo ordinal của lượt — để nghe lại câu mình vừa
  // nói bên cạnh chữ máy chuyển ngữ. Máy chủ không lưu audio nên chỉ giữ ở đây.
  const [turnAudio, setTurnAudio] = useState<Record<number, string>>({});
  const turnAudioRef = useRef(turnAudio);
  turnAudioRef.current = turnAudio;

  // Đổi/kết thúc cuộc hội thoại và rời trang: thu hồi object URL để không rò bộ nhớ
  useEffect(() => {
    return () => {
      Object.values(turnAudioRef.current).forEach((url) => URL.revokeObjectURL(url));
      setTurnAudio({});
    };
  }, [convo?.id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [convo?.turns.length]);

  // Ghi âm xong thì gửi luôn
  useEffect(() => {
    if (!recorder.blob || busy || !convo) return;
    const blob = recorder.blob;
    recorder.reset();
    setError(null);
    replyAudio.mutate(blob, {
      onSuccess: (data) => {
        const lastUser = [...data.turns].reverse().find((t) => t.speaker === 'user');
        if (lastUser && !turnAudioRef.current[lastUser.ordinal]) {
          const url = URL.createObjectURL(blob);
          setTurnAudio((prev) => ({ ...prev, [lastUser.ordinal]: url }));
        }
        setConvo(data);
      },
      onError: (e) =>
        setError(e instanceof ApiError ? e.message : 'Không gửi được đoạn ghi âm.'),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recorder.blob]);

  const send = () => {
    const text = draft.trim();
    if (!text || !convo) return;
    setError(null);
    replyText.mutate(text, {
      onSuccess: (data) => {
        setConvo(data);
        setDraft('');
      },
      onError: (e) =>
        setError(e instanceof ApiError ? e.message : 'Không gửi được. Thử lại sau.'),
    });
  };

  const handleEndConversation = () => {
    if (!convo) return;
    finish.mutate(convo.id, {
      onSuccess: (detail) => {
        setFinishedConvo(detail || convo);
        setConvo(null);
        setDraft('');
      },
      onError: () => {
        setFinishedConvo(convo);
        setConvo(null);
      },
    });
  };

  // Màn hình kết quả sau cuộc gọi
  if (finishedConvo) {
    return (
      <PostCallReview
        convo={finishedConvo}
        onRetry={() => {
          const key = finishedConvo.scenario;
          setFinishedConvo(null);
          start.mutate(key, { onSuccess: (d) => setConvo(d) });
        }}
        onClose={() => setFinishedConvo(null)}
      />
    );
  }

  const activeMissions = convo ? getMissions(convo.scenario, convo.scenario_name) : [];
  const userTurnsCount = convo?.turns.filter((t) => t.speaker === 'user').length ?? 0;
  const currentMissionIndex = Math.min(activeMissions.length - 1, Math.floor(userTurnsCount / 1.5));

  return (
    <Box sx={{ maxWidth: 1000, mx: 'auto' }}>
      <PageHeader
        title="Hội thoại với AI"
        subtitle="Luyện nói theo tình huống thật cùng AI."
      />

      <Alert severity="info" sx={{ mb: 3 }}>
        Phần luyện nói không tính vào mức nắm vững từ vựng - nó rèn phản xạ giao tiếp và độ trôi chảy, là một kỹ năng khác.
      </Alert>

      {/* Danh sách tình huống (Scenario Selector Grid) */}
      {!convo && (
        <>
          {scenarios.isLoading && (
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <CircularProgress />
            </Box>
          )}
          {scenarios.isError && (
            <Alert severity="error">Không tải được danh sách tình huống.</Alert>
          )}
          {start.isError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              Không mở được hội thoại. Thử lại sau.
            </Alert>
          )}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' },
              gap: 2.5,
            }}
          >
            {scenarios.data?.map((s) => (
              <ScenarioCard
                key={s.key}
                scenario={s}
                pending={start.isPending}
                onStart={() => start.mutate(s.key, { onSuccess: (d) => setConvo(d) })}
              />
            ))}
          </Box>
        </>
      )}

      {/* Màn hình cuộc gọi — nhân vật đại diện theo giọng: nữ = Na, nam = Bin */}
      {convo && (
        <Box>
          {/* Top Bar: Header & Controls */}
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              mb: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 2,
              borderRadius: '12px',
              flexWrap: 'wrap',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{ width: 52, height: 52, display: 'grid', placeItems: 'center', bgcolor: personaFace,
                         border: `1px solid ${LINE}`, borderRadius: '12px', overflow: 'hidden' }}>
                <Persona size={48} />
              </Box>
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                    {convo.scenario_name}
                  </Typography>
                  <Box component="span" sx={{ px: 0.75, bgcolor: FLAT.green, color: '#FFFFFF', borderRadius: '999px', fontFamily: LABEL_FONT, fontWeight: 700, fontSize: 13, lineHeight: 1.3 }}>
                    {convo.cefr}
                  </Box>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  Đang đàm thoại với <strong>{convo.persona}</strong>
                </Typography>
              </Box>
            </Box>

            <Button
              variant="outlined"
              color="error"
              size="small"
              onClick={handleEndConversation}
              disabled={finish.isPending}
              sx={{ fontWeight: 700 }}
            >
              Kết thúc cuộc gọi
            </Button>
          </Paper>

          {/* Top 3-Mission Checklist */}
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              mb: 2.5,
              borderRadius: '16px',
              bgcolor: RETRO_YELLOW,
              boxShadow: SOFT_SHADOW,
            }}
          >
            <Typography sx={{ fontFamily: LABEL_FONT, fontWeight: 700, fontSize: 14, lineHeight: 1, display: 'block', mb: 1.25, color: INK }}>
              ▸ 3 MỤC TIÊU GIAO TIẾP CẦN ĐẠT TRONG BUỔI NÀY
            </Typography>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' },
                gap: 1.5,
              }}
            >
              {activeMissions.map((mission, idx) => {
                const isCompleted = idx < currentMissionIndex;
                const isCurrent = idx === currentMissionIndex;
                return (
                  <Box
                    key={idx}
                    sx={{
                      p: 1.25,
                      borderRadius: '12px',
                      border: `1px solid ${LINE}`,
                      boxShadow: isCurrent ? hardShadow(3) : 'none',
                      bgcolor: isCompleted ? '#FFFFFF' : isCurrent ? '#FFFFFF' : '#FFF4C7',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 1,
                    }}
                  >
                    <Box
                      sx={{
                        width: 22,
                        height: 22,
                        borderRadius: '6px',
                        border: `1px solid ${LINE}`,
                        bgcolor: isCompleted ? '#FFFFFF' : isCurrent ? SECONDARY : '#FFFFFF',
                        color: INK,
                        display: 'grid',
                        placeItems: 'center',
                        fontFamily: LABEL_FONT, fontWeight: 700,
                        fontSize: 13,
                        mt: 0.1,
                        flexShrink: 0,
                      }}
                    >
                      {isCompleted ? <CheckIcon size={12} /> : idx + 1}
                    </Box>
                    <Typography
                      variant="caption"
                      sx={{
                        fontWeight: isCurrent ? 800 : 600,
                        color: INK,
                        textDecoration: isCompleted ? 'line-through' : 'none',
                        lineHeight: 1.35,
                      }}
                    >
                      {mission}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          </Paper>

          {/* Main Stage & Chat Panel */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: '280px 1fr' },
              gap: 2.5,
              mb: 2.5,
            }}
          >
            {/* Persona Presence Studio (Left) */}
            <Paper
              variant="outlined"
              sx={{
                p: 3,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
                minHeight: 280,
                bgcolor: personaFace,
                borderRadius: '18px',
                boxShadow: SOFT_SHADOW,
              }}
            >
              <Box
                sx={{
                  position: 'relative',
                  width: 168,
                  height: 168,
                  borderRadius: '24px',
                  bgcolor: RETRO_YELLOW,
                  border: `1px solid ${LINE}`,
                  display: 'grid',
                  placeItems: 'center',
                  mb: 2,
                }}
              >
                <Persona size={148} bob={speech.speaking} />
                {speech.speaking && (
                  <Box
                    sx={{
                      position: 'absolute',
                      inset: -8,
                      borderRadius: '28px',
                      border: `1px solid ${LINE}`,
                      animation: 'pulseRing 1.5s infinite',
                      '@keyframes pulseRing': {
                        '0%': { transform: 'scale(0.95)', opacity: 0.8 },
                        '100%': { transform: 'scale(1.15)', opacity: 0 },
                      },
                    }}
                  />
                )}
              </Box>

              <Typography variant="h6" sx={{ fontWeight: 800, fontSize: 17 }}>
                {convo.persona}
              </Typography>
              <Typography variant="caption" sx={{ mb: 2, fontWeight: 700 }}>
                Đối tác hội thoại AI
              </Typography>

              {/* SoundWave Indicator */}
              <Box sx={{ mb: 1.5 }}>
                <SoundWave
                  active={recorder.recording || busy || speech.speaking}
                  color={
                    recorder.recording
                      ? theme.palette.error.main
                      : speech.speaking
                      ? theme.palette.primary.main
                      : INK
                  }
                />
              </Box>

              <Chip
                size="small"
                label={
                  recorder.recording
                    ? `Đang ghi âm... (${recorder.elapsedSec}s)`
                    : speech.speaking
                    ? `${convo.persona} đang nói...`
                    : busy
                    ? 'Đang chuẩn bị phản hồi...'
                    : 'Chờ bạn trả lời'
                }
                color={recorder.recording ? 'error' : speech.speaking ? 'primary' : 'default'}
                sx={{ fontWeight: 800, fontSize: 13, ...(!recorder.recording && !speech.speaking && { bgcolor: '#FFFFFF' }) }}
              />
            </Paper>

            {/* Transcript Area (Right) */}
            <Paper
              variant="outlined"
              sx={{
                p: 2.5,
                borderRadius: '18px',
                boxShadow: SOFT_SHADOW,
                height: 440,
                display: 'flex',
                flexDirection: 'column',
                bgcolor: 'background.paper',
              }}
            >
              <Box sx={{ flexGrow: 1, overflowY: 'auto', pr: 1 }}>
                {convo.turns.map((t) => (
                  <Bubble
                    key={t.ordinal}
                    turn={t}
                    audioUrl={turnAudio[t.ordinal]}
                    onSpeak={(text) => speech.speak(text, { gender: convo.voice })}
                  />
                ))}
                {busy && (
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 1, p: 1 }}>
                    <CircularProgress size={16} />
                    <Typography variant="body2" color="text.secondary">
                      {replyAudio.isPending
                        ? 'Hệ thống đang nghe và chuyển ngữ...'
                        : `${convo.persona} đang soạn câu trả lời…`}
                    </Typography>
                  </Stack>
                )}
                <div ref={endRef} />
              </Box>
            </Paper>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {/* Bottom Action / Record Bar */}
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              borderRadius: '16px',
              bgcolor: SECONDARY,
              boxShadow: SOFT_SHADOW,
            }}
          >
            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
              <TextField
                fullWidth
                size="small"
                value={draft}
                disabled={busy}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder="Nhập câu trả lời bằng tiếng Anh (Enter để gửi) hoặc bấm Mic..."
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: '8px',
                  },
                }}
              />

              {recorder.supported && (
                <IconButton
                  color={recorder.recording ? 'error' : 'primary'}
                  disabled={busy}
                  aria-label={recorder.recording ? 'Dừng ghi âm' : 'Ghi âm câu trả lời'}
                  onClick={() => (recorder.recording ? recorder.stop() : recorder.start())}
                  sx={{
                    width: 44,
                    height: 44,
                    color: recorder.recording ? '#FFFFFF' : INK,
                    bgcolor: recorder.recording ? theme.palette.error.main : PRIMARY,
                    border: `1px solid ${LINE}`,
                    boxShadow: SOFT_SHADOW,
                    '&:hover': { bgcolor: recorder.recording ? theme.palette.error.main : '#2FC2B4' },
                    transition: 'all 0.15s ease',
                    ...(recorder.recording && {
                      animation: 'micPulse 1.2s infinite',
                      '@keyframes micPulse': {
                        '0%': { transform: 'scale(1)' },
                        '50%': { transform: 'scale(1.08)' },
                        '100%': { transform: 'scale(1)' },
                      },
                    }),
                  }}
                >
                  <MicIcon size={20} />
                </IconButton>
              )}

              <Button
                variant="contained"
                disabled={busy || !draft.trim()}
                onClick={send}
                sx={{ px: 3, fontWeight: 700, height: 40 }}
              >
                Gửi
              </Button>
            </Stack>

            {recorder.recording && (
              <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1, fontWeight: 600 }}>
                Đang ghi âm… {recorder.elapsedSec}s - bấm biểu tượng Mic lần nữa để hoàn tất và gửi.
              </Typography>
            )}
            {recorder.error && (
              <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1 }}>
                {recorder.error}
              </Typography>
            )}
          </Paper>
        </Box>
      )}
    </Box>
  );
}

export default Conversation;
