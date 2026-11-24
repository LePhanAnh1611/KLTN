import { createContext, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { decodeJwtPayload, getToken, setToken as setStoredToken } from '../api/token';

interface AuthState {
  token: string | null;
  userId: number | null;
  role: string | null;
}

interface AuthContextValue extends AuthState {
  login: (accessToken: string) => string;
  logout: () => void;
}

const EMPTY_STATE: AuthState = { token: null, userId: null, role: null };

/** Khôi phục phiên đã nhớ (token còn hạn trong localStorage — xem api/token.ts). */
function initialState(): AuthState {
  const token = getToken();
  if (!token) return EMPTY_STATE;
  const payload = decodeJwtPayload(token);
  return { token, userId: Number(payload.sub), role: payload.role };
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(initialState);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login: (accessToken: string) => {
        const payload = decodeJwtPayload(accessToken);
        setStoredToken(accessToken);
        setState({ token: accessToken, userId: Number(payload.sub), role: payload.role });
        return payload.role;
      },
      logout: () => {
        setStoredToken(null);
        setState(EMPTY_STATE);
      },
    }),
    [state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
