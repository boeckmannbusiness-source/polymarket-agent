import type { Metadata } from "next";
import "@/styles/globals.css";
import { AlertCenter } from "@/components/AlertCenter";
import { ToastContainer } from "@/components/Toast";

export const metadata: Metadata = {
  title: "Polymarket Intelligence Agent",
  description: "Prediction market analysis and monitoring dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <nav className="border-b border-[var(--border)] bg-[var(--background)] px-4 md:px-6 py-3">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <div className="flex items-center gap-4 md:gap-8">
              <a href="/" className="text-lg font-bold text-white shrink-0">
                Polymarket<span className="text-[var(--primary)]">Intel</span>
              </a>
              <div className="flex gap-4 md:gap-6 text-xs md:text-sm text-gray-400 overflow-x-auto">
                <a href="/" className="hover:text-white transition-colors whitespace-nowrap">Dashboard</a>
                <a href="/portfolio" className="hover:text-white transition-colors whitespace-nowrap">Portfolio</a>
                <a href="/portfolio/positions" className="hover:text-white transition-colors whitespace-nowrap">Positions</a>
                <a href="/portfolio/strategies" className="hover:text-white transition-colors whitespace-nowrap">Strategies</a>
                <a href="/portfolio/exposure" className="hover:text-white transition-colors whitespace-nowrap">Exposure</a>
                <a href="/monitoring" className="hover:text-white transition-colors whitespace-nowrap">Monitoring</a>
                <a href="/monitoring/replay" className="hover:text-white transition-colors whitespace-nowrap">Replay</a>
                <a href="/monitoring/strategies-control" className="hover:text-white transition-colors whitespace-nowrap">Control</a>
                <a href="/incidents" className="hover:text-white transition-colors whitespace-nowrap">Incidents</a>
                <a href="/monitoring/shadow" className="hover:text-white transition-colors whitespace-nowrap">Shadow</a>
                <a href="/markets" className="hover:text-white transition-colors whitespace-nowrap">Markets</a>
                <a href="/trades" className="hover:text-white transition-colors whitespace-nowrap">Trades</a>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0 ml-2">
              <AlertCenter />
            </div>
          </div>
        </nav>
        <main className="mx-auto max-w-7xl px-4 md:px-6 py-4 md:py-6">{children}</main>
        <ToastContainer />
      </body>
    </html>
  );
}
