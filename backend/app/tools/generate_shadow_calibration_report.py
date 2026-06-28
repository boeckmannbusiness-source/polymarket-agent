import asyncio
import os
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Mock environment if needed
os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from app.services.shadow.outcome_evaluator import OutcomeEvaluator
from app.database import Base

async def generate_report():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        evaluator = OutcomeEvaluator(session)
        metrics = await evaluator.get_global_metrics()

        # We need to get strategy-specific metrics too
        from sqlalchemy import select
        from app.models.shadow_decision_log import ShadowDecisionLog
        result = await session.execute(select(ShadowDecisionLog.strategy_id).distinct())
        strategies = [r[0] for r in result.all() if r[0]]

        strat_metrics = []
        for s in strategies:
            m = await evaluator.evaluate_strategy(s)
            strat_metrics.append(m)

        report = f"""# SHADOW_CALIBRATION_REPORT
Generated at: {datetime.now(timezone.utc).isoformat()}

## Global Metrics
- **Total Decisions**: {metrics.get('total_decisions', 0)}
- **Global Win Rate**: {metrics.get('global_win_rate', 0.0):.2%}
- **Total EV**: {metrics.get('total_ev', 0.0):.4f}
- **Replay Parity**: {metrics.get('replay_parity', 0.0):.2%}
- **Certification Violations**: {metrics.get('certification_violations', 0)}

## Strategy Calibration
"""
        for m in strat_metrics:
            report += f"""
### Strategy: {m['strategy_id']}
- **Brier Score**: {m.get('brier_score', 0.0):.4f}
- **Overconfidence Index**: {m.get('overconfidence_index', 0.0):.4f}
- **Avg Prediction Error**: {m.get('avg_prediction_error', 0.0):.4f}
- **Win Rate**: {m['win_rate']:.2%}

#### Reliability Curve
| Bin | Count | Actual Win Rate |
| --- | ----- | --------------- |
"""
            for bin_data in m.get('calibration_curve', []):
                report += f"| {bin_data['bin']} | {bin_data['count']} | {bin_data['actual_win_rate']:.2%} |\n"

        with open("SHADOW_CALIBRATION_REPORT.md", "w") as f:
            f.write(report)
        print("SHADOW_CALIBRATION_REPORT.md generated successfully.")

if __name__ == "__main__":
    asyncio.run(generate_report())
