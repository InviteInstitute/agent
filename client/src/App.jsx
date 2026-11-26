import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Eye,
  EyeOff,
  LifeBuoy,
  LogOut,
  MessageCircle,
  Minus,
  Volume2,
  VolumeX,
} from "lucide-react";
import { api, readStored, writeStored } from "./api.js";
import Avatar, { avatarInstalled } from "./Avatar.jsx";
import Chat from "./Chat.jsx";
import Panel from "./Panel.jsx";
import Research, { PRODUCTION_SETTINGS, describeOverrides, overridesFor } from "./Research.jsx";
import SignIn from "./SignIn.jsx";
import VoiceButton, { canRecord } from "./VoiceButton.jsx";
import { Notice, Spinner } from "./ui.jsx";

const STUDENT_KEY = "agent:student";
const SETTINGS_KEY = "agent:settings";
const MUTED_KEY = "agent:muted";
const TUTOR_KEY = "agent:tutor";
// While the agent cannot see a student's code yet, it checks again this often.
const WAITING_POLL_MS = 10000;

// The Research view is for the team, at /research. Students use / and never see it.
export function researchMode(path = window.location.pathname) {
  return path.replace(/\/+$/, "") === "/research";
}
const DELAYED = "The agent ran into a delay. Try asking again in a moment.";

// A message as the server keeps it, the way the chat shows it.
export const fromServer = (m) => ({
  id: `m${m.id}`,
  role: m.role,
  origin: m.origin,
  body: m.body,
  responseId: m.response_id,
  thumb: m.thumb,
  speech: m.speech || null,
});

export default function App() {
  const [site, setSite] = useState(null);
  const [siteError, setSiteError] = useState("");
  const [student, setStudent] = useState(() => readStored(sessionStorage, STUDENT_KEY, null));
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [signingIn, setSigningIn] = useState(false);
  const [signInError, setSignInError] = useState("");
  const [busy, setBusy] = useState(false);
  // /research opens on the Research view, since that is what the team comes there for.
  const [view, setView] = useState(() => (researchMode() ? "research" : "chat"));
  const [settings, setSettings] = useState(() => ({
    ...PRODUCTION_SETTINGS,
    ...readStored(localStorage, SETTINGS_KEY, {}),
  }));
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState("");
  const [tokens, setTokens] = useState(null);
  const [open, setOpen] = useState(true);
  const [seen, setSeen] = useState(0);
  const [moving, setMoving] = useState(false);
  const [panelRect, setPanelRect] = useState(null);
  // The 3D tutor, once its Unity build is installed. Showing it and its voice are choices per
  // browser, so a quiet classroom stays quiet and a slow computer can hide it.
  const [avatar, setAvatar] = useState(false);
  const [tutorShown, setTutorShown] = useState(
    () => readStored(localStorage, TUTOR_KEY, true) !== false,
  );
  const [muted, setMuted] = useState(() => readStored(localStorage, MUTED_KEY, false) === true);
  const [hush, setHush] = useState(0);
  const [voiceError, setVoiceError] = useState("");

  const [research] = useState(() => researchMode());
  // Research settings only ever apply in research mode, so a student never gets them.
  const overrides = research ? overridesFor(settings, config) : null;
  const custom = research && JSON.stringify(settings) !== JSON.stringify(PRODUCTION_SETTINGS);
  const chat = overrides ? "research" : "student";

  // The gate shows its challenge at page load rather than at the student's first question.
  useEffect(() => {
    api.ping().catch(() => {});
    api.environments().then(setSite, (error) => setSiteError(error.message));
  }, []);

  useEffect(() => writeStored(localStorage, SETTINGS_KEY, settings), [settings]);
  useEffect(() => writeStored(localStorage, MUTED_KEY, muted), [muted]);
  useEffect(() => writeStored(localStorage, TUTOR_KEY, tutorShown), [tutorShown]);
  useEffect(() => {
    avatarInstalled().then(setAvatar);
  }, []);

  const loadConfig = useCallback(() => {
    setConfigError("");
    api.researchConfig().then(
      (c) => {
        setConfig(c);
        setTokens(c.session_tokens);
      },
      (error) => setConfigError(error.message),
    );
  }, []);

  // Saved custom settings need the config to become overrides, so the chat loads it too.
  useEffect(() => {
    if (student && (view === "research" || custom) && !config && !configError) loadConfig();
  }, [student, view, custom, config, configError, loadConfig]);

  const signIn = useCallback(
    async (who) => {
      setSigningIn(true);
      setSignInError("");
      try {
        const data = await api.signIn(who, chat);
        writeStored(sessionStorage, STUDENT_KEY, who);
        setStudent(who);
        setSession({ frame: data.frame, sessionId: data.session_id, playground: data.playground });
        setMessages(data.messages.map(fromServer));
      } catch (error) {
        setSignInError(error.message);
        if (error.status === 404 || error.status === 400) {
          writeStored(sessionStorage, STUDENT_KEY, null);
          setStudent(null);
        }
      } finally {
        setSigningIn(false);
      }
    },
    [chat],
  );

  // A reload signs the same student back in and shows their chat again.
  useEffect(() => {
    if (site && student && !session && !signingIn && !signInError) signIn(student);
  }, [site, student, session, signingIn, signInError, signIn]);

  // Check-ins come from the server on its own, so it keeps a copy of the research settings.
  // Sent once per sign-in and per change, not after every message.
  const live = Boolean(session);
  const savedOverrides = JSON.stringify(overrides);
  useEffect(() => {
    if (!live || (custom && !config)) return;
    api.saveSettings(student, JSON.parse(savedOverrides)).catch(() => {});
  }, [live, student, savedOverrides, custom, config]);

  // Until the agent can see the student's code, it looks again every few seconds, so the
  // walkthrough ticks off "run your program" on its own.
  const waiting = live && !session.sessionId;
  useEffect(() => {
    if (!waiting) return undefined;
    const timer = setInterval(() => {
      api.signIn(student, chat).then(
        (data) =>
          data.session_id &&
          setSession((s) => ({ ...s, sessionId: data.session_id, playground: data.playground })),
        () => {},
      );
    }, WAITING_POLL_MS);
    return () => clearInterval(timer);
  }, [waiting, student, chat]);

  // Check-ins arrive while the student works. One already shown (after a reconnect) is skipped.
  useEffect(() => {
    if (!live) return undefined;
    const source = api.checkins(student, (c) => {
      const message = fromServer({ ...c, role: "agent", origin: "proactive", thumb: null });
      setMessages((list) => (list.some((m) => m.id === message.id) ? list : [...list, message]));
    });
    return () => source?.close();
  }, [live, student]);

  const signOut = () => {
    writeStored(sessionStorage, STUDENT_KEY, null);
    setStudent(null);
    setSession(null);
    setMessages([]);
    setView("chat");
  };

  const ask = async (text) => {
    const studentTurn = { id: crypto.randomUUID(), role: "student", body: text || "Help" };
    const pending = { id: crypto.randomUUID(), role: "agent", body: "", pending: true };
    setMessages((list) => [...list, studentTurn, pending]);
    setBusy(true);
    try {
      const data = await api.turn(student, {
        message: text,
        overrides,
        speak: avatar && tutorShown && !muted,
      });
      const reply = data.reply;
      setMessages((list) =>
        list.map((m) =>
          m.id === pending.id
            ? {
                id: reply.response_id || pending.id,
                role: "agent",
                origin: "reactive",
                body: reply.body,
                responseId: reply.response_id,
                speech: reply.speech || null,
                model: reply.model,
                prompt: reply.prompt,
                tokens: reply.tokens,
              }
            : m,
        ),
      );
      if (data.session_id) {
        setSession((s) => ({
          ...s,
          sessionId: data.session_id,
          playground: data.playground || s.playground,
        }));
      }
      if (data.session_tokens) setTokens(data.session_tokens);
    } catch (error) {
      const message = error.status === 429 || error.status === 502 ? error.message : DELAYED;
      setMessages((list) =>
        list.map((m) =>
          m.id === pending.id ? { ...m, pending: false, failed: true, body: message } : m,
        ),
      );
    } finally {
      setBusy(false);
    }
  };

  // A spoken question becomes text first, then is asked like a typed one, so the student sees
  // exactly what the tutor heard.
  const askAloud = async (recording) => {
    setVoiceError("");
    setBusy(true);
    let text = "";
    try {
      text = (await api.transcribe(student, recording)).text.trim();
    } catch (error) {
      setVoiceError(error.message);
    } finally {
      setBusy(false);
    }
    if (text) ask(text);
    else
      setVoiceError(
        (current) => current || "I didn't catch that. Try again closer to the mic, or type it.",
      );
  };

  const rate = async (message, thumb, comment) => {
    await api.rate(student, { response_id: message.responseId, thumb, comment: comment || null });
    setMessages((list) => list.map((m) => (m.id === message.id ? { ...m, thumb } : m)));
  };

  const agentReplies = messages.filter((m) => m.role === "agent" && !m.pending).length;
  const unseen = open ? 0 : Math.max(0, agentReplies - seen);
  const collapse = () => {
    setSeen(agentReplies);
    setOpen(false);
  };

  const environment = useMemo(
    () => site?.environments.find((e) => e.id === student?.environment),
    [site, student],
  );
  // Before sign-in, a site with one environment shows it if it can be framed without IDs.
  const frame =
    session?.frame ?? (site?.environments.length === 1 ? site.environments[0].frame : null);
  const signedIn = Boolean(student && session);
  // What the tutor says: the newest finished reply or check-in.
  const latest = [...messages].reverse().find((m) => m.role === "agent" && !m.pending && !m.failed);
  const utterance = latest
    ? {
        id: latest.id,
        text: latest.body,
        parts: latest.speech?.length ? latest.speech : [latest.body],
      }
    : null;

  if (siteError) {
    return (
      <main className="agent-shell agent-screen dotted">
        <Notice kind="error" title="The agent is not reachable">
          {siteError}
        </Notice>
      </main>
    );
  }
  if (!site)
    return (
      <main className="agent-shell agent-screen dotted">
        <Spinner label="Loading the agent…" />
      </main>
    );

  // The title bar: the name, the student in ZANY's ID pill, sign out and collapse.
  const header = (
    <>
      <h1 className="agent-panel__title">INVITE Agent</h1>
      {signedIn ? (
        <div
          className="id-pill"
          title={[
            `Student ID ${student.studentId}`,
            environment?.needs_class_code ? `Class ${student.classCode}` : null,
            `Session ${session.sessionId || "not started"}`,
          ]
            .filter(Boolean)
            .join("\n")}
        >
          <span>Student ID</span>
          <strong>{student.studentId}</strong>
        </div>
      ) : null}
      <span className="agent-panel__spacer" />
      {signedIn ? (
        <button
          type="button"
          className="title-button"
          aria-label="Sign out"
          title="Sign out"
          onClick={signOut}
        >
          <LogOut size={19} aria-hidden="true" />
        </button>
      ) : null}
      <button
        type="button"
        className="title-button"
        aria-label="Collapse chat"
        title="Collapse chat"
        onClick={collapse}
      >
        <Minus size={22} aria-hidden="true" />
      </button>
    </>
  );

  // The tool bar under it, like ZANY's Code bar: Help, and the tutor's switches.
  const toolbar = signedIn ? (
    <>
      <button type="button" className="help-pill" onClick={() => ask("")} disabled={busy}>
        <LifeBuoy size={16} strokeWidth={2.4} aria-hidden="true" />
        Help
      </button>
      <p
        className={session.sessionId ? "code-status code-status--seen" : "code-status"}
        title={
          session.sessionId
            ? "The agent can see your code."
            : "Run your program once so the agent can see your code."
        }
      >
        <span className="code-status__dot" aria-hidden="true" />
        <span className="code-status__text">
          {session.sessionId
            ? `Watching ${session.playground || "your code"}`
            : "Can't see your code yet"}
        </span>
      </p>
      {avatar && tutorShown ? (
        <button
          type="button"
          className="square-button"
          aria-label={muted ? "Turn the tutor's voice on" : "Mute the tutor"}
          title={muted ? "Turn the tutor's voice on" : "Mute the tutor"}
          aria-pressed={muted}
          onClick={() => setMuted((m) => !m)}
        >
          {muted ? (
            <VolumeX size={19} aria-hidden="true" />
          ) : (
            <Volume2 size={19} aria-hidden="true" />
          )}
        </button>
      ) : null}
      {avatar ? (
        <button
          type="button"
          className="square-button"
          aria-label={tutorShown ? "Hide the tutor" : "Show the tutor"}
          title={tutorShown ? "Hide the tutor" : "Show the tutor"}
          aria-pressed={!tutorShown}
          onClick={() => setTutorShown((shown) => !shown)}
        >
          {tutorShown ? (
            <Eye size={19} aria-hidden="true" />
          ) : (
            <EyeOff size={19} aria-hidden="true" />
          )}
        </button>
      ) : null}
    </>
  ) : null;

  const footer =
    signedIn && research ? (
      <div className="halves" role="group" aria-label="View">
        <button type="button" aria-pressed={view === "chat"} onClick={() => setView("chat")}>
          Chat
        </button>
        <button
          type="button"
          aria-pressed={view === "research"}
          onClick={() => setView("research")}
        >
          Research
        </button>
      </div>
    ) : null;

  return (
    <main className="agent-shell">
      {frame ? (
        <iframe
          className={`environment-frame ${moving ? "environment-frame--inert" : ""}`}
          src={frame}
          title={environment?.name || site.environments[0].name}
          allow="fullscreen"
        />
      ) : (
        <div className="environment-placeholder dotted">
          <p>Your coding space opens here once you sign in.</p>
        </div>
      )}

      {avatar ? (
        <Avatar
          panel={open ? panelRect : null}
          visible={signedIn && tutorShown}
          utterance={signedIn ? utterance : null}
          muted={muted}
          hush={hush}
        />
      ) : null}

      {open ? (
        <Panel
          label="INVITE Agent chat"
          header={header}
          toolbar={toolbar}
          footer={footer}
          resizable={signedIn}
          onMoving={setMoving}
          onRect={setPanelRect}
        >
          {!signedIn ? (
            student && !signInError ? (
              <div className="sign-in">
                <Spinner label="Finding your session…" />
              </div>
            ) : (
              <SignIn
                environments={site.environments}
                onSignIn={signIn}
                pending={signingIn}
                error={signInError}
              />
            )
          ) : view === "research" ? (
            <Research
              config={config}
              error={configError}
              onRetry={loadConfig}
              settings={settings}
              onChange={setSettings}
              tokens={tokens}
            />
          ) : (
            <Chat
              messages={messages}
              guide={{
                environment: student.environment,
                studentId: student.studentId,
                seesCode: Boolean(session.sessionId),
              }}
              onSend={ask}
              onRate={rate}
              busy={busy}
              customNote={overrides ? `Custom agent: ${describeOverrides(overrides)}.` : ""}
              notice={voiceError}
              composerExtra={
                site.voice && canRecord() ? (
                  <VoiceButton
                    disabled={busy}
                    onStart={() => {
                      setVoiceError("");
                      setHush((n) => n + 1);
                    }}
                    onRecorded={askAloud}
                    onError={setVoiceError}
                  />
                ) : null
              }
            />
          )}
        </Panel>
      ) : (
        <button type="button" className="agent-launcher" onClick={() => setOpen(true)}>
          <MessageCircle size={20} strokeWidth={2.4} aria-hidden="true" />
          Open chat
          {unseen ? <span className="agent-launcher__count">{unseen} new</span> : null}
        </button>
      )}
    </main>
  );
}
