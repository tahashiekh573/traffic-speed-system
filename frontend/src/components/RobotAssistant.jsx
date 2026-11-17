import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Mic, MicOff, Send, Volume2, VolumeX, X, Trash2 } from "lucide-react";
import RobotFace from "./RobotFace";
import { useSpeech } from "../hooks/useSpeech";
import {
  ROBOT_NAME,
  SUGGESTIONS,
  announce,
  reply,
  welcomeMessage,
} from "../assistant/assistantBrain";

const THINK_DELAY_MS = 420;

function readPref(key, fallback) {
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function writePref(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode) — preference just isn't remembered */
  }
}

let messageId = 0;
const makeMessage = (from, text) => ({
  id: ++messageId,
  from,
  text,
  time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
});

/**
 * Floating voice assistant. Talks (speechSynthesis), listens
 * (SpeechRecognition) and answers from the live analysis context.
 */
export default function RobotAssistant({ ctx, actions }) {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState(() => readPref("raftaar.lang", "ur"));
  const [voiceOn, setVoiceOn] = useState(() => readPref("raftaar.voice", "on") === "on");
  const [messages, setMessages] = useState(() => [makeMessage("bot", welcomeMessage(readPref("raftaar.lang", "ur")))]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [unread, setUnread] = useState(0);
  const [bubble, setBubble] = useState("");

  const speech = useSpeech(lang);
  const listRef = useRef(null);
  const inputRef = useRef(null);
  const ctxRef = useRef(ctx);
  useLayoutEffect(() => {
    ctxRef.current = ctx;
  });

  useEffect(() => writePref("raftaar.lang", lang), [lang]);
  useEffect(() => writePref("raftaar.voice", voiceOn ? "on" : "off"), [voiceOn]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking, open]);

  useEffect(() => {
    if (!open) return undefined;
    const timer = setTimeout(() => inputRef.current?.focus(), 150);
    return () => clearTimeout(timer);
  }, [open]);

  const togglePanel = (next) => {
    setOpen(next);
    if (next) {
      setUnread(0);
      setBubble("");
    }
  };

  const botSay = useCallback(
    (text, { speakIt = true } = {}) => {
      if (!text) return;
      setMessages((list) => [...list.slice(-60), makeMessage("bot", text)]);
      if (speakIt && voiceOn) speech.speak(text);
      if (!open) {
        setUnread((n) => n + 1);
        setBubble(text);
      }
    },
    [voiceOn, speech, open]
  );

  const runAction = useCallback(
    (action) => {
      if (action === "analyze") actions.analyze();
      if (action === "pick_file") actions.pickFile();
      if (action === "show_output") actions.showOutput();
      if (action === "refresh_stats") {
        actions.refreshStats().then((stats) => {
          if (stats) botSay(reply("total history", { ...ctxRef.current, stats }, lang).text);
        });
      }
    },
    [actions, botSay, lang]
  );

  const send = useCallback(
    (text) => {
      const message = String(text || "").trim();
      if (!message) return;

      setMessages((list) => [...list.slice(-60), makeMessage("user", message)]);
      setDraft("");
      setThinking(true);

      setTimeout(() => {
        const answer = reply(message, ctxRef.current, lang);
        setThinking(false);
        if (answer.action === "stop_speaking") {
          speech.stopSpeaking();
          setMessages((list) => [...list, makeMessage("bot", answer.text)]);
          return;
        }
        botSay(answer.text);
        if (answer.action) runAction(answer.action);
      }, THINK_DELAY_MS);
    },
    [lang, speech, botSay, runAction]
  );

  /* ---------------- automatic announcements ---------------- */
  const announced = useRef({});
  const status = ctx.progress?.status;

  useEffect(() => {
    if (ctx.fileName && announced.current.file !== ctx.fileName) {
      announced.current = { file: ctx.fileName };
      botSay(announce("selected", ctxRef.current, lang), { speakIt: false });
    }
    if (!ctx.fileName) announced.current = {};
  }, [ctx.fileName, botSay, lang]);

  useEffect(() => {
    if (status === "uploading" && !announced.current.started) {
      announced.current.started = true;
      announced.current.done = false;
      announced.current.error = null;
      botSay(announce("started", ctxRef.current, lang));
    }
  }, [status, botSay, lang]);

  useEffect(() => {
    if (ctx.result && !announced.current.done) {
      announced.current.done = true;
      announced.current.started = false;
      botSay(announce("completed", ctxRef.current, lang));
    }
  }, [ctx.result, botSay, lang]);

  useEffect(() => {
    if (ctx.error && announced.current.error !== ctx.error) {
      announced.current.error = ctx.error;
      announced.current.started = false;
      botSay(announce("failed", ctxRef.current, lang));
    }
  }, [ctx.error, botSay, lang]);

  const offlineWarned = useRef(false);
  useEffect(() => {
    if (ctx.backendOnline === false && !offlineWarned.current) {
      offlineWarned.current = true;
      botSay(announce("offline", ctxRef.current, lang), { speakIt: false });
    }
    if (ctx.backendOnline) offlineWarned.current = false;
  }, [ctx.backendOnline, botSay, lang]);

  /* ---------------- voice input ---------------- */
  const toggleMic = () => {
    if (speech.isListening) {
      speech.stopListening();
      return;
    }
    speech.listen((finalText) => send(finalText));
  };

  const switchLang = (next) => {
    if (next === lang) return;
    speech.stopSpeaking();
    setLang(next);
    setMessages((list) => [...list, makeMessage("bot", welcomeMessage(next))]);
  };

  const mood = speech.isListening
    ? "listening"
    : thinking
      ? "thinking"
      : speech.isSpeaking
        ? "speaking"
        : ctx.isProcessing
          ? "thinking"
          : ctx.error
            ? "alert"
            : ctx.result
              ? ctx.result.violations_saved
                ? "alert"
                : "happy"
              : "idle";

  return (
    <>
      <AnimatePresence>
        {!open && bubble && (
          <motion.button
            className="robot-bubble"
            initial={{ opacity: 0, y: 12, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8 }}
            onClick={() => togglePanel(true)}
          >
            {bubble.length > 140 ? `${bubble.slice(0, 140)}…` : bubble}
          </motion.button>
        )}
      </AnimatePresence>

      <motion.button
        className={`robot-fab ${open ? "is-open" : ""}`}
        onClick={() => togglePanel(!open)}
        aria-label={open ? "Close assistant" : `Open ${ROBOT_NAME} assistant`}
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.95 }}
      >
        {open ? <X size={24} /> : <RobotFace mood={mood} size={54} />}
        {!open && unread > 0 && <span className="robot-fab-badge">{unread}</span>}
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.section
            className="robot-panel"
            role="dialog"
            aria-label={`${ROBOT_NAME} assistant`}
            initial={{ opacity: 0, y: 30, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
          >
            <header className="robot-panel-head">
              <RobotFace mood={mood} size={64} />
              <div className="robot-panel-title">
                <strong>{ROBOT_NAME}</strong>
                <span className={`robot-state state-${mood}`}>
                  {{
                    listening: lang === "ur" ? "Sun raha hoon…" : "Listening…",
                    thinking: lang === "ur" ? "Soch raha hoon…" : "Thinking…",
                    speaking: lang === "ur" ? "Bol raha hoon…" : "Speaking…",
                    alert: lang === "ur" ? "Violations mili!" : "Violations found",
                    happy: lang === "ur" ? "Sab theek!" : "All clear",
                    idle: lang === "ur" ? "Online" : "Online",
                  }[mood]}
                </span>
              </div>

              <div className="robot-panel-tools">
                <div className="lang-switch" role="group" aria-label="Language">
                  <button className={lang === "ur" ? "active" : ""} onClick={() => switchLang("ur")}>
                    UR
                  </button>
                  <button className={lang === "en" ? "active" : ""} onClick={() => switchLang("en")}>
                    EN
                  </button>
                </div>
                <button
                  className="icon-btn"
                  onClick={() => {
                    if (voiceOn) speech.stopSpeaking();
                    setVoiceOn((v) => !v);
                  }}
                  title={voiceOn ? "Mute voice" : "Unmute voice"}
                  disabled={!speech.canSpeak}
                >
                  {voiceOn && speech.canSpeak ? <Volume2 size={17} /> : <VolumeX size={17} />}
                </button>
                <button
                  className="icon-btn"
                  title="Clear chat"
                  onClick={() => setMessages([makeMessage("bot", welcomeMessage(lang))])}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </header>

            <div className="robot-messages" ref={listRef}>
              {messages.map((message) => (
                <div key={message.id} className={`chat-row from-${message.from}`}>
                  <div className="chat-bubble">
                    <p>{message.text}</p>
                    <time>{message.time}</time>
                  </div>
                  {message.from === "bot" && speech.canSpeak && (
                    <button className="replay-btn" title="Speak again" onClick={() => speech.speak(message.text)}>
                      <Volume2 size={13} />
                    </button>
                  )}
                </div>
              ))}
              {thinking && (
                <div className="chat-row from-bot">
                  <div className="chat-bubble typing">
                    <span /><span /><span />
                  </div>
                </div>
              )}
            </div>

            <div className="robot-suggestions">
              {SUGGESTIONS[lang].map((text) => (
                <button key={text} onClick={() => send(text)}>
                  {text}
                </button>
              ))}
            </div>

            {(speech.isListening || speech.listenError) && (
              <div className={`listen-strip ${speech.listenError ? "has-error" : ""}`}>
                {speech.listenError ? (
                  speech.listenError
                ) : (
                  <>
                    <span className="wave"><i /><i /><i /><i /><i /></span>
                    {speech.interim || (lang === "ur" ? "Boliye…" : "Go ahead, I'm listening…")}
                  </>
                )}
              </div>
            )}

            <form
              className="robot-input"
              onSubmit={(event) => {
                event.preventDefault();
                send(draft);
              }}
            >
              <button
                type="button"
                className={`mic-btn ${speech.isListening ? "live" : ""}`}
                onClick={toggleMic}
                disabled={!speech.canListen}
                title={speech.canListen ? (speech.isListening ? "Stop listening" : "Speak") : "Voice input needs Chrome or Edge"}
              >
                {speech.canListen ? <Mic size={18} /> : <MicOff size={18} />}
              </button>
              <input
                ref={inputRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={lang === "ur" ? "Poochiye… e.g. result batao" : "Ask me… e.g. what's the result?"}
                aria-label="Message the assistant"
              />
              <button type="submit" className="send-btn" disabled={!draft.trim()} title="Send">
                <Send size={17} />
              </button>
            </form>
          </motion.section>
        )}
      </AnimatePresence>
    </>
  );
}
