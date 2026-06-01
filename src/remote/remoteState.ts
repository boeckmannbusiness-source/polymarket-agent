import Redis from 'ioredis';
import dotenv from 'dotenv';

dotenv.config();

let redis: Redis | null = null;
let redisConnectPromise: Promise<void> | null = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY_MS = 1000;

function createRedisClient(): Redis {
  const url = process.env.REDIS_URL || 'redis://localhost:6379';
  const password = process.env.REDIS_PASSWORD || '';
  const tlsEnabled = process.env.REDIS_TLS === 'true';

  return new Redis(url, {
    password: password || undefined as any,
    tls: tlsEnabled ? {} : undefined as any,
    maxRetriesPerRequest: 3,
    retryStrategy: (times: number) => {
      reconnectAttempts = times;
      if (times > MAX_RECONNECT_ATTEMPTS) {
        console.error('Max Redis reconnect attempts reached in remoteState');
        return null;
      }
      const delay = Math.min(BASE_RECONNECT_DELAY_MS * Math.pow(2, times), 30000);
      console.warn(`Redis reconnecting (attempt ${times}) in ${delay}ms...`);
      return delay;
    },
    enableReadyCheck: true,
    lazyConnect: true,
  });
}

function getRedis(): Redis {
  const needsNewClient = !redis || redis.status === 'end' || redis.status === 'close';
  if (needsNewClient) {
    if (redis) {
      try { redis.disconnect(true); } catch (_) {}
    }
    redis = createRedisClient();
    redis.on('error', (err) => {
      console.warn('Redis connection error in remoteState:', err.message);
    });
    redis.on('connect', () => {
      reconnectAttempts = 0;
    });
    redisConnectPromise = redis.connect().catch((err) => {
      console.warn('Redis initial connect failed in remoteState:', err.message);
    });
  }
  return redis!;
}

export interface RemoteState {
  tradingEnabled: boolean;
  emergencyMode: boolean;
  approvalMode: boolean;
  lastOperatorAction: number;
}

const REDIS_KEY = 'remote:state';

const DEFAULT_STATE: RemoteState = {
  tradingEnabled: true,
  emergencyMode: false,
  approvalMode: false,
  lastOperatorAction: Date.now()
};

export async function getRemoteState(): Promise<RemoteState> {
  const r = getRedis();
  try {
    const data = await r.get(REDIS_KEY);
    if (!data) {
      return DEFAULT_STATE;
    }
    return JSON.parse(data);
  } catch (e) {
    console.warn('Failed to get remote state from Redis, using default');
    return DEFAULT_STATE;
  }
}

export async function updateRemoteState(patch: Partial<RemoteState>): Promise<RemoteState> {
  const r = getRedis();
  const currentState = await getRemoteState();
  const newState = {
    ...currentState,
    ...patch,
    lastOperatorAction: Date.now()
  };
  try {
    await r.set(REDIS_KEY, JSON.stringify(newState));
  } catch (e) {
    console.warn('Failed to set remote state in Redis');
  }
  return newState;
}

export async function isTradingEnabled(): Promise<boolean> {
  const state = await getRemoteState();
  return state.tradingEnabled && !state.emergencyMode;
}
