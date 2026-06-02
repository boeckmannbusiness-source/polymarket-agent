"use client";

import { useState, useEffect, useCallback } from "react";

interface ToastMessage {
  id: string;
  title: string;
  message: string;
  severity: "info" | "warning" | "critical";
}

let addToastFn: ((t: Omit<ToastMessage, "id">) => void) | null = null;

export function notify(toast: Omit<ToastMessage, "id">) {
  addToastFn?.(toast);
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((toast: Omit<ToastMessage, "id">) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 6000);
  }, []);

  useEffect(() => {
    addToastFn = addToast;
    return () => { addToastFn = null; };
  }, [addToast]);

  const severityBorder: Record<string, string> = {
    info: "border-blue-500",
    warning: "border-amber-500",
    critical: "border-red-500",
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`px-4 py-3 border-l-4 ${severityBorder[t.severity]} border border-border rounded bg-background shadow-xl animate-in slide-in-from-right`}
        >
          <p className="text-sm font-semibold">{t.title}</p>
          <p className="text-xs text-muted-foreground mt-1">{t.message}</p>
        </div>
      ))}
    </div>
  );
}
