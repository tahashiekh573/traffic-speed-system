import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertCircle, ArrowUpRight, Bot, CarFront, CheckCircle2, Cpu, Database,
  Download, FileVideo, Gauge, LayoutDashboard, LoaderCircle, Radar, ScanLine,
  ShieldAlert, Timer, Upload, Video, Zap,
} from "lucide-react";
import { trafficApi } from "./api/trafficApi";
import { DEFAULT_CONFIG } from "./config";
import { useVideoAnalysis } from "./hooks/useVideoAnalysis";
import RobotAssistant from "./components/RobotAssistant";
import RobotFace from "./components/RobotFace";
import ResultsPanel from "./components/ResultsPanel";
import { ROBOT_NAME } from "./assistant/assistantBrain";
import "./App.css";

const HEALTH_INTERVAL_MS = 10000;

const NAV = [
  { id: "top", label: "Overview", icon: LayoutDashboard },
  { id: "analysis", label: "Video Analysis", icon: Video },
  { id: "speeds", label: "Speed Board", icon: Gauge },
  { id: "plates", label: "Plate Recognition", icon: ScanLine },
  { id: "violations", label: "Violations", icon: ShieldAlert },
];

const PIPELINE = [
  { key: "upload", label: "Upload", tech: "FastAPI", icon: Upload },
  { key: "detect", label: "Detect", tech: "YOLOv8", icon: Radar },
  { key: "track", label: "Track", tech: "ByteTrack", icon: CarFront },
  { key: "speed", label: "Speed", tech: "2-line timing", icon: Gauge },
  { key: "plate", label: "Plate OCR", tech: "EasyOCR", icon: ScanLine },
  { key: "save", label: "Save", tech: "SQLite", icon: Database },
];

const fmt = (value, digits = 1) =>
  value === null || value === undefined ? "—" : Number(value).toFixed(digits);

function stageState(index, progress, result, error) {
  if (error) return index === 0 ? "done" : "error";
  if (result) return "done";
  if (!progress) return "idle";
  if (progress.status === "uploading" || progress.status === "queued") {
    return index === 0 ? "active" : "idle";
  }
  return index === 0 ? "done" : index === PIPELINE.length - 1 ? "idle" : "active";
}

export default function App() {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [backendOnline, setBackendOnline] = useState(null);
  const [stats, setStats] = useState(null);
  const [activeNav, setActiveNav] = useState("top");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);
  const outputVideoRef = useRef(null);

  const refreshStats = useCallback(async () => {
    try {
      const data = await trafficApi.stats();
      setStats(data);
      return data;
    } catch {
      return null;
    }
  }, []);

  const analysis = useVideoAnalysis(config, { onComplete: refreshStats });
  const { videoFile, videoUrl, processedVideoUrl, isProcessing, progress, result, error } = analysis;

  // Backend heartbeat; load config + history once it is reachable.
  useEffect(() => {
    let cancelled = false;
    let loaded = false;

    const check = async () => {
      try {
        await trafficApi.health();
        if (cancelled) return;
        setBackendOnline(true);
        if (!loaded) {
          loaded = true;
          trafficApi.config().then((c) => !cancelled && setConfig({ ...DEFAULT_CONFIG, ...c })).catch(() => {});
          refreshStats();
        }
      } catch {
        if (!cancelled) setBackendOnline(false);
        loaded = false;
      }
    };

    check();
    const timer = setInterval(check, HEALTH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [refreshStats]);

  const scrollTo = (id) => {
    setActiveNav(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const pickFile = useCallback(() => {
    if (!isProcessing) fileInputRef.current?.click();
  }, [isProcessing]);

  const showOutput = useCallback(() => {
    const video = outputVideoRef.current;
    if (!video) return;
    video.scrollIntoView({ behavior: "smooth", block: "center" });
    video.play().catch(() => {});
  }, []);

  const robotActions = useMemo(
    () => ({ analyze: analysis.analyze, pickFile, showOutput, refreshStats }),
    [analysis.analyze, pickFile, showOutput, refreshStats]
  );

  const robotContext = {
    hasVideo: Boolean(videoFile),
    fileName: videoFile?.name || null,
    isProcessing,
    progress,
    result,
    error,
    stats,
    config,
    backendOnline,
  };

  const progressPercent = Math.min(100, Math.max(0, Number(progress?.progress_percent || 0)));
  const limit = result?.speed_limit_kmh ?? config.speed_limit_kmh;

  const statCards = [
    {
      label: "Vehicles Tracked",
      value: result ? result.vehicles_tracked : isProcessing ? `${progressPercent.toFixed(0)}%` : "—",
      note: result
        ? `${result.speed_records?.length || 0} crossed both speed lines`
        : isProcessing ? "Analysing frames…" : "Waiting for analysis",
      icon: CarFront,
      tone: "cyan",
    },
    {
      label: "Top Speed",
      value: result ? fmt(result.max_speed_kmh) : "—",
      unit: result?.max_speed_kmh != null ? "km/h" : "",
      note: result ? `avg ${fmt(result.average_speed_kmh)} km/h · limit ${fmt(limit, 0)}` : `Limit ${fmt(limit, 0)} km/h`,
      icon: Gauge,
      tone: "amber",
    },
    {
      label: "Plates Identified",
      value: result ? result.plates_identified : "—",
      note: result ? "Unique plates read by OCR" : "OCR results appear here",
      icon: ScanLine,
      tone: "violet",
    },
    {
      label: "Violations",
      value: result ? result.violations_saved : "—",
      note: stats ? `${stats.total_violations} saved all-time` : "Overspeeding tickets",
      icon: ShieldAlert,
      tone: "red",
    },
  ];

  const heroMood = isProcessing ? "thinking" : error ? "alert" : result ? (result.violations_saved ? "alert" : "happy") : "idle";

  return (
    <div className="app-shell">
      <div className="bg-grid" aria-hidden="true" />

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Zap size={21} /></div>
          <div>
            <h2>RAFTAAR<span>.AI</span></h2>
            <p>TRAFFIC INTELLIGENCE</p>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav>
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`nav-item ${activeNav === id ? "active" : ""}`}
              onClick={() => scrollTo(id)}
            >
              <Icon size={17} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className={`system-card ${backendOnline === false ? "offline" : ""}`}>
            <div className="system-status">
              <span className="status-dot" />
              {backendOnline === null ? "CONNECTING" : backendOnline ? "BACKEND ONLINE" : "BACKEND OFFLINE"}
            </div>
            <p>
              {backendOnline === false
                ? "Run: uvicorn app.main:app --reload"
                : "YOLOv8 · ByteTrack · EasyOCR"}
            </p>
            {stats && (
              <div className="system-figures">
                <div><b>{stats.total_violations}</b><small>tickets</small></div>
                <div><b>{stats.videos_analyzed}</b><small>videos</small></div>
                <div><b>{fmt(stats.max_speed_kmh, 0)}</b><small>top km/h</small></div>
              </div>
            )}
          </div>
          <div className="sidebar-footer">
            <span className="mini-logo">R</span>
            <span>Raftaar <b>v1.1</b></span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar" id="top">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="crumb-slash">/</span>
            <strong>Control Room</strong>
          </div>
          <div className="topbar-right">
            <div className="limit-sign" title="Configured speed limit">
              <span>{fmt(limit, 0)}</span>
            </div>
            <div className={`live-pill ${backendOnline === false ? "offline" : ""}`}>
              <span className="status-dot" />
              {backendOnline === false ? "OFFLINE" : "LIVE"}
            </div>
          </div>
        </header>

        <section className="hero">
          <motion.div
            className="hero-copy"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="eyebrow"><Cpu size={13} /> COMPUTER VISION TRAFFIC ENFORCEMENT</div>
            <h1>Every vehicle.<br /><span>Every km/h.</span> Every plate.</h1>
            <p>
              Upload road footage — {ROBOT_NAME} detects, tracks and times each vehicle between two
              virtual lines, reads number plates of speeders and talks you through the result.
            </p>
          </motion.div>

          <div className="hero-road" aria-hidden="true">
            <div className="road">
              <div className="road-line line-a"><span>LINE 1</span></div>
              <div className="road-line line-b"><span>LINE 2</span></div>
              <div className="lane-dashes" />
              <div className="car car-1" />
              <div className="car car-2 speeding" />
              <div className="car car-3" />
            </div>
            <motion.div
              className="hero-robot"
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
            >
              <RobotFace mood={heroMood} size={112} />
            </motion.div>
          </div>
        </section>

        <section className="stats-grid">
          {statCards.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <motion.div
                className={`stat-card tone-${stat.tone}`}
                key={stat.label}
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + index * 0.07 }}
              >
                <div className="stat-top">
                  <span>{stat.label}</span>
                  <div className="stat-icon"><Icon size={18} /></div>
                </div>
                <div className="stat-value">
                  {stat.value}
                  {stat.unit && <small>{stat.unit}</small>}
                </div>
                <div className="stat-note">{stat.note}</div>
              </motion.div>
            );
          })}
        </section>

        <section className="workspace-grid" id="analysis">
          <div className="panel video-panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title"><FileVideo size={18} /> Video Analysis</div>
                <p>Upload traffic footage to begin processing</p>
              </div>
              <span className="panel-tag">INPUT</span>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept={`video/*,${config.allowed_video_extensions}`}
              onChange={(event) => {
                analysis.selectFile(event.target.files?.[0]);
                event.target.value = "";
              }}
              hidden
            />

            {!videoUrl ? (
              <button
                type="button"
                className={`upload-zone ${isDragging ? "dragging" : ""}`}
                onClick={pickFile}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setIsDragging(false);
                  analysis.selectFile(event.dataTransfer.files?.[0]);
                }}
              >
                <motion.div
                  className="upload-icon-wrap"
                  animate={{ y: [0, -5, 0] }}
                  transition={{ duration: 2.2, repeat: Infinity }}
                >
                  <Upload size={24} />
                </motion.div>
                <h3>Drop your traffic video here</h3>
                <p>or click to browse files</p>
                <span className="upload-formats">
                  {config.allowed_video_extensions.replaceAll(".", "").toUpperCase().split(",").join(" · ")} · up to {config.max_upload_size_mb} MB
                </span>
              </button>
            ) : (
              <div className="video-preview">
                <video src={videoUrl} controls playsInline />
                <div className="video-file-info">
                  <div className="file-icon"><FileVideo size={18} /></div>
                  <div className="file-name">
                    <strong>{videoFile.name}</strong>
                    <span>{(videoFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                  </div>
                  <button className="ghost-button" onClick={analysis.removeVideo}>
                    {isProcessing ? "Cancel" : "Remove"}
                  </button>
                </div>
              </div>
            )}

            {error && (
              <div className="notice notice-error">
                <AlertCircle size={17} /> {error}
              </div>
            )}

            {isProcessing && progress && (
              <div className="progress-card">
                <div className="progress-head">
                  <strong>
                    <LoaderCircle size={15} className="spin-icon" />
                    {progress.status === "uploading" ? "Uploading video…" : progress.status === "queued" ? "Queued…" : "Processing frames…"}
                  </strong>
                  <b>{progressPercent.toFixed(1)}%</b>
                </div>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
                </div>
                <div className="progress-foot">
                  <span>Frames {progress.processed_frames || 0} / {progress.total_frames || "—"}</span>
                  <span>Live progress</span>
                </div>
              </div>
            )}

            {result && (
              <div className="notice notice-success">
                <CheckCircle2 size={17} />
                Analysis complete in {fmt(result.processing_seconds)} s · {result.processed_frames} frames
              </div>
            )}

            <div className="upload-footer">
              <div className="secure-note">
                <ShieldAlert size={15} /> Processed locally by your backend
              </div>
              <button
                className="analyze-button"
                disabled={!videoFile || isProcessing || backendOnline === false}
                onClick={analysis.analyze}
              >
                {isProcessing ? (
                  <><LoaderCircle size={17} className="spin-icon" /> Processing…</>
                ) : (
                  <><ScanLine size={17} /> Analyze Video <ArrowUpRight size={16} /></>
                )}
              </button>
            </div>
          </div>

          <div className="panel pipeline-panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title"><Bot size={18} /> Agent Pipeline</div>
                <p>Independent agents coordinated per frame</p>
              </div>
              <span className="panel-tag">ORCHESTRATOR</span>
            </div>

            <ol className="pipeline">
              {PIPELINE.map((stage, index) => {
                const Icon = stage.icon;
                const state = stageState(index, progress, result, error);
                return (
                  <li key={stage.key} className={`pipe-stage is-${state}`}>
                    <div className="pipe-icon"><Icon size={16} /></div>
                    <div className="pipe-text">
                      <strong>{stage.label}</strong>
                      <span>{stage.tech}</span>
                    </div>
                    <div className="pipe-state">
                      {state === "done" ? <CheckCircle2 size={15} /> : state === "active" ? <LoaderCircle size={15} className="spin-icon" /> : state === "error" ? <AlertCircle size={15} /> : null}
                    </div>
                  </li>
                );
              })}
            </ol>

            <div className="pipeline-facts">
              <div><Timer size={14} /><span>Duration</span><b>{result ? `${fmt(result.duration_seconds)} s` : "—"}</b></div>
              <div><Video size={14} /><span>Resolution</span><b>{result ? `${result.width}×${result.height}` : "—"}</b></div>
              <div><Gauge size={14} /><span>FPS</span><b>{result ? fmt(result.fps, 0) : "—"}</b></div>
              <div><CarFront size={14} /><span>Mix</span><b>{result && Object.keys(result.vehicle_types || {}).length ? Object.entries(result.vehicle_types).map(([k, v]) => `${v} ${k}`).join(", ") : "—"}</b></div>
            </div>
          </div>
        </section>

        {result && processedVideoUrl && (
          <section className="panel output-panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title"><Radar size={18} /> Annotated Output</div>
                <p>Vehicle boxes, tracking IDs, speeds, plates and live HUD</p>
              </div>
              <a className="ghost-button" href={processedVideoUrl} download>
                <Download size={15} /> Download
              </a>
            </div>
            <video
              ref={outputVideoRef}
              key={processedVideoUrl}
              src={processedVideoUrl}
              controls
              playsInline
              preload="metadata"
            />
          </section>
        )}

        <ResultsPanel result={result} isProcessing={isProcessing} />

        <footer className="page-footer">
          <span><span className="status-dot" /> RAFTAAR SYSTEM {backendOnline === false ? "OFFLINE" : "ONLINE"}</span>
          <span>YOLOv8 · ByteTrack · OpenCV · EasyOCR · FastAPI</span>
        </footer>
      </main>

      <RobotAssistant ctx={robotContext} actions={robotActions} />
    </div>
  );
}
