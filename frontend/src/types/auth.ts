export interface RegisterRequest {
  email: string;
  password: string;
  password_confirm: string;
  display_name: string;
}

export interface UserResponse {
  id: number;
  email: string;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  role: string;
  is_email_verified: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  email_verified: boolean;
}
