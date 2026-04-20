"""Tests for executor sizing logic — catches NameErrors and formula bugs."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from models import Direction, TradeProposal, ProposalStatus


def _make_proposal(conviction=0.70, risk_pct=0.05, asset="SOL", direction="short"):
    return TradeProposal(
        id=99,
        agent_id="funding_analyst",
        asset=asset,
        direction=Direction(direction),
        conviction=conviction,
        edge_type="funding",
        reasoning="test",
        suggested_risk_pct=risk_pct,
        allocated_risk_pct=risk_pct,
        status=ProposalStatus.APPROVED,
    )


def test_sizing_formula_no_name_errors():
    """The sizing code path must not raise NameError on any variable."""
    from agents.executor import ExecutionSpecialist

    executor = ExecutionSpecialist.__new__(ExecutionSpecialist)
    executor.boba = MagicMock()
    executor.client = MagicMock()
    executor.AGENT_ID = "executor"
    executor._gemini_tools = None

    proposal = _make_proposal(conviction=0.70, risk_pct=0.05)

    # Mock all external calls
    with patch("agents.executor.get_stats", return_value={"total_pnl": -5.0}), \
         patch("agents.executor.can_open_position", return_value=(True, "")), \
         patch("agents.executor.can_open_position_for_asset", return_value=(True, "")), \
         patch("agents.executor.check_trade_cooldown", return_value=(True, "")), \
         patch("agents.executor.compute_atr", new_callable=AsyncMock, return_value=2.5), \
         patch("agents.executor.compute_stop_take_atr", new_callable=AsyncMock, return_value=(83.0, 95.0)), \
         patch("agents.executor.check_orderbook_liquidity", new_callable=AsyncMock, return_value=(True, 0.01, "ok")), \
         patch("agents.executor.confirm_fill_and_track_slippage", new_callable=AsyncMock, return_value=(86.5, 0.001)), \
         patch("agents.executor.clamp_leverage", return_value=3), \
         patch("agents.executor.save_position", side_effect=lambda p: setattr(p, 'id', 999) or p), \
         patch("agents.executor.save_signal", side_effect=lambda s: setattr(s, 'id', 999) or s), \
         patch("agents.executor.save_analysis", side_effect=lambda a: setattr(a, 'id', 999) or a), \
         patch("agents.executor.update_position"), \
         patch("agents.executor.update_proposal"), \
         patch("agents.executor.get_open_positions", return_value=[]), \
         patch("db._get_conn") as mock_conn:

        mock_conn.return_value.execute = MagicMock()
        mock_conn.return_value.commit = MagicMock()

        # Mock boba.call_tool
        async def mock_call_tool(name, args, **kwargs):
            if name == "hl_get_asset":
                return '{"mark": 86.5}'
            return '{"success": true}'

        executor.boba.call_tool = mock_call_tool
        executor.get_asset_price = AsyncMock(return_value=86.5)

        # This is the critical test — if any variable is undefined, this raises NameError
        result = asyncio.run(executor.execute_proposal(proposal))
        assert result is not None, "Executor should have returned a position"
        print(f"OK  Position created: {result.asset} {result.direction.value} ${result.size_usd:.0f}")


def test_sizing_varies_with_risk_allocation():
    """Higher risk allocation should produce larger positions."""
    from agents.executor import ExecutionSpecialist

    sizes = {}
    for risk_pct, label in [(0.01, "low"), (0.05, "med"), (0.10, "high")]:
        proposal = _make_proposal(conviction=0.70, risk_pct=risk_pct)

        executor = ExecutionSpecialist.__new__(ExecutionSpecialist)
        executor.boba = MagicMock()
        executor.client = MagicMock()
        executor.AGENT_ID = "executor"
        executor._gemini_tools = None

        with patch("agents.executor.get_stats", return_value={"total_pnl": -5.0}), \
             patch("agents.executor.can_open_position", return_value=(True, "")), \
             patch("agents.executor.can_open_position_for_asset", return_value=(True, "")), \
             patch("agents.executor.check_trade_cooldown", return_value=(True, "")), \
             patch("agents.executor.compute_atr", new_callable=AsyncMock, return_value=2.5), \
             patch("agents.executor.compute_stop_take_atr", new_callable=AsyncMock, return_value=(83.0, 95.0)), \
             patch("agents.executor.check_orderbook_liquidity", new_callable=AsyncMock, return_value=(True, 0.01, "ok")), \
             patch("agents.executor.confirm_fill_and_track_slippage", new_callable=AsyncMock, return_value=(86.5, 0.001)), \
             patch("agents.executor.clamp_leverage", return_value=3), \
             patch("agents.executor.save_position", side_effect=lambda p: setattr(p, 'id', 999) or p), \
             patch("agents.executor.save_signal", side_effect=lambda s: setattr(s, 'id', 999) or s), \
             patch("agents.executor.save_analysis", side_effect=lambda a: setattr(a, 'id', 999) or a), \
             patch("agents.executor.update_position"), \
             patch("agents.executor.update_proposal"), \
             patch("agents.executor.get_open_positions", return_value=[]), \
             patch("db._get_conn") as mock_conn:

            mock_conn.return_value.execute = MagicMock()
            mock_conn.return_value.commit = MagicMock()

            async def mock_call_tool(name, args, **kwargs):
                if name == "hl_get_asset":
                    return '{"mark": 86.5}'
                return '{"success": true}'

            executor.boba.call_tool = mock_call_tool
            executor.get_asset_price = AsyncMock(return_value=86.5)

            result = asyncio.run(executor.execute_proposal(proposal))
            sizes[label] = result.size_usd
            print(f"  {label} risk ({risk_pct*100:.0f}%): ${result.size_usd:.0f}")

    assert sizes["high"] > sizes["med"] > sizes["low"], \
        f"Sizes should increase with risk: low=${sizes['low']:.0f} med=${sizes['med']:.0f} high=${sizes['high']:.0f}"
    print(f"OK  Sizes scale correctly: ${sizes['low']:.0f} < ${sizes['med']:.0f} < ${sizes['high']:.0f}")


if __name__ == "__main__":
    print("=== Test 1: No NameErrors in sizing path ===")
    test_sizing_formula_no_name_errors()
    print()
    print("=== Test 2: Size varies with risk allocation ===")
    test_sizing_varies_with_risk_allocation()
    print()
    print("All tests passed.")
