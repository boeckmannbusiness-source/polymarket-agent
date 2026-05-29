import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Polymarket Intelligence Agent",
  description: "Prediction market analysis and monitoring dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <nav className="border-b border-[var(--border)] bg-[var(--background)] px-6 py-3">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <div className="flex items-center gap-8">
              <h1 className="text-lg font-bold text-white">
                Polymarket<span className="text-[var(--primary)]">Intel</span>
              </h1>
              <div className="flex gap-6 text-sm text-gray-400">
                <a href="/" className="hover:text-white transition-colors">Dashboard</a>
                <a href="/markets" className="hover:text-white transition-colors">Markets</a>
                <a href="/whales" className="hover:text-white transition-colors">Whales</a>
                <a href="/signals" className="hover:text-white transition-colors">Signals</a>
                <a href="/trades" className="hover:text-white transition-colors">Trades</a>
                <a href="/agents" className="hover:text-white transition-colors">Agents</a>
                <a href="/cockpit" className="hover:text-white transition-colors text-[var(--primary)] font-semibold">Cockpit</a>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              <span className="text-xs text-gray-500">Paper Trading</span>
            </div>
          </div>
        </nav>
        <main className="mx-auto max-w-7xl px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
