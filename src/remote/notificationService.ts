import TelegramBot from 'node-telegram-bot-api';
import dotenv from 'dotenv';

dotenv.config();

const botToken = process.env.TELEGRAM_BOT_TOKEN;
const chatId = process.env.TELEGRAM_CHAT_ID;

let bot: TelegramBot | null = null;

if (botToken) {
  bot = new TelegramBot(botToken);
}

export async function sendNotification(message: string, parseMode: TelegramBot.ParseMode = 'Markdown') {
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

  await sendNotification(message);
}

export async function notifyTradeClosed(data: any) {
  const message = `🔵 *TRADE CLOSED*

*Market:* ${data.market || 'Unknown'}
*PnL:* ${data.pnl || 'N/A'}
*Duration:* ${data.duration || 'N/A'}
*Reason:* ${data.reason || 'N/A'}`;

  await sendNotification(message);
}

export async function notifyRiskAlert(data: any) {
  const message = `🟠 *RISK ALERT*

*State:* ${data.state || 'N/A'}
*Reason:* ${data.reason || 'N/A'}
*Action Taken:* ${data.action || 'N/A'}`;

  await sendNotification(message);
}

export async function notifySystemFailure(data: any) {
  const message = `🔴 *SYSTEM ALERT*

*Component:* ${data.component || 'Unknown'}
*Error:* ${data.error || 'N/A'}
*Current Mode:* ${data.mode || 'N/A'}`;

  await sendNotification(message);
}
