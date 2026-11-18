import { motion } from "framer-motion";
import { CheckCircle2, Gauge, HardHat, ScanLine, ShieldAlert, Siren } from "lucide-react";

const fmt = (value, digits = 1) =>
  value === null || value === undefined ? "—" : Number(value).toFixed(digits);

function EmptyState({ icon: Icon, title, text }) {
  return (
    <div className="empty-results">
      <div className="empty-icon"><Icon size={22} /></div>
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function SpeedBoard({ result }) {
  const records = [...(result.speed_records || [])].sort((a, b) => b.speed_kmh - a.speed_kmh);
  const limit = Number(result.speed_limit_kmh) || 60;
  const scaleMax = Math.max(limit * 1.6, ...records.map((r) => r.speed_kmh)) || 1;
  const limitPos = (limit / scaleMax) * 100;

  if (!records.length) {
    return (
      <EmptyState
        icon={Gauge}
        title="No speeds measured"
        text="Vehicles were tracked, but none crossed both virtual speed lines. Lines sit at LINE_1_Y / LINE_2_Y (fractions of the frame height). Speed needs a fixed camera looking along the road."
      />
    );
  }

  return (
    <div className="speed-board">
      {records.map((record, index) => (
        <motion.div
          className={`speed-row ${record.is_overspeeding ? "is-over" : ""}`}
          key={record.track_id}
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: Math.min(index * 0.04, 0.6) }}
        >
          <div className="speed-row-id">
            <strong>#{record.track_id}</strong>
            <span>{record.vehicle_type || "vehicle"}</span>
          </div>
          <div className="speed-meter" aria-hidden="true">
            <div className="speed-meter-fill" style={{ width: `${(record.speed_kmh / scaleMax) * 100}%` }} />
            <div className="speed-meter-limit" style={{ left: `${limitPos}%` }} />
          </div>
          <div className="speed-row-value">
            {fmt(record.speed_kmh)} <small>km/h</small>
          </div>
          <div className="speed-row-plate">
            {record.plate_number ? <span className="mini-plate">{record.plate_number}</span> : <em>no plate</em>}
          </div>
        </motion.div>
      ))}
      <div className="speed-legend">
        <span><i className="legend-ok" /> within limit</span>
        <span><i className="legend-over" /> overspeeding</span>
        <span><i className="legend-limit" /> {fmt(limit, 0)} km/h limit</span>
      </div>
    </div>
  );
}

function PlateWall({ result }) {
  const plates = result.recognized_plates || [];
  const overspeeders = new Set((result.violations || []).map((v) => v.track_id));

  if (!plates.length) {
    return (
      <EmptyState
        icon={ScanLine}
        title="No number plates recognized"
        text={
          result.plates_attempted
            ? `OCR tried ${result.plates_attempted} vehicles but no plate was readable — the characters are too small or blurry in this video. Plates need roughly 20+ pixel tall letters: use 1080p/4K footage or a camera closer to the road.`
            : "No vehicle came close enough for a plate read. Higher-resolution, closer footage helps."
        }
      />
    );
  }

  return (
    <div className="plate-wall">
      {plates.map((plate, index) => (
        <motion.div
          className={`plate-card ${overspeeders.has(plate.track_id) ? "flagged" : ""}`}
          key={`${plate.track_id}-${plate.plate_number}`}
          initial={{ opacity: 0, rotateX: -50 }}
          animate={{ opacity: 1, rotateX: 0 }}
          transition={{ delay: Math.min(index * 0.05, 0.6) }}
        >
          <div className="plate-face">
            <span className="plate-region">TRK</span>
            <span className="plate-text">{plate.plate_number}</span>
          </div>
          <div className="plate-meta">
            <span>Vehicle #{plate.track_id}</span>
            {overspeeders.has(plate.track_id) ? (
              <b className="tag-danger"><Siren size={12} /> Violation</b>
            ) : (
              <b className="tag-ok"><CheckCircle2 size={12} /> Read</b>
            )}
          </div>
        </motion.div>
      ))}
    </div>
  );
}

function HelmetBoard({ result, helmetAvailable }) {
  if (!result.helmet_check_enabled) {
    return (
      <EmptyState
        icon={HardHat}
        title="Helmet check is off"
        text={
          helmetAvailable
            ? "The helmet model was not active for this video. Re-run the analysis."
            : "Helmet check is not ready. It needs the model at weights/helmet.onnx plus onnxruntime (.venv/Scripts/python -m pip install onnxruntime), then a server restart. Riders without a helmet will then be boxed in red and ticketed."
        }
      />
    );
  }

  const records = result.helmet_records || [];
  if (!records.length) {
    return (
      <EmptyState
        icon={HardHat}
        title="No riders checked"
        text="No motorcycle was close enough to check the rider's head."
      />
    );
  }

  return (
    <div className="helmet-grid">
      {records.map((record) => (
        <div key={record.track_id} className={`helmet-card ${record.has_helmet ? "ok" : "bad"}`}>
          <div className="helmet-icon"><HardHat size={18} /></div>
          <div>
            <strong>Motorcycle #{record.track_id}</strong>
            <span>{record.has_helmet ? "Helmet worn" : "No helmet"} · {Math.round(record.confidence * 100)}%</span>
          </div>
          {record.plate_number && <span className="mini-plate">{record.plate_number}</span>}
        </div>
      ))}
    </div>
  );
}

function ViolationTable({ result }) {
  const violations = result.violations || [];

  if (!violations.length) {
    return (
      <EmptyState
        icon={CheckCircle2}
        title="No violations"
        text={`${result.processed_frames} frames processed — no overspeeding${result.helmet_check_enabled ? " and no rider without a helmet" : ""}.`}
      />
    );
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Ticket</th>
            <th>Type</th>
            <th>Vehicle</th>
            <th>Number plate</th>
            <th>Speed</th>
            <th>Over by</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {violations.map((item) => {
            const helmet = item.violation_type === "no_helmet";
            return (
              <tr key={item.id}>
                <td className="mono">TKT-{String(item.id).padStart(5, "0")}</td>
                <td>
                  <span className={`type-badge ${helmet ? "type-helmet" : "type-speed"}`}>
                    {helmet ? <HardHat size={12} /> : <Gauge size={12} />}
                    {helmet ? "No helmet" : "Overspeed"}
                  </span>
                </td>
                <td>#{item.track_id}</td>
                <td>{item.plate_number ? <span className="mini-plate">{item.plate_number}</span> : <em>Not recognized</em>}</td>
                <td className={helmet ? "" : "danger-text"}>
                  {item.speed_kmh != null ? `${fmt(item.speed_kmh)} km/h` : "—"}
                </td>
                <td>
                  {!helmet && item.speed_kmh != null ? `+${fmt(item.speed_kmh - item.speed_limit_kmh)} km/h` : "—"}
                </td>
                <td>{item.violation_time ? new Date(item.violation_time).toLocaleString() : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function ResultsPanel({ result, isProcessing, helmetAvailable }) {
  return (
    <section className="panel results-panel" id="results">
      <div className="panel-heading">
        <div>
          <div className="panel-title"><ScanLine size={18} /> Detection Results</div>
          <p>Measured speeds, helmet checks, recognized plates and tickets</p>
        </div>
        <span className="panel-tag">ANALYSIS RESULTS</span>
      </div>

      {!result ? (
        <EmptyState
          icon={ScanLine}
          title={isProcessing ? "Processing video…" : "No detection results yet"}
          text={
            isProcessing
              ? "Results appear here as soon as the backend finishes."
              : "Speed readings, plates and violation tickets will appear here after analysis."
          }
        />
      ) : (
        <div className="results-stack">
          <div className="result-block" id="speeds">
            <h3><Gauge size={16} /> Speed board <span>{result.speed_records?.length || 0} measured</span></h3>
            <SpeedBoard result={result} />
          </div>

          <div className="result-block" id="plates">
            <h3><ScanLine size={16} /> Number plates <span>{result.plates_identified} identified</span></h3>
            <PlateWall result={result} />
          </div>

          <div className="result-block" id="helmets">
            <h3>
              <HardHat size={16} /> Helmet check
              <span>
                {result.helmet_check_enabled
                  ? `${result.motorcycles_checked} checked · ${result.no_helmet_violations} without helmet`
                  : "off"}
              </span>
            </h3>
            <HelmetBoard result={result} helmetAvailable={helmetAvailable} />
          </div>

          <div className="result-block" id="violations">
            <h3>
              <ShieldAlert size={16} /> Violation tickets
              <span>
                {result.overspeed_violations ?? result.violations_saved} overspeed · {result.no_helmet_violations || 0} no helmet
              </span>
            </h3>
            <ViolationTable result={result} />
          </div>
        </div>
      )}
    </section>
  );
}
