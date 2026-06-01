from dataclasses import dataclass, field
from datetime import time


@dataclass
class ReportScheduleConfig:
    telegram_interval_hours: int = 3
    email_hour: int = 8
    email_minute: int = 0
    max_retries: int = 3
    retry_delay_seconds: int = 30
    alert_pnl_drop_threshold: float = -5.0
    alert_risk_high_push: bool = True


_report_config: ReportScheduleConfig | None = None


def get_report_config() -> ReportScheduleConfig:
    global _report_config
    if _report_config is None:
        _report_config = ReportScheduleConfig()
    return _report_config


def set_report_config(cfg: ReportScheduleConfig):
    global _report_config
    _report_config = cfg
