// Global typing for the Telegram WebApp script loaded in __root.tsx.
// Kept loose on purpose — the strict shape lives in src/lib/telegram.tsx.

interface Window {
  Telegram?: {
    WebApp?: any;
  };
}
