/*
 * Rule-based assistant for the traffic dashboard.
 *
 * Deliberately NOT an LLM: it understands English, Roman Urdu and Urdu
 * script through keywords, spelling-tolerant (fuzzy) matching and a few
 * pattern parsers, and answers only from the real data the backend
 * returned. Every number it says comes from the API.
 */

export const ROBOT_NAME = "Raftaar";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

const fmt = (value, digits = 1) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? "—"
    : Number(value).toFixed(digits);

const plural = (n, one, many) => (Number(n) === 1 ? one : many);

const URDU_SCRIPT = /[؀-ۿ]/;

// Common Roman Urdu spellings collapse to one form before matching.
const SPELLING_VARIANTS = [
  [/\b(gari|gaadi|gadi|garhi|gaddi|gaarhi)\b/g, "gaari"],
  [/\b(gariyan|gadiyan|gaadiyan|garian|gaariyaan|gariyaan|gaarian|gaadian)\b/g, "gaariyan"],
  [/\b(kitny|kitnay|kitne|kitna|kitni)\b/g, "kitni"],
  [/\b(btao|bta|bata|batao|bataen|batain|batayen|bataiye|bataye|batado|bata do)\b/g, "batao"],
  [/\b(kia|kya|kiya)\b/g, "kya"],
  [/\b(hy|hai|he|hain|hen)\b/g, "hai"],
  [/\b(tez|taiz|tezz|teez)\b/g, "tez"],
  [/\b(raftar|raftaar|rftar)\b/g, "raftaar"],
  [/\b(nateeja|natija|nateja|natiija)\b/g, "natija"],
  [/\b(challan|chalan|chaalan|chalaan)\b/g, "challan"],
  [/\b(nambar|numbr|nmbr|nmber)\b/g, "number"],
  [/\b(relut|reslut|rezult|rizalt|rizult|resut|reult|rsult|reslt|resalt|reesult|rezalt)\b/g, "result"],
  [/\b(voilation|vilation|violaton|volation|voilations|vilations)\b/g, "violation"],
  [/\b(plait|plates?|plete)\b/g, "plate"],
];

function normalize(text) {
  let s = ` ${String(text)
    .toLowerCase()
    .replace(/[?!.,،؟۔:;"'()[\]{}]/g, " ")
    .replace(/\s+/g, " ")
    .trim()} `;
  for (const [pattern, replacement] of SPELLING_VARIANTS) {
    s = s.replace(pattern, replacement);
  }
  return s;
}

function editDistance(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  // Optimal string alignment: a swapped pair of letters counts as one edit.
  let before = null;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    const cur = [i];
    let rowMin = i;
    for (let j = 1; j <= b.length; j += 1) {
      cur[j] = Math.min(
        prev[j] + 1,
        cur[j - 1] + 1,
        prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)
      );
      if (before && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        cur[j] = Math.min(cur[j], before[j - 2] + 1);
      }
      rowMin = Math.min(rowMin, cur[j]);
    }
    if (rowMin > max) return max + 1;
    before = prev;
    prev = cur;
  }
  return prev[b.length];
}

/**
 * Does the message contain this keyword?
 *  - Urdu script: plain substring.
 *  - Phrases: whole-phrase match.
 *  - Single Latin words: word-prefix match, or a small spelling mistake
 *    ("relut", "reslut", "voilation", "speeed") for words of 5+ letters.
 */
function hasKeyword(normalized, tokens, keyword) {
  if (URDU_SCRIPT.test(keyword)) return normalized.includes(keyword);
  if (keyword.includes(" ")) return normalized.includes(` ${keyword} `) || normalized.includes(` ${keyword}`);

  return tokens.some((token) => {
    if (token === keyword) return true;
    if (keyword.length >= 3 && token.startsWith(keyword)) return true;
    if (keyword.length >= 5 && token.length >= 4) {
      const allowed = keyword.length >= 8 ? 2 : 1;
      return editDistance(token, keyword, allowed) <= allowed;
    }
    return false;
  });
}

/* ------------------------------------------------------------------ */
/* Intents                                                             */
/* ------------------------------------------------------------------ */

const INTENTS = [
  { id: "stop", words: ["stop", "chup", "bas karo", "ruk jao", "quiet", "shut up", "khamosh", "خاموش", "بس کرو", "رک جاؤ"] },
  { id: "analyze", words: ["analyze", "analyse", "start", "process karo", "shuru", "chalao", "scan", "begin", "check karo", "شروع", "چلاؤ"] },
  { id: "upload", words: ["upload", "select video", "video kaise", "video dalo", "video daalo", "file", "اپلوڈ", "ویڈیو کیسے"] },
  { id: "greeting", words: ["hi", "hello", "hey", "salam", "assalam", "aoa", "slam", "سلام", "ہیلو"] },
  { id: "howareyou", words: ["how are you", "kaise ho", "kaisy ho", "kese ho", "kya haal", "kia haal", "theek ho", "کیسے ہو", "کیا حال"] },
  { id: "thanks", words: ["thank", "thanks", "shukriya", "shukria", "jazak", "great", "zabardast", "wah", "nice", "شکریہ"] },
  { id: "bye", words: ["bye", "khuda hafiz", "allah hafiz", "goodbye", "خدا حافظ", "اللہ حافظ"] },
  { id: "who", words: ["who are you", "your name", "tum kaun", "ap kaun", "aap kaun", "naam kya", "kaun ho", "تم کون", "نام کیا"] },
  { id: "help", words: ["help", "madad", "kya kar sakte", "what can you", "commands", "options", "kya pooch", "مدد"] },
  { id: "error", words: ["error", "masla", "problem", "issue", "failed", "galat", "kyun nahi", "nahi chal", "مسئلہ", "خرابی"] },
  { id: "status", words: ["status", "progress", "kahan tak", "kitna hua", "kab tak", "percent", "how long", "kitni der", "ho gaya", "complete hua", "فیصد", "کہاں تک"] },
  { id: "explain", words: ["kaise kaam", "how does", "how do you", "how is", "kaise naapi", "kaise calculate", "explain", "samjhao", "samjha", "kaise", "yolo", "bytetrack", "easyocr", "کیسے"] },
  // "boost": specific questions that should beat generic words in the same sentence.
  { id: "accuracy", boost: 2, words: ["accurate", "accuracy", "sahi hai", "theek hai kya", "reliable", "durust"] },
  { id: "latest", boost: 2, words: ["latest", "last violation", "akhri", "aakhri", "recent", "sab se nayi"] },
  { id: "percent", boost: 2, words: ["percentage", "fisad", "feesad", "ratio", "kitne fisad"] },
  { id: "helmet", boost: 2, words: ["helmet", "helmit", "helmat", "hilmet", "helmets", "no helmet", "bina helmet", "without helmet", "ہیلمٹ"] },
  { id: "noplate", boost: 2, words: ["without plate", "no plate", "bina plate", "plate nahi", "unread"] },
  { id: "fastest", words: ["fastest", "maximum", "max", "highest", "top speed", "sab se tez", "sabse tez", "tez tareen", "zyada speed", "سب سے تیز"] },
  { id: "slowest", words: ["slowest", "minimum", "lowest", "sab se aahista", "sabse kam", "kam speed", "slow", "aahista", "سب سے آہستہ"] },
  { id: "average", words: ["average", "avg", "mean", "ausat", "اوسط"] },
  { id: "violations", words: ["violation", "overspeed", "over speed", "speeding", "challan", "tez", "jurmana", "khilaf", "ticket", "خلاف", "چالان", "تیز"] },
  { id: "plates", words: ["plate", "number plate", "registration", "anpr", "ocr", "پلیٹ", "نمبر"] },
  { id: "vehicles", words: ["vehicle", "car", "gaari", "gaariyan", "bus", "truck", "bike", "motorcycle", "traffic", "kitni gaari", "گاڑی", "گاڑیاں"] },
  { id: "limit", words: ["limit", "had", "allowed", "حد"] },
  { id: "speed", words: ["speed", "raftaar", "kmh", "km/h", "رفتار"] },
  { id: "history", words: ["total", "history", "database", "all time", "ab tak", "overall", "records", "sab videos", "ٹوٹل", "ریکارڈ"] },
  { id: "video", words: ["video dikhao", "output", "download", "annotated", "show video", "play", "ویڈیو دکھاؤ"] },
  { id: "duration", words: ["duration", "length", "kitni lambi", "seconds", "frames", "fps", "time laga", "der lagi", "processing time", "دورانیہ"] },
  { id: "summary", words: ["result", "summary", "report", "natija", "kya aya", "kya hua", "batao", "overview", "findings", "detail", "نتیجہ", "رزلٹ", "بتاؤ"] },
];

function detectIntent(message) {
  const normalized = normalize(message);
  const tokens = normalized.trim().split(" ").filter(Boolean);
  let best = null;

  INTENTS.forEach((intent, order) => {
    const hits = intent.words.filter((word) => hasKeyword(normalized, tokens, word));
    if (!hits.length) return;
    // Longer (more specific) matches win.
    const score = hits.reduce((sum, word) => sum + word.length, 0) * (intent.boost || 1);
    if (!best || score > best.score || (score === best.score && order < best.order)) {
      best = { id: intent.id, score, order };
    }
  });

  return best?.id || null;
}

/* ------------------------------------------------------------------ */
/* Pattern parsers                                                     */
/* ------------------------------------------------------------------ */

function findPlateMention(message, result) {
  const plates = result?.recognized_plates || [];
  if (!plates.length) return null;
  const compact = String(message).toUpperCase().replace(/[^A-Z0-9 ]/g, " ");
  const tokens = compact.split(/\s+/).filter((t) => /[A-Z]/.test(t) && /\d/.test(t));
  const joined = compact.replace(/\s+/g, "");
  return (
    plates.find((p) => tokens.includes(p.plate_number)) ||
    plates.find((p) => p.plate_number.length >= 4 && joined.includes(p.plate_number)) ||
    null
  );
}

// "gaari 7", "vehicle #12", "track 3", "id 5", "#9"
function findTrackId(message) {
  const match = normalize(message).match(
    /(?:#|\bid\s*#?|\btrack\s*#?|\bgaari\s*#?|\bvehicle\s*#?|\bcar\s*#?)\s*(\d{1,5})\b/
  );
  return match ? Number(match[1]) : null;
}

// "80 se tez", "above 70", "over 100 km/h", "more than 90", "> 80"
function findThreshold(message) {
  const s = normalize(message);
  const patterns = [
    /(\d{2,3})\s*(?:km\/?h|kmh|km)?\s*(?:se|say|sy)\s*(?:tez|zyada|ziada|upar|oopar|above)/,
    /(?:above|over|more than|greater than|faster than|>)\s*(\d{2,3})/,
  ];
  for (const pattern of patterns) {
    const match = s.match(pattern);
    if (match) return Number(match[1]);
  }
  return null;
}

const TYPE_WORDS = {
  car: ["car", "cars", "کار"],
  truck: ["truck", "trucks", "ٹرک"],
  bus: ["bus", "buses", "بس"],
  motorcycle: ["motorcycle", "motorcycles", "bike", "bikes", "motorbike", "موٹر سائیکل"],
};

function findVehicleType(message) {
  const s = normalize(message);
  for (const [type, words] of Object.entries(TYPE_WORDS)) {
    if (words.some((w) => (URDU_SCRIPT.test(w) ? s.includes(w) : new RegExp(`\\b${w}\\b`).test(s)))) {
      return type;
    }
  }
  return null;
}

function findExplainTopic(message) {
  const s = normalize(message);
  if (/helm|ہیلمٹ/.test(s)) return "helmet";
  if (/yolo|detect/.test(s)) return "yolo";
  if (/bytetrack|byte track|track|id /.test(s)) return "tracking";
  if (/plate|ocr|number|پلیٹ/.test(s)) return "ocr";
  if (/speed|raftaar|tez|رفتار/.test(s)) return "speed";
  if (/robot|tum|aap|you|raftaar bot/.test(s)) return "robot";
  return "system";
}

/* ------------------------------------------------------------------ */
/* Sentences                                                           */
/* ------------------------------------------------------------------ */

function describeVehicleMix(result) {
  const types = Object.entries(result?.vehicle_types || {});
  if (!types.length) return "";
  return types
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => `${count} ${count === 1 ? type : type === "bus" ? "buses" : `${type}s`}`)
    .join(", ");
}

export function summarize(result, lang) {
  const r = result;
  const limit = fmt(r.speed_limit_kmh, 0);
  const measured = r.speed_records?.length || 0;
  const mix = describeVehicleMix(r);
  const speeders = r.overspeed_violations ?? r.violations_saved;

  if (lang === "ur") {
    let text = `${r.filename} ka analysis mukammal ho gaya. Maine ${r.vehicles_tracked} ${plural(r.vehicles_tracked, "gaari", "gaariyan")} track ki${mix ? ` (${mix})` : ""} aur ${measured} ki speed naapi. `;
    text += speeders
      ? `${speeders} ${plural(speeders, "gaari", "gaariyan")} ${limit} km/h ki limit se tez thi — ${plural(speeders, "yeh violation", "yeh violations")} database mein save ho gayi. `
      : `Koi bhi gaari ${limit} km/h ki limit se tez nahi thi. `;
    if (r.max_speed_kmh != null) text += `Sab se tez raftaar ${fmt(r.max_speed_kmh)} km/h thi. `;
    if (r.helmet_check_enabled) {
      text += r.no_helmet_violations
        ? `${r.motorcycles_checked} motorcycles check ki, ${r.no_helmet_violations} rider bina helmet the. `
        : `${r.motorcycles_checked} motorcycles check ki — sab ne helmet pehna tha. `;
    }
    text += r.plates_identified
      ? `${r.plates_identified} number ${plural(r.plates_identified, "plate parhi gayi", "plates parhi gayin")}.`
      : r.violations_saved
        ? "Violators ki number plate parhi nahi ja saki."
        : "";
    return text.trim();
  }

  let text = `Analysis of ${r.filename} is complete. I tracked ${r.vehicles_tracked} ${plural(r.vehicles_tracked, "vehicle", "vehicles")}${mix ? ` (${mix})` : ""} and measured the speed of ${measured}. `;
  text += speeders
    ? `${speeders} ${plural(speeders, "vehicle was", "vehicles were")} over the ${limit} km/h limit and saved as ${plural(speeders, "a violation", "violations")}. `
    : `No vehicle crossed the ${limit} km/h limit. `;
  if (r.max_speed_kmh != null) text += `Top speed was ${fmt(r.max_speed_kmh)} km/h. `;
  if (r.helmet_check_enabled) {
    text += r.no_helmet_violations
      ? `I checked ${r.motorcycles_checked} motorcycles: ${r.no_helmet_violations} ${plural(r.no_helmet_violations, "rider had", "riders had")} no helmet. `
      : `I checked ${r.motorcycles_checked} motorcycles — every rider wore a helmet. `;
  }
  text += r.plates_identified
    ? `I read ${r.plates_identified} number ${plural(r.plates_identified, "plate", "plates")}.`
    : r.violations_saved
      ? "I couldn't read the violators' number plates."
      : "";
  return text.trim();
}

function liveUpdate(ctx, lang) {
  const p = ctx.progress || {};
  const live = p.live;
  const pct = fmt(p.progress_percent, 0);
  if (!live) {
    return lang === "ur"
      ? `Abhi kaam chal raha hai — ${pct}% ho gaya. Mukammal hote hi bata dunga.`
      : `Still working — ${pct}% done. I'll tell you the moment it finishes.`;
  }
  return lang === "ur"
    ? `Abhi ${pct}% hua hai. Ab tak ${live.vehicles_seen} gaariyan nazar aayin, ${live.violations} violations${live.no_helmet ? ` (${live.no_helmet} bina helmet)` : ""} aur ${live.plates} plates parhi gayin. Final result thori der mein.`
    : `${pct}% done. So far: ${live.vehicles_seen} vehicles, ${live.violations} violations${live.no_helmet ? ` (${live.no_helmet} without helmet)` : ""} and ${live.plates} plates read. Final result shortly.`;
}

/** Messages the robot says on its own when the pipeline changes state. */
export function announce(event, ctx, lang) {
  const ur = lang === "ur";
  switch (event) {
    case "selected":
      return ur
        ? `Video "${ctx.fileName}" mil gayi. "Analyze" dabayein ya mujhe bolein "shuru karo".`
        : `Got "${ctx.fileName}". Press Analyze or just tell me "start".`;
    case "started":
      return ur
        ? "Video upload ho rahi hai. Main gaariyan detect aur track kar raha hoon — live view upload box ke neeche dekhein."
        : "Uploading now. I'm detecting and tracking vehicles — watch the live view under the upload box.";
    case "completed":
      return summarize(ctx.result, lang);
    case "failed":
      return ur ? `Maaf kijiye, processing fail ho gayi: ${ctx.error}` : `Sorry, processing failed: ${ctx.error}`;
    case "offline":
      return ur
        ? "Backend se rabta nahi ho raha. run.bat chala kar server start karein."
        : "I can't reach the backend. Start the server with run.bat.";
    default:
      return "";
  }
}

export function welcomeMessage(lang) {
  return lang === "ur"
    ? `Assalam o Alaikum! Main ${ROBOT_NAME} hoon, aap ka traffic assistant. Video upload karein, phir kuch bhi poochein — "result batao", "kitni violations", "80 se tez kitni gaariyan", "gaari 7", "kitne trucks" ya "speed kaise naapi". Mic dabakar bol bhi sakte hain.`
    : `Hi! I'm ${ROBOT_NAME}, your traffic assistant. Upload a video, then ask anything — "what's the result", "how many violations", "how many above 80", "vehicle 7", "how many trucks" or "how is speed measured". Tap the mic to talk.`;
}

export const SUGGESTIONS = {
  en: ["What's the result?", "Violations?", "Who has no helmet?", "Fastest vehicle", "How many above 80?", "Number plates", "How is speed measured?", "Help"],
  ur: ["Result batao", "Kitni violations?", "Helmet kis ne nahi pehna?", "Sab se tez gaari", "80 se tez kitni?", "Number plates", "Speed kaise naapi?", "Madad"],
};

const EXPLANATIONS = {
  yolo: {
    en: "YOLOv8 looks at each frame once and draws boxes around cars, buses, trucks and motorcycles. I run it about 10 times per second of video to stay fast.",
    ur: "YOLOv8 har frame ko ek nazar mein dekh kar car, bus, truck aur motorcycle ke gird box banata hai. Tez rehne ke liye main ise video ke har second mein taqreeban 10 dafa chalata hoon.",
  },
  tracking: {
    en: "ByteTrack links the boxes from frame to frame so every vehicle keeps the same ID number while it moves through the video.",
    ur: "ByteTrack har frame ke boxes ko aapas mein jorta hai taake har gaari ka ID number poori video mein wohi rahe.",
  },
  speed: {
    en: "Two virtual lines are drawn on the road. I note the exact moment a vehicle crosses line 1 and line 2 (interpolated between frames), then speed = real distance ÷ time × 3.6 to get km/h.",
    ur: "Sarak par do virtual lines hain. Gaari jab line 1 aur line 2 cross karti hai to main dono ka exact waqt note karta hoon, phir speed = asli faasla ÷ waqt × 3.6, yani km/h.",
  },
  ocr: {
    en: "For speeding vehicles I crop the lower half of the box, enlarge and sharpen it, and EasyOCR reads the letters. Only text with letters and digits (4–12 characters) is accepted as a plate.",
    ur: "Tez gaariyon ke box ka neeche wala hissa kaat kar bara aur saaf kiya jata hai, phir EasyOCR huroof parhta hai. Sirf woh text plate mana jata hai jisme huroof aur number dono hon (4–12 characters).",
  },
  helmet: {
    en: "For every motorcycle I crop the area above and around it, where the riders' heads are, and a helmet model labels each head as helmet or no helmet. After 3 consistent checks a rider without a helmet is boxed in red, ticketed, and the plate is read.",
    ur: "Har motorcycle ke upar aur aas paas ka hissa, jahan rider ka sar hota hai, kaat kar helmet model ko diya jata hai jo batata hai helmet hai ya nahi. 3 dafa ek jaisa nateeja aane par bina helmet rider laal box mein aata hai, ticket banta hai aur plate parhi jati hai.",
  },
  robot: {
    en: `I'm a rule-based assistant — no chatbot or internet. I match your words to the analysis data and speak using your browser's voice.`,
    ur: `Main rule-based assistant hoon — koi chatbot ya internet nahi. Aap ke alfaaz ko analysis data se mila kar jawab deta hoon aur browser ki awaz mein bolta hoon.`,
  },
  system: {
    en: "Pipeline: upload → YOLOv8 detects vehicles → ByteTrack gives IDs → two-line timing measures speed → EasyOCR reads speeders' plates → violations are saved in the database → annotated video.",
    ur: "Pipeline: upload → YOLOv8 gaariyan pehchanta hai → ByteTrack ID deta hai → do lines se speed naapi jati hai → EasyOCR tez gaariyon ki plate parhta hai → violations database mein save → annotated video.",
  },
};

/* ------------------------------------------------------------------ */
/* Reply                                                               */
/* ------------------------------------------------------------------ */

const ACTION_INTENTS = new Set(["stop", "analyze", "upload", "video"]);

/**
 * @returns {{ text: string, action?: "analyze"|"pick_file"|"show_output"|"stop_speaking"|"refresh_stats" }}
 */
export function reply(message, ctx, lang) {
  // "result batao aur sab se tez gaari" → answer both parts.
  const parts = String(message)
    .split(/\s+(?:aur|and|or|also|phir|plus|اور)\s+|[?؟;]+/i)
    .map((part) => part.trim())
    .filter((part) => part.length > 1);

  if (parts.length > 1) {
    const answers = [];
    const seen = new Set();
    let action;
    for (const part of parts) {
      const key = detectIntent(part) || part;
      if (seen.has(key)) continue;
      seen.add(key);
      const answer = replyOne(part, ctx, lang);
      if (answer.unknown) continue;
      answers.push(answer.text);
      action = action || answer.action;
    }
    if (answers.length > 1) return { text: answers.join(" "), action };
  }

  const answer = replyOne(message, ctx, lang);
  delete answer.unknown;
  return answer;
}

function replyOne(message, ctx, lang) {
  const ur = lang === "ur";
  const L = (en, urdu) => ({ text: ur ? urdu : en });
  const r = ctx.result;
  const limit = fmt(r?.speed_limit_kmh ?? ctx.config?.speed_limit_kmh, 0);
  const intent = detectIntent(message);

  const needResult = () => {
    if (ctx.isProcessing) return { text: liveUpdate(ctx, lang) };
    if (!ctx.hasVideo) {
      return L(
        "There's no result yet. Upload a traffic video first, then press Analyze.",
        "Abhi koi result nahi hai. Pehle traffic video upload karein, phir Analyze dabayein."
      );
    }
    return L(
      'The video is ready but not analysed yet. Say "start" and I\'ll begin.',
      'Video tayyar hai lekin abhi analyze nahi hui. "Shuru karo" bolein to main shuru kar dunga.'
    );
  };

  /* ---- questions that work without a result ---- */
  const asksHow = /\b(how|kaise|kaisy|explain|samjha|work|kaam)/.test(normalize(message));
  if (intent === "explain" || (intent === "helmet" && asksHow)) {
    const topic = findExplainTopic(message);
    return { text: EXPLANATIONS[topic][ur ? "ur" : "en"] };
  }

  switch (intent) {
    case "stop":
      return { ...L("Okay, I'll be quiet.", "Theek hai, main chup ho jata hoon."), action: "stop_speaking" };
    case "greeting":
      return L(
        `Hello! I'm ${ROBOT_NAME}. ${r ? "Your analysis is ready — ask me anything about it." : "Upload a video and I'll analyse it for you."}`,
        `Walaikum Assalam! Main ${ROBOT_NAME} hoon. ${r ? "Aap ka analysis tayyar hai — jo chahein poochein." : "Video upload karein, main us ka analysis kar dunga."}`
      );
    case "howareyou":
      return L(
        "I'm great and ready to catch some speeders! How can I help?",
        "Main bilkul theek hoon aur speeders pakarne ko tayyar! Bataiye kya madad karun?"
      );
    case "thanks":
      return L("Anytime! Drive safe.", "Koi baat nahi! Gaari aahista chalayein.");
    case "bye":
      return L("Goodbye! Stay within the limit.", "Khuda Hafiz! Speed limit ka khayal rakhein.");
    case "who":
      return { text: EXPLANATIONS.robot[ur ? "ur" : "en"] };
    case "help":
      return L(
        'Ask me: "result", "violations", "fastest" / "slowest", "average speed", "how many above 80", "vehicle 7", a plate like ABC123, "how many trucks", "plates", "vehicles without plate", "who has no helmet", "percentage", "latest violation", "how long did it take", "total history", or "how is speed measured". Commands: "start", "upload", "show video", "stop".',
        'Poochiye: "result batao", "violations", "sab se tez" / "sab se aahista", "average speed", "80 se tez kitni", "gaari 7", koi plate jaise ABC123, "kitne trucks", "plates", "bina plate gaariyan", "helmet kis ne nahi pehna", "kitne fisad", "aakhri violation", "kitna time laga", "total record", ya "speed kaise naapi". Commands: "shuru karo", "upload", "video dikhao", "chup".'
      );
    case "analyze":
      if (ctx.isProcessing) return { text: liveUpdate(ctx, lang) };
      if (!ctx.hasVideo) {
        return { ...L("Pick a video first — I'm opening the file browser.", "Pehle video chunein — main file browser khol raha hoon."), action: "pick_file" };
      }
      return { ...L("Starting the analysis now!", "Analysis shuru kar raha hoon!"), action: "analyze" };
    case "upload":
      return {
        ...L(
          `Drag a video onto the upload box or click it. Accepted: ${ctx.config?.allowed_video_extensions || "mp4"} up to ${ctx.config?.max_upload_size_mb || 500} MB.`,
          `Video ko upload box par drag karein ya click karein. ${ctx.config?.allowed_video_extensions || "mp4"} files, ${ctx.config?.max_upload_size_mb || 500} MB tak.`
        ),
        action: ctx.isProcessing ? undefined : "pick_file",
      };
    case "error":
      if (ctx.error) return L(`The last problem was: ${ctx.error}`, `Aakhri masla yeh tha: ${ctx.error}`);
      if (ctx.backendOnline === false) return { text: announce("offline", ctx, lang) };
      return L("Everything looks fine — no errors right now.", "Sab theek hai — abhi koi error nahi.");
    case "status":
      if (ctx.isProcessing) {
        if (ctx.progress?.status === "uploading") {
          return L(
            `Uploading… ${fmt(ctx.progress.upload_percent, 0)}%`,
            `Upload ho rahi hai… ${fmt(ctx.progress.upload_percent, 0)}%`
          );
        }
        if (ctx.progress?.status === "queued") {
          return L("Waiting for the previous video to finish.", "Pichli video khatam hone ka intezar hai.");
        }
        return { text: liveUpdate(ctx, lang) };
      }
      if (r) return L("The analysis is complete. Ask me for the result!", "Analysis mukammal ho chuka hai. Result poochein!");
      return needResult();
    case "accuracy":
      return L(
        "Speed accuracy depends on calibration: LINE_1_Y, LINE_2_Y and REAL_DISTANCE_METERS must match the real road for this camera. Plates depend on resolution and angle — treat them as candidates, not legal proof.",
        "Speed ki durusti calibration par hai: LINE_1_Y, LINE_2_Y aur REAL_DISTANCE_METERS is camera ki asli sarak ke mutabiq hon. Plates resolution aur angle par depend karti hain — inhein sirf andaza samjhein, qanooni saboot nahi."
      );
    case "history": {
      const s = ctx.stats;
      if (!s) return { ...L("Let me fetch the database records…", "Database se record la raha hoon…"), action: "refresh_stats" };
      if (!s.total_violations) return L("The database has no violations yet.", "Database mein abhi tak koi violation nahi.");
      return L(
        `All time: ${s.total_violations} violations across ${s.videos_analyzed} ${plural(s.videos_analyzed, "video", "videos")}. Average violating speed ${fmt(s.average_speed_kmh)} km/h, highest ${fmt(s.max_speed_kmh)} km/h. ${s.violations_with_plate} have a number plate.`,
        `Ab tak: ${s.videos_analyzed} videos mein ${s.total_violations} violations. Ausat raftaar ${fmt(s.average_speed_kmh)} km/h, sab se zyada ${fmt(s.max_speed_kmh)} km/h. ${s.violations_with_plate} ki number plate mili.`
      );
    }
    case "limit":
      if (!findThreshold(message)) {
        return L(
          `The speed limit is ${limit} km/h. Anything faster is saved as a violation.`,
          `Speed limit ${limit} km/h hai. Is se tez har gaari violation mein save hoti hai.`
        );
      }
      break;
    default:
      break;
  }

  /* ---- everything below needs (live or final) analysis data ---- */
  if (!r) {
    if (ctx.isProcessing) return { text: liveUpdate(ctx, lang) };
    if (!intent && !findTrackId(message) && !findThreshold(message)) {
      return {
        ...L(
          `I didn't quite get that. ${ctx.hasVideo ? 'Say "start" to analyse your video' : "Upload a video first"}, or say "help".`,
          `Mujhe samajh nahi aaya. ${ctx.hasVideo ? '"Shuru karo" bolein' : "Pehle video upload karein"}, ya "madad" bolein.`
        ),
        unknown: true,
      };
    }
    return needResult();
  }

  const records = [...(r.speed_records || [])].sort((a, b) => b.speed_kmh - a.speed_kmh);
  const violations = r.violations || [];

  // A plate number in the message.
  const plate = findPlateMention(message, r);
  if (plate) return describeVehicle(plate.track_id, r, lang, limit);

  // "gaari 7", "#12"
  const trackId = findTrackId(message);
  if (trackId !== null) return describeVehicle(trackId, r, lang, limit);

  // "80 se tez kitni gaariyan"
  const threshold = findThreshold(message);
  if (threshold !== null) {
    const above = records.filter((rec) => rec.speed_kmh > threshold);
    if (!above.length) {
      return L(
        `No measured vehicle went above ${threshold} km/h.`,
        `Koi naapi gayi gaari ${threshold} km/h se tez nahi thi.`
      );
    }
    const list = above.slice(0, 5).map((rec) => `#${rec.track_id} ${fmt(rec.speed_kmh)}`).join(", ");
    return L(
      `${above.length} of ${records.length} measured vehicles went above ${threshold} km/h: ${list} km/h.`,
      `${records.length} mein se ${above.length} gaariyan ${threshold} km/h se tez thin: ${list} km/h.`
    );
  }

  // "kitne trucks" / "how many buses" / "fastest truck"
  const type = findVehicleType(message);
  if (type && (intent === "fastest" || intent === "slowest")) {
    const ofType = records.filter((rec) => rec.vehicle_type === type);
    if (!ofType.length) {
      return L(`No ${type} had its speed measured.`, `Kisi ${type} ki speed nahi naapi gayi.`);
    }
    const pick = intent === "fastest" ? ofType[0] : ofType[ofType.length - 1];
    return L(
      `The ${intent === "fastest" ? "fastest" : "slowest"} ${type} was #${pick.track_id} at ${fmt(pick.speed_kmh)} km/h${pick.is_overspeeding ? " — overspeeding!" : "."}`,
      `Sab se ${intent === "fastest" ? "tez" : "aahista"} ${type} #${pick.track_id} thi — ${fmt(pick.speed_kmh)} km/h${pick.is_overspeeding ? ", limit se zyada!" : "."}`
    );
  }
  if (type && (intent === "vehicles" || intent === null || /kitni|how many|count/.test(normalize(message)))) {
    const count = r.vehicle_types?.[type] || 0;
    const fast = records.filter((rec) => rec.vehicle_type === type && rec.is_overspeeding).length;
    return L(
      `I tracked ${count} ${type}${count === 1 ? "" : type === "bus" ? "es" : "s"}${fast ? `, ${fast} of them overspeeding` : ""}.`,
      `Maine ${count} ${type} track kiye${fast ? `, jin mein se ${fast} over-speeding kar rahe the` : ""}.`
    );
  }

  switch (intent) {
    case "helmet": {
      if (!r.helmet_check_enabled) {
        return L(
          "Helmet check was off for this video — the helmet model is not active. Install onnxruntime (.venv/Scripts/python -m pip install onnxruntime), restart the server, and analyse again.",
          "Is video ke liye helmet check band tha — helmet model active nahi. onnxruntime install karein (.venv/Scripts/python -m pip install onnxruntime), server restart karein aur dobara analyze karein."
        );
      }
      const bad = (r.helmet_records || []).filter((h) => !h.has_helmet);
      if (!bad.length) {
        return L(
          `I checked ${r.motorcycles_checked} motorcycles — every rider wore a helmet.`,
          `${r.motorcycles_checked} motorcycles check ki — sab riders ne helmet pehna tha.`
        );
      }
      const list = bad
        .slice(0, 6)
        .map((h) => `#${h.track_id}${h.plate_number ? ` (${h.plate_number})` : ""}`)
        .join(", ");
      return L(
        `${bad.length} of ${r.motorcycles_checked} checked riders had no helmet: ${list}. They are marked red in the video.`,
        `${r.motorcycles_checked} mein se ${bad.length} riders ne helmet nahi pehna tha: ${list}. Video mein inhein laal box mein dikhaya gaya hai.`
      );
    }

    case "summary":
      return { text: summarize(r, lang) };

    case "violations": {
      if (!violations.length) {
        return L(
          `Good news — no vehicle exceeded ${limit} km/h${r.helmet_check_enabled ? " and every rider wore a helmet" : ""}.`,
          `Achhi khabar — koi gaari ${limit} km/h se tez nahi thi${r.helmet_check_enabled ? " aur sab riders ne helmet pehna tha" : ""}.`
        );
      }
      const list = violations
        .slice(0, 5)
        .map((x) =>
          x.violation_type === "no_helmet"
            ? `#${x.track_id} ${x.plate_number ? `(${x.plate_number}) ` : ""}${ur ? "bina helmet" : "no helmet"}`
            : `#${x.track_id} ${x.plate_number ? `(${x.plate_number}) ` : ""}${fmt(x.speed_kmh)} km/h`
        )
        .join(", ");
      return L(
        `${violations.length} ${plural(violations.length, "violation", "violations")}: ${list}${violations.length > 5 ? " and more" : ""}.`,
        `${violations.length} ${plural(violations.length, "violation", "violations")}: ${list}${violations.length > 5 ? " aur mazeed" : ""}.`
      );
    }

    case "latest": {
      const last = violations[violations.length - 1];
      if (!last) return L("There are no violations in this video.", "Is video mein koi violation nahi.");
      return L(
        `The latest violation is vehicle #${last.track_id}${last.plate_number ? ` (${last.plate_number})` : ""} at ${fmt(last.speed_kmh)} km/h, ${fmt(last.speed_kmh - last.speed_limit_kmh)} km/h over the limit.`,
        `Aakhri violation gaari #${last.track_id}${last.plate_number ? ` (${last.plate_number})` : ""} ki hai — ${fmt(last.speed_kmh)} km/h, limit se ${fmt(last.speed_kmh - last.speed_limit_kmh)} km/h zyada.`
      );
    }

    case "percent": {
      if (!records.length) return L("No speeds were measured, so I can't give a percentage.", "Koi speed nahi naapi gayi, is liye percentage nahi bata sakta.");
      const speeding = records.filter((rec) => rec.is_overspeeding).length;
      const pct = (speeding / records.length) * 100;
      return L(
        `${fmt(pct, 0)}% of measured vehicles were overspeeding (${speeding} of ${records.length}).`,
        `Naapi gayi gaariyon mein se ${fmt(pct, 0)}% over-speeding kar rahi thin (${records.length} mein se ${speeding}).`
      );
    }

    case "noplate": {
      const missing = violations.filter((v) => !v.plate_number);
      if (!missing.length) {
        return L("Every violating vehicle has a plate reading.", "Har violation wali gaari ki plate parh li gayi.");
      }
      return L(
        `${missing.length} violating ${plural(missing.length, "vehicle has", "vehicles have")} no readable plate: ${missing.map((v) => `#${v.track_id}`).join(", ")}.`,
        `${missing.length} violation wali gaariyon ki plate parhi nahi ja saki: ${missing.map((v) => `#${v.track_id}`).join(", ")}.`
      );
    }

    case "fastest": {
      const top = records[0];
      if (!top) return L("No vehicle crossed both speed lines, so I have no speeds.", "Kisi gaari ne dono speed lines cross nahi ki, is liye speed nahi mili.");
      return L(
        `The fastest was vehicle #${top.track_id}${top.vehicle_type ? ` (${top.vehicle_type})` : ""}${top.plate_number ? `, plate ${top.plate_number}` : ""}, at ${fmt(top.speed_kmh)} km/h${top.is_overspeeding ? " — overspeeding!" : "."}`,
        `Sab se tez gaari #${top.track_id}${top.vehicle_type ? ` (${top.vehicle_type})` : ""}${top.plate_number ? `, plate ${top.plate_number}` : ""} thi — ${fmt(top.speed_kmh)} km/h${top.is_overspeeding ? ", jo limit se zyada hai!" : "."}`
      );
    }

    case "slowest": {
      const low = records[records.length - 1];
      if (!low) return L("I have no speed measurements.", "Koi speed measurement nahi hai.");
      return L(
        `The slowest measured vehicle was #${low.track_id} at ${fmt(low.speed_kmh)} km/h.`,
        `Sab se aahista gaari #${low.track_id} thi — ${fmt(low.speed_kmh)} km/h.`
      );
    }

    case "average":
    case "speed":
      if (!records.length) {
        return L(
          "No vehicle crossed both speed lines in this video, so no speeds were measured. The lines may need adjusting for this camera.",
          "Is video mein kisi gaari ne dono speed lines cross nahi ki, is liye speed nahi naapi gayi. Shayad is camera ke liye lines adjust karni hongi."
        );
      }
      return L(
        `Across ${records.length} measured vehicles the average speed was ${fmt(r.average_speed_kmh)} km/h and the top speed ${fmt(r.max_speed_kmh)} km/h (limit ${limit}).`,
        `${records.length} gaariyon ki ausat raftaar ${fmt(r.average_speed_kmh)} km/h aur sab se zyada ${fmt(r.max_speed_kmh)} km/h thi (limit ${limit}).`
      );

    case "plates": {
      const plates = r.recognized_plates || [];
      if (!plates.length) {
        return L(
          violations.length
            ? "I couldn't read the speeders' plates. Plates need to be large and sharp in the frame."
            : "No plates were read — I only read plates of overspeeding vehicles, and there were none.",
          violations.length
            ? "Speeders ki plate parhi nahi ja saki. Plate frame mein bari aur saaf honi chahiye."
            : "Koi plate nahi parhi gayi — main sirf over-speeding gaariyon ki plate parhta hoon, aur koi nahi thi."
        );
      }
      const list = plates.slice(0, 6).map((p) => p.plate_number).join(", ");
      return L(
        `I read ${plates.length} ${plural(plates.length, "plate", "plates")}: ${list}${plates.length > 6 ? "…" : "."} Ask me about any one of them.`,
        `${plates.length} ${plural(plates.length, "plate parhi gayi", "plates parhi gayin")}: ${list}${plates.length > 6 ? "…" : "."} Kisi bhi plate ke baare mein poochein.`
      );
    }

    case "vehicles": {
      const mix = describeVehicleMix(r);
      return L(
        `I tracked ${r.vehicles_tracked} ${plural(r.vehicles_tracked, "vehicle", "vehicles")}${mix ? `: ${mix}` : ""}. ${records.length} crossed both speed lines.`,
        `Maine ${r.vehicles_tracked} gaariyan track ki${mix ? `: ${mix}` : ""}. ${records.length} ne dono speed lines cross ki.`
      );
    }

    case "video":
      return {
        ...L("Here's the annotated video with boxes, speeds and plates.", "Yeh rahi annotated video — boxes, speed aur plates ke saath."),
        action: "show_output",
      };

    case "duration":
      return L(
        `The video is ${fmt(r.duration_seconds)} seconds long (${r.total_frames} frames at ${fmt(r.fps, 0)} fps). Processing took ${fmt(r.processing_seconds)} seconds.`,
        `Video ${fmt(r.duration_seconds)} second lambi hai (${r.total_frames} frames, ${fmt(r.fps, 0)} fps). Processing mein ${fmt(r.processing_seconds)} second lage.`
      );

    default:
      if (ACTION_INTENTS.has(intent)) break;
      return {
        ...L(
          `I didn't quite get that. Try "result", "violations", "fastest vehicle", "vehicle 7", "above 80" or "help".`,
          `Mujhe samajh nahi aaya. "Result batao", "violations", "sab se tez gaari", "gaari 7", "80 se tez" ya "madad" try karein.`
        ),
        unknown: true,
      };
  }
  return { text: "" };
}

function describeVehicle(trackId, r, lang, limit) {
  const ur = lang === "ur";
  const record = r.speed_records?.find((s) => s.track_id === trackId);
  const violation = r.violations?.find(
    (v) => v.track_id === trackId && v.violation_type !== "no_helmet"
  );
  const helmet = r.helmet_records?.find((h) => h.track_id === trackId);
  const plate = r.recognized_plates?.find((p) => p.track_id === trackId)?.plate_number;
  const type = record?.vehicle_type || (helmet ? "motorcycle" : undefined);
  const name = `#${trackId}${type ? ` (${type})` : ""}${plate ? `, plate ${plate}` : ""}`;
  const helmetNote = !helmet
    ? ""
    : helmet.has_helmet
      ? ur ? " Rider ne helmet pehna tha." : " The rider wore a helmet."
      : ur ? " Rider ne helmet NAHI pehna tha — is ki bhi violation bani." : " The rider had NO helmet — that is a violation too.";

  if (violation) {
    return {
      text: (ur
        ? `Gaari ${name} ${fmt(violation.speed_kmh)} km/h par chal rahi thi — limit ${limit} se ${fmt(violation.speed_kmh - violation.speed_limit_kmh)} zyada. Violation record ho gayi hai.`
        : `Vehicle ${name} was doing ${fmt(violation.speed_kmh)} km/h — ${fmt(violation.speed_kmh - violation.speed_limit_kmh)} over the ${limit} limit. A violation was recorded.`) + helmetNote,
    };
  }
  if (helmet && !record) {
    const bike = `#${trackId}${plate ? `, plate ${plate}` : ""}`;
    return {
      text: ur
        ? `Motorcycle ${bike}: speed nahi naapi gayi.${helmetNote}`
        : `Motorcycle ${bike}: no speed measured.${helmetNote}`,
    };
  }
  if (record) {
    return {
      text: (ur
        ? `Gaari ${name} ki speed ${fmt(record.speed_kmh)} km/h thi, jo ${limit} km/h limit ke andar hai.`
        : `Vehicle ${name} was measured at ${fmt(record.speed_kmh)} km/h, within the ${limit} km/h limit.`) + helmetNote,
    };
  }
  if (plate) {
    return {
      text: ur
        ? `Gaari #${trackId} ki plate ${plate} parhi gayi, lekin is ne dono speed lines cross nahi ki is liye speed nahi mili.`
        : `I read plate ${plate} on vehicle #${trackId}, but it didn't cross both speed lines so I have no speed for it.`,
    };
  }
  return {
    text: ur
      ? `Gaari #${trackId} ki speed record nahi hui — ya to woh dono lines tak nahi pohanchi ya yeh ID is video mein nahi.`
      : `I have no speed for vehicle #${trackId} — it either didn't cross both lines or that ID isn't in this video.`,
  };
}
