import time

from app.domain.replay.replay_seed import ReplaySeed
from app.services.replay.execution_fingerprint import ExecutionFingerprint


class DeterminismController:
    def __init__(self, seed: int | None = None):
        self._seed = seed or int(time.time() * 1000) % 1000000
        self._used_seeds: set[int] = set()

    @property
    def current_seed(self) -> int:
        return self._seed

    def get_seed(self) -> ReplaySeed:
        bucket = ExecutionFingerprint.generate_bucket(minutes=1)
        return ReplaySeed(seed=self._seed, timestamp_bucket=bucket)

    def advance_seed(self) -> int:
        self._used_seeds.add(self._seed)
        self._seed = (self._seed * 1103515245 + 12345) & 0x7FFFFFFF
        return self._seed

    def reset_seed(self, seed: int) -> None:
        self._seed = seed

    def has_seed_been_used(self, seed: int) -> bool:
        return seed in self._used_seeds
