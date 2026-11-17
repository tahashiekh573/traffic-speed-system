/*
 * Rule-based assistant for the traffic dashboard.
 *
 * This is deliberately NOT an LLM: it matches keywords (English, Roman
 * Urdu and Urdu script) to intents and answers from the real analysis
 * data the backend returned. Every number it says comes from the API.
 */

export const ROBOT_NAME = "Raftaar";

const fmt = (value, digits = 1) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? "—"
    : Number(value).toFixed(digits);

const plural = (n, one, many) => (Number(n) === 1 ? one : many);

function normalize(text) {
  return ` ${String(text)
    .toLowerCase()
    .replace(/[?!.,،؟۔:;"'()]/g, " ")
    .replace(/\s+/g, " ")
    .trim()} `;
}

// Latin keywords match on word starts ("car" ≠ "scar"); Urdu script uses includes.
function hasKeyword(normalized, keyword) {
  if (/[؀-ۿ]/.test(keyword)) return normalized.includes(keyword);
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|\\s)${escaped}`).test(normalized);
}

const INTENTS = [
  { id: "stop", words: ["stop", "chup", "bas karo", "ruk jao", "quiet", "shut up", "خاموش", "بس کرو", "رک جاؤ"] },
  { id: "analyze", words: ["analyze", "analyse", "start", "process", "shuru", "chalao", "scan", "run", "begin", "شروع", "چلاؤ"] },
  { id: "upload", words: ["upload", "select video", "file", "video kaise", "video dalo", "اپلوڈ", "ویڈیو کیسے"] },
  { id: "greeting", words: ["hi", "hello", "hey", "salam", "assalam", "aoa", "slam", "hy", "سلام", "ہیلو"] },
  { id: "thanks", words: ["thank", "thanks", "shukriya", "shukria", "jazak", "شکریہ"] },
  { id: "bye", words: ["bye", "khuda hafiz", "allah hafiz", "goodbye", "خدا حافظ", "اللہ حافظ"] },
  { id: "who", words: ["who are you", "your name", "tum kaun", "ap kaun", "aap kaun", "naam kya", "kaun ho", "تم کون", "نام کیا"] },
  { id: "help", words: ["help", "madad", "kya kar sakte", "what can you", "commands", "options", "مدد"] },
  { id: "error", words: ["error", "masla", "problem", "issue", "fail", "galat", "kyun nahi", "مسئلہ", "خرابی"] },
  { id: "status", words: ["status", "progress", "kahan tak", "kitna hua", "kab tak", "percent", "how long", "kitni der", "ho gaya", "فیصد", "کہاں تک"] },
  { id: "fastest", words: ["fastest", "maximum", "max", "highest", "top speed", "sab se tez", "sabse tez", "tez tareen", "zyada speed", "سب سے تیز"] },
  { id: "slowest", words: ["slowest", "minimum", "lowest", "sab se aahista", "sabse kam", "kam speed", "سب سے آہستہ"] },
  { id: "average", words: ["average", "avg", "mean", "ausat", "اوسط"] },
  { id: "violations", words: ["violation", "overspeed", "over speed", "speeding", "challan", "chalan", "tez", "jurmana", "khilaf", "خلاف", "چالان", "تیز"] },
  { id: "plates", words: ["plate", "number", "nambar", "registration", "anpr", "ocr", "پلیٹ", "نمبر"] },
  { id: "vehicles", words: ["vehicle", "car", "cars", "gaadi", "gadi", "gaari", "gariyan", "gaariyan", "bus", "truck", "bike", "motorcycle", "traffic", "گاڑی", "گاڑیاں"] },
  { id: "limit", words: ["limit", "had", "allowed", "حد"] },
  { id: "speed", words: ["speed", "raftar", "raftaar", "kmh", "km/h", "رفتار"] },
  { id: "history", words: ["total", "history", "database", "all time", "ab tak", "overall", "records", "sab videos", "ٹوٹل", "ریکارڈ"] },
  { id: "video", words: ["video dikhao", "output", "download", "annotated", "show video", "play", "ویڈیو دکھاؤ"] },
  { id: "duration", words: ["duration", "length", "kitni lambi", "seconds", "frames", "fps", "دورانیہ"] },
  { id: "summary", words: ["result", "summary", "report", "natija", "kya aya", "kya hua", "batao", "bataen", "overview", "findings", "نتیجہ", "رزلٹ", "بتاؤ"] },
];

function detectIntent(message) {
  const normalized = normalize(message);
  let best = null;

  INTENTS.forEach((intent, order) => {
    const hits = intent.words.filter((word) => hasKeyword(normalized, word));
    if (!hits.length) return;
    // Longer phrase matches are more specific than single words.
    const score = hits.reduce((sum, word) => sum + word.length, 0);
    if (!best || score > best.score || (score === best.score && order < best.order)) {
      best = { id: intent.id, score, order };
    }
  });

  return best?.id || null;
}

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

/* ------------------------------------------------------------------ */
/* Sentences                                                           */
/* ------------------------------------------------------------------ */

function describeVehicleMix(result, lang) {
  const types = Object.entries(result?.vehicle_types || {});
  if (!types.length) return "";
  const names = {
    car: ["car", "cars", "car", "cars"],
    bus: ["bus", "buses", "bus", "buses"],
    truck: ["truck", "trucks", "truck", "trucks"],
    motorcycle: ["motorcycle", "motorcycles", "motorcycle", "motorcycles"],
  };
  const parts = types.map(([type, count]) => {
    const label = names[type] || [type, `${type}s`, type, `${type}s`];
    return `${count} ${count === 1 ? label[lang === "ur" ? 2 : 0] : label[lang === "ur" ? 3 : 1]}`;
  });
  return parts.join(", ");
}

export function summarize(result, lang) {
  const r = result;
  const limit = fmt(r.speed_limit_kmh, 0);
  const measured = r.speed_records?.length || 0;
  const mix = describeVehicleMix(r, lang);

  if (lang === "ur") {
    let text = `${r.filename} ka analysis mukammal ho gaya. Maine ${r.vehicles_tracked} ${plural(r.vehicles_tracked, "gaari", "gaariyan")} track ki${mix ? ` (${mix})` : ""} aur ${measured} ki speed naapi. `;
    text += r.violations_saved
      ? `${r.violations_saved} ${plural(r.violations_saved, "gaari", "gaariyan")} ${limit} km/h ki limit se tez thi — ${plural(r.violations_saved, "yeh violation", "yeh violations")} database mein save ho gayi. `
      : `Koi bhi gaari ${limit} km/h ki limit se tez nahi thi. `;
    if (r.max_speed_kmh != null) text += `Sab se tez raftaar ${fmt(r.max_speed_kmh)} km/h thi. `;
    text += r.plates_identified
      ? `${r.plates_identified} number ${plural(r.plates_identified, "plate parhi gayi", "plates parhi gayin")}.`
      : "Koi number plate parhi nahi ja saki.";
    return text;
  }

  let text = `Analysis of ${r.filename} is complete. I tracked ${r.vehicles_tracked} ${plural(r.vehicles_tracked, "vehicle", "vehicles")}${mix ? ` (${mix})` : ""} and measured the speed of ${measured}. `;
  text += r.violations_saved
    ? `${r.violations_saved} ${plural(r.violations_saved, "vehicle was", "vehicles were")} over the ${limit} km/h limit and saved as ${plural(r.violations_saved, "a violation", "violations")}. `
    : `No vehicle crossed the ${limit} km/h limit. `;
  if (r.max_speed_kmh != null) text += `Top speed was ${fmt(r.max_speed_kmh)} km/h. `;
  text += r.plates_identified
    ? `I read ${r.plates_identified} number ${plural(r.plates_identified, "plate", "plates")}.`
    : "No number plates could be read.";
  return text;
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
        ? "Video upload ho rahi hai. Main gaariyan detect aur track kar raha hoon — thora intezar karein."
        : "Uploading now. I'm detecting and tracking vehicles — this can take a moment.";
    case "completed":
      return summarize(ctx.result, lang);
    case "failed":
      return ur
        ? `Maaf kijiye, processing fail ho gayi: ${ctx.error}`
        : `Sorry, processing failed: ${ctx.error}`;
    case "offline":
      return ur
        ? "Backend se rabta nahi ho raha. Pehle FastAPI server chalayein: uvicorn app.main:app --reload"
        : "I can't reach the backend. Start it with: uvicorn app.main:app --reload";
    default:
      return "";
  }
}

export function welcomeMessage(lang) {
  return lang === "ur"
    ? `Assalam o Alaikum! Main ${ROBOT_NAME} hoon, aap ka traffic assistant. Video upload karein, phir mujh se poochein: "result batao", "kitni violations", "sab se tez gaari" ya "number plates". Mic dabakar bol bhi sakte hain.`
    : `Hi! I'm ${ROBOT_NAME}, your traffic assistant. Upload a video, then ask me "what's the result", "how many violations", "fastest vehicle" or "number plates". Tap the mic to talk to me.`;
}

export const SUGGESTIONS = {
  en: ["What's the result?", "Violations?", "Fastest vehicle", "Number plates", "Status", "Help"],
  ur: ["Result batao", "Kitni violations?", "Sab se tez gaari", "Number plates", "Kahan tak hua?", "Madad"],
};

/* ------------------------------------------------------------------ */
/* Main reply function                                                 */
/* ------------------------------------------------------------------ */

/**
 * @returns {{ text: string, action?: "analyze"|"pick_file"|"show_output"|"stop_speaking"|"refresh_stats" }}
 */
export function reply(message, ctx, lang) {
  const ur = lang === "ur";
  const L = (en, urdu) => ({ text: ur ? urdu : en });
  const r = ctx.result;
  const limit = fmt(r?.speed_limit_kmh ?? ctx.config?.speed_limit_kmh, 0);

  const needResult = () => {
    if (ctx.isProcessing) {
      const pct = fmt(ctx.progress?.progress_percent, 0);
      return L(
        `Still working on it — ${pct}% done. I'll tell you the moment it finishes.`,
        `Abhi kaam chal raha hai — ${pct}% ho gaya. Jaise hi mukammal hoga main bata dunga.`
      );
    }
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

  // A plate number in the message beats every keyword.
  const plate = findPlateMention(message, r);
  if (plate) {
    const record = r.speed_records?.find((s) => s.track_id === plate.track_id);
    const violation = r.violations?.find((v) => v.track_id === plate.track_id);
    if (violation) {
      return L(
        `Plate ${plate.plate_number} (vehicle #${plate.track_id}) was overspeeding at ${fmt(violation.speed_kmh)} km/h — a violation has been recorded.`,
        `Plate ${plate.plate_number} (gaari #${plate.track_id}) ${fmt(violation.speed_kmh)} km/h par over-speeding kar rahi thi — violation record ho gayi hai.`
      );
    }
    if (record) {
      return L(
        `Plate ${plate.plate_number} was measured at ${fmt(record.speed_kmh)} km/h, within the ${limit} km/h limit.`,
        `Plate ${plate.plate_number} ki speed ${fmt(record.speed_kmh)} km/h thi, jo ${limit} km/h limit ke andar hai.`
      );
    }
    return L(
      `I read plate ${plate.plate_number} on vehicle #${plate.track_id}, but it didn't cross both speed lines so I have no speed for it.`,
      `Gaari #${plate.track_id} ki plate ${plate.plate_number} parhi gayi, lekin is ne dono speed lines cross nahi ki is liye speed nahi naapi ja saki.`
    );
  }

  const intent = detectIntent(message);

  switch (intent) {
    case "stop":
      return { ...L("Okay, I'll be quiet.", "Theek hai, main chup ho jata hoon."), action: "stop_speaking" };

    case "greeting":
      return L(
        `Hello! I'm ${ROBOT_NAME}. ${r ? "Your last analysis is ready — ask me about it." : "Upload a video and I'll analyse it for you."}`,
        `Walaikum Assalam! Main ${ROBOT_NAME} hoon. ${r ? "Aap ka pichla analysis tayyar hai — us ke baare mein poochein." : "Video upload karein, main us ka analysis kar dunga."}`
      );

    case "thanks":
      return L("Anytime! Drive safe.", "Koi baat nahi! Gaari aahista chalayein. 🙂");

    case "bye":
      return L("Goodbye! Stay within the limit.", "Khuda Hafiz! Speed limit ka khayal rakhein.");

    case "who":
      return L(
        `I'm ${ROBOT_NAME}, the voice assistant of this traffic system. I read the YOLOv8 + ByteTrack + EasyOCR results and explain them to you. I work offline in your browser — no AI chatbot behind me.`,
        `Main ${ROBOT_NAME} hoon, is traffic system ka voice assistant. Main YOLOv8, ByteTrack aur EasyOCR ke results parh kar aap ko batata hoon. Main browser mein hi chalta hoon — koi chatbot nahi.`
      );

    case "help":
      return L(
        'You can ask: "result", "how many violations", "fastest vehicle", "average speed", "number plates", "how many cars", "speed limit", "status", "total history", or a plate number like ABC123. Commands: "start", "upload", "show video", "stop".',
        'Aap pooch sakte hain: "result batao", "kitni violations", "sab se tez gaari", "average speed", "number plates", "kitni gaariyan", "speed limit", "kahan tak hua", "total record", ya koi plate number jaise ABC123. Commands: "shuru karo", "upload", "video dikhao", "chup".'
      );

    case "analyze":
      if (ctx.isProcessing) return needResult();
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
      if (ctx.error) {
        return L(
          `The last problem was: ${ctx.error}`,
          `Aakhri masla yeh tha: ${ctx.error}`
        );
      }
      if (!ctx.backendOnline) return { text: announce("offline", ctx, lang) };
      return L("Everything looks fine — no errors right now.", "Sab theek hai — abhi koi error nahi.");

    case "status":
      if (ctx.isProcessing) {
        const p = ctx.progress || {};
        if (p.status === "uploading") return L("Uploading the video…", "Video upload ho rahi hai…");
        return L(
          `Processing: ${fmt(p.progress_percent)}% — frame ${p.processed_frames || 0} of ${p.total_frames || "?"}.`,
          `Processing: ${fmt(p.progress_percent)}% — ${p.total_frames || "?"} mein se ${p.processed_frames || 0} frames ho gaye.`
        );
      }
      if (r) return L("The analysis is complete. Ask me for the result!", "Analysis mukammal ho chuka hai. Result poochein!");
      return needResult();

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
      return L(
        `The speed limit is ${limit} km/h. Anything faster is saved as a violation.`,
        `Speed limit ${limit} km/h hai. Is se tez har gaari violation mein save hoti hai.`
      );
    default:
      break;
  }

  // Everything below needs a finished result.
  if (!r) {
    if (!intent) {
      return L(
        `I didn't quite get that. ${ctx.hasVideo ? 'Say "start" to analyse your video' : "Upload a video first"}, or say "help".`,
        `Mujhe samajh nahi aaya. ${ctx.hasVideo ? '"Shuru karo" bolein' : "Pehle video upload karein"}, ya "madad" bolein.`
      );
    }
    return needResult();
  }

  const records = [...(r.speed_records || [])].sort((a, b) => b.speed_kmh - a.speed_kmh);

  switch (intent) {
    case "summary":
      return { text: summarize(r, lang) };

    case "violations": {
      const v = r.violations || [];
      if (!v.length) {
        return L(
          `Good news — no vehicle exceeded ${limit} km/h.`,
          `Achhi khabar — koi gaari ${limit} km/h se tez nahi thi.`
        );
      }
      const list = v
        .slice(0, 5)
        .map((x) => `#${x.track_id} ${x.plate_number ? `(${x.plate_number}) ` : ""}${fmt(x.speed_kmh)} km/h`)
        .join(", ");
      return L(
        `${v.length} ${plural(v.length, "violation", "violations")}: ${list}${v.length > 5 ? " and more" : ""}.`,
        `${v.length} ${plural(v.length, "violation", "violations")}: ${list}${v.length > 5 ? " aur mazeed" : ""}.`
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
      if (!records.length) return L("No speeds were measured in this video.", "Is video mein koi speed nahi naapi gayi.");
      return L(
        `Across ${records.length} measured vehicles the average speed was ${fmt(r.average_speed_kmh)} km/h and the top speed ${fmt(r.max_speed_kmh)} km/h (limit ${limit}).`,
        `${records.length} gaariyon ki ausat raftaar ${fmt(r.average_speed_kmh)} km/h aur sab se zyada ${fmt(r.max_speed_kmh)} km/h thi (limit ${limit}).`
      );

    case "plates": {
      const plates = r.recognized_plates || [];
      if (!plates.length) {
        return L(
          "I couldn't read any number plates. Plates need to be large and sharp in the frame.",
          "Koi number plate parhi nahi ja saki. Plate frame mein bari aur saaf honi chahiye."
        );
      }
      const list = plates.slice(0, 6).map((p) => p.plate_number).join(", ");
      return L(
        `I read ${plates.length} ${plural(plates.length, "plate", "plates")}: ${list}${plates.length > 6 ? "…" : "."} Ask me about any one of them.`,
        `${plates.length} ${plural(plates.length, "plate parhi gayi", "plates parhi gayin")}: ${list}${plates.length > 6 ? "…" : "."} Kisi bhi plate ke baare mein poochein.`
      );
    }

    case "vehicles": {
      const mix = describeVehicleMix(r, lang);
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
      return L(
        `I didn't quite get that. Try "result", "violations", "fastest vehicle" or "help".`,
        `Mujhe samajh nahi aaya. "Result batao", "violations", "sab se tez gaari" ya "madad" try karein.`
      );
  }
}
