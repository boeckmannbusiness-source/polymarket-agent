"use client";

import { useState } from "react";

interface ReplayControlsProps {
  onPlay?: () => void;
  onPause?: () => void;
  onSeek?: (time: string) => void;
  onFilter?: (filters: Record<string, string>) => void;
}

export function ReplayControls({ onPlay, onPause, onSeek, onFilter }: ReplayControlsProps) {
  const [playing, setPlaying] = useState(false);
  const [entityFilter, setEntityFilter] = useState("");
  const [eventFilter, setEventFilter] = useState("");

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button
          onClick={() => {
            setPlaying(!playing);
            if (playing) onPause?.();
            else onPlay?.();
          }}
          className="px-3 py-1.5 text-xs border border-border rounded hover:bg-accent"
        >
          {playing ? "⏸ Pause" : "▶ Play"}
        </button>
        <input
          type="datetime-local"
          onChange={(e) => onSeek?.(e.target.value)}
          className="px-2 py-1.5 text-xs bg-black border border-border rounded font-mono"
        />
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Filter by entity_id..."
          value={entityFilter}
          onChange={(e) => {
            setEntityFilter(e.target.value);
            onFilter?.({ entity_id: e.target.value, event_type: eventFilter });
          }}
          className="flex-1 px-2 py-1.5 text-xs bg-black border border-border rounded font-mono"
        />
        <input
          type="text"
          placeholder="Filter by event_type..."
          value={eventFilter}
          onChange={(e) => {
            setEventFilter(e.target.value);
            onFilter?.({ entity_id: entityFilter, event_type: e.target.value });
          }}
          className="flex-1 px-2 py-1.5 text-xs bg-black border border-border rounded font-mono"
        />
      </div>
    </div>
  );
}
