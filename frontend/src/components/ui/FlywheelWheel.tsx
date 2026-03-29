import { useRef, useEffect, useCallback } from 'react'

interface FlywheelWheelProps {
  size?: number
  className?: string
}

/**
 * A literal spinning wheel — like a turbine/alloy rim — with energy effects.
 * The wheel accelerates over time as "knowledge compounds."
 * Canvas-based for smooth 60fps.
 */
export function FlywheelWheel({ size = 120, className }: FlywheelWheelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)

  const draw = useCallback((canvas: HTMLCanvasElement) => {
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const w = size
    const h = size
    canvas.width = w * dpr
    canvas.height = h * dpr
    canvas.style.width = `${w}px`
    canvas.style.height = `${h}px`
    ctx.scale(dpr, dpr)

    const cx = w / 2
    const cy = h / 2
    const outerR = w * 0.42
    const innerR = w * 0.30
    const hubR = w * 0.10
    const spokeCount = 5

    // Colors
    const coral = '#E94D35'
    const coralLight = '#F97316'
    const coralGlow = 'rgba(233, 77, 53, 0.3)'

    // Particles for energy effect
    interface Particle {
      angle: number
      radius: number
      speed: number
      size: number
      opacity: number
      life: number
      maxLife: number
    }

    const particles: Particle[] = []
    const maxParticles = 40

    let startTime = performance.now()
    let rotation = 0

    function spawnParticle() {
      if (particles.length >= maxParticles) return
      const angle = Math.random() * Math.PI * 2
      particles.push({
        angle,
        radius: outerR + 2 + Math.random() * 8,
        speed: 0.02 + Math.random() * 0.03,
        size: 1 + Math.random() * 2,
        opacity: 0.6 + Math.random() * 0.4,
        life: 0,
        maxLife: 40 + Math.random() * 60,
      })
    }

    function animate() {
      if (!ctx) return
      ctx.clearRect(0, 0, w, h)

      const elapsed = (performance.now() - startTime) / 1000
      // Accelerate: starts at 1.5 rad/s, reaches ~6 rad/s over 8 seconds
      const speed = 1.5 + Math.min(elapsed * 0.6, 4.5)
      rotation += speed * (1 / 60)

      // Spawn energy particles
      if (Math.random() < 0.3) spawnParticle()

      ctx.save()
      ctx.translate(cx, cy)

      // === Outer glow (intensifies with speed) ===
      const glowIntensity = Math.min(speed / 6, 1)
      const glow = ctx.createRadialGradient(0, 0, innerR, 0, 0, outerR + 15)
      glow.addColorStop(0, 'rgba(233, 77, 53, 0)')
      glow.addColorStop(0.7, `rgba(233, 77, 53, ${0.04 * glowIntensity})`)
      glow.addColorStop(1, `rgba(233, 77, 53, ${0.12 * glowIntensity})`)
      ctx.fillStyle = glow
      ctx.beginPath()
      ctx.arc(0, 0, outerR + 15, 0, Math.PI * 2)
      ctx.fill()

      // === Energy particles orbiting around the wheel ===
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i]
        p.angle += p.speed + speed * 0.01
        p.life++
        p.opacity *= 0.98

        if (p.life > p.maxLife || p.opacity < 0.05) {
          particles.splice(i, 1)
          continue
        }

        const px = Math.cos(p.angle) * p.radius
        const py = Math.sin(p.angle) * p.radius

        ctx.beginPath()
        ctx.arc(px, py, p.size, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(249, 115, 22, ${p.opacity})`
        ctx.shadowColor = coralLight
        ctx.shadowBlur = 4
        ctx.fill()
        ctx.shadowBlur = 0
      }

      // === Rotating wheel group ===
      ctx.save()
      ctx.rotate(rotation)

      // -- Outer rim --
      ctx.beginPath()
      ctx.arc(0, 0, outerR, 0, Math.PI * 2)
      ctx.lineWidth = w * 0.035
      const rimGrad = ctx.createLinearGradient(-outerR, -outerR, outerR, outerR)
      rimGrad.addColorStop(0, '#D4403A')
      rimGrad.addColorStop(0.5, coral)
      rimGrad.addColorStop(1, coralLight)
      ctx.strokeStyle = rimGrad
      ctx.stroke()

      // -- Inner rim --
      ctx.beginPath()
      ctx.arc(0, 0, innerR, 0, Math.PI * 2)
      ctx.lineWidth = w * 0.02
      ctx.strokeStyle = 'rgba(233, 77, 53, 0.5)'
      ctx.stroke()

      // -- Spokes (curved, like alloy wheel arms) --
      for (let i = 0; i < spokeCount; i++) {
        const baseAngle = (i / spokeCount) * Math.PI * 2
        const startAngle = baseAngle + 0.15
        const endAngle = baseAngle - 0.15

        const sx = Math.cos(startAngle) * hubR
        const sy = Math.sin(startAngle) * hubR
        const ex = Math.cos(baseAngle) * (outerR - w * 0.02)
        const ey = Math.sin(baseAngle) * (outerR - w * 0.02)

        // Control point for curve — offset perpendicular to spoke
        const midR = (hubR + outerR) * 0.5
        const perpAngle = baseAngle + Math.PI * 0.12
        const cpx = Math.cos(perpAngle) * midR
        const cpy = Math.sin(perpAngle) * midR

        ctx.beginPath()
        ctx.moveTo(sx, sy)
        ctx.quadraticCurveTo(cpx, cpy, ex, ey)
        ctx.lineWidth = w * 0.028
        ctx.lineCap = 'round'

        const spokeGrad = ctx.createLinearGradient(sx, sy, ex, ey)
        spokeGrad.addColorStop(0, 'rgba(233, 77, 53, 0.9)')
        spokeGrad.addColorStop(1, 'rgba(249, 115, 22, 0.7)')
        ctx.strokeStyle = spokeGrad
        ctx.stroke()
      }

      // -- Hub (center) --
      const hubGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, hubR)
      hubGrad.addColorStop(0, '#FFF')
      hubGrad.addColorStop(0.3, '#FECACA')
      hubGrad.addColorStop(0.7, coral)
      hubGrad.addColorStop(1, '#D4403A')
      ctx.beginPath()
      ctx.arc(0, 0, hubR, 0, Math.PI * 2)
      ctx.fillStyle = hubGrad
      ctx.fill()

      // Hub highlight
      ctx.beginPath()
      ctx.arc(-hubR * 0.2, -hubR * 0.2, hubR * 0.35, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.fill()

      ctx.restore() // end rotation

      // === Motion blur streaks (behind the wheel, speed-dependent) ===
      if (speed > 3) {
        const streakAlpha = Math.min((speed - 3) / 3, 0.3)
        for (let i = 0; i < 3; i++) {
          const angle = rotation - (i + 1) * 0.3
          const sx = Math.cos(angle) * outerR * 0.85
          const sy = Math.sin(angle) * outerR * 0.85
          const ex = Math.cos(angle + 0.5) * outerR * 1.05
          const ey = Math.sin(angle + 0.5) * outerR * 1.05

          ctx.beginPath()
          ctx.moveTo(sx, sy)
          ctx.lineTo(ex, ey)
          ctx.lineWidth = 1.5
          ctx.strokeStyle = `rgba(233, 77, 53, ${streakAlpha * (1 - i * 0.3)})`
          ctx.stroke()
        }
      }

      ctx.restore()

      animRef.current = requestAnimationFrame(animate)
    }

    animate()
  }, [size])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    draw(canvas)
    return () => cancelAnimationFrame(animRef.current)
  }, [draw])

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ width: size, height: size }}
    />
  )
}
