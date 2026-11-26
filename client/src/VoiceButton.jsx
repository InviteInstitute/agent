import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";

// Ask out loud: tap to record, tap again to send. The browser records WebM/Opus, which the
// server's speech-to-text takes as is, and stops on its own after MAX_SECONDS.

export const MAX_SECONDS = 30;

export function canRecord() {
  return Boolean(
    typeof window !== "undefined" && window.MediaRecorder && navigator.mediaDevices?.getUserMedia,
  );
}

export default function VoiceButton({ disabled, onStart, onRecorded, onError }) {
  const [seconds, setSeconds] = useState(null);
  const recorder = useRef(null);
  const stream = useRef(null);
  const timer = useRef(null);

  const release = () => {
    clearInterval(timer.current);
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  };

  // Leaving mid-recording frees the microphone and sends nothing.
  useEffect(
    () => () => {
      if (recorder.current?.state === "recording") {
        recorder.current.onstop = null;
        recorder.current.stop();
      }
      release();
    },
    [],
  );

  const stop = () => recorder.current?.state === "recording" && recorder.current.stop();

  const start = async () => {
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError("The microphone is blocked. Allow it in your browser, or type your question.");
      return;
    }
    const chunks = [];
    const rec = new MediaRecorder(stream.current);
    rec.ondataavailable = (event) => event.data.size && chunks.push(event.data);
    rec.onstop = () => {
      release();
      setSeconds(null);
      const recording = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      if (recording.size) onRecorded(recording);
    };
    recorder.current = rec;
    rec.start();
    setSeconds(0);
    onStart?.();
    const began = Date.now();
    timer.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - began) / 1000);
      setSeconds(elapsed);
      if (elapsed >= MAX_SECONDS) stop();
    }, 250);
  };

  const recording = seconds !== null;
  const clock = `0:${String(seconds).padStart(2, "0")}`;
  return (
    <button
      type="button"
      className="square-button voice-button"
      aria-label={recording ? `Stop and send (${clock})` : "Ask out loud"}
      title={recording ? "Stop and send" : "Ask out loud"}
      onClick={recording ? stop : start}
      disabled={disabled && !recording}
      aria-pressed={recording}
    >
      {recording ? (
        <>
          <Square size={14} fill="currentColor" aria-hidden="true" />
          <span aria-hidden="true">{clock}</span>
        </>
      ) : (
        <Mic size={20} aria-hidden="true" />
      )}
    </button>
  );
}
