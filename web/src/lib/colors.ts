/** SignalFlow theme colors */
export const COLORS = {
  bg: "#090B10",
  surface: "#0F1219",
  card: "#151921",
  cardAlt: "#1A1F2A",
  border: "rgba(255,255,255,0.06)",
  borderBold: "rgba(255,255,255,0.10)",
  brand: "#8B5CF6",
  brand2: "#06B6D4",
  up: "#22C55E",
  down: "#EF4444",
  warn: "#F59E0B",
  info: "#3B82F6",
  text: "#F1F5F9",
  text2: "#CBD5E1",
  muted: "#64748B",
  subtle: "#475569",
} as const;

/** Recharts color cycle */
export const CHART_COLORS = [
  COLORS.brand,
  COLORS.brand2,
  COLORS.up,
  COLORS.warn,
  COLORS.info,
  COLORS.down,
  "#A78BFA",
  "#2DD4BF",
];

/** Per-asset colors for portfolio charts */
export const ASSET_COLORS: Record<string, string> = {
  BTC: "#F7931A",
  ETH: "#627EEA",
  SOL: "#14F195",
  DOGE: "#C3A634",
  ARB: "#28A0F0",
  MATIC: "#8247E5",
  LINK: "#2A5ADA",
  AVAX: "#E84142",
  XRP: "#23292F",
  NEAR: "#00EC97",
  OP: "#FF0420",
  SUI: "#4DA2FF",
};

export function getAssetColor(asset: string): string {
  return ASSET_COLORS[asset.toUpperCase()] ?? COLORS.brand;
}
