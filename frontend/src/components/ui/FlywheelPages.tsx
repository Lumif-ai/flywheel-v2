import { useRef, useEffect, useCallback } from "react"
import { cn } from "@/lib/cn"

interface FlywheelPagesProps {
  size?: number
  className?: string
}

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

interface Page {
  /** Angle on the spawn circle (radians) */
  angle: number
  /** Current distance from center (normalised 0‑1, 1 = edge) */
  r: number
  /** Extra per-page rotation so pages tumble as they spiral */
  spin: number
  /** Speed multiplier — slight per‑page variation for organic feel */
  speed: number
  /** 0‑1 lifecycle, 1 = just spawned, 0 = merged */
  life: number
  /** Whether this page has a coral header accent bar */
  hasAccent: boolean
  /** Width of the page card (px, at life=1) */
  w: number
  /** Height of the page card (px, at life=1) */
  h: number
}

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

const CORAL = "#E94D35"
const ORANGE = "#F97316"
const PAGE_BG = "#FEFCFB"
const LINE_COLOR = "#D1D5DB"
const ACCENT_HEADER = CORAL
const SHADOW_COLOR = "rgba(0,0,0,0.12)"

/** How many turns the logarithmic spiral makes from edge → center */
const SPIRAL_TURNS = 2.2
/** Base inward speed (fraction of radius per second) */
const BASE_SPEED = 0.22
/** Min interval between spawns (seconds) */
const SPAWN_MIN = 0.45
/** Max interval between spawns (seconds) */
const SPAWN_MAX = 0.9

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t
}

function rand(min: number, max: number) {
  return Math.random() * (max - min) + min
}

/** Attempt high‑DPI canvas. Returns the effective pixel ratio. */
function setupHiDpi(
  canvas: HTMLCanvasElement,
  ctx: CanvasRenderingContext2D,
  logicalSize: number,
) {
  const dpr = window.devicePixelRatio || 1
  canvas.width = logicalSize * dpr
  canvas.height = logicalSize * dpr
  canvas.style.width = `${logicalSize}px`
  canvas.style.height = `${logicalSize}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  return dpr
}

/* ------------------------------------------------------------------ */
/*  Component                                                         */
/* ------------------------------------------------------------------ */

function FlywheelPages({ size = 120, className }: FlywheelPagesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const stateRef = useRef({
    pages: [] as Page[],
    mergedCount: 0,
    discRadius: 0,
    discAngle: 0,
    discAngularVelocity: 1.2, // rad/s — accelerates
    nextSpawn: 0,
    time: 0,
    lastFrame: 0,
  })

  /* ---- spawn a page ---- */
  const spawnPage = useCallback((): Page => {
    const angle = rand(0, Math.PI * 2)
    const w = rand(10, 14)
    const h = w * rand(1.25, 1.4)
    return {
      angle,
      r: 1,
      spin: rand(0, Math.PI * 2),
      speed: rand(0.85, 1.15),
      life: 1,
      hasAccent: Math.random() < 0.4,
      w,
      h,
    }
  }, [])

  /* ---- draw one page card ---- */
  const drawPage = useCallback(
    (ctx: CanvasRenderingContext2D, page: Page, cx: number, cy: number, outerR: number) => {
      // Logarithmic spiral: as r decreases, angle increases
      const t = 1 - page.r // 0 at edge, 1 at center
      const spiralAngle = page.angle + t * SPIRAL_TURNS * Math.PI * 2
      const dist = page.r * outerR

      const x = cx + Math.cos(spiralAngle) * dist
      const y = cy + Math.sin(spiralAngle) * dist

      // Scale shrinks as page approaches center
      const scale = lerp(1, 0.15, t * t)
      const opacity = page.r < 0.08 ? page.r / 0.08 : Math.min(1, page.life)

      if (opacity <= 0) return

      const w = page.w * scale
      const h = page.h * scale
      const rotation = page.spin + t * Math.PI * 4 // tumble

      ctx.save()
      ctx.translate(x, y)
      ctx.rotate(rotation)
      ctx.globalAlpha = opacity

      // Shadow
      ctx.shadowColor = SHADOW_COLOR
      ctx.shadowBlur = 3 * scale
      ctx.shadowOffsetY = 1 * scale

      // Page body
      const rx = 1.2 * scale // corner radius
      ctx.beginPath()
      ctx.roundRect(-w / 2, -h / 2, w, h, rx)
      ctx.fillStyle = PAGE_BG
      ctx.fill()

      // Remove shadow for details
      ctx.shadowColor = "transparent"
      ctx.shadowBlur = 0
      ctx.shadowOffsetY = 0

      // Accent header bar
      if (page.hasAccent) {
        const barH = h * 0.16
        ctx.beginPath()
        // Top-left and top-right rounded, bottom square
        ctx.roundRect(-w / 2, -h / 2, w, barH, [rx, rx, 0, 0])
        ctx.fillStyle = ACCENT_HEADER
        ctx.globalAlpha = opacity * 0.85
        ctx.fill()
        ctx.globalAlpha = opacity
      }

      // Text placeholder lines
      const lineStartY = page.hasAccent ? -h / 2 + h * 0.28 : -h / 2 + h * 0.18
      const lineCount = Math.max(2, Math.round(h * scale * 0.35))
      const lineSpacing = (h * 0.55) / Math.max(lineCount, 1)
      ctx.strokeStyle = LINE_COLOR
      ctx.lineWidth = Math.max(0.4, 0.6 * scale)
      for (let i = 0; i < lineCount; i++) {
        const ly = lineStartY + i * lineSpacing
        // Vary line widths for realism
        const lw = w * rand(0.5, 0.85)
        ctx.beginPath()
        ctx.moveTo(-w / 2 + w * 0.1, ly)
        ctx.lineTo(-w / 2 + w * 0.1 + lw, ly)
        ctx.stroke()
      }

      ctx.restore()
    },
    [],
  )

  /* ---- draw the central disc ---- */
  const drawDisc = useCallback(
    (ctx: CanvasRenderingContext2D, cx: number, cy: number, state: typeof stateRef.current) => {
      const baseR = size * 0.04
      const growR = Math.min(state.mergedCount * 0.35, size * 0.14)
      const r = baseR + growR
      state.discRadius = r

      ctx.save()
      ctx.translate(cx, cy)
      ctx.rotate(state.discAngle)

      // Outer glow
      const glowIntensity = Math.min(0.45, 0.1 + state.mergedCount * 0.012)
      const glow = ctx.createRadialGradient(0, 0, r * 0.3, 0, 0, r * 2.2)
      glow.addColorStop(0, `rgba(233, 77, 53, ${glowIntensity})`)
      glow.addColorStop(0.5, `rgba(249, 115, 22, ${glowIntensity * 0.4})`)
      glow.addColorStop(1, "rgba(249, 115, 22, 0)")
      ctx.fillStyle = glow
      ctx.beginPath()
      ctx.arc(0, 0, r * 2.2, 0, Math.PI * 2)
      ctx.fill()

      // Main disc gradient
      const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, r)
      grad.addColorStop(0, "#F97316")
      grad.addColorStop(0.4, CORAL)
      grad.addColorStop(1, "#C53A2A")
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(0, 0, r, 0, Math.PI * 2)
      ctx.fill()

      // Concentric ring texture (stacked pages illusion)
      const rings = Math.min(Math.floor(state.mergedCount / 2) + 2, 8)
      for (let i = 1; i <= rings; i++) {
        const ringR = (r * i) / (rings + 1)
        ctx.beginPath()
        ctx.arc(0, 0, ringR, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(255,255,255,${0.12 + (i % 2) * 0.06})`
        ctx.lineWidth = 0.6
        ctx.stroke()
      }

      // Bright center highlight
      const highlight = ctx.createRadialGradient(0, 0, 0, 0, 0, r * 0.45)
      highlight.addColorStop(0, "rgba(255,255,255,0.3)")
      highlight.addColorStop(1, "rgba(255,255,255,0)")
      ctx.fillStyle = highlight
      ctx.beginPath()
      ctx.arc(0, 0, r * 0.45, 0, Math.PI * 2)
      ctx.fill()

      ctx.restore()
    },
    [size],
  )

  /* ---- main animation loop ---- */
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    setupHiDpi(canvas, ctx, size)

    const state = stateRef.current
    // Reset state on mount
    state.pages = []
    state.mergedCount = 0
    state.discRadius = 0
    state.discAngle = 0
    state.discAngularVelocity = 1.2
    state.nextSpawn = 0.2
    state.time = 0
    state.lastFrame = 0

    // Pre-seed a few pages at various spiral positions for instant visual
    for (let i = 0; i < 4; i++) {
      const p = spawnPage()
      p.r = rand(0.25, 0.85)
      p.life = p.r
      state.pages.push(p)
    }
    state.mergedCount = 3 // Pretend a few already merged

    let raf = 0

    const tick = (timestamp: number) => {
      if (!state.lastFrame) state.lastFrame = timestamp
      const dt = Math.min((timestamp - state.lastFrame) / 1000, 0.05) // cap at 50ms
      state.lastFrame = timestamp
      state.time += dt

      const cx = size / 2
      const cy = size / 2
      const outerR = size * 0.44

      // -- Spawn --
      state.nextSpawn -= dt
      if (state.nextSpawn <= 0) {
        state.pages.push(spawnPage())
        state.nextSpawn = rand(SPAWN_MIN, SPAWN_MAX)
      }

      // -- Update pages --
      for (let i = state.pages.length - 1; i >= 0; i--) {
        const p = state.pages[i]
        p.r -= BASE_SPEED * p.speed * dt
        p.life = p.r

        // Merge when close enough to center
        if (p.r <= 0.02) {
          state.pages.splice(i, 1)
          state.mergedCount++
          // Accelerate disc
          state.discAngularVelocity = Math.min(
            12,
            state.discAngularVelocity + 0.15,
          )
        }
      }

      // Gentle deceleration to keep it from staying at max forever
      state.discAngularVelocity = Math.max(
        1.2,
        state.discAngularVelocity - 0.02 * dt,
      )

      // Rotate disc
      state.discAngle += state.discAngularVelocity * dt

      // -- Draw --
      ctx.clearRect(0, 0, size, size)

      // Draw pages (back to front — further pages first)
      const sorted = [...state.pages].sort((a, b) => b.r - a.r)
      for (const p of sorted) {
        drawPage(ctx, p, cx, cy, outerR)
      }

      // Draw central disc on top
      drawDisc(ctx, cx, cy, state)

      raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)

    return () => cancelAnimationFrame(raf)
  }, [size, spawnPage, drawPage, drawDisc])

  return (
    <canvas
      ref={canvasRef}
      className={cn("pointer-events-none", className)}
      style={{ width: size, height: size }}
      aria-label="Loading — pages spiraling into flywheel"
      role="img"
    />
  )
}

export { FlywheelPages }
