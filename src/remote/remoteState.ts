import Redis from 'ioredis';
import dotenv from 'dotenv';

dotenv.config();

let redis: Redis | null = null;

function getRedis() {
  if (!redis) {
    redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
      maxRetriesPerRequest: 1
    });
    redis.on('error', (err) => {
      console.warn('Redis connection error in remoteState:', err.message);
    });
  }
  return redis;
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
