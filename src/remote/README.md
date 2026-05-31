# Remote Control & Mobile Operations Layer (Phase 6B)

Secure remote monitoring and control of the Polymarket Intelligence Agent via Telegram.

## Architecture

The remote control layer is a Node.js TypeScript application that interfaces with the Python backend through Redis and REST APIs.

- **`telegramBot.ts`**: Main entry point, handles polling and notification delivery.
- **`commandHandler.ts`**: Processes commands, enforces rate limits, and logs audits.
- **`remoteState.ts`**: Maintains persistent state (e.g., `tradingEnabled`) in Redis.
- **`authorization.ts`**: Enforces user whitelist.
- **`notificationService.ts`**: Formats messages for trades, risk alerts, and system health.

## Commands

- `/status`: Current system mode, trading state, PnL, and health overview.
- `/positions`: Lists all currently open paper and live positions.
- `/pause`: Disables new trade execution (persisted in Redis).
- `/resume`: Re-enables trade execution.
- `/closeall`: Triggers emergency position closing (requires confirmation).
- `/confirm_closeall`: Executes the emergency close on the backend.
- `/risk`: Detailed risk metrics, exposure utilization, and circuit breaker status.
- `/health`: Component-level health status and uptime.

## Security Features

- **User Whitelist**: Only user IDs listed in `TELEGRAM_ALLOWED_USER_IDS` can execute commands.
- **Rate Limiting**: Commands are limited to 10 per minute per user to prevent spam/abuse.
- **Audit Trail**: Every command and its result is recorded in the `remote:audit` Redis stream.
- **API Security**: Administrative commands (like `/closeall`) use `ADMIN_API_KEY` for backend authentication.
- **No Secrets**: Telegram messages never contain API keys, private keys, or sensitive PII.

## Setup & Deployment

### Environment Variables

Add the following to your `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ALLOWED_USER_IDS=user_id1,user_id2
TELEGRAM_CHAT_ID=your_target_chat_id
API_URL=http://localhost:8000
ADMIN_API_KEY=your_admin_key
REDIS_URL=redis://localhost:6379
```

### Running the Bot

```bash
# Install dependencies
npm install

# Build the project
npm run build

# Start the bot
npm start
```

## Security Review

1. **Access Control**: Strict ID-based whitelist is the first line of defense.
2. **Backend Hardening**: The Python backend requires the `ADMIN_API_KEY` for any action triggered by the bot. The `/emergency/close-all` endpoint is protected.
3. **Fail-Safe**: If the remote control bot or Redis goes down, the backend defaults to the last known state or `tradingEnabled: true` (configurable), while still respecting its internal safety circuit breakers.
4. **Rate Limiting**: Prevents unintentional command flooding.

## Production Readiness Checklist

- [x] Telegram bot online and responsive.
- [x] Authorized user can control system state.
- [x] Unauthorized users are blocked and logged.
- [x] Trade notifications delivered via Redis stream.
- [x] Risk alerts delivered instantly.
- [x] Pause/resume functionality verified against `TradeService`.
- [x] Emergency close functional via confirmed command.
- [x] Full audit trail stored in Redis.
- [x] Backend API secured with admin keys.
