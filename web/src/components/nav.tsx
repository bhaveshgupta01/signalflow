"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

/* ── SVG icon components ───────────────────────────────── */

function IconDashboard(p: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  );
}

function IconPortfolio(p: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4" />
      <path d="M3 5v14a2 2 0 0 0 2 2h16v-5" />
      <path d="M18 12a2 2 0 0 0 0 4h4v-4z" />
    </svg>
  );
}

function IconSignals(p: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M2 12h2" /><path d="M6 8v8" /><path d="M10 4v16" /><path d="M14 6v12" /><path d="M18 10v4" /><path d="M22 12h-2" />
    </svg>
  );
}

function IconAnalytics(p: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M3 3v16a2 2 0 0 0 2 2h16" />
      <path d="m7 11 4-4 4 4 5-5" />
    </svg>
  );
}

function IconWhales(p: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a14.5 14.5 0 0 0 0 20" />
      <path d="M12 2a14.5 14.5 0 0 1 0 20" />
      <path d="M2 12h20" />
    </svg>
  );
}

function IconMenu(p: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

function IconX(p: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

/* ── Link data ──────────────────────────────────────────── */

const mainLinks = [
  { href: "/dashboard", label: "Command Center", icon: IconDashboard },
  { href: "/portfolio", label: "Portfolio", icon: IconPortfolio },
  { href: "/signals", label: "Scanner", icon: IconSignals },
  { href: "/analytics", label: "Performance", icon: IconAnalytics },
  { href: "/whales", label: "Whales", icon: IconWhales },
];

/* ── Component ──────────────────────────────────────────── */

export default function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const isLanding = pathname === "/";

  /* ── Desktop sidebar ─────────────────────────────────── */
  const sidebar = (
    <nav className="flex flex-col w-[220px] min-h-screen bg-[#1e1d21] border-r border-[#3c3a41] select-none">
      {/* Brand */}
      <div className="px-4 h-14 flex items-center border-b border-[#3c3a41] gap-2">
        <Link href="/" className="flex items-center gap-2.5 group" onClick={() => setOpen(false)}>
          <div className="w-7 h-7 rounded-lg bg-[#8239ef]/20 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#bfa1f5" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
          </div>
          <span className="text-sm font-semibold text-white group-hover:text-[#bfa1f5] transition-colors" style={{ fontFamily: "'Sora', sans-serif" }}>
            SignalFlow
          </span>
        </Link>
      </div>

      {/* Boba branding badge */}
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#8239ef]/10 border border-[#8239ef]/20">
          <div className="w-2 h-2 rounded-full bg-[#bfa1f5] boba-pulse" />
          <span className="text-[11px] font-medium text-[#bfa1f5]" style={{ fontFamily: "'Sora', sans-serif" }}>
            Powered by Boba
          </span>
        </div>
      </div>

      {/* Main links */}
      <div className="flex-1 px-2 py-1 space-y-0.5">
        <div className="px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-widest text-[#656169]" style={{ fontFamily: "'Sora', sans-serif" }}>
          Monitor
        </div>
        {mainLinks.map((link) => {
          const active = pathname === link.href;
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className={`flex items-center gap-2.5 px-3 py-[8px] rounded-[10px] text-[13px] transition-all duration-150 ${
                active
                  ? "bg-[#8239ef]/15 text-[#bfa1f5] font-medium"
                  : "text-[#858189] hover:text-[#b8b5bb] hover:bg-[hsla(264,4%,64%,0.1)]"
              }`}
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              <Icon className={active ? "text-[#bfa1f5]" : ""} />
              {link.label}
            </Link>
          );
        })}
      </div>

      {/* Bottom section */}
      <div className="px-3 py-3 border-t border-[#3c3a41]">
        <div className="flex items-center gap-2 px-2">
          <div className="w-2 h-2 rounded-full bg-[#84f593] boba-pulse" />
          <span className="text-[11px] text-[#858189]" style={{ fontFamily: "'Inter', sans-serif" }}>Agent Active</span>
        </div>
      </div>
    </nav>
  );

  return (
    <>
      {/* Desktop sidebar */}
      {!isLanding && <div className="hidden lg:block flex-shrink-0">{sidebar}</div>}

      {/* Mobile topbar */}
      {!isLanding && (
        <div className="lg:hidden fixed top-0 left-0 right-0 z-50 h-14 bg-[#1e1d21]/95 backdrop-blur-md border-b border-[#3c3a41] flex items-center px-4 justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[#8239ef]/20 flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#bfa1f5" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <span className="text-sm font-semibold" style={{ fontFamily: "'Sora', sans-serif" }}>SignalFlow</span>
          </Link>
          <button onClick={() => setOpen(!open)} className="p-1.5 rounded-md hover:bg-[hsla(264,4%,64%,0.16)] text-[#858189]">
            {open ? <IconX /> : <IconMenu />}
          </button>
        </div>
      )}

      {/* Mobile drawer */}
      {open && !isLanding && (
        <>
          <div className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <div className="lg:hidden fixed left-0 top-0 bottom-0 z-50">{sidebar}</div>
        </>
      )}
    </>
  );
}
