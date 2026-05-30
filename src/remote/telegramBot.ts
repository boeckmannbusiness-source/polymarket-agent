import TelegramBot from 'node-telegram-bot-api';
import dotenv from 'dotenv';
import Redis from 'ioredis';
import { handleCommand } from './commandHandler';
import { getAllowedUsers } from './authorization';
import { sendNotification } from './notificationService';

dotenv.config();

const token = process.env.TELEGRAM_BOT_TOKEN;

if (!token) {
  console.error('TELEGRAM_BOT_TOKEN is not defined in environment variables.');
  process.exit(1);
}

const bot = new TelegramBot(token, { polling: true });
const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
const chatId = process.env.TELEGRAM_CHAT_ID;

console.log('Telegram bot is starting...');
console.log('Allowed User IDs:', getAllowedUsers());

bot.on('message', (msg) => {
  handleCommand(bot, msg);
});

bot.on('polling_error', (error) => {
  console.error('Polling error:', error);
});

async function listenForNotifications() {
  console.log('Listening for notifications on Redis...');
  let lastId = '$';
  while (true) {
    try {
      const results = await redis.xread('BLOCK', 0, 'STREAMS', 'remote:notifications', lastId);
      if (results) {
        for (const [stream, messages] of results) {
          for (const [id, [_, message]] of messages) {
            lastId = id;
            await sendNotification(message);
          }
        }
      }
    } catch (error) {
      console.error('Error reading notifications from Redis:', error);
      await new Promise(resolve => setTimeout(resolve, 5000));
    }
  }
}

listenForNotifications();

process.on('SIGINT', () => {
  bot.stopPolling();
  process.exit(0);
});

process.on('SIGTERM', () => {
  bot.stopPolling();
  process.exit(0);
});
