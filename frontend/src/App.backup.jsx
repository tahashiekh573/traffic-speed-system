import { useState } from "react";
import { motion } from "framer-motion";
import {
  Activity, ArrowUpRight, CarFront, CircleGauge, Clock3,
  FileVideo, Gauge, LayoutDashboard, ScanLine, ShieldAlert,
  Upload, Video, Zap, LoaderCircle, AlertCircle, CheckCircle2,
} from "lucide-react";
import "./App.css";

const API_URL = "http://localhost:8000/api/v1/videos/process";

function App() {
  const [videoFile, setVideoFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleFile = (file) => {
    if (!file) return;

    const allowedExtensions = ["mp4", "avi", "mov", "mkv"];
    const extension = file.name.split(".").pop().toLowerCase();

    if (!allowedExtensions.includes(extension)) {
      setError("Please select an MP4, AVI, MOV, or MKV video.");
      return;
    }

    if (file.size > 500 * 1024 * 1024) {
      setError("Video size must be less than 500 MB.");
      return;
    }

    if (videoUrl) URL.revokeObjectURL(videoUrl);

    setVideoFile(file);
    setVideoUrl(URL.createObjectURL(file));
    setResult(null);
    setError("");
  };

  const handleInput = (event) => {
    handleFile(event.target.files?.[0]);
    event.target.value = "";
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    handleFile(event.dataTransfer.files?.[0]);
  };

  const removeVideo = () => {
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoUrl("");
    setVideoFile(null);
    setResult(null);
    setError("");
  };

  const analyzeVideo = async () => {
    if (!videoFile || isProcessing) return;

    setIsProcessing(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", videoFile);

      const response = await fetch(API_URL, {
        method: "POST",
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const message =
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail || data);
        throw new Error(message || `Server error: ${response.status}`);
      }

      setResult(data);
    } catch (err) {
      setError(
        err.message ||
        "Could not connect to the backend. Make sure FastAPI is running."
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const violations = result?.violations || [];
  const plates = [
    ...new Set(
      violations
        .map((item) => item.plate_number)
        .filter(Boolean)
    ),
  ];
  const averageSpeed = violations.length
    ? (
        violations.reduce((sum, item) => sum + item.speed_kmh, 0) /
        violations.length
      ).toFixed(1)
    : "—";

  const stats = [
    {
      label: "Frames Processed",
      value: result ? result.processed_frames : "—",
      note: result ? `${result.total_frames} total frames` : "Waiting for analysis",
      icon: CarFront,
      color: "blue",
    },
    {
      label: "Avg. Violation Speed",
      value: result ? averageSpeed : "—",
      note: result ? "km/h · violating records" : "Speed data not processed",
      icon: Gauge,
      color: "purple",
    },
    {
      label: "Plates Identified",
      value: result ? plates.length : "—",
      note: result ? "Unique recognized plates in violations" : "OCR results will appear here",
      icon: ScanLine,
      color: "cyan",
    },
    {
      label: "Violations Saved",
      value: result ? result.violations_saved : "—",
      note: result ? "Overspeeding records saved" : "No analysis yet",
      icon: ShieldAlert,
      color: "orange",
    },
  ];

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Activity size={23} /></div>
          <div>
            <h2>TRAFFIC<span>IQ</span></h2>
            <p>INTELLIGENCE SYSTEM</p>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <div className="nav-item active">
          <LayoutDashboard size={18} />
          <span>Overview</span>
          <div className="nav-indicator" />
        </div>
        <div className="nav-item">
          <Video size={18} />
          <span>Video Analysis</span>
        </div>
        <div className="nav-item">
          <ScanLine size={18} />
          <span>Plate Recognition</span>
        </div>
        <div className="nav-item">
          <ShieldAlert size={18} />
          <span>Violations</span>
        </div>

        <div className="sidebar-bottom">
          <div className="system-card">
            <div className="system-status">
              <span className="status-dot" />
              SYSTEM READY
            </div>
            <p>AI traffic monitoring</p>
            <div className="system-line"><span /></div>
            <small>Local processing environment</small>
          </div>
          <div className="sidebar-footer">
            <span className="mini-logo">T</span>
            <span>TrafficIQ <b>v1.0</b></span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="crumb-slash">/</span>
            <strong>Overview</strong>
          </div>
          <div className="topbar-right">
            <div className="live-pill">
              <span className="status-dot" />
              LOCAL SYSTEM
            </div>
            <div className="avatar">AI</div>
          </div>
        </header>

        <section className="page-heading">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="eyebrow">
              <Zap size={13} /> AI-POWERED TRAFFIC ANALYTICS
            </div>
            <h1>Traffic <span>Intelligence</span></h1>
            <p>
              Analyze traffic footage. Detect vehicles. Read plates.
              <br className="desktop-break" /> Understand the road in real time.
            </p>
          </motion.div>

          <motion.div
            className="heading-badge"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
          >
            <CircleGauge size={20} />
            <div>
              <strong>AI ANALYTICS</strong>
              <span>Video intelligence</span>
            </div>
          </motion.div>
        </section>

        <section className="stats-grid">
          {stats.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <motion.div
                className={`stat-card ${stat.color}`}
                key={stat.label}
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + index * 0.08 }}
                whileHover={{ y: -4 }}
              >
                <div className="stat-top">
                  <span>{stat.label}</span>
                  <div className="stat-icon"><Icon size={19} /></div>
                </div>
                <div className="stat-value">{stat.value}</div>
                <div className="stat-note">
                  <span className="note-dot" />
                  {stat.note}
                </div>
              </motion.div>
            );
          })}
        </section>

        <section className="workspace-grid">
          <motion.div
            className="panel video-panel"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
          >
            <div className="panel-heading">
              <div>
                <div className="panel-title">
                  <FileVideo size={18} /> Video Analysis
                </div>
                <p>Upload traffic footage to begin processing</p>
              </div>
              <span className="panel-tag">VIDEO INPUT</span>
            </div>

            {!videoUrl ? (
              <label
                className={`upload-zone ${isDragging ? "dragging" : ""}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
              >
                <input
                  type="file"
                  accept="video/mp4,video/avi,video/quicktime,video/x-matroska,.mkv,.avi"
                  onChange={handleInput}
                  hidden
                />
                <motion.div
                  className="upload-icon-wrap"
                  animate={{ y: [0, -5, 0] }}
                  transition={{ duration: 2.2, repeat: Infinity }}
                >
                  <Upload size={25} />
                </motion.div>
                <h3>Drop your traffic video here</h3>
                <p>or click to browse files</p>
                <span className="upload-formats">MP4 · AVI · MOV · MKV</span>
              </label>
            ) : (
              <div className="video-preview">
                <video src={videoUrl} controls />
                <div className="video-file-info">
                  <div className="file-icon"><FileVideo size={18} /></div>
                  <div className="file-name">
                    <strong>{videoFile.name}</strong>
                    <span>{(videoFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                  </div>
                  <button
                    className="remove-video"
                    onClick={removeVideo}
                    disabled={isProcessing}
                  >
                    Remove
                  </button>
                </div>
              </div>
            )}

            {error && (
              <div style={{
                marginTop: 14, padding: 12, borderRadius: 10,
                background: "rgba(255,70,90,0.10)",
                color: "#ff7d8b", display: "flex",
                alignItems: "center", gap: 9, fontSize: 13,
                overflowWrap: "anywhere"
              }}>
                <AlertCircle size={17} /> {error}
              </div>
            )}

            {result && (
              <div style={{
                marginTop: 14, padding: 12, borderRadius: 10,
                background: "rgba(40,210,150,0.10)",
                color: "#5ce0ad", display: "flex",
                alignItems: "center", gap: 9, fontSize: 13
              }}>
                <CheckCircle2 size={17} />
                Video analysis completed successfully.
              </div>
            )}

            <div className="upload-footer">
              <div className="secure-note">
                <ShieldAlert size={15} />
                Video is processed by your local backend
              </div>
              <button
                className="analyze-button"
                disabled={!videoFile || isProcessing}
                onClick={analyzeVideo}
              >
                {isProcessing ? (
                  <>
                    <LoaderCircle size={17} className="spin-icon" />
                    Processing...
                  </>
                ) : (
                  <>
                    <ScanLine size={17} />
                    Analyze Video
                    <ArrowUpRight size={16} />
                  </>
                )}
              </button>
            </div>
          </motion.div>

          <motion.div
            className="panel activity-panel"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45 }}
          >
            <div className="panel-heading">
              <div>
                <div className="panel-title">
                  <Activity size={18} /> Analysis Overview
                </div>
                <p>Detection insights from your video</p>
              </div>
              <span className="panel-tag">INSIGHTS</span>
            </div>

            <div className="overview-visual">
              <div className="visual-orbit orbit-one" />
              <div className="visual-orbit orbit-two" />
              <div className="visual-center"><ScanLine size={32} /></div>
              <div className="orbit-point point-one"><CarFront size={16} /></div>
              <div className="orbit-point point-two"><Gauge size={16} /></div>
              <div className="orbit-point point-three"><ShieldAlert size={16} /></div>
            </div>

            <div className="overview-message">
              <h3>
                {isProcessing
                  ? "Analyzing your video..."
                  : result
                    ? "Analysis completed"
                    : "Ready to analyze"}
              </h3>
              <p>
                {isProcessing
                  ? "The AI system is processing frames and checking traffic violations. This may take some time."
                  : result
                    ? `${result.violations_saved} violations saved from ${result.processed_frames} processed frames.`
                    : "Upload a video to view processing statistics, recognized plates, and traffic violations."}
              </p>
            </div>

            <div className="overview-bottom">
              <div><Clock3 size={15} /><span>Processing status</span></div>
              <strong>
                {isProcessing ? "In progress" : result ? "Completed" : "Not started"}
              </strong>
            </div>
          </motion.div>
        </section>

        <section className="panel results-panel">
          <div className="panel-heading">
            <div>
              <div className="panel-title">
                <ScanLine size={18} /> Detection Results
              </div>
              <p>Recognized plates and overspeeding records</p>
            </div>
            <span className="panel-tag">ANALYSIS RESULTS</span>
          </div>

          {!result ? (
            <div className="empty-results">
              <div className="empty-icon"><ScanLine size={24} /></div>
              <strong>
                {isProcessing ? "Processing video..." : "No detection results yet"}
              </strong>
              <span>
                {isProcessing
                  ? "Results will appear here when the backend finishes processing."
                  : "Your violation records and plate readings will appear here after analysis."}
              </span>
            </div>
          ) : violations.length === 0 ? (
            <div className="empty-results">
              <div className="empty-icon"><CheckCircle2 size={24} /></div>
              <strong>No violations found</strong>
              <span>
                {result.processed_frames} frames were processed and no overspeeding records were returned.
              </span>
            </div>
          ) : (
            <div style={{ width: "100%", overflowX: "auto" }}>
              <table style={{
                width: "100%", borderCollapse: "collapse",
                textAlign: "left", fontSize: 13, minWidth: 620
              }}>
                <thead>
                  <tr style={{ color: "#9ba9bd", borderBottom: "1px solid rgba(150,170,200,0.16)" }}>
                    {["Track ID", "Number Plate", "Vehicle Speed", "Speed Limit", "Violation Time"].map((heading) => (
                      <th key={heading} style={{ padding: "14px 12px", fontWeight: 600 }}>{heading}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {violations.map((item, index) => (
                    <tr key={item.id ?? index} style={{ borderBottom: "1px solid rgba(150,170,200,0.10)" }}>
                      <td style={{ padding: "14px 12px" }}>{item.track_id}</td>
                      <td style={{ padding: "14px 12px", fontWeight: 600 }}>
                        {item.plate_number || "Not recognized"}
                      </td>
                      <td style={{ padding: "14px 12px", color: "#ff8b8b" }}>
                        {Number(item.speed_kmh).toFixed(1)} km/h
                      </td>
                      <td style={{ padding: "14px 12px" }}>
                        {Number(item.speed_limit_kmh).toFixed(1)} km/h
                      </td>
                      <td style={{ padding: "14px 12px" }}>
                        {item.violation_time
                          ? new Date(item.violation_time).toLocaleString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <footer className="page-footer">
          <span><span className="status-dot" /> TRAFFICIQ SYSTEM ONLINE</span>
          <span>AI Traffic Monitoring Dashboard</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
