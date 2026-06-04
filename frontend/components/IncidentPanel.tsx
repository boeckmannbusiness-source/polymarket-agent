"use client";

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: string;
  status: string;
  source: string;
  entity_id: string;
  created_at: string;
}

interface IncidentPanelProps {
  incidents: Incident[];
  onResolve?: (id: string) => void;
  loading?: boolean;
}

const severityColor: Record<string, string> = {
  critical: "border-red-600 bg-red-950/30",
  warning: "border-amber-600 bg-amber-950/30",
  info: "border-blue-600 bg-blue-950/30",
};

export function IncidentPanel({ incidents, onResolve, loading }: IncidentPanelProps) {
  return (
    <div className="space-y-2">
      {loading && (
        <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
          Loading incidents...
        </div>
      )}
      {!loading && incidents.length === 0 && (
        <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
          No incidents
        </div>
      )}
      {incidents.map((inc) => (
        <div
          key={inc.id}
          className={`border-l-4 p-3 rounded-r-lg ${severityColor[inc.severity] || "border-border"} ${
            inc.status === "resolved" ? "opacity-50" : ""
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono uppercase text-muted-foreground">{inc.severity}</span>
                <span className="text-[10px] font-mono uppercase text-muted-foreground">{inc.status}</span>
                <span className="text-[10px] text-muted-foreground">
                  {new Date(inc.created_at).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-sm font-medium truncate">{inc.title}</p>
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{inc.description}</p>
            </div>
            {inc.status !== "resolved" && onResolve && (
              <button
                onClick={() => onResolve(inc.id)}
                className="shrink-0 px-2 py-0.5 text-[10px] border border-border rounded hover:bg-accent"
              >
                Resolve
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
