export interface UserUpdateRequest {
  display_name: string;
  bio: string | null;
}

export interface AvatarResponse {
  avatar_url: string;
}
