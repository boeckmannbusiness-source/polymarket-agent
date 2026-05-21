"use client";

import { useEffect, useState } from "react";

interface AgentStatus {
  name: string;
  label: string;
  status: "running" | "stopped" | "error";
  lastEvent: string;
}

const defaultAgents: AgentStatus[] = [
  { name: "research", label: "Research Agent", status: "running", lastEvent: "-" },
  { name: "whale", label: "Whale Analysis Agent", status: "running", lastEvent: "-" },
  { name: "signal", label: "Signal Generation Agent", status: "running", lastEvent: "-" },
  { name: "risk", label: "Risk Management Agent", status: "running", lastEvent: "-" },
  { name: "execution", label: "Execution Agent", status: "running", lastEvent: "-" },
  { name: "monitoring", label: "Monitoring Agent", status: "running", lastEvent: "-" },
];

export default function AgentsPage() {
  const [agents] = useState<AgentStatus[]>(defaultAgents);

  return (
    <div>
      <h2 className="mb-4 text-2xl font-bold text-white">Agent System</h2>

      <div className="mb-6 grid grid-cols-3 gap-4">
        {agents.map((a) => (
          <div key={a.name} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-white">{a.label}</h3>
              <span className={`h-2.5 w-2.5 rounded-full ${a.status === "running" ? "bg-green-500" : a.status === "error" ? "bg-red-500" : "bg-gray-500"}`} />
            </div>
            <div className="mt-2 text-xs text-gray-500">
              <div className="flex justify-between">
                <span>Status</span>
                <span className={a.status === "running" ? "text-green-400" : "text-gray-400"}>{a.status}</span>
              </div>
              <div className="flex justify-between">
                <span>Last Event</span>
                <span className="text-gray-400">{a.lastEvent}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-400 uppercase tracking-wider">Agent Communication Flow</h3>
        <div className="space-y-2 text-sm text-gray-500">
          <div className="flex items-center gap-2">
            <span className="rounded bg-blue-900 px-2 py-0.5 text-xs text-blue-400">Market Data</span>
            <span className="text-gray-600">→</span>
            <span className="rounded bg-purple-900 px-2 py-0.5 text-xs text-purple-400">Research Agent</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-purple-900 px-2 py-0.5 text-xs text-purple-400">Wallet Events</span>
            <span className="text-gray-600">→</span>
            <span className="rounded bg-purple-900 px-2 py-0.5 text-xs text-purple-400">Whale Agent</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-purple-900 px-2 py-0.5 text-xs text-purple-400">Research + Whale</span>
            <span className="text-gray-600">→</span>
            <span className="rounded bg-yellow-900 px-2 py-0.5 text-xs text-yellow-400">Signal Agent</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-yellow-900 px-2 py-0.5 text-xs text-yellow-400">Signal</span>
            <span className="text-gray-600">→</span>
            <span className="rounded bg-red-900 px-2 py-0.5 text-xs text-red-400">Risk Agent</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-red-900 px-2 py-0.5 text-xs text-red-400">Risk Approved</span>
            <span className="text-gray-600">→</span>
            <span className="rounded bg-green-900 px-2 py-0.5 text-xs text-green-400">Execution Agent</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-green-900 px-2 py-0.5 text-xs text-green-400">All Events</span>
            <span className="text-gray-600">→</span>
            <span className="rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-400">Monitoring Agent</span>
          </div>
        </div>
      </section>
    </div>
  );
}
