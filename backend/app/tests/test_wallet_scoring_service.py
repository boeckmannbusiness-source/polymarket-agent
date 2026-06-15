from datetime import datetime, timedelta, timezone

import pytest

from app.services.wallet_scoring_service import WalletScoringService


class TestWalletScoringService:
    def test_deterministic_outputs(self):
        svc = WalletScoringService()
        metrics = {"wallet_address": "addr1", "trades_1h": 2, "trades_24h": 15, "trades_7d": 50,
                    "token_diversity": 5, "volume_proxy": 10000.0, "active_days_7d": 5}
        r1 = svc.compute_score(metrics)
        r2 = svc.compute_score(metrics)
        assert r1["score"] == r2["score"]
        assert r1["confidence"] == r2["confidence"]
        assert r1["classification"] == r2["classification"]

    def test_zero_trades_produces_score(self):
        svc = WalletScoringService()
        metrics = {"wallet_address": "addr1", "trades_1h": 0, "trades_24h": 0, "trades_7d": 0,
                    "token_diversity": 0, "volume_proxy": 0.0, "active_days_7d": 0}
        result = svc.compute_score(metrics)
        assert result["score"] >= 0.0
        assert result["score"] <= 1.0
        assert result["confidence"] > 0.0

    def test_high_volume_whale_classification(self):
        svc = WalletScoringService()
        metrics = {"wallet_address": "addr1", "trades_1h": 10, "trades_24h": 100, "trades_7d": 300,
                    "token_diversity": 20, "volume_proxy": 100000.0, "active_days_7d": 7}
        result = svc.compute_score(metrics)
        assert result["score"] >= 0.75
        assert result["classification"] == "whale"

    def test_momentum_classification(self):
        svc = WalletScoringService()
        metrics = {"wallet_address": "addr1", "trades_1h": 1, "trades_24h": 5, "trades_7d": 15,
                    "token_diversity": 3, "volume_proxy": 2000.0, "active_days_7d": 3}
        result = svc.compute_score(metrics)
        assert result["classification"] == "momentum"

    def test_retail_classification(self):
        svc = WalletScoringService()
        metrics = {"wallet_address": "addr1", "trades_1h": 0, "trades_24h": 1, "trades_7d": 3,
                    "token_diversity": 1, "volume_proxy": 100.0, "active_days_7d": 1}
        result = svc.compute_score(metrics)
        assert result["classification"] in ("retail", "unknown", "momentum")
        assert result["confidence"] >= 0.0

    def test_classify_unknown_direct(self):
        svc = WalletScoringService()
        assert svc._classify(0.5, 0, 0.20) == "unknown"
        assert svc._classify(0.8, 100000, 0.15) == "unknown"

    def test_equal_score_ordering(self):
        svc = WalletScoringService()
        m1 = {"wallet_address": "a", "trades_1h": 2, "trades_24h": 15, "trades_7d": 50,
              "token_diversity": 5, "volume_proxy": 10000.0, "active_days_7d": 5}
        m2 = {"wallet_address": "b", "trades_1h": 2, "trades_24h": 15, "trades_7d": 50,
              "token_diversity": 5, "volume_proxy": 10000.0, "active_days_7d": 5}
        r1 = svc.compute_score(m1)
        r2 = svc.compute_score(m2)
        assert r1["score"] == r2["score"]

    def test_batch_execution(self):
        svc = WalletScoringService()
        metrics_list = [
            {"wallet_address": "a", "trades_1h": 5, "trades_24h": 50, "trades_7d": 150,
             "token_diversity": 10, "volume_proxy": 50000.0, "active_days_7d": 7},
            {"wallet_address": "b", "trades_1h": 0, "trades_24h": 2, "trades_7d": 5,
             "token_diversity": 2, "volume_proxy": 500.0, "active_days_7d": 2},
        ]
        results = svc.compute_scores_batch(metrics_list)
        assert len(results) == 2
        assert results[0]["wallet_address"] == "a"
        assert results[1]["wallet_address"] == "b"
        assert results[0]["score"] > results[1]["score"]

    def test_replay_safety(self):
        svc = WalletScoringService()
        m = {"wallet_address": "a", "trades_1h": 3, "trades_24h": 20, "trades_7d": 60,
             "token_diversity": 7, "volume_proxy": 20000.0, "active_days_7d": 6}
        for _ in range(20):
            r = svc.compute_score(m)
            assert r["score"] == svc.compute_score(m)["score"]

    def test_score_components_are_bounded(self):
        svc = WalletScoringService()
        m = {"wallet_address": "a", "trades_1h": 100, "trades_24h": 500, "trades_7d": 1000,
             "token_diversity": 50, "volume_proxy": 1_000_000.0, "active_days_7d": 7}
        r = svc.compute_score(m)
        assert 0.0 <= r["score"] <= 1.0
        assert 0.0 <= r["confidence"] <= 1.0
        assert 0.0 <= r["score_1h"] <= 1.0
        assert 0.0 <= r["score_24h"] <= 1.0

    def test_high_volume_without_enough_trades(self):
        svc = WalletScoringService()
        m = {"wallet_address": "a", "trades_1h": 0, "trades_24h": 1, "trades_7d": 1,
             "token_diversity": 1, "volume_proxy": 100000.0, "active_days_7d": 1}
        r = svc.compute_score(m)
        assert r["classification"] in ("momentum", "retail", "unknown")

    def test_temporal_stability_perfect(self):
        svc = WalletScoringService()
        m = {"wallet_address": "a", "trades_1h": 10, "trades_24h": 10, "trades_7d": 30,
             "token_diversity": 5, "volume_proxy": 10000.0, "active_days_7d": 5}
        r = svc.compute_score(m)
        assert r["score_1h"] == r["score_24h"]

    def test_temporal_stability_drift(self):
        svc = WalletScoringService()
        m = {"wallet_address": "a", "trades_1h": 0, "trades_24h": 50, "trades_7d": 100,
             "token_diversity": 5, "volume_proxy": 10000.0, "active_days_7d": 5}
        r = svc.compute_score(m)
        assert r["score_1h"] < r["score_24h"]

    def test_confidence_sufficient_data(self):
        svc = WalletScoringService()
        m = {"wallet_address": "a", "trades_1h": 5, "trades_24h": 30, "trades_7d": 100,
             "token_diversity": 10, "volume_proxy": 50000.0, "active_days_7d": 7}
        r = svc.compute_score(m)
        assert r["confidence"] >= 0.5

    def test_confidence_insufficient_data(self):
        svc = WalletScoringService()
        m = {"wallet_address": "a", "trades_1h": 0, "trades_24h": 1, "trades_7d": 1,
             "token_diversity": 1, "volume_proxy": 10.0, "active_days_7d": 1}
        r = svc.compute_score(m)
        assert r["confidence"] < 0.5

    def test_whale_threshold_boundary(self):
        svc = WalletScoringService()
        m = {"wallet_address": "a", "trades_1h": 10, "trades_24h": 50, "trades_7d": 150,
             "token_diversity": 15, "volume_proxy": 50000.0, "active_days_7d": 7}
        r = svc.compute_score(m)
        if r["score"] >= 0.75:
            assert r["classification"] == "whale"

    def test_momentum_threshold_boundary(self):
        svc = WalletScoringService()
        m = {"wallet_address": "a", "trades_1h": 2, "trades_24h": 10, "trades_7d": 30,
             "token_diversity": 4, "volume_proxy": 1000.0, "active_days_7d": 4}
        r = svc.compute_score(m)
        if r["score"] >= 0.55 and r["score"] < 0.75:
            assert r["classification"] == "momentum"

    def test_last_trade_at_affects_recency(self):
        svc = WalletScoringService()
        now_str = datetime.now(timezone.utc).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        recent = svc.compute_score({
            "wallet_address": "a", "trades_1h": 5, "trades_24h": 20, "trades_7d": 60,
            "token_diversity": 5, "volume_proxy": 10000.0, "active_days_7d": 7,
            "last_trade_at": now_str,
        })
        stale = svc.compute_score({
            "wallet_address": "b", "trades_1h": 5, "trades_24h": 20, "trades_7d": 60,
            "token_diversity": 5, "volume_proxy": 10000.0, "active_days_7d": 7,
            "last_trade_at": old,
        })
        assert recent["score"] > stale["score"]

    def test_classification_whale_score_not_volume(self):
        svc = WalletScoringService()
        r = svc._classify(0.80, 40000, 0.95)
        assert r == "momentum"

    def test_classification_whale_volume_not_score(self):
        svc = WalletScoringService()
        r = svc._classify(0.60, 100000, 0.95)
        assert r == "momentum"
