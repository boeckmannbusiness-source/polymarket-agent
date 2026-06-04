"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { ReplayControls } from "@/components/ReplayControls";
import { LiveIndicator } from "@/components/LiveIndicator";
import { api } from "@/lib/api";

export default function ReplayPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filteredEvents, setFilteredEvents] = useState<any[]>([]);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [selectedEvent, setSelectedEvent] = useState<any>(null);
  const [playing, setPlaying] = useState(false);
  const playIndex = useRef(0);
  const playTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchReplay = useCallback(async (from_ts?: string, to_ts?: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (from_ts) params.set("from", from_ts);
      if (to_ts) params.set("to", to_ts);
      if (filters.event_type) params.set("event_type", filters.event_type);
      if (filters.entity_id) params.set("entity_id", filters.entity_id);
      const res = await fetch(`/api/v1/events/replay?${params.toString()}`);
      const data = await res.json();
      setEvents(data.events || []);
    } catch {
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchReplay();
  }, [fetchReplay]);

  useEffect(() => {
    let filtered = events;
    if (filters.entity_id) {
      filtered = filtered.filter((e: any) => (e.entity_id || "").includes(filters.entity_id));
    }
    if (filters.event_type) {
      filtered = filtered.filter((e: any) => (e.event_type || "").includes(filters.event_type));
    }
    setFilteredEvents(filtered);
  }, [events, filters]);

  useEffect(() => {
    if (playing) {
      playTimer.current = setInterval(() => {
        if (playIndex.current < filteredEvents.length) {
          setSelectedEvent(filteredEvents[playIndex.current]);
          playIndex.current++;
        } else {
          setPlaying(false);
        }
      }, 500);
    } else {
      if (playTimer.current) clearInterval(playTimer.current);
    }
    return () => { if (playTimer.current) clearInterval(playTimer.current); };
  }, [playing, filteredEvents]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Forensic Replay</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Event reconstruction and trade execution path</p>
        </div>
        <LiveIndicator status="connected" />
      </div>

      <ReplayControls
        onPlay={() => { playIndex.current = 0; setPlaying(true); }}
        onPause={() => setPlaying(false)}
        onSeek={(t) => fetchReplay(t)}
        onFilter={(f) => setFilters(f)}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            Event Stream ({filteredEvents.length})
          </h2>
          <div className="h-96 overflow-y-auto space-y-1">
            {loading && (
              <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                Loading events...
              </div>
            )}
            {!loading && filteredEvents.length === 0 && (
              <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                No events found
              </div>
            )}
            {filteredEvents.map((event: any, i: number) => (
              <button
                key={event.event_id || i}
                onClick={() => setSelectedEvent(event)}
                className={`w-full text-left flex items-start gap-2 py-1.5 px-2 border-b border-border/30 text-xs rounded transition-colors ${
                  selectedEvent?.event_id === event.event_id ? "bg-accent" : "hover:bg-accent/50"
                }`}
              >
                <span className="text-[10px] text-muted-foreground font-mono shrink-0 w-14">
                  {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "-"}
                </span>
                <span className="text-[10px] text-muted-foreground font-mono shrink-0 w-8">
                  #{event.sequence ?? "-"}
                </span>
                <span className="font-mono uppercase text-[10px] shrink-0 text-blue-400">
                  {event.event_type}
                </span>
                <span className="font-mono uppercase text-[10px] shrink-0 text-muted-foreground">
                  {event.entity_type}
                </span>
                <span className="text-muted-foreground truncate">{event.entity_id}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            Event Detail
          </h2>
          {selectedEvent ? (
            <div className="space-y-3 text-xs font-mono">
              <div><span className="text-muted-foreground">event_id:</span> <span className="text-white break-all">{selectedEvent.event_id}</span></div>
              <div><span className="text-muted-foreground">sequence:</span> <span className="text-white">#{selectedEvent.sequence}</span></div>
              <div><span className="text-muted-foreground">event_type:</span> <span className="text-blue-400">{selectedEvent.event_type}</span></div>
              <div><span className="text-muted-foreground">entity_type:</span> <span className="text-white">{selectedEvent.entity_type}</span></div>
              <div><span className="text-muted-foreground">entity_id:</span> <span className="text-white">{selectedEvent.entity_id}</span></div>
              <div><span className="text-muted-foreground">timestamp:</span> <span className="text-white">{selectedEvent.timestamp}</span></div>
              {selectedEvent.payload && (
                <div>
                  <span className="text-muted-foreground">payload:</span>
                  <pre className="mt-1 p-2 bg-black/50 rounded text-[10px] text-green-400 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(selectedEvent.payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
              Select an event to inspect
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
