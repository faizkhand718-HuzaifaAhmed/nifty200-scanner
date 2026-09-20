import type { Alert } from "./alerts";
import { ALERT_TYPE_LABELS } from "./alerts";

/**
 * Thin wrapper around the browser's Notification API. Permission must be
 * requested from a user gesture (a click) - browsers reject silent
 * auto-requests on page load, so callers should invoke
 * requestNotificationPermission() from a button handler, not on mount.
 */

export type NotificationPermissionState = "default" | "granted" | "denied" | "unsupported";

export function getNotificationPermission(): NotificationPermissionState {
  if (typeof window === "undefined" || !("Notification" in window)) return "unsupported";
  return Notification.permission as NotificationPermissionState;
}

export async function requestNotificationPermission(): Promise<NotificationPermissionState> {
  if (typeof window === "undefined" || !("Notification" in window)) return "unsupported";
  const result = await Notification.requestPermission();
  return result as NotificationPermissionState;
}

export function showBrowserNotification(alert: Alert): void {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;

  const title = `${alert.symbol} — ${ALERT_TYPE_LABELS[alert.alertType]}`;
  new Notification(title, {
    body: alert.message,
    tag: alert.id, // same tag replaces rather than stacks, extra duplicate protection at the browser level
    silent: true, // the SOUND channel handles audio separately - avoid double-notifying with the OS's own sound too
  });
}
