"use client";

import { useState, useCallback } from "react";

interface ControlSwitchProps {
  label: string;
  initialState?: boolean;
  onChange?: (enabled: boolean) => void;
  disabled?: boolean;
}

export function ControlSwitch({ label, initialState = true, onChange, disabled }: ControlSwitchProps) {
  const [enabled, setEnabled] = useState(initialState);

  const toggle = useCallback(() => {
    const next = !enabled;
    setEnabled(next);
    onChange?.(next);
  }, [enabled, onChange]);

  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-xs text-gray-300">{label}</span>
      <button
        onClick={toggle}
        disabled={disabled}
        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
          disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"
        } ${enabled ? "bg-emerald-600" : "bg-gray-700"}`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
            enabled ? "translate-x-4.5" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}
