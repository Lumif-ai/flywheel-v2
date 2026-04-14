interface CarrierColumnHeaderProps {
  carrier: { name: string; carrier_config_id: string | null }
  checked: boolean
  onToggle: (name: string) => void
}

export function CarrierColumnHeader({
  carrier,
  checked,
  onToggle,
}: CarrierColumnHeaderProps) {
  return (
    <th
      className="px-3 py-2 border-b border-r text-center bg-white min-w-[160px]"
      style={{ position: 'sticky', top: 0, zIndex: 20 }}
    >
      <div className="flex flex-col items-center gap-1">
        <input
          type="checkbox"
          checked={checked}
          onChange={() => onToggle(carrier.name)}
          className="h-4 w-4 rounded border-gray-300 accent-blue-600"
        />
        <span className="text-sm font-medium truncate max-w-[140px]" title={carrier.name}>
          {carrier.name}
        </span>
      </div>
    </th>
  )
}
