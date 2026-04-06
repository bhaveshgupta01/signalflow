export interface Signal {
  id: number;
  market_id: string;
  market_question: string;
  current_price: number;
  price_change_pct: number;
  timeframe_minutes: number;
  category: string;
  detected_at: string;
}

export interface Analysis {
  id: number;
  signal_id: number;
  reasoning: string;
  conviction_score: number;
  suggested_direction: "long" | "short";
  suggested_asset: string;
  suggested_size_usd: number;
  risk_notes: string;
  created_at: string;
}

export interface Position {
  id: number;
  analysis_id: number;
  asset: string;
  direction: "long" | "short";
  entry_price: number;
  size_usd: number;
  leverage: number;
  stop_loss: number;
  take_profit: number;
  status: "open" | "closed" | "stopped";
  pnl: number;
  opened_at: string;
  closed_at: string | null;
}

export interface PositionSnapshot {
  id: number;
  position_id: number;
  asset: string;
  current_price: number;
  unrealized_pnl: number;
  timestamp: string;
}

export interface WalletSnapshot {
  id: number;
  balance: number;
  total_pnl: number;
  open_positions: number;
  timestamp: string;
}

export interface KolSignal {
  id: number;
  kol_name: string;
  wallet_address: string;
  asset: string;
  direction: "long" | "short";
  trade_size_usd: number;
  detected_at: string;
}

export interface AgentDecision {
  id: number;
  cycle_id: string;
  signals_detected: number;
  analyses_produced: number;
  trades_executed: number;
  reasoning_summary: string;
  timestamp: string;
}

export interface TradingStats {
  total_trades: number;
  closed_trades: number;
  wins: number;
  win_rate: number;
  total_pnl: number;
  open_exposure: number;
}

export interface TradeEvent {
  type: "open" | "close";
  position_id: number;
  asset: string;
  direction: string;
  price: number;
  size_usd: number;
  leverage?: number;
  pnl?: number;
  status?: string;
  timestamp: string;
}
