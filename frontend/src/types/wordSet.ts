export interface WordSet {
  id: number;
  name: string;
  description: string | null;
  category: string | null;
  difficulty: string | null;
  cover_image_url: string | null;
  is_public: boolean;
  is_featured: boolean;
  download_count: number;
  item_count: number;
  mastered_count: number;
  /** Đã học >= 1 lần nhưng chưa thuộc — đoạn giữa của thanh tiến độ 3 nấc. */
  learning_count?: number;
  tags: string[];              // UC-96
  created_at: string;
}

export interface WordSetInput {
  name: string;
  description: string | null;
  category: string | null;
  difficulty: string | null;
  tags?: string[];             // UC-96 — bỏ trống = gỡ hết nhãn
}

/**
 * Mức tin cậy của NGHĨA, do bước dựng bộ từ nền gắn.
 * null = người học tự nhập — không gắn cờ lên chữ của chính họ.
 */
export type MeaningConfidence = 'confirmed' | 'single-source' | 'needs-review' | 'llm';

export interface Item {
  id: number;
  word_set_id: number;
  word: string;
  phonetic: string | null;
  part_of_speech: string | null;
  meaning: string;
  example: string | null;
  /** Bản dịch tiếng Việt của câu ví dụ — chỉ có với bộ dựng sẵn. */
  example_vi?: string | null;
  meaning_confidence: MeaningConfidence | null;
  meaning_source: string | null;
  example_source: string | null;
  created_at: string;
}

export interface ItemInput {
  word: string;
  phonetic: string | null;
  part_of_speech: string | null;
  meaning: string;
  example: string | null;
}

export interface ImportReport {
  imported: number;
  errors: { row: number; message: string }[];
}

export interface RecommendedItem {
  id: number;
  word: string;
  phonetic: string | null;
  part_of_speech: string | null;
  meaning: string;
  example: string | null;
  example_vi?: string | null;
  meaning_confidence: MeaningConfidence | null;
  mastery: number;
  in_band: boolean;
  /** Pilot — 'band' = chọn theo vùng vừa sức · 'explore' = chọn ngẫu nhiên để thăm dò */
  selection: 'band' | 'explore';
}
