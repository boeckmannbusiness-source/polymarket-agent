"use client";

export default function SettingsPage() {
  return (
    <div>
      <h2 className="mb-4 text-2xl font-bold text-white">Settings</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-400 uppercase tracking-wider">Trading Configuration</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Mode</span>
              <span className="rounded bg-yellow-900 px-2 py-0.5 text-xs text-yellow-400">Paper Trading</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Initial Capital</span>
              <span className="font-mono text-white">$10,000.00</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Max Position Size</span>
              <span className="text-gray-400">10%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Max Daily Loss</span>
              <span className="text-gray-400">$500.00</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Max Open Positions</span>
              <span className="text-gray-400">5</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Stop Loss</span>
              <span className="text-gray-400">15%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Take Profit</span>
              <span className="text-gray-400">50%</span>
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-400 uppercase tracking-wider">System Status</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">LLM Provider</span>
              <span className="text-[var(--primary)]">OpenRouter</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">API Connected</span>
              <span className="flex items-center gap-1.5 text-green-400">
                <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
                Online
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Polymarket WS</span>
              <span className="flex items-center gap-1.5 text-gray-400">
                <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
                Disconnected
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Telegram Bot</span>
              <span className="flex items-center gap-1.5 text-gray-400">
                <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
                Not Configured
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Database</span>
              <span className="flex items-center gap-1.5 text-gray-400">
                <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
                Cloud (Not Connected)
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
