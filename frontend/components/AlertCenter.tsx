"use client";

import { useEffect, useRef, useState } from "react";
import type { Alert } from "@/lib/alerts";
import { subscribeToAlerts } from "@/lib/api";
import { showBrowserNotification, getNotificationPermission } from "@/lib/browserNotifications";
import { playAlertSound } from "@/lib/soundAlert";
import { AlertBell } from "./AlertBell";
import { AlertToastStack, useToastQueue } from "./AlertToast";

/**
 * Wires one incoming alert stream to all three "start with" channels:
 *   - Dashboard alert: the toast stack (always on, no permission needed)
 *   - Browser notification: only if the user has granted permission
 *   - Sound: only if the user has enabled it (starts OFF - audio
 *     shouldn't play before a deliberate opt-in)
 * Deduplication already happened server-side (AlertHistory); this
 * component trusts that every alert it receives from subscribeToAlerts
 * is genuinely new and does not re-filter.
 */
export function AlertCenter() {
  const [history, setHistory] = useState<Alert[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const { toasts, push: pushToasts, dismiss: dismissToast } = useToastQueue();
  const soundEnabledRef = useRef(soundEnabled);
  soundEnabledRef.current = soundEnabled;

  useEffect(() => {
    const unsubscribe = subscribeToAlerts((newAlerts) => {
      setHistory((prev) => [...newAlerts, ...prev].slice(0, 100));
      setUnreadCount((prev) => prev + newAlerts.length);
      pushToasts(newAlerts);

      for (const alert of newAlerts) {
        if (alert.channels.includes("BROWSER_NOTIFICATION") && getNotificationPermission() === "granted") {
          showBrowserNotification(alert);
        }
        if (alert.channels.includes("SOUND") && soundEnabledRef.current) {
          playAlertSound(alert);
        }
      }
    });
    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <AlertBell
        alerts={history}
        unreadCount={unreadCount}
        onOpen={() => setUnreadCount(0)}
        soundEnabled={soundEnabled}
        onToggleSound={setSoundEnabled}
      />
      <AlertToastStack toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
