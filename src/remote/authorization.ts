import dotenv from 'dotenv';

dotenv.config();

export function getAllowedUsers(): string[] {
  return (process.env.TELEGRAM_ALLOWED_USER_IDS || '')
    .split(',')
    .map(id => id.trim())
    .filter(id => id.length > 0);
}

export function isAuthorized(userId: number | string | undefined): boolean {
  if (userId === undefined) return false;
  const allowed = getAllowedUsers();
  return allowed.includes(userId.toString());
}
