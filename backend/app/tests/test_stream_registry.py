from app.core.stream_registry import StreamRegistry, StreamConfig


class TestStreamConfig:
    def test_frozen_dataclass(self):
        config = StreamConfig(
            name="test:stream",
            maxlen=1000,
            trim_mode="approximate",
            consumer_groups=("group1",),
            description="test",
            phase="1",
        )
        assert config.name == "test:stream"
        assert config.maxlen == 1000
        assert config.trim_mode == "approximate"
        assert config.consumer_groups == ("group1",)
        assert config.phase == "1"


class TestStreamRegistry:
    @classmethod
    def teardown_class(cls):
        StreamRegistry._streams = {s.name: s for s in [
            StreamConfig(name="market:data", maxlen=100000, trim_mode="approximate",
                         consumer_groups=("helius_ingester", "smart_wallet_agent", "research_trade_worker", "monitoring"),
                         description="Raw swap events from Helius, enriched prices from Birdeye", phase="1"),
            StreamConfig(name="wallet:trade", maxlen=100000, trim_mode="approximate",
                         consumer_groups=("smart_wallet_agent", "research_trade_worker", "monitoring"),
                         description="Normalized wallet trade events with research score", phase="1"),
            StreamConfig(name="signal:generated", maxlen=50000, trim_mode="approximate",
                         consumer_groups=("shadow_portfolio_service", "monitoring"),
                         description="Trading signals from SmartWalletAgent", phase="1"),
            StreamConfig(name="trade:request", maxlen=50000, trim_mode="approximate",
                         consumer_groups=("monitoring",),
                         description="Shadow trade requests", phase="1"),
            StreamConfig(name="shadow:position", maxlen=50000, trim_mode="approximate",
                         consumer_groups=("monitoring",),
                         description="Shadow position lifecycle events", phase="1"),
            StreamConfig(name="agent:event", maxlen=50000, trim_mode="approximate",
                         consumer_groups=("monitoring_agent", "whale_agent", "signal_agent", "risk_agent", "execution_agent"),
                         description="Agent lifecycle and health events", phase="1"),
            StreamConfig(name="system:alert", maxlen=10000, trim_mode="approximate",
                         consumer_groups=("monitoring", "notification"),
                         description="System alerts", phase="1"),
            StreamConfig(name="trade:execution", maxlen=50000, trim_mode="approximate",
                         consumer_groups=("monitoring",),
                         description="Live trade execution events — DEFERRED TO PHASE 2", phase="2"),
        ]}

    def test_register_and_get(self):
        # Use a unique name to avoid collision with module-level registrations
        config = StreamConfig(
            name="test:register",
            maxlen=100,
            trim_mode="exact",
            consumer_groups=("g1", "g2"),
            description="test register",
        )
        StreamRegistry.register(config)
        assert StreamRegistry.get("test:register") is config
        # Clean up
        StreamRegistry._streams.pop("test:register", None)

    def test_get_missing(self):
        assert StreamRegistry.get("nonexistent") is None

    def test_all_returns_copy(self):
        all_streams = StreamRegistry.all()
        assert len(all_streams) >= 7
        # Verify it's a copy
        saved = dict(StreamRegistry._streams)
        orig_len = len(all_streams)
        all_streams["fake"] = StreamConfig(name="fake", maxlen=0, trim_mode="exact", consumer_groups=(), description="f")
        assert len(StreamRegistry.all()) == orig_len

    def test_validate_group_passes(self):
        assert StreamRegistry.validate_group("market:data", "monitoring") is True

    def test_validate_group_fails(self):
        assert StreamRegistry.validate_group("market:data", "invalid_group") is False

    def test_validate_group_for_missing_stream(self):
        assert StreamRegistry.validate_group("nonexistent", "any_group") is False

    def test_active_in_phase1(self):
        active = StreamRegistry.active_in_phase1()
        for config in active:
            assert config.phase == "1"
        all_phase1 = [c for c in StreamRegistry.all().values() if c.phase == "1"]
        assert len(active) == len(all_phase1)

    def test_phase2_not_in_active(self):
        trade_exec = StreamRegistry.get("trade:execution")
        assert trade_exec is not None
        assert trade_exec.phase == "2"
        active_names = [c.name for c in StreamRegistry.active_in_phase1()]
        assert "trade:execution" not in active_names

    def test_stream_names(self):
        names = StreamRegistry.stream_names()
        assert "market:data" in names
        assert "shadow:position" in names

    def test_phase1_stream_names(self):
        names = StreamRegistry.phase1_stream_names()
        assert "market:data" in names
        assert "trade:execution" not in names


class TestStreamDefinitions:
    def test_market_data_stream(self):
        config = StreamRegistry.get("market:data")
        assert config is not None
        assert config.maxlen == 100_000
        assert config.trim_mode == "approximate"
        assert "helius_ingester" in config.consumer_groups
        assert config.phase == "1"

    def test_wallet_trade_stream(self):
        config = StreamRegistry.get("wallet:trade")
        assert config is not None
        assert config.maxlen == 100_000
        assert "smart_wallet_agent" in config.consumer_groups
        assert config.phase == "1"

    def test_signal_generated_stream(self):
        config = StreamRegistry.get("signal:generated")
        assert config is not None
        assert config.maxlen == 50_000
        assert "shadow_portfolio_service" in config.consumer_groups
        assert config.phase == "1"

    def test_trade_request_stream(self):
        config = StreamRegistry.get("trade:request")
        assert config is not None
        assert config.maxlen == 50_000
        assert config.phase == "1"

    def test_shadow_position_stream(self):
        config = StreamRegistry.get("shadow:position")
        assert config is not None
        assert config.maxlen == 50_000
        assert config.trim_mode == "approximate"
        assert "monitoring" in config.consumer_groups
        assert config.phase == "1"

    def test_agent_event_stream(self):
        config = StreamRegistry.get("agent:event")
        assert config is not None
        assert config.maxlen == 50_000
        assert "monitoring_agent" in config.consumer_groups
        assert config.phase == "1"

    def test_system_alert_stream(self):
        config = StreamRegistry.get("system:alert")
        assert config is not None
        assert config.maxlen == 10_000
        assert config.phase == "1"

    def test_trade_execution_is_phase2(self):
        config = StreamRegistry.get("trade:execution")
        assert config is not None
        assert config.phase == "2"

    def test_all_phase1_streams_have_consumer_groups(self):
        for config in StreamRegistry.active_in_phase1():
            assert len(config.consumer_groups) > 0, f"Stream {config.name} has no consumer groups"

    def test_all_phase1_streams_positive_maxlen(self):
        for config in StreamRegistry.active_in_phase1():
            assert config.maxlen > 0, f"Stream {config.name} has maxlen <= 0"

    def test_no_whale_activity_stream(self):
        config = StreamRegistry.get("whale:activity")
        assert config is None

    def test_shadow_position_not_in_pubsub(self):
        from app.core.events import EventBus
        assert "shadow:position" not in EventBus.PUBSUB_CHANNELS

    def test_market_data_consumer_groups(self):
        config = StreamRegistry.get("market:data")
        expected = {"helius_ingester", "smart_wallet_agent", "research_trade_worker", "monitoring"}
        assert set(config.consumer_groups) == expected

    def test_all_streams_count(self):
        all_streams = StreamRegistry.all()
        assert len(all_streams) >= 8

    def test_phase1_count(self):
        active = StreamRegistry.active_in_phase1()
        assert len(active) >= 6

    def test_shadow_position_consumer_group(self):
        config = StreamRegistry.get("shadow:position")
        assert "monitoring" in config.consumer_groups
        assert len(config.consumer_groups) == 1
