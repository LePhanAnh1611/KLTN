import { createContext, useContext, useEffect, useMemo } from 'react';
import type { ReactNode } from 'react';
import type { PaletteMode } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

import { buildTheme } from './theme';

interface ColorModeValue {
  /** Bug #4: dark mode đã bỏ — ứng dụng luôn chạy nền sáng. */
  mode: PaletteMode;
}

const STORAGE_KEY = 'dkt-color-mode';
const ColorModeContext = createContext<ColorModeValue | undefined>(undefined);
const VALUE: ColorModeValue = { mode: 'light' };

/** Cung cấp theme MUI. Dark mode đã bỏ (bug #4): trước đây chế độ khởi tạo
 * đi theo `prefers-color-scheme` của hệ điều hành, nên máy đặt nền tối là vừa
 * đăng nhập đã thấy giao diện tối. Giờ cố định 'light'. */
export function ColorModeProvider({ children }: { children: ReactNode }) {
  // Xóa lựa chọn cũ còn lưu trong trình duyệt để không ai kẹt ở nền tối.
  useEffect(() => {
    try { window.localStorage.removeItem(STORAGE_KEY); } catch { /* bỏ qua */ }
  }, []);

  const theme = useMemo(() => buildTheme('light'), []);

  return (
    <ColorModeContext.Provider value={VALUE}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

export function useColorMode(): ColorModeValue {
  const ctx = useContext(ColorModeContext);
  if (!ctx) throw new Error('useColorMode must be used within a ColorModeProvider');
  return ctx;
}
