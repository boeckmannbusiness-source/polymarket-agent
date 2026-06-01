from datetime import datetime, timezone


TELEGRAM_SYSTEM_PROMPT = """You are a Trading Intelligence Analyst for a Polymarket automated trading system.

You receive structured system state including:
- portfolio metrics
- strategy performance
- market state
- risk state

Your task:
1. Interpret performance (not just restate numbers)
2. Identify key drivers of PnL
3. Detect anomalies or risk changes
4. Summarize system health

Output rules:
- max 8-12 lines
- extremely concise
- include:
  - total PnL
  - daily PnL
  - risk level
  - 1-2 key drivers
  - 1 action suggestion (if relevant)
- Never expose raw JSON
- Use markdown formatting for readability"""


EMAIL_SYSTEM_PROMPT = """You are a Trading Intelligence Analyst for a Polymarket automated trading system.

You receive structured system state including:
- portfolio metrics
- strategy performance
- market state
- risk state

Your task:
1. Interpret performance (not just restate numbers)
2. Identify key drivers of PnL
3. Detect anomalies or risk changes
4. Summarize system health

Output rules:
- structured sections:
  - Performance Overview
  - Strategy Breakdown
  - Risk Analysis
  - Market Conditions
  - Outlook
- still concise, no fluff
- Never expose raw JSON
- Use plain text sections (no markdown)"""


def build_user_prompt(snapshot: dict, mode: str = "telegram") -> str:
    ts = snapshot.get("timestamp") or datetime.now(timezone.utc).isoformat()
    portfolio = snapshot.get("portfolio", {})
    strategies = snapshot.get("strategies", [])
    market = snapshot.get("market", {})
    risk = snapshot.get("risk", {})

    lines = [f"System snapshot at {ts}"]
    lines.append("")

    lines.append("--- PORTFOLIO ---")
    lines.append(f"Total Equity: {portfolio.get('total_equity', 'N/A')}")
    lines.append(f"Cash Balance: {portfolio.get('cash_balance', 'N/A')}")
    lines.append(f"Exposure: {portfolio.get('exposure', 'N/A')}")
    lines.append(f"PnL 24h: {portfolio.get('pnl_24h', 'N/A')}")
    lines.append(f"PnL Total: {portfolio.get('pnl_total', 'N/A')}")
    lines.append("")

    lines.append("--- STRATEGIES ---")
    if strategies:
        for s in strategies:
            lines.append(
                f"- {s.get('name', '?')}: "
                f"PnL 24h={s.get('pnl_24h', 'N/A')}, "
                f"Total={s.get('pnl_total', 'N/A')}, "
                f"WinRate={s.get('win_rate', 'N/A')}, "
                f"Trades={s.get('num_trades', 0)}, "
                f"Sharpe={s.get('sharpe_ratio', 'N/A')}"
            )
    else:
        lines.append("(no active strategies)")
    lines.append("")

    lines.append("--- MARKET STATE ---")
    sig_dist = market.get("signal_distribution", {})
    lines.append(f"Active Markets: {market.get('active_markets_count', 'N/A')}")
    lines.append(f"Volatility Index: {market.get('volatility_index', 'N/A')}")
    lines.append(f"Liquidity Score: {market.get('liquidity_score', 'N/A')}")
    lines.append(f"Signal Distribution: long={sig_dist.get('long', 0)}, "
                 f"short={sig_dist.get('short', 0)}, neutral={sig_dist.get('neutral', 0)}")
    lines.append("")

    lines.append("--- RISK STATE ---")
    lines.append(f"Risk Level: {risk.get('risk_level', 'N/A')}")
    lines.append(f"Max Drawdown: {risk.get('max_drawdown', 'N/A')}")
    lines.append(f"Exposure Utilization: {risk.get('exposure_utilization_pct', 'N/A')}%")
    alerts = risk.get("active_risk_alerts", [])
    if alerts:
        lines.append(f"Active Alerts ({len(alerts)}):")
        for a in alerts:
            lines.append(f"  - {a}")
    else:
        lines.append("Active Alerts: none")
    lines.append("")

    lines.append(f"Report mode: {mode}")
    lines.append(f"Generate a {'concise telegram summary' if mode == 'telegram' else 'structured daily email report'}.")

    return "\n".join(lines)
