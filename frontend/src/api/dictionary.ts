import { useQuery } from '@tanstack/react-query';

import { apiGet } from './client';

/** UC-95 — tra cứu từ trong kho dữ liệu hệ thống.
 *
 * KHÔNG phải từ điển đầy đủ: nghĩa lấy từ bộ từ của chính người tra và các bộ
 * công khai, mức CEFR lấy từ wordlist chuẩn. Không có thì trả rỗng kèm gợi ý,
 * không bịa nghĩa.
 */
export interface DictionaryEntry {
  word: string;
  phonetic: string | null;
  part_of_speech: string | null;
  meaning: string;
  example: string | null;
  word_set_id: number;
  word_set_name: string;
  in_my_library: boolean;
}

export interface DictionaryResult {
  query: string;
  cefr_level: string | null;
  in_my_library: boolean;
  entries: DictionaryEntry[];
  suggestions: string[];
}

export function useDictionary(query: string) {
  const q = query.trim();
  return useQuery({
    queryKey: ['dictionary', q],
    queryFn: () => apiGet<DictionaryResult>(`/api/v1/dictionary?q=${encodeURIComponent(q)}`),
    enabled: q.length > 0,
    // Tra cùng một từ hai lần trong một phiên là chuyện thường; kết quả gần như
    // không đổi nên giữ lại thay vì gọi lại mạng.
    staleTime: 5 * 60 * 1000,
  });
}
