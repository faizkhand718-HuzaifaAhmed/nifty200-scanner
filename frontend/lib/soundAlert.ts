import type { Alert } from "./alerts";

/**
 * Plays a short alert tone using the Web Audio API's oscillator - no
 * bundled audio file needed (and none was fetchable in this sandbox
 * anyway, no network). A user gesture is generally required before any
 * audio can play in modern browsers, so the first call should follow a
 * click (e.g. enabling sound in alert settings).
 *
 * Different alert "weights" get different tones so a target-hit doesn't
 * sound identical to a stop-loss - a two-tone rising chime for good
 * outcomes (TARGET), a single lower tone for bad outcomes (STOP_LOSS),
 * a short neutral blip for everything else.
 */

let sharedContext: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
  if (!AudioContextClass) return null;
  if (!sharedContext) sharedContext = new AudioContextClass();
  return sharedContext;
}

function playTone(ctx: AudioContext, frequency: number, startOffset: number, duration: number, gainValue = 0.15) {
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = "sine";
  oscillator.frequency.value = frequency;
  gain.gain.value = gainValue;
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  const startTime = ctx.currentTime + startOffset;
  oscillator.start(startTime);
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
  oscillator.stop(startTime + duration);
}

export function playAlertSound(alert: Alert): void {
  const ctx = getAudioContext();
  if (!ctx) return;

  if (alert.alertType === "TARGET") {
    playTone(ctx, 660, 0, 0.15);
    playTone(ctx, 880, 0.12, 0.2);
  } else if (alert.alertType === "STOP_LOSS") {
    playTone(ctx, 220, 0, 0.35, 0.18);
  } else {
    playTone(ctx, 520, 0, 0.12);
  }
}
