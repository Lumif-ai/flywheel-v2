import { Outlet } from 'react-router'
import { GateStrip } from './GateStrip'

export function BrokerLayout() {
  return (
    <div className="flex flex-col h-full">
      <GateStrip />
      <div className="flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  )
}
