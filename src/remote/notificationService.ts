import TelegramBot from 'node-telegram-bot-api';
import dotenv from 'dotenv';

dotenv.config();

const botToken = process.env.TELEGRAM_BOT_TOKEN;
const chatId = process.env.TELEGRAM_CHAT_ID;
const minAlertLevel = (process.env.TELEGRAM_ALERT_LEVEL || 'info').toLowerCase();

const ALERT_LEVELS: Record<string, number> = {
  debug: 0,
  info: 1,
  warning: 2,
  critical: 3,
};

let bot: TelegramBot | null = null;

if (botToken) {
  bot = new TelegramBot(botToken);
}

export function shouldSend(level: string = 'info'): boolean {
  const msgLevel = ALERT_LEVELS[level.toLowerCase()] ?? 1;
  const minLevel = ALERT_LEVELS[minAlertLevel] ?? 1;
  return msgLevel >= minLevel;
}

export async function sendNotification(message: string, parseMode: TelegramBot.ParseMode = 'Markdown', level: string = 'info') {
  if (!shouldSend(level)) {
    return;
  }
  if (bot && chatId) {
    try {
      await bot.sendMessage(chatId, message, { parse_mode: parseMode });
    } catch (error) {
      console.error('Failed to send telegram notification:', error);
    }
  }
}

export async function notifyTradeOpened(data: any) {
  const message = `🟢 *TRADE OPENED*

*Market:* ${data.market || 'Unknown'}
*Side:* ${data.side || 'N/A'}
*Price:* ${data.price || 'N/A'}
*Size:* ${data.size || 'N/A'}
*Confidence:* ${(data.confidence * 100).toFixed(1)}%

*Position Exposure:* ${data.exposure || 'N/A'}
*Portfolio Risk:* ${data.risk || 'N/A'}`;

  await sendNotification(message, 'Markdown', 'info');
}

export async function notifyTradeClosed(data: any) {
  const message = `🔵 *TRADE CLOSED*

*Market:* ${data.market || 'Unknown'}
*PnL:* ${data.pnl || 'N/A'}
*Duration:* ${data.duration || 'N/A'}
*Reason:* ${data.reason || 'N/A'}`;

  await sendNotification(message, 'Markdown', 'info');
}

export async function notifyRiskAlert(data: any) {
  const message = `🟠 *RISK ALERT*

*State:* ${data.state || 'N/A'}
*Reason:* ${data.reason || 'N/A'}
*Action Taken:* ${data.action || 'N/A'}`;

  await sendNotification(message, 'Markdown', 'warning');
}

export async function notifySystemFailure(data: any) {
  const message = `🔴 *SYSTEM ALERT*

*Component:* ${data.component || 'Unknown'}
*Error:* ${data.error || 'N/A'}
*Current Mode:* ${data.mode || 'N/A'}`;

  await sendNotification(message, 'Markdown', 'critical');
}
