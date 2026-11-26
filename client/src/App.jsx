import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Button,
  ContentSwitcher,
  IconButton,
  InlineNotification,
  Loading,
  Switch,
  Tag,
} from "@carbon/react";
import {
  Chat as ChatIcon,
  Help,
  Logout,
  Minimize,
  VolumeMute,
  VolumeUp,
} from "@carbon/icons-react";
import { api, readStored, writeStored } from "./api.js";
import Avatar, { avatarInstalled } from "./Avatar.jsx";
import Chat from "./Chat.jsx";
import Panel from "./Panel.jsx";
import Research, { PRODUCTION_SETTINGS, describeOverrides, overridesFor } from "./Research.jsx";
import SignIn from "./SignIn.jsx";
import VoiceButton, { canRecord } from "./VoiceButton.jsx";

const STUDENT_KEY = "agent:student";
const SETTINGS_KEY = "agent:settings";
const MUTED_KEY = "agent:muted";
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
  const [view, setView] = useState("chat");
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
  // The 3D tutor, when the site has it and a build is installed. Its voice is a choice per
  // browser, so a quiet classroom stays quiet.
  const [avatar, setAvatar] = useState(false);
  const [muted, setMuted] = useState(() => readStored(localStorage, MUTED_KEY, false) === true);
  const [hush, setHush] = useState(0);
  const [voiceError, setVoiceError] = useState("");

  const overrides = overridesFor(settings, config);
  const custom = JSON.stringify(settings) !== JSON.stringify(PRODUCTION_SETTINGS);
  const chat = overrides ? "research" : "student";

  // The gate shows its challenge at page load rather than at the student's first question.
  useEffect(() => {
    api.ping().catch(() => {});
    api.environments().then(setSite, (error) => setSiteError(error.message));
  }, []);

  useEffect(() => writeStored(localStorage, SETTINGS_KEY, settings), [settings]);
  useEffect(() => writeStored(localStorage, MUTED_KEY, muted), [muted]);
  useEffect(() => {
    if (site?.avatar) avatarInstalled().then(setAvatar);
  }, [site]);

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
  const savedOverrides = JSON.stringify(overrides);
  useEffect(() => {
    if (!session || (custom && !config)) return;
    api.saveSettings(student, JSON.parse(savedOverrides)).catch(() => {});
  }, [session, student, savedOverrides, custom, config]);

  // Check-ins arrive while the student works. One already shown (after a reconnect) is skipped.
  const live = Boolean(session);
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
      const data = await api.turn(student, { message: text, overrides, speak: avatar && !muted });
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
      if (data.session_id) setSession((s) => ({ ...s, sessionId: data.session_id }));
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
      <main className="agent-shell agent-shell--message">
        <InlineNotification
          kind="error"
          title="The agent is not reachable"
          subtitle={siteError}
          hideCloseButton
        />
      </main>
    );
  }
  if (!site) return <Loading description="Loading the agent" withOverlay={false} />;

  const header = (
    <>
      <h1 className="agent-panel__title">INVITE Agent</h1>
      {signedIn ? (
        <Tag size="sm" type="cool-gray" title={`Session ${session.sessionId || "not started"}`}>
          {environment?.needs_class_code ? `${student.classCode} / ` : ""}
          {student.studentId}
        </Tag>
      ) : null}
      <span className="agent-panel__spacer" />
      {signedIn ? (
        <>
          <Button size="sm" renderIcon={Help} onClick={() => ask("")} disabled={busy}>
            Help
          </Button>
          {avatar ? (
            <IconButton
              kind="ghost"
              size="sm"
              label={muted ? "Turn the tutor's voice on" : "Mute the tutor"}
              align="bottom"
              aria-pressed={muted}
              onClick={() => setMuted((m) => !m)}
            >
              {muted ? <VolumeMute /> : <VolumeUp />}
            </IconButton>
          ) : null}
          <IconButton kind="ghost" size="sm" label="Sign out" align="bottom" onClick={signOut}>
            <Logout />
          </IconButton>
        </>
      ) : null}
      <IconButton
        kind="ghost"
        size="sm"
        label="Collapse chat"
        align="bottom-end"
        onClick={collapse}
      >
        <Minimize />
      </IconButton>
    </>
  );

  const footer = signedIn ? (
    <ContentSwitcher
      size="sm"
      selectedIndex={view === "chat" ? 0 : 1}
      onChange={({ name }) => setView(name)}
      aria-label="View"
    >
      <Switch name="chat" text="Chat" />
      <Switch name="research" text="Research" />
    </ContentSwitcher>
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
        <div className="environment-placeholder">
          <p>Your coding space opens here once you sign in.</p>
        </div>
      )}

      {avatar ? (
        <Avatar
          panel={open ? panelRect : null}
          visible={signedIn}
          utterance={signedIn ? utterance : null}
          muted={muted}
          hush={hush}
        />
      ) : null}

      {open ? (
        <Panel
          label="INVITE Agent chat"
          header={header}
          footer={footer}
          resizable={signedIn}
          onMoving={setMoving}
          onRect={setPanelRect}
        >
          {!signedIn ? (
            student && !signInError ? (
              <Loading description="Finding your session" withOverlay={false} small />
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
        <Button className="agent-launcher" renderIcon={ChatIcon} onClick={() => setOpen(true)}>
          Open chat
          {unseen ? (
            <Tag size="sm" type="red" className="agent-launcher__count">
              {unseen} new
            </Tag>
          ) : null}
        </Button>
      )}
    </main>
  );
}
