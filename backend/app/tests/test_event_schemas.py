import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.events import (
    EventEnvelope,
    MarketDataPayload,
    WalletTradePayload,
    SignalGeneratedPayload,
    TradeRequestPayload,
    ShadowPositionOpenedPayload,
    ShadowPositionClosedPayload,
    SolanaTradeDetectedPayload,
    EVENT_PAYLOAD_MAP,
)

# Helper: generate IDs of exact required length
EVT = "evt_" + "a" * 21          # 25 chars total
CORR = "corr_" + "b" * 20        # 25 chars total
SIG = "sig_" + "c" * 21          # 25 chars total
REQ = "req_" + "d" * 21          # 25 chars total
POS = "pos_" + "e" * 21          # 25 chars total
TS = "2026-06-11T10:00:00+00:00"  # 25 chars
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
WALLET = B58[:44]        # 44 chars, all valid base58
MINT = B58[5:49]         # 44 chars, all valid base58
TX = B58 + B58[:6]       # 64 chars (valid base58, min allowed)


class TestEventEnvelope:
    def test_valid_envelope(self):
        env = EventEnvelope(
            event_id=EVT,
            event_type="swap.detected",
            source="helius_ingester",
            timestamp=TS,
            correlation_id=CORR,
            data={"key": "value"},
        )
        assert env.event_id.startswith("evt_")
        assert env.correlation_id.startswith("corr_")

    def test_missing_event_id(self):
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_type="swap.detected",
                source="test",
                timestamp=TS,
                correlation_id=CORR,
                data={},
            )

    def test_invalid_event_id_prefix(self):
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_id="xxx_" + "a" * 21,
                event_type="swap.detected",
                source="test",
                timestamp=TS,
                correlation_id=CORR,
                data={},
            )

    def test_invalid_correlation_prefix(self):
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_id=EVT,
                event_type="swap.detected",
                source="test",
                timestamp=TS,
                correlation_id="bad_" + "b" * 21,
                data={},
            )

    def test_invalid_timestamp_format(self):
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_id=EVT,
                event_type="swap.detected",
                source="test",
                timestamp="not-a-timestamp",
                correlation_id=CORR,
                data={},
            )

    def test_timestamp_naive_rejected(self):
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_id=EVT,
                event_type="swap.detected",
                source="test",
                timestamp="2026-06-11T10:00:00",
                correlation_id=CORR,
                data={},
            )

    def test_event_type_too_short(self):
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_id=EVT,
                event_type="ab",
                source="test",
                timestamp=TS,
                correlation_id=CORR,
                data={},
            )


class TestMarketDataPayload:
    def test_valid_payload(self):
        payload = MarketDataPayload(
            wallet_address=WALLET,
            mint_address=MINT,
            token_symbol="SOL",
            side="buy",
            size_usd=5000.00,
            price_usd=142.50,
            tx_signature=TX,
            source_dex="Raydium",
            slot=284195632,
        )
        assert payload.side == "buy"
        assert payload.size_usd == 5000.00

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            MarketDataPayload(
                mint_address=MINT,
                side="buy",
                size_usd=100.0,
                price_usd=50.0,
                tx_signature=TX,
            )

    def test_invalid_side(self):
        with pytest.raises(ValidationError):
            MarketDataPayload(
                wallet_address=WALLET,
                mint_address=MINT,
                side="hold",
                size_usd=100.0,
                price_usd=50.0,
                tx_signature=TX,
            )

    def test_invalid_base58(self):
        with pytest.raises(ValidationError):
            MarketDataPayload(
                wallet_address="000000000000000000000000000000000000000000",
                mint_address=MINT,
                side="buy",
                size_usd=100.0,
                price_usd=50.0,
                tx_signature=TX,
            )

    def test_size_gt_0(self):
        with pytest.raises(ValidationError):
            MarketDataPayload(
                wallet_address=WALLET,
                mint_address=MINT,
                side="buy",
                size_usd=0,
                price_usd=50.0,
                tx_signature=TX,
            )

    def test_wallet_too_short(self):
        with pytest.raises(ValidationError):
            MarketDataPayload(
                wallet_address="abc",
                mint_address=MINT,
                side="buy",
                size_usd=100.0,
                price_usd=50.0,
                tx_signature=TX,
            )

    def test_sell_side_valid(self):
        payload = MarketDataPayload(
            wallet_address=WALLET,
            mint_address=MINT,
            side="sell",
            size_usd=2500.00,
            price_usd=155.00,
            tx_signature=TX,
        )
        assert payload.side == "sell"

    def test_optional_fields_default(self):
        payload = MarketDataPayload(
            wallet_address=WALLET,
            mint_address=MINT,
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            tx_signature=TX,
        )
        assert payload.token_symbol is None
        assert payload.source_dex is None
        assert payload.slot is None

    def test_price_gt_0(self):
        with pytest.raises(ValidationError):
            MarketDataPayload(
                wallet_address=WALLET,
                mint_address=MINT,
                side="buy",
                size_usd=100.0,
                price_usd=-1.0,
                tx_signature=TX,
            )


class TestWalletTradePayload:
    def test_valid_payload(self):
        payload = WalletTradePayload(
            wallet_address=WALLET,
            mint_address=MINT,
            side="buy",
            size_usd=5000.00,
            price_usd=142.50,
            tx_signature=TX,
            research_score=0.75,
            total_trades_observed=42,
            win_rate_observed=0.61,
        )
        assert payload.research_score == 0.75
        assert payload.total_trades_observed == 42
        assert payload.win_rate_observed == 0.61

    def test_research_score_out_of_range(self):
        with pytest.raises(ValidationError):
            WalletTradePayload(
                wallet_address=WALLET,
                mint_address=MINT,
                side="buy",
                size_usd=100.0,
                price_usd=50.0,
                tx_signature=TX,
                research_score=1.5,
                total_trades_observed=10,
                win_rate_observed=0.5,
            )

    def test_win_rate_out_of_range(self):
        with pytest.raises(ValidationError):
            WalletTradePayload(
                wallet_address=WALLET,
                mint_address=MINT,
                side="buy",
                size_usd=100.0,
                price_usd=50.0,
                tx_signature=TX,
                research_score=0.5,
                total_trades_observed=10,
                win_rate_observed=-0.1,
            )

    def test_total_trades_negative(self):
        with pytest.raises(ValidationError):
            WalletTradePayload(
                wallet_address=WALLET,
                mint_address=MINT,
                side="buy",
                size_usd=100.0,
                price_usd=50.0,
                tx_signature=TX,
                research_score=0.5,
                total_trades_observed=-1,
                win_rate_observed=0.5,
            )


class TestSignalGeneratedPayload:
    def test_valid_payload(self):
        payload = SignalGeneratedPayload(
            signal_id=SIG,
            mint_address=MINT,
            token_symbol="SOL",
            direction="long",
            confidence=0.65,
            trigger="coordinated_buy_3_wallets",
            wallet_addresses=[WALLET],
            detected_price_usd=142.50,
            signal_timestamp=TS,
            strategy="smart_wallet_follow",
        )
        assert payload.direction == "long"
        assert payload.trigger == "coordinated_buy_3_wallets"

    def test_direction_only_long(self):
        with pytest.raises(ValidationError):
            SignalGeneratedPayload(
                signal_id=SIG,
                mint_address=MINT,
                direction="short",
                confidence=0.65,
                trigger="high_score_entry",
                wallet_addresses=[WALLET],
                detected_price_usd=142.50,
                signal_timestamp=TS,
                strategy="smart_wallet_follow",
            )

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            SignalGeneratedPayload(
                signal_id=SIG,
                mint_address=MINT,
                direction="long",
                confidence=1.5,
                trigger="early_entry_trending",
                wallet_addresses=[WALLET],
                detected_price_usd=142.50,
                signal_timestamp=TS,
                strategy="smart_wallet_follow",
            )

    def test_invalid_trigger(self):
        with pytest.raises(ValidationError):
            SignalGeneratedPayload(
                signal_id=SIG,
                mint_address=MINT,
                direction="long",
                confidence=0.5,
                trigger="unknown_trigger",
                wallet_addresses=[WALLET],
                detected_price_usd=142.50,
                signal_timestamp=TS,
                strategy="smart_wallet_follow",
            )

    def test_wallet_list_empty(self):
        with pytest.raises(ValidationError):
            SignalGeneratedPayload(
                signal_id=SIG,
                mint_address=MINT,
                direction="long",
                confidence=0.5,
                trigger="high_score_entry",
                wallet_addresses=[],
                detected_price_usd=142.50,
                signal_timestamp=TS,
                strategy="smart_wallet_follow",
            )


class TestTradeRequestPayload:
    def test_valid_payload(self):
        payload = TradeRequestPayload(
            request_id=REQ,
            signal_id=SIG,
            mint_address=MINT,
            direction="long",
            size_usd=100.00,
            entry_price_usd=142.50,
            stop_loss_usd=121.12,
            take_profit_usd=178.12,
            max_hold_hours=72,
            strategy="smart_wallet_follow",
        )
        assert payload.is_shadow is True
        assert payload.simulated_slippage == 0.01
        assert payload.simulated_fee == 0.005

    def test_invalid_request_id_prefix(self):
        with pytest.raises(ValidationError):
            TradeRequestPayload(
                request_id="bad_" + "d" * 21,
                signal_id=SIG,
                mint_address=MINT,
                direction="long",
                size_usd=100.0,
                entry_price_usd=50.0,
                stop_loss_usd=40.0,
                take_profit_usd=70.0,
                max_hold_hours=72,
                strategy="test",
            )

    def test_max_hold_too_high(self):
        with pytest.raises(ValidationError):
            TradeRequestPayload(
                request_id=REQ,
                signal_id=SIG,
                mint_address=MINT,
                direction="long",
                size_usd=100.0,
                entry_price_usd=50.0,
                stop_loss_usd=40.0,
                take_profit_usd=70.0,
                max_hold_hours=9999,
                strategy="test",
            )

    def test_size_gt_0(self):
        with pytest.raises(ValidationError):
            TradeRequestPayload(
                request_id=REQ,
                signal_id=SIG,
                mint_address=MINT,
                direction="long",
                size_usd=0,
                entry_price_usd=50.0,
                stop_loss_usd=40.0,
                take_profit_usd=70.0,
                max_hold_hours=72,
                strategy="test",
            )


class TestShadowPositionOpenedPayload:
    def test_valid_payload(self):
        payload = ShadowPositionOpenedPayload(
            position_id=POS,
            request_id=REQ,
            mint_address=MINT,
            token_symbol="SOL",
            direction="long",
            entry_price_usd=142.50,
            size_usd=100.00,
            gross_entry_cost=100.00,
            simulated_slippage_cost=1.00,
            simulated_fee_cost=0.50,
            net_entry_cost=101.50,
            stop_loss_usd=121.12,
            take_profit_usd=178.12,
            entry_timestamp=TS,
        )
        assert payload.status == "open"
        assert payload.max_hold_hours == 72

    def test_status_must_be_open(self):
        with pytest.raises(ValidationError):
            ShadowPositionOpenedPayload(
                position_id=POS,
                request_id=REQ,
                mint_address=MINT,
                direction="long",
                entry_price_usd=100.0,
                size_usd=100.0,
                gross_entry_cost=100.0,
                simulated_slippage_cost=1.0,
                simulated_fee_cost=0.5,
                net_entry_cost=101.5,
                entry_timestamp=TS,
                status="closed",
            )

    def test_max_hold_default(self):
        payload = ShadowPositionOpenedPayload(
            position_id=POS,
            request_id=REQ,
            mint_address=MINT,
            direction="long",
            entry_price_usd=100.0,
            size_usd=100.0,
            gross_entry_cost=100.0,
            simulated_slippage_cost=1.0,
            simulated_fee_cost=0.5,
            net_entry_cost=101.5,
            entry_timestamp=TS,
        )
        assert payload.max_hold_hours == 72

    def test_net_entry_cost_gt_0(self):
        with pytest.raises(ValidationError):
            ShadowPositionOpenedPayload(
                position_id=POS,
                request_id=REQ,
                mint_address=MINT,
                direction="long",
                entry_price_usd=100.0,
                size_usd=100.0,
                gross_entry_cost=100.0,
                simulated_slippage_cost=1.0,
                simulated_fee_cost=0.5,
                net_entry_cost=0,
                entry_timestamp=TS,
            )


class TestShadowPositionClosedPayload:
    def test_valid_payload(self):
        payload = ShadowPositionClosedPayload(
            position_id=POS,
            mint_address=MINT,
            token_symbol="SOL",
            direction="long",
            entry_price_usd=142.50,
            exit_price_usd=178.12,
            size_usd=100.00,
            gross_pnl_usd=25.00,
            simulated_slippage=0.01,
            simulated_fee=0.005,
            net_pnl_usd=23.50,
            exit_reason="take_profit",
            entry_timestamp=TS,
            exit_timestamp=TS,
            hold_hours=48.0,
            strategy="smart_wallet_follow",
        )
        assert payload.status == "closed"
        assert payload.exit_reason == "take_profit"

    def test_status_must_be_closed(self):
        with pytest.raises(ValidationError):
            ShadowPositionClosedPayload(
                position_id=POS,
                mint_address=MINT,
                direction="long",
                entry_price_usd=100.0,
                exit_price_usd=120.0,
                size_usd=100.0,
                gross_pnl_usd=20.0,
                net_pnl_usd=18.5,
                exit_reason="take_profit",
                entry_timestamp=TS,
                exit_timestamp=TS,
                hold_hours=48.0,
                status="open",
            )

    def test_invalid_exit_reason(self):
        with pytest.raises(ValidationError):
            ShadowPositionClosedPayload(
                position_id=POS,
                mint_address=MINT,
                direction="long",
                entry_price_usd=100.0,
                exit_price_usd=120.0,
                size_usd=100.0,
                gross_pnl_usd=20.0,
                net_pnl_usd=18.5,
                exit_reason="manual",
                entry_timestamp=TS,
                exit_timestamp=TS,
                hold_hours=48.0,
            )

    def test_hold_hours_gt_0(self):
        with pytest.raises(ValidationError):
            ShadowPositionClosedPayload(
                position_id=POS,
                mint_address=MINT,
                direction="long",
                entry_price_usd=100.0,
                exit_price_usd=120.0,
                size_usd=100.0,
                gross_pnl_usd=20.0,
                net_pnl_usd=18.5,
                exit_reason="stop_loss",
                entry_timestamp=TS,
                exit_timestamp=TS,
                hold_hours=0,
            )

    def test_expired_reason_valid(self):
        payload = ShadowPositionClosedPayload(
            position_id=POS,
            mint_address=MINT,
            direction="long",
            entry_price_usd=100.0,
            exit_price_usd=90.0,
            size_usd=100.0,
            gross_pnl_usd=-10.0,
            net_pnl_usd=-11.5,
            exit_reason="expired",
            entry_timestamp=TS,
            exit_timestamp=TS,
            hold_hours=72.0,
        )
        assert payload.exit_reason == "expired"


class TestEventPayloadMap:
    def test_all_mappings_exist(self):
        expected = {
            "market:data",
            "wallet:trade",
            "signal:generated",
            "trade:request",
            "shadow:position.opened",
            "shadow:position.closed",
            "solana:trade:detected",
        }
        assert set(EVENT_PAYLOAD_MAP.keys()) == expected

    def test_each_mapping_is_valid_model(self):
        for event_type, model in EVENT_PAYLOAD_MAP.items():
            assert issubclass(model, BaseModel), f"{event_type} is not a BaseModel"

    def test_market_data_mapped_correctly(self):
        assert EVENT_PAYLOAD_MAP["market:data"] == MarketDataPayload

    def test_wallet_trade_mapped_correctly(self):
        assert EVENT_PAYLOAD_MAP["wallet:trade"] == WalletTradePayload

    def test_signal_generated_mapped_correctly(self):
        assert EVENT_PAYLOAD_MAP["signal:generated"] == SignalGeneratedPayload

    def test_trade_request_mapped_correctly(self):
        assert EVENT_PAYLOAD_MAP["trade:request"] == TradeRequestPayload

    def test_shadow_position_opened_mapped_correctly(self):
        assert EVENT_PAYLOAD_MAP["shadow:position.opened"] == ShadowPositionOpenedPayload

    def test_shadow_position_closed_mapped_correctly(self):
        assert EVENT_PAYLOAD_MAP["shadow:position.closed"] == ShadowPositionClosedPayload

    def test_solana_trade_detected_mapped_correctly(self):
        assert EVENT_PAYLOAD_MAP["solana:trade:detected"] == SolanaTradeDetectedPayload
