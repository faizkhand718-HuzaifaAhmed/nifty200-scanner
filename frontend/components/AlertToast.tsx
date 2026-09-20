"use client";

import { useEffect, useState } from "react";
import type { Alert } from "@/lib/alerts";
import { ALERT_TYPE_LABELS, alertTone } from "@/lib/alerts";

const TONE_CLASSES: Record<string, string> = {
  long: "border-l-long",
  short: "border-l-short",
  watch: "border-l-watch",
  neutral: "border-l-text-faint",
};

const AUTO_DISMISS_MS = 6000;

/**
 * The "Dashboard alert" channel: a stack of transient toasts in the
 * corner of the screen. This is the always-on channel - it needs no
 * permission and works the moment an alert fires, unlike browser
 * notifications (needs permission) or sound (needs a prior user gesture).
 */
export function AlertToastStack({ toasts, onDismiss }: { toasts: Alert[]; onDismiss: (id: string) => void }) {
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
      {toasts.map((alert) => (
        <Toast key={alert.id} alert={alert} onDismiss={() => onDismiss(alert.id)} />
      ))}
    </div>
  );
}

function Toast({ alert, onDismiss }: { alert: Alert; onDismiss: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alert.id]);

  const tone = alertTone(alert);

  return (
    <div
      className={`bg-surface border border-border ${TONE_CLASSES[tone]} border-l-[3px] rounded-md p-3 shadow-lg`}
      role="status"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[13px] font-medium">
            {alert.symbol} <span className="text-text-dim font-normal">· {ALERT_TYPE_LABELS[alert.alertType]}</span>
          </div>
          <div className="text-[12px] text-text-dim mt-0.5">{alert.message}</div>
        </div>
        <button onClick={onDismiss} className="text-text-faint hover:text-text text-xs shrink-0">
          ✕
        </button>
      </div>
    </div>
  );
}

export function useToastQueue() {
  const [toasts, setToasts] = useState<Alert[]>([]);

  function push(alerts: Alert[]) {
    setToasts((prev) => [...alerts, ...prev].slice(0, 5));
  }
  function dismiss(id: string) {
    setToasts((prev) => prev.filter((a) => a.id !== id));
  }

  return { toasts, push, dismiss };
}
