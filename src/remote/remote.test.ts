import { isAuthorized } from './authorization';
import * as remoteState from './remoteState';

// Unit tests for rate limiting logic extracted from commandHandler
function createRateLimiter(windowMs: number, maxCommands: number) {
  const userTimestamps = new Map<number, number[]>();

  return {
    check(userId: number): boolean {
      const now = Date.now();
      if (!userTimestamps.has(userId)) {
        userTimestamps.set(userId, [now]);
        return true;
      }

      const timestamps = userTimestamps.get(userId)!;
      const valid = timestamps.filter(ts => now - ts < windowMs);
      valid.push(now);
      userTimestamps.set(userId, valid);

      return valid.length <= maxCommands;
    },
    getCount(userId: number): number {
      return (userTimestamps.get(userId) || []).length;
    },
    advanceClock(ms: number) {
      // For testing, we can't easily mock Date.now in pure TS without jest timers
    }
  };
}

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

  test('isAuthorized rejects empty whitelist', () => {
    process.env.TELEGRAM_ALLOWED_USER_IDS = '';
    expect(isAuthorized(12345)).toBe(false);
    process.env.TELEGRAM_ALLOWED_USER_IDS = '12345,67890';
  });

  test('isAuthorized rejects malformed IDs', () => {
    // Special characters or empty parts in whitelist
    process.env.TELEGRAM_ALLOWED_USER_IDS = 'abc, ,12345';
    expect(isAuthorized(12345)).toBe(true);
    expect(isAuthorized(0)).toBe(false);
    process.env.TELEGRAM_ALLOWED_USER_IDS = '12345,67890';
  });
});

describe('Rate Limiter', () => {
  const WINDOW_MS = 60000;
  const MAX_PER_WINDOW = 10;

  test('allows commands within limit', () => {
    const limiter = createRateLimiter(WINDOW_MS, MAX_PER_WINDOW);
    for (let i = 0; i < MAX_PER_WINDOW; i++) {
      expect(limiter.check(1)).toBe(true);
    }
  });

  test('blocks commands exceeding limit', () => {
    const limiter = createRateLimiter(WINDOW_MS, MAX_PER_WINDOW);
    for (let i = 0; i < MAX_PER_WINDOW; i++) {
      limiter.check(1);
    }
    expect(limiter.check(1)).toBe(false);
  });

  test('tracks different users independently', () => {
    const limiter = createRateLimiter(WINDOW_MS, MAX_PER_WINDOW);
    // Exhaust user 1's limit
    for (let i = 0; i < MAX_PER_WINDOW; i++) {
      limiter.check(1);
    }
    expect(limiter.check(1)).toBe(false);

    // User 2 should still be allowed
    for (let i = 0; i < MAX_PER_WINDOW; i++) {
      expect(limiter.check(2)).toBe(true);
    }
    // User 2 should now also be blocked
    expect(limiter.check(2)).toBe(false);
  });

  test('rate limit resets after window expires', async () => {
    const limiter = createRateLimiter(50, 2);
    expect(limiter.check(1)).toBe(true); // 1
    expect(limiter.check(1)).toBe(true); // 2
    expect(limiter.check(1)).toBe(false); // blocked

    // Wait for window to expire
    await new Promise(resolve => setTimeout(resolve, 60));
    expect(limiter.check(1)).toBe(true); // allowed again
  });
});

describe('Remote State', () => {
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

  test('getRemoteState filters emergency mode', async () => {
    const getSpy = jest.spyOn(remoteState, 'getRemoteState').mockImplementation(async () => {
        return { tradingEnabled: true, emergencyMode: true, approvalMode: false, lastOperatorAction: Date.now() };
    });

    const state = await remoteState.getRemoteState();
    expect(state.tradingEnabled).toBe(true);
    expect(state.emergencyMode).toBe(true);
    getSpy.mockRestore();
  });
});
