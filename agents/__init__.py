"""v3 multi-agent architecture — specialized agents communicating via proposal DB."""

from agents.base import BaseSpecialist
from agents.pm_analyst import PMAnalyst
from agents.funding_analyst import FundingAnalyst
from agents.trend_analyst import TrendAnalyst
from agents.executor import ExecutionSpecialist
from agents.orchestrator import Orchestrator

__all__ = [
    "BaseSpecialist",
    "PMAnalyst",
    "FundingAnalyst",
    "TrendAnalyst",
    "ExecutionSpecialist",
    "Orchestrator",
]
