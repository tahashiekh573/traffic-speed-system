/**
 * Animated SVG robot. Mood drives eyes, mouth, ears and antenna:
 *   idle | listening | thinking | speaking | happy | alert
 */
export default function RobotFace({ mood = "idle", size = 120, className = "" }) {
  return (
    <svg
      className={`robot-face mood-${mood} ${className}`}
      width={size}
      height={size}
      viewBox="0 0 120 120"
      role="img"
      aria-label={`Robot assistant (${mood})`}
    >
      <defs>
        <linearGradient id="robot-shell" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--robot-shell-a)" />
          <stop offset="1" stopColor="var(--robot-shell-b)" />
        </linearGradient>
        <radialGradient id="robot-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="var(--robot-eye)" stopOpacity="0.55" />
          <stop offset="1" stopColor="var(--robot-eye)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* antenna */}
      <line x1="60" y1="22" x2="60" y2="10" className="robot-antenna-stem" />
      <circle cx="60" cy="8" r="5" className="robot-antenna-bulb" />

      {/* ears */}
      <rect x="10" y="48" width="10" height="26" rx="5" className="robot-ear robot-ear-left" />
      <rect x="100" y="48" width="10" height="26" rx="5" className="robot-ear robot-ear-right" />

      {/* sound rings while listening */}
      <g className="robot-sound-rings">
        <path d="M6 50 Q-2 61 6 72" />
        <path d="M114 50 Q122 61 114 72" />
      </g>

      {/* head */}
      <rect x="18" y="22" width="84" height="78" rx="24" fill="url(#robot-shell)" className="robot-head" />

      {/* visor */}
      <rect x="27" y="36" width="66" height="40" rx="16" className="robot-visor" />
      <circle cx="60" cy="56" r="34" fill="url(#robot-glow)" className="robot-visor-glow" />

      {/* eyes */}
      <g className="robot-eyes">
        <g className="robot-eye-group">
          <ellipse cx="45" cy="54" rx="7" ry="8" className="robot-eye" />
          <ellipse cx="75" cy="54" rx="7" ry="8" className="robot-eye" />
        </g>
        <path d="M38 56 Q45 47 52 56" className="robot-eye-happy" />
        <path d="M68 56 Q75 47 82 56" className="robot-eye-happy" />
        <path d="M38 50 L52 54" className="robot-eye-brow" />
        <path d="M82 50 L68 54" className="robot-eye-brow" />
      </g>

      {/* mouth */}
      <g className="robot-mouth">
        <rect x="47" y="84" width="4" height="6" rx="2" className="robot-mouth-bar bar-1" />
        <rect x="54" y="84" width="4" height="6" rx="2" className="robot-mouth-bar bar-2" />
        <rect x="61" y="84" width="4" height="6" rx="2" className="robot-mouth-bar bar-3" />
        <rect x="68" y="84" width="4" height="6" rx="2" className="robot-mouth-bar bar-4" />
      </g>

      {/* thinking dots */}
      <g className="robot-thinking">
        <circle cx="51" cy="87" r="2.6" />
        <circle cx="60" cy="87" r="2.6" />
        <circle cx="69" cy="87" r="2.6" />
      </g>
    </svg>
  );
}
