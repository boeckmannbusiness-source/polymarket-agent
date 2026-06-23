import pytest
from decimal import Decimal
import uuid
from sqlalchemy import create_engine, Column, String, JSON, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import sessionmaker, declarative_base
from app.domain.solana.models import TransactionEnvelope, SimulationReceipt, TransactionPayload
from app.domain.replay.execution_trace import ExecutionTrace
from app.domain.replay.replay_seed import ReplaySeed
from app.domain.replay.execution_snapshot import ExecutionAuthorizationSnapshot
from app.domain.execution.execution_intent import ExecutionIntent
from app.domain.execution.instrument import Instrument
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints

Base = declarative_base()

class PersistenceTestModel(Base):
    __tablename__ = "persistence_validation"
    id = Column(String, primary_key=True)
    data = Column(JSON)

# Real-ish model to verify Decimal precision
class TradeValidation(Base):
    __tablename__ = "trade_validation"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price = Column(Numeric(24, 8))
    size = Column(Numeric(24, 8))
    fee = Column(Numeric(24, 8))

@pytest.fixture
def db_session():
    # Using a local postgres if available
    try:
        engine = create_engine("postgresql://postgres:postgres@localhost:5432/postgres")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        Base.metadata.drop_all(engine)
    except Exception:
        pytest.skip("Real PostgreSQL instance not available")

def test_decimal_precision_in_postgres(db_session):
    test_price = Decimal("123.45678901")
    test_size = Decimal("1.12345678")
    test_fee = Decimal("0.00000001")

    trade = TradeValidation(price=test_price, size=test_size, fee=test_fee)
    db_session.add(trade)
    db_session.commit()

    retrieved = db_session.query(TradeValidation).filter_by(id=trade.id).one()
    assert retrieved.price == test_price
    assert retrieved.size == test_size
    assert retrieved.fee == test_fee

def test_complex_model_persistence(db_session):
    # 1. Prepare complex models
    instrument = Instrument(venue="jupiter", symbol="SOL", asset_identifier="SOL", quote_asset="USDC")
    intent = ExecutionIntent(instrument=instrument, side="buy", quantity=Decimal("1.0"), order_type="market")

    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("100"),
        expected_amount_out=Decimal("1"),
        estimated_price=Decimal("100"),
        slippage_bps=50,
        source="jupiter"
    )

    route = Route(venue="jupiter", hops=["USDC", "SOL"])
    constraints = ExecutionConstraints(max_slippage_bps=50)

    plan = TransactionPlan(
        quote=quote,
        route=route,
        constraints=constraints,
        instructions=[],
        serialized_payload_b64="base64payload"
    )

    payload = TransactionPayload(serialized_payload_b64=plan.serialized_payload_b64)
    envelope = TransactionEnvelope(
        instructions=[],
        payload=payload,
        slippage_bps=50,
        fee_estimate=5000
    )

    receipt = SimulationReceipt(
        success=True,
        compute_units=150000,
        estimated_fee=5000,
        logs=["log1", "log2"],
        slot=12345678,
        blockhash="hash123"
    )

    seed = ReplaySeed(seed=12345, timestamp_bucket="2023-01-01T00:00:00")

    auth_snapshot = ExecutionAuthorizationSnapshot(
        mode="SANDBOX",
        granted=True,
        reason="Test",
        permissions=["RPC_SIMULATE"]
    )

    trace = ExecutionTrace(
        execution_id=str(uuid.uuid4()),
        intent=intent,
        plan=plan,
        seed=seed,
        instruction_trace_snapshot=["ix1"],
        fill_prices=[Decimal("100.5")],
        fill_sizes=[Decimal("1.0")],
        fill_fees=[Decimal("0.005")],
        total_fees=Decimal("0.005"),
        average_price=Decimal("100.5"),
        quantity_executed=Decimal("1.0"),
        latency_ms=150.0,
        authorization=auth_snapshot
    )

    # 2. Persist
    test_id = str(uuid.uuid4())
    record = PersistenceTestModel(
        id=test_id,
        data={
            "envelope": envelope.model_dump(),
            "receipt": receipt.model_dump(),
            "trace": trace.model_dump(mode='json'),
            "auth": auth_snapshot.model_dump()
        }
    )
    db_session.add(record)
    db_session.commit()

    # 3. Retrieve and verify
    retrieved = db_session.query(PersistenceTestModel).filter_by(id=test_id).one()
    data = retrieved.data

    assert data["envelope"]["payload"]["serialized_payload_b64"] == "base64payload"
    assert data["receipt"]["compute_units"] == 150000
    assert data["trace"]["intent"]["instrument"]["symbol"] == "SOL"
    assert data["auth"]["mode"] == "SANDBOX"
