/** Boba.xyz-aligned theme colors */
export const COLORS = {
  bg: "#141316",
  surface: "#1e1d21",
  card: "#28272b",
  cardAlt: "#1e1d21",
  border: "#3c3a41",
  borderBold: "#656169",
  brand: "#8239ef",
  brand2: "#bfa1f5",
  up: "#84f593",
  upStrong: "#14eb31",
  down: "#f2685f",
  downStrong: "#eb2314",
  warn: "#F59E0B",
  info: "#bfa1f5",
  text: "#ffffff",
  text2: "#b8b5bb",
  muted: "#858189",
  subtle: "#656169",
} as const;

/** Recharts color cycle — boba palette */
export const CHART_COLORS = [
  COLORS.brand,
  COLORS.brand2,
  COLORS.up,
  COLORS.warn,
  COLORS.info,
  COLORS.down,
  "#a78bfa",
  "#2dd4bf",
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
