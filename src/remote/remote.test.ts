import { isAuthorized } from './authorization';
import * as remoteState from './remoteState';
import Redis from 'ioredis';

describe('Remote Control Auth', () => {
  beforeAll(() => {
    process.env.TELEGRAM_ALLOWED_USER_IDS = '12345,67890';
  });

  test('isAuthorized identifies allowed users', () => {
    expect(isAuthorized(12345)).toBe(true);
    expect(isAuthorized('67890')).toBe(true);
    expect(isAuthorized(999)).toBe(false);
    expect(isAuthorized(undefined)).toBe(false);
  });
});

describe('Remote State', () => {
  let redis: Redis;

  beforeAll(() => {
    redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
  });

  afterAll(async () => {
    await redis.quit();
  });

  test('updateRemoteState and getRemoteState (mocked)', async () => {
    const updateSpy = jest.spyOn(remoteState, 'updateRemoteState').mockImplementation(async (patch) => {
        return { tradingEnabled: patch.tradingEnabled ?? true, emergencyMode: false, approvalMode: false, lastOperatorAction: Date.now() };
    });
    const getSpy = jest.spyOn(remoteState, 'getRemoteState').mockImplementation(async () => {
        return { tradingEnabled: false, emergencyMode: false, approvalMode: false, lastOperatorAction: Date.now() };
    });

    await remoteState.updateRemoteState({ tradingEnabled: false });
    const state = await remoteState.getRemoteState();
    expect(state.tradingEnabled).toBe(false);

    updateSpy.mockRestore();
    getSpy.mockRestore();
  });
});
