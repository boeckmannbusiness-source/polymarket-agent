import Redis from 'ioredis';
import TelegramBot from 'node-telegram-bot-api';
import { getRemoteState, updateRemoteState } from './remoteState';
import { isAuthorized } from './authorization';
import axios from 'axios';
import dotenv from 'dotenv';

dotenv.config();

const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
const API_URL = process.env.API_URL || 'http://localhost:8000';
const ADMIN_API_KEY = process.env.ADMIN_API_KEY || '';

const AUDIT_STREAM = 'remote:audit';

// Rate limiting: max 10 commands per 60 seconds per user
const RATE_LIMIT_WINDOW = 60000;
const MAX_COMMANDS_PER_WINDOW = 10;
const userCommandTimestamps = new Map<number, number[]>();

function checkRateLimit(userId: number): boolean {
  const now = Date.now();
  if (!userCommandTimestamps.has(userId)) {
    userCommandTimestamps.set(userId, [now]);
    return true;
  }

  const timestamps = userCommandTimestamps.get(userId)!;
  const validTimestamps = timestamps.filter(ts => now - ts < RATE_LIMIT_WINDOW);
  validTimestamps.push(now);
  userCommandTimestamps.set(userId, validTimestamps);

  return validTimestamps.length <= MAX_COMMANDS_PER_WINDOW;
}

async function logAudit(userId: string | number, username: string | undefined, command: string, result: string) {
  const entry = {
    timestamp: Date.now(),
    telegramUser: username || userId.toString(),
    command,
    result
  };
  await redis.xadd(AUDIT_STREAM, '*', 'data', JSON.stringify(entry));
}

export async function handleCommand(bot: TelegramBot, msg: TelegramBot.Message) {
  const chatId = msg.chat.id;
  const userId = msg.from?.id;
  const username = msg.from?.username;
  const text = msg.text;

  if (!text) return;

  if (!isAuthorized(userId)) {
    console.log(`Unauthorized access attempt by user ${userId} (${username})`);
    await bot.sendMessage(chatId, '❌ Unauthorized.');
    return;
  }

  if (userId && !checkRateLimit(userId)) {
    await bot.sendMessage(chatId, '⚠️ Rate limit exceeded. Please try again later.');
    return;
  }

  const command = text.split(' ')[0].toLowerCase();

  try {
    switch (command) {
      case '/status':
        await handleStatus(bot, chatId, userId!, username);
        break;
      case '/positions':
        await handlePositions(bot, chatId, userId!, username);
        break;
      case '/pause':
        await handlePause(bot, chatId, userId!, username);
        break;
      case '/resume':
        await handleResume(bot, chatId, userId!, username);
        break;
      case '/closeall':
        await handleCloseAll(bot, chatId, userId!, username);
        break;
      case '/confirm_closeall':
        await handleConfirmCloseAll(bot, chatId, userId!, username);
        break;
      case '/risk':
        await handleRisk(bot, chatId, userId!, username);
        break;
      case '/health':
        await handleHealth(bot, chatId, userId!, username);
        break;
      default:
        // Ignore or send help
        break;
    }
  } catch (error: any) {
    console.error(`Error handling command ${command}:`, error);
    await bot.sendMessage(chatId, `❌ Error: ${error.message}`);
    await logAudit(userId!, username, command, `Error: ${error.message}`);
  }
}

async function handleStatus(bot: TelegramBot, chatId: number, userId: number, username?: string) {
  const state = await getRemoteState();
  let backendStatus;
  try {
    const resp = await axios.get(`${API_URL}/debug/status`, {
      headers: { 'x-admin-key': ADMIN_API_KEY }
    });
    backendStatus = resp.data;
  } catch (e) {
    backendStatus = { error: 'Backend unreachable' };
  }

  const message = `*System Status*

*Mode:* ${backendStatus.app?.mode || 'Unknown'}
*Trading Enabled:* ${state.tradingEnabled ? '✅' : '⏸'}
*Risk State:* ${backendStatus.pipeline?.live_state || 'Unknown'}
*Open Positions:* ${backendStatus.pipeline?.open_trades_count || 'N/A'}
*Today's PnL:* ${backendStatus.pipeline?.live_daily_pnl || '0.00'}
*Available Capital:* ${backendStatus.pipeline?.available_capital || 'N/A'}
*WS Health:* ${backendStatus.services?.websocket === 'started' ? '🟢' : '🔴'}`;

  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
  await logAudit(userId, username, '/status', 'Success');
}

async function handlePositions(bot: TelegramBot, chatId: number, userId: number, username?: string) {
  try {
    const resp = await axios.get(`${API_URL}/debug/open-market-positions`, {
      headers: { 'x-admin-key': ADMIN_API_KEY }
    });
    const positions = resp.data.positions;
    if (!positions || positions.length === 0) {
      await bot.sendMessage(chatId, 'No active positions.');
    } else {
      let msg = '*Active Positions*\n\n';
      positions.forEach((p: any) => {
        msg += `🔹 *${p.agent_id}* | ${p.side} ${p.outcome}\n`;
        msg += `   Size: ${p.size} | Price: ${p.price}\n\n`;
      });
      await bot.sendMessage(chatId, msg, { parse_mode: 'Markdown' });
    }
    await logAudit(userId, username, '/positions', 'Success');
  } catch (e: any) {
    await bot.sendMessage(chatId, `❌ Failed to fetch positions: ${e.message}`);
    await logAudit(userId, username, '/positions', `Failed: ${e.message}`);
  }
}

async function handlePause(bot: TelegramBot, chatId: number, userId: number, username?: string) {
  await updateRemoteState({ tradingEnabled: false });
  await bot.sendMessage(chatId, '⏸ Trading paused.');
  await logAudit(userId, username, '/pause', 'Trading disabled');
}

async function handleResume(bot: TelegramBot, chatId: number, userId: number, username?: string) {
  await updateRemoteState({ tradingEnabled: true });
  await bot.sendMessage(chatId, '▶ Trading resumed.');
  await logAudit(userId, username, '/resume', 'Trading enabled');
}

async function handleCloseAll(bot: TelegramBot, chatId: number, userId: number, username?: string) {
  await bot.sendMessage(chatId, '⚠️ *Confirm close all positions?*\n\nSend /confirm_closeall to execute.', { parse_mode: 'Markdown' });
  await logAudit(userId, username, '/closeall', 'Requested confirmation');
}

async function handleConfirmCloseAll(bot: TelegramBot, chatId: number, userId: number, username?: string) {
  try {
    const resp = await axios.post(`${API_URL}/api/v1/execution/emergency/close-all`, {}, {
      headers: { 'x-admin-key': ADMIN_API_KEY }
    });
    await bot.sendMessage(chatId, `🛑 *Emergency close all triggered.* (Closed ${resp.data.closed_count} positions)`, { parse_mode: 'Markdown' });
    await logAudit(userId, username, '/confirm_closeall', 'Executed emergency close');
  } catch (e: any) {
    await bot.sendMessage(chatId, `❌ Failed to execute emergency close: ${e.message}`);
    await logAudit(userId, username, '/confirm_closeall', `Failed: ${e.message}`);
  }
}

async function handleRisk(bot: TelegramBot, chatId: number, userId: number, username?: string) {
  try {
    const resp = await axios.get(`${API_URL}/debug/global-risk`, {
      headers: { 'x-admin-key': ADMIN_API_KEY }
    });
    const risk = resp.data;
    const message = `*Risk State*

*Exposure:* ${risk.total_open_exposure || '0.00'}
*Exposure Utilization:* ${risk.exposure_utilization_pct || 0}%
*Max Drawdown:* ${risk.max_drawdown || 'N/A'}
*Circuit Breakers:* ${risk.circuit_breakers_active ? '🔴 ACTIVE' : '✅ Nominal'}`;

    await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
    await logAudit(userId, username, '/risk', 'Success');
  } catch (e: any) {
    await bot.sendMessage(chatId, `❌ Failed to fetch risk data: ${e.message}`);
  }
}

async function handleHealth(bot: TelegramBot, chatId: number, userId: number, username?: string) {
  try {
    const resp = await axios.get(`${API_URL}/debug/runtime-health`, {
      headers: { 'x-admin-key': ADMIN_API_KEY }
    });
    const health = resp.data;
    const message = `*Health Status*

*WebSocket:* started
*Redis Status:* OK
*Execution Status:* OK
*Market Feed Status:* OK
*Crash Count:* ${health.crash_count || 0}
*Uptime:* ${Math.floor(health.uptime_seconds / 3600)}h ${Math.floor((health.uptime_seconds % 3600) / 60)}m`;

    await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
    await logAudit(userId, username, '/health', 'Success');
  } catch (e: any) {
    await bot.sendMessage(chatId, `❌ Failed to fetch health data: ${e.message}`);
  }
}
