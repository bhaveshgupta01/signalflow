import { NextRequest } from "next/server";
import {
  getRecentSignals,
  getRecentAnalyses,
  getOpenPositions,
  getAllPositions,
  getStats,
  getRecentDecisions,
  getAllKolSignals,
  getWalletHistory,
  getPositionSnapshots,
  getTradeEvents,
} from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const q = searchParams.get("q") ?? "";

  try {
    switch (q) {
      case "signals":
        return Response.json(getRecentSignals(Number(searchParams.get("minutes") ?? 30)));
      case "analyses":
        return Response.json(getRecentAnalyses(Number(searchParams.get("limit") ?? 20)));
      case "positions_open":
        return Response.json(getOpenPositions());
      case "positions_all":
        return Response.json(getAllPositions(Number(searchParams.get("limit") ?? 50)));
      case "stats":
        return Response.json(getStats());
      case "decisions":
        return Response.json(getRecentDecisions(Number(searchParams.get("limit") ?? 50)));
      case "kol_signals":
        return Response.json(getAllKolSignals(Number(searchParams.get("limit") ?? 50)));
      case "wallet_history":
        return Response.json(getWalletHistory(Number(searchParams.get("limit") ?? 500)));
      case "position_snapshots": {
        const pid = searchParams.get("position_id");
        return Response.json(
          getPositionSnapshots(pid ? Number(pid) : undefined, Number(searchParams.get("minutes") ?? 1440))
        );
      }
      case "trade_events":
        return Response.json(getTradeEvents(Number(searchParams.get("minutes") ?? 999999)));
      default:
        return Response.json({ error: "Unknown query. Use ?q=signals|analyses|positions_open|positions_all|stats|decisions|kol_signals|wallet_history|position_snapshots|trade_events" }, { status: 400 });
    }
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return Response.json({ error: message }, { status: 500 });
  }
}
