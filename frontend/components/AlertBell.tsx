"use client";

import { useState } from "react";
import type { Alert } from "@/lib/alerts";
import { ALERT_TYPE_LABELS, alertTone } from "@/lib/alerts";
import {
  getNotificationPermission,
  requestNotificationPermission,
  type NotificationPermissionState,
} from "@/lib/browserNotifications";

const TONE_TEXT: Record<string, string> = {
  long: "text-long",
  short: "text-short",
  watch: "text-watch",
  neutral: "text-text-dim",
};

export function AlertBell({
  alerts,
  unreadCount,
  onOpen,
  soundEnabled,
  onToggleSound,
}: {
  alerts: Alert[];
  unreadCount: number;
  onOpen: () => void;
  soundEnabled: boolean;
  onToggleSound: (enabled: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [permission, setPermission] = useState<NotificationPermissionState>(
    typeof window === "undefined" ? "unsupported" : getNotificationPermission()
  );

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) onOpen();
  }

  async function enableBrowserNotifications() {
    const result = await requestNotificationPermission();
    setPermission(result);
  }

  return (
    <div className="relative">
      <button onClick={toggle} className="relative text-text-dim hover:text-text px-2 py-1" aria-label="Alerts">
        <BellIcon />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-short text-white text-[10px] leading-none rounded-full w-4 h-4 flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-surface border border-border rounded-lg shadow-xl z-40 max-h-[70vh] flex flex-col">
          <div className="px-3.5 py-2.5 border-b border-border flex items-center justify-between">
            <span className="text-xs font-medium text-text-dim">Alerts</span>
            <div className="flex items-center gap-2">
              {permission !== "granted" && permission !== "unsupported" && (
                <button onClick={enableBrowserNotifications} className="text-[11px] text-accent hover:underline">
                  Enable notifications
                </button>
              )}
              <button
                onClick={() => onToggleSound(!soundEnabled)}
                className={`text-[11px] px-2 py-0.5 rounded border ${
                  soundEnabled ? "border-text-faint text-text" : "border-border text-text-faint"
                }`}
              >
                Sound {soundEnabled ? "on" : "off"}
              </button>
            </div>
          </div>

          <div className="overflow-y-auto flex-1">
            {alerts.length === 0 ? (
              <div className="px-3.5 py-6 text-xs text-text-faint text-center">No alerts yet.</div>
            ) : (
              alerts.map((alert) => {
                const tone = alertTone(alert);
                return (
                  <div key={alert.id} className="px-3.5 py-2.5 border-b border-border last:border-b-0">
                    <div className="flex items-center justify-between">
                      <span className="text-[13px] font-medium">{alert.symbol}</span>
                      <span className={`text-[11px] ${TONE_TEXT[tone]}`}>{ALERT_TYPE_LABELS[alert.alertType]}</span>
                    </div>
                    <div className="text-[12px] text-text-dim mt-0.5">{alert.message}</div>
                    <div className="text-[10.5px] text-text-faint mt-1">
                      {new Date(alert.firedAt).toLocaleTimeString("en-IN")}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}
