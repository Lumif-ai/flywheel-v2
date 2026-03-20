import { useEffect, useState } from 'react'

function App() {
  const [health, setHealth] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/v1/health')
      .then((res) => res.json())
      .then((data) => setHealth(data.status ?? 'ok'))
      .catch(() => setError('Backend unavailable'))
  }, [])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center space-y-6">
        <h1 className="text-5xl font-bold text-gray-900">Flywheel v2</h1>
        <p className="text-xl text-gray-500">Knowledge compounding engine</p>
        <div className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium bg-white shadow-sm border border-gray-200">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              health ? 'bg-green-500' : error ? 'bg-red-500' : 'bg-yellow-500 animate-pulse'
            }`}
          />
          <span className="text-gray-600">
            {health ? `Backend: ${health}` : error ? error : 'Connecting...'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default App
