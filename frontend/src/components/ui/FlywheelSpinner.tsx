import { cn } from "@/lib/cn"

const sizes = {
  sm: 32,
  md: 64,
  lg: 96,
} as const

interface FlywheelSpinnerProps {
  size?: keyof typeof sizes
  className?: string
}

function FlywheelSpinner({ size = "md", className }: FlywheelSpinnerProps) {
  const px = sizes[size]
  const r = px * 0.3        // orbit radius
  const dotR = px * 0.055   // dot radius
  const center = px / 2

  return (
    <svg
      width={px}
      height={px}
      viewBox={`0 0 ${px} ${px}`}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("flywheel-spinner", className)}
      aria-label="Loading"
      role="img"
    >
      <defs>
        {/* Gradient trails for each dot */}
        <linearGradient id={`trail-coral-${px}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#E94D35" stopOpacity="0" />
          <stop offset="100%" stopColor="#E94D35" stopOpacity="0.8" />
        </linearGradient>
        <linearGradient id={`trail-orange-${px}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#F97316" stopOpacity="0" />
          <stop offset="100%" stopColor="#F97316" stopOpacity="0.7" />
        </linearGradient>
        <linearGradient id={`trail-light-${px}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#FB923C" stopOpacity="0" />
          <stop offset="100%" stopColor="#FB923C" stopOpacity="0.6" />
        </linearGradient>

        {/* Glow filter */}
        <filter id={`glow-${px}`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation={px * 0.015} result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <style>{`
        /* Orbit keyframes — full rotation */
        @keyframes fw-orbit-${px} {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }

        /* Trail arc grows longer as speed increases */
        @keyframes fw-trail-grow-${px} {
          0%   { stroke-dashoffset: ${r * 2 * Math.PI * 0.92}; opacity: 0.2; }
          50%  { stroke-dashoffset: ${r * 2 * Math.PI * 0.7};  opacity: 0.6; }
          100% { stroke-dashoffset: ${r * 2 * Math.PI * 0.92}; opacity: 0.2; }
        }

        /* Spawn dot — appears, orbits outward, fades */
        @keyframes fw-spawn-${px} {
          0%   { opacity: 0; transform: scale(0) translate(0, 0); }
          15%  { opacity: 0.8; transform: scale(1) translate(0, 0); }
          80%  { opacity: 0.4; transform: scale(0.6) translate(${px * 0.06}px, -${px * 0.06}px); }
          100% { opacity: 0; transform: scale(0) translate(${px * 0.09}px, -${px * 0.09}px); }
        }

        /* Pulse on the center point */
        @keyframes fw-center-pulse-${px} {
          0%, 100% { opacity: 0.15; r: ${px * 0.025}px; }
          50%      { opacity: 0.35; r: ${px * 0.045}px; }
        }

        /* Dot 1 — coral, fastest acceleration curve */
        .fw-orbit-1-${px} {
          transform-origin: ${center}px ${center}px;
          animation: fw-orbit-${px} 3s cubic-bezier(0.2, 0, 0.4, 1) infinite;
        }
        .fw-trail-1-${px} {
          transform-origin: ${center}px ${center}px;
          animation:
            fw-orbit-${px} 3s cubic-bezier(0.2, 0, 0.4, 1) infinite,
            fw-trail-grow-${px} 3s cubic-bezier(0.2, 0, 0.4, 1) infinite;
        }

        /* Dot 2 — orange, offset start, slightly different curve */
        .fw-orbit-2-${px} {
          transform-origin: ${center}px ${center}px;
          animation: fw-orbit-${px} 3.4s cubic-bezier(0.25, 0, 0.35, 1) infinite;
          animation-delay: -0.8s;
        }
        .fw-trail-2-${px} {
          transform-origin: ${center}px ${center}px;
          animation:
            fw-orbit-${px} 3.4s cubic-bezier(0.25, 0, 0.35, 1) infinite,
            fw-trail-grow-${px} 3.4s cubic-bezier(0.25, 0, 0.35, 1) infinite;
          animation-delay: -0.8s;
        }

        /* Dot 3 — light orange, most delayed */
        .fw-orbit-3-${px} {
          transform-origin: ${center}px ${center}px;
          animation: fw-orbit-${px} 3.8s cubic-bezier(0.15, 0, 0.45, 1) infinite;
          animation-delay: -1.6s;
        }
        .fw-trail-3-${px} {
          transform-origin: ${center}px ${center}px;
          animation:
            fw-orbit-${px} 3.8s cubic-bezier(0.15, 0, 0.45, 1) infinite,
            fw-trail-grow-${px} 3.8s cubic-bezier(0.15, 0, 0.45, 1) infinite;
          animation-delay: -1.6s;
        }

        /* Spawn particle */
        .fw-spawn-${px} {
          transform-origin: center;
          animation: fw-spawn-${px} 3s ease-out infinite;
          animation-delay: -1.2s;
        }

        /* Center pulse */
        .fw-center-${px} {
          animation: fw-center-pulse-${px} 3s ease-in-out infinite;
        }
      `}</style>

      {/* Center glow */}
      <circle
        cx={center}
        cy={center}
        r={px * 0.03}
        fill="#E94D35"
        className={`fw-center-${px}`}
      />

      {/* Trail arcs — drawn as dashed circle strokes that rotate with the dots */}
      <circle
        cx={center}
        cy={center}
        r={r}
        fill="none"
        stroke={`url(#trail-coral-${px})`}
        strokeWidth={dotR * 1.8}
        strokeLinecap="round"
        strokeDasharray={`${r * 2 * Math.PI}`}
        strokeDashoffset={`${r * 2 * Math.PI * 0.85}`}
        className={`fw-trail-1-${px}`}
        filter={`url(#glow-${px})`}
      />
      <circle
        cx={center}
        cy={center}
        r={r}
        fill="none"
        stroke={`url(#trail-orange-${px})`}
        strokeWidth={dotR * 1.4}
        strokeLinecap="round"
        strokeDasharray={`${r * 2 * Math.PI}`}
        strokeDashoffset={`${r * 2 * Math.PI * 0.88}`}
        className={`fw-trail-2-${px}`}
      />
      <circle
        cx={center}
        cy={center}
        r={r}
        fill="none"
        stroke={`url(#trail-light-${px})`}
        strokeWidth={dotR * 1.1}
        strokeLinecap="round"
        strokeDasharray={`${r * 2 * Math.PI}`}
        strokeDashoffset={`${r * 2 * Math.PI * 0.9}`}
        className={`fw-trail-3-${px}`}
      />

      {/* Dot 1 — coral (largest) */}
      <circle
        cx={center}
        cy={center - r}
        r={dotR}
        fill="#E94D35"
        className={`fw-orbit-1-${px}`}
        filter={`url(#glow-${px})`}
      />

      {/* Dot 2 — orange */}
      <circle
        cx={center}
        cy={center - r}
        r={dotR * 0.8}
        fill="#F97316"
        className={`fw-orbit-2-${px}`}
      />

      {/* Dot 3 — light orange (smallest) */}
      <circle
        cx={center}
        cy={center - r}
        r={dotR * 0.65}
        fill="#FB923C"
        className={`fw-orbit-3-${px}`}
      />

      {/* Spawn particle — appears near dot 1's path */}
      <circle
        cx={center + r * 0.7}
        cy={center - r * 0.7}
        r={dotR * 0.4}
        fill="#E94D35"
        className={`fw-spawn-${px}`}
      />
    </svg>
  )
}

export { FlywheelSpinner }
