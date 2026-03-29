import { FlywheelMagnetic } from '@/components/ui/FlywheelMagnetic'
import { FlywheelPages } from '@/components/ui/FlywheelPages'
import { FlywheelWheel } from '@/components/ui/FlywheelWheel'

export function SpinnerPreview() {
  return (
    <div style={{
      minHeight: '100vh',
      background: '#fff',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '60px',
      padding: '60px 40px',
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#121212', margin: 0 }}>
        Flywheel Spinner Comparison
      </h1>

      <div style={{ display: 'flex', gap: '60px', flexWrap: 'wrap', justifyContent: 'center' }}>
        {/* Option A: Actual Wheel */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '24px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 500, color: '#E94D35', margin: 0 }}>
            ★ The Wheel
          </h2>
          <div style={{
            background: '#FAFAFA',
            borderRadius: '16px',
            padding: '40px',
            border: '2px solid rgba(233, 77, 53, 0.2)',
          }}>
            <FlywheelWheel size={200} />
          </div>
          <p style={{ fontSize: '13px', color: '#9CA3AF', maxWidth: '250px', textAlign: 'center', margin: 0 }}>
            An actual wheel with spokes spinning and accelerating.
            Energy particles orbit around it as momentum builds.
          </p>
        </div>

        {/* Option B: Magnetic Particles */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '24px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 500, color: '#6B7280', margin: 0 }}>
            Magnetic Particles
          </h2>
          <div style={{
            background: '#FAFAFA',
            borderRadius: '16px',
            padding: '40px',
            border: '1px solid #E5E7EB',
          }}>
            <FlywheelMagnetic size={200} />
          </div>
          <p style={{ fontSize: '13px', color: '#9CA3AF', maxWidth: '250px', textAlign: 'center', margin: 0 }}>
            Particles drawn to a spinning ring by gravity.
            They stick and accumulate.
          </p>
        </div>

        {/* Option C: Spiraling Pages */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '24px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 500, color: '#6B7280', margin: 0 }}>
            Spiraling Pages
          </h2>
          <div style={{
            background: '#FAFAFA',
            borderRadius: '16px',
            padding: '40px',
            border: '1px solid #E5E7EB',
          }}>
            <FlywheelPages size={200} />
          </div>
          <p style={{ fontSize: '13px', color: '#9CA3AF', maxWidth: '250px', textAlign: 'center', margin: 0 }}>
            Document cards spiral inward and compress
            into a spinning disc.
          </p>
        </div>
      </div>

      {/* All three at smaller sizes */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#6B7280', margin: 0 }}>Inline size (64px)</h3>
        <div style={{ display: 'flex', gap: '48px', alignItems: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <FlywheelWheel size={64} />
            <p style={{ fontSize: '11px', color: '#9CA3AF', margin: '8px 0 0' }}>Wheel</p>
          </div>
          <div style={{ textAlign: 'center' }}>
            <FlywheelMagnetic size={64} />
            <p style={{ fontSize: '11px', color: '#9CA3AF', margin: '8px 0 0' }}>Magnetic</p>
          </div>
          <div style={{ textAlign: 'center' }}>
            <FlywheelPages size={64} />
            <p style={{ fontSize: '11px', color: '#9CA3AF', margin: '8px 0 0' }}>Pages</p>
          </div>
        </div>
      </div>

      {/* Dark background variant */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#6B7280', margin: 0 }}>On dark background</h3>
        <div style={{
          display: 'flex',
          gap: '48px',
          alignItems: 'center',
          background: '#1a1a1a',
          borderRadius: '16px',
          padding: '40px 60px',
        }}>
          <FlywheelWheel size={120} />
          <FlywheelMagnetic size={120} />
          <FlywheelPages size={120} />
        </div>
      </div>
    </div>
  )
}
