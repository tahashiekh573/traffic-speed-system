import { useCallback, useEffect, useRef, useState } from "react";

/*
 * Thin wrapper over the browser Web Speech API.
 *   - speechSynthesis      -> the robot talks
 *   - SpeechRecognition    -> the robot listens (Chrome / Edge)
 * No external service or package is used.
 */

const RECOGNITION_LANG = { en: "en-US", ur: "ur-PK" };

// Replies in "ur" mode are Roman Urdu, which Hindi / Indian-English
// voices pronounce far better than Latin-unaware Urdu voices.
const VOICE_PREFERENCE = {
  en: ["en-US", "en-GB", "en-IN", "en"],
  ur: ["hi-IN", "en-IN", "ur-PK", "ur", "en"],
};

function getRecognitionClass() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function pickVoice(voices, language) {
  for (const prefix of VOICE_PREFERENCE[language] || VOICE_PREFERENCE.en) {
    const match =
      voices.find((v) => v.lang?.toLowerCase().startsWith(prefix.toLowerCase()) && /natural|online|google/i.test(v.name)) ||
      voices.find((v) => v.lang?.toLowerCase().startsWith(prefix.toLowerCase()));
    if (match) return match;
  }
  return voices[0] || null;
}

// Remove emoji / symbols so the voice reads cleanly.
function speakable(text) {
  return String(text)
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, "")
    .replace(/km\/h/gi, " kilometre per hour")
    .replace(/[#*_`•]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function useSpeech(language) {
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;
  const canListen = Boolean(getRecognitionClass());

  const [voices, setVoices] = useState([]);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [listenError, setListenError] = useState("");
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (!canSpeak) return undefined;
    const load = () => setVoices(window.speechSynthesis.getVoices());
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", load);
      window.speechSynthesis.cancel();
    };
  }, [canSpeak]);

  const stopSpeaking = useCallback(() => {
    if (!canSpeak) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, [canSpeak]);

  const speak = useCallback(
    (text) => {
      if (!canSpeak || !text) return;
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(speakable(text));
      const voice = pickVoice(voices, language);
      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      }
      utterance.rate = 1.02;
      utterance.pitch = 1.08;
      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);

      window.speechSynthesis.speak(utterance);
    },
    [canSpeak, voices, language]
  );

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const listen = useCallback(
    (onFinalText) => {
      const Recognition = getRecognitionClass();
      if (!Recognition) {
        setListenError("Voice input is not supported in this browser. Use Chrome or Edge.");
        return;
      }

      recognitionRef.current?.abort();
      stopSpeaking();

      const recognition = new Recognition();
      recognition.lang = RECOGNITION_LANG[language] || "en-US";
      recognition.interimResults = true;
      recognition.continuous = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setListenError("");
        setInterim("");
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        let finalText = "";
        let partial = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += transcript;
          else partial += transcript;
        }
        setInterim(partial);
        if (finalText.trim()) onFinalText(finalText.trim());
      };

      recognition.onerror = (event) => {
        const messages = {
          "not-allowed": "Microphone permission denied. Browser settings mein mic allow karein.",
          "no-speech": "Kuch sunai nahi diya — dobara try karein.",
          "audio-capture": "Koi microphone nahi mila.",
          network: "Speech service tak network nahi pohanch saka.",
        };
        if (event.error !== "aborted") {
          setListenError(messages[event.error] || `Voice error: ${event.error}`);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        setInterim("");
      };

      recognitionRef.current = recognition;
      try {
        recognition.start();
      } catch {
        setIsListening(false);
      }
    },
    [language, stopSpeaking]
  );

  useEffect(() => () => recognitionRef.current?.abort(), []);

  return {
    canSpeak,
    canListen,
    isSpeaking,
    isListening,
    interim,
    listenError,
    speak,
    stopSpeaking,
    listen,
    stopListening,
  };
}
