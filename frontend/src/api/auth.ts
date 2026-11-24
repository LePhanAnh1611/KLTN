import { useMutation } from '@tanstack/react-query';

import type { LoginRequest, RegisterRequest, TokenResponse, UserResponse } from '../types/auth';
import { apiPost } from './client';

function registerUser(data: RegisterRequest): Promise<UserResponse> {
  return apiPost<UserResponse>('/api/v1/auth/register', data);
}

export function useRegister() {
  return useMutation({
    mutationFn: registerUser,
  });
}

function loginUser(data: LoginRequest): Promise<TokenResponse> {
  return apiPost<TokenResponse>('/api/v1/auth/login', data);
}

export function useLogin() {
  return useMutation({
    mutationFn: loginUser,
  });
}
