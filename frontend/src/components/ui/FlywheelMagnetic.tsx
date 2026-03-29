import { useRef, useEffect, useCallback } from "react"
import { cn } from "@/lib/cn"

interface FlywheelMagneticProps {
  size?: number
  className?: string
}

// --- Palette & constants ---------------------------------------------------

const COLORS = ["#E94D35", "#F97316", "#FB923C", "#FDBA74"] as const
const RING_COLOR = "#E94D35"
const GLOW_COLOR = "rgba(233, 77, 53, 0.35)"

const SPAWN_INTERVAL_MS = 120      // new particle every N ms
const MAX_FREE_PARTICLES = 60      // cap in-flight particles
const MAX_LOCKED_PARTICLES = 220   // cap orbiting particles
const BASE_ROTATION_SPEED = 0.4    // rad/s at zero particles
const MAX_ROTATION_SPEED = 3.8     // rad/s at full density
const GRAVITY_STRENGTH = 160       // px/s² pull toward ring
const RING_THICKNESS = 2           // base ring stroke width

// --- Types -----------------------------------------------------------------

interface FreeParticle {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  color: string
  opacity: number
}

interface LockedParticle {
  angle: number           // angle on the ring (radians)
  layer: number           // 0 = on ring, 1 = inner, 2 = outer …
  radius: number
  color: string
  brightness: number      // 1 = normal, >1 = flash on lock
  lockedAt: number        // timestamp for flash decay
}

// --- Helpers ---------------------------------------------------------------

function randomBetween(a: number, b: number) {
  return a + Math.random() * (b - a)
}

function pickColor() {
  return COLORS[Math.floor(Math.random() * COLORS.length)]
}

/** Spawn a particle at a random point outside the visible area. */
function spawnParticle(center: number, ringRadius: number): FreeParticle {
  // Pick a random angle and push the spawn point well outside the ring
  const angle = Math.random() * Math.PI * 2
  const spawnDist = ringRadius + randomBetween(ringRadius * 0.7, ringRadius * 1.4)
  const x = center + Math.cos(angle) * spawnDist
  const y = center + Math.sin(angle) * spawnDist

  // Give a slight initial inward drift so they don't just sit still
  const toCenter = Math.atan2(center - y, center - x)
  const speed = randomBetween(10, 30)

  return {
    x,
    y,
    vx: Math.cos(toCenter) * speed + randomBetween(-8, 8),
    vy: Math.sin(toCenter) * speed + randomBetween(-8, 8),
    radius: randomBetween(1.2, 2.8),
    color: pickColor(),
    opacity: randomBetween(0.5, 0.9),
  }
}

// --- Component -------------------------------------------------------------

function FlywheelMagnetic({ size = 120, className }: FlywheelMagneticProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const dprRef = useRef(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1)

  const draw = useCallback((canvasSize: number) => {
    const canvas = canvasRef.current
    if (!canvas) return () => {}

    const dpr = dprRef.current
    canvas.width = canvasSize * dpr
    canvas.height = canvasSize * dpr
    canvas.style.width = `${canvasSize}px`
    canvas.style.height = `${canvasSize}px`

    const ctx = canvas.getContext("2d")!
    ctx.scale(dpr, dpr)

    const center = canvasSize / 2
    const ringRadius = canvasSize * 0.32

    // State
    const free: FreeParticle[] = []
    const locked: LockedParticle[] = []
    let wheelAngle = 0
    let lastSpawn = 0
    let lastTime = 0
    let animId = 0

    // Pre-seed a few locked particles so the ring isn't bare on first frame
    for (let i = 0; i < 8; i++) {
      locked.push({
        angle: (Math.PI * 2 * i) / 8,
        layer: 0,
        radius: randomBetween(1.2, 2.2),
        color: pickColor(),
        brightness: 1,
        lockedAt: 0,
      })
    }

    function rotationSpeed() {
      const t = Math.min(locked.length / MAX_LOCKED_PARTICLES, 1)
      // Ease-in-out curve for smooth acceleration
      const eased = t * t * (3 - 2 * t)
      return BASE_ROTATION_SPEED + (MAX_ROTATION_SPEED - BASE_ROTATION_SPEED) * eased
    }

    function tick(now: number) {
      if (!lastTime) lastTime = now
      const dt = Math.min((now - lastTime) / 1000, 0.05) // cap delta to avoid spirals
      lastTime = now

      // --- Spawn ---
      if (now - lastSpawn > SPAWN_INTERVAL_MS && free.length < MAX_FREE_PARTICLES) {
        free.push(spawnParticle(center, ringRadius))
        lastSpawn = now
      }

      // --- Update wheel ---
      const speed = rotationSpeed()
      wheelAngle += speed * dt

      // --- Update free particles ---
      for (let i = free.length - 1; i >= 0; i--) {
        const p = free[i]
        const dx = center - p.x
        const dy = center - p.y
        const dist = Math.sqrt(dx * dx + dy * dy)

        if (dist < 0.01) {
          free.splice(i, 1)
          continue
        }

        // Gravity toward ring center (with slight spiral component)
        const nx = dx / dist
        const ny = dy / dist
        const pull = GRAVITY_STRENGTH / Math.max(dist / ringRadius, 0.3)

        // Add a tangential nudge for spiral effect
        const tangentX = -ny * pull * 0.15
        const tangentY = nx * pull * 0.15

        p.vx += (nx * pull + tangentX) * dt
        p.vy += (ny * pull + tangentY) * dt

        // Light damping so they don't overshoot forever
        p.vx *= 0.995
        p.vy *= 0.995

        p.x += p.vx * dt
        p.y += p.vy * dt

        // Fade in as they approach
        const approachRatio = 1 - Math.min(dist / (ringRadius * 2), 1)
        p.opacity = 0.3 + approachRatio * 0.6

        // Lock condition: within capture radius of the ring
        const captureThreshold = ringRadius * 0.12
        if (Math.abs(dist - ringRadius) < captureThreshold && locked.length < MAX_LOCKED_PARTICLES) {
          const angle = Math.atan2(p.y - center, p.x - center) - wheelAngle
          // Pick a layer — mostly layer 0, some on inner/outer bands
          const layerRand = Math.random()
          const layer = layerRand < 0.55 ? 0 : layerRand < 0.8 ? 1 : layerRand < 0.95 ? -1 : (Math.random() < 0.5 ? 2 : -2)

          locked.push({
            angle,
            layer,
            radius: p.radius * randomBetween(0.9, 1.3),
            color: p.color,
            brightness: 2.5,  // flash
            lockedAt: now,
          })
          free.splice(i, 1)
        }
      }

      // --- Decay brightness on locked particles ---
      for (const lp of locked) {
        if (lp.brightness > 1) {
          const elapsed = (now - lp.lockedAt) / 1000
          lp.brightness = 1 + Math.max(0, 1.5 * Math.exp(-elapsed * 4))
        }
      }

      // --- Draw ---
      ctx.clearRect(0, 0, canvasSize, canvasSize)

      // Center glow — intensifies with accumulation
      const glowIntensity = 0.06 + 0.25 * Math.min(locked.length / MAX_LOCKED_PARTICLES, 1)
      const glowRadius = ringRadius * (0.5 + 0.5 * Math.min(locked.length / MAX_LOCKED_PARTICLES, 1))
      const centerGlow = ctx.createRadialGradient(center, center, 0, center, center, glowRadius)
      centerGlow.addColorStop(0, `rgba(233, 77, 53, ${glowIntensity})`)
      centerGlow.addColorStop(0.5, `rgba(249, 115, 22, ${glowIntensity * 0.4})`)
      centerGlow.addColorStop(1, "rgba(233, 77, 53, 0)")
      ctx.fillStyle = centerGlow
      ctx.beginPath()
      ctx.arc(center, center, glowRadius, 0, Math.PI * 2)
      ctx.fill()

      // Ring stroke
      const ringAlpha = 0.25 + 0.35 * Math.min(locked.length / 80, 1)
      ctx.strokeStyle = `rgba(233, 77, 53, ${ringAlpha})`
      ctx.lineWidth = RING_THICKNESS
      ctx.beginPath()
      ctx.arc(center, center, ringRadius, 0, Math.PI * 2)
      ctx.stroke()

      // Second (outer) faint ring that appears as density grows
      if (locked.length > 40) {
        const outerAlpha = 0.08 + 0.15 * Math.min((locked.length - 40) / 100, 1)
        ctx.strokeStyle = `rgba(233, 77, 53, ${outerAlpha})`
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(center, center, ringRadius + ringRadius * 0.12, 0, Math.PI * 2)
        ctx.stroke()
      }

      // Inner faint ring
      if (locked.length > 60) {
        const innerAlpha = 0.06 + 0.12 * Math.min((locked.length - 60) / 100, 1)
        ctx.strokeStyle = `rgba(233, 77, 53, ${innerAlpha})`
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(center, center, ringRadius - ringRadius * 0.1, 0, Math.PI * 2)
        ctx.stroke()
      }

      // Free particles
      for (const p of free) {
        ctx.globalAlpha = p.opacity
        ctx.fillStyle = p.color
        ctx.shadowColor = p.color
        ctx.shadowBlur = 4
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.shadowBlur = 0
      ctx.globalAlpha = 1

      // Locked particles — draw orbiting with the wheel
      for (const lp of locked) {
        const layerOffset = lp.layer * ringRadius * 0.055
        const r = ringRadius + layerOffset
        const absAngle = lp.angle + wheelAngle
        const px = center + Math.cos(absAngle) * r
        const py = center + Math.sin(absAngle) * r

        const alpha = Math.min(lp.brightness, 1)
        ctx.globalAlpha = alpha

        if (lp.brightness > 1.05) {
          // Glow flash
          const flashAlpha = (lp.brightness - 1) * 0.6
          ctx.shadowColor = lp.color
          ctx.shadowBlur = 8 * (lp.brightness - 1)
          ctx.fillStyle = lp.color
          ctx.beginPath()
          ctx.arc(px, py, lp.radius * lp.brightness * 0.8, 0, Math.PI * 2)
          ctx.fill()

          // White-hot core
          ctx.fillStyle = `rgba(255, 255, 255, ${flashAlpha})`
          ctx.beginPath()
          ctx.arc(px, py, lp.radius * 0.6, 0, Math.PI * 2)
          ctx.fill()
          ctx.shadowBlur = 0
        } else {
          ctx.fillStyle = lp.color
          ctx.shadowColor = lp.color
          ctx.shadowBlur = 2
          ctx.beginPath()
          ctx.arc(px, py, lp.radius, 0, Math.PI * 2)
          ctx.fill()
          ctx.shadowBlur = 0
        }
      }

      ctx.globalAlpha = 1

      animId = requestAnimationFrame(tick)
    }

    animId = requestAnimationFrame(tick)

    return () => cancelAnimationFrame(animId)
  }, [])

  useEffect(() => {
    return draw(size)
  }, [size, draw])

  return (
    <canvas
      ref={canvasRef}
      className={cn("pointer-events-none", className)}
      aria-label="Loading"
      role="img"
      style={{ width: size, height: size }}
    />
  )
}

export { FlywheelMagnetic }
