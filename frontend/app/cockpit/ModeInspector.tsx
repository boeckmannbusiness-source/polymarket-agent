"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MODE_COLORS, MODE_BG_CSS } from "@/lib/utils";
import type { CurrentMode } from "@/lib/api";
import { Lock, User, Clock, Activity } from "lucide-react";

function modeVariant(mode: string): any {
  const map: Record<string, any> = {
    normal: "mode_normal",
    degraded: "mode_degraded",
    protected: "mode_protected",
    read_only: "mode_read_only",
    emergency_stop: "mode_emergency_stop",
  };
  return map[mode] || "default";
}

export default function ModeInspector({ data }: { data: CurrentMode | null }) {
  if (!data) {
    return (
      <Card>
        <CardHeader><CardTitle>Mode Inspector</CardTitle></CardHeader>
        <CardContent><div className="text-sm text-gray-500">Loading...</div></CardContent>
      </Card>
    );
  }

  const modeName = data.mode.replace(/_/g, " ").toUpperCase();
  const holdTimeRemaining = data.ttl_seconds ? `${data.ttl_seconds}s remaining` : null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Mode Inspector</CardTitle>
          <Badge variant={modeVariant(data.mode)} className="text-xs font-bold tracking-wider">
            {modeName}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-3">
          <span
            className="h-3 w-3 rounded-full"
            style={{ backgroundColor: MODE_COLORS[data.mode] || "#888" }}
          />
          <span className="text-sm text-white font-medium capitalize">{data.reason || "No reason"}</span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-1.5 text-gray-400">
            <Lock className="h-3 w-3" />
            <span>Override: {data.is_manual_override ? "Active" : "Inactive"}</span>
          </div>
          {data.operator && (
            <div className="flex items-center gap-1.5 text-gray-400">
              <User className="h-3 w-3" />
              <span>Operator: {data.operator}</span>
            </div>
          )}
          <div className="flex items-center gap-1.5 text-gray-400">
            <Clock className="h-3 w-3" />
            <span>{holdTimeRemaining || "No override TTL"}</span>
          </div>
          <div className="flex items-center gap-1.5 text-gray-400">
            <Activity className="h-3 w-3" />
            <span>Sensitivity: {(data.sensitivity * 100).toFixed(0)}%</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
