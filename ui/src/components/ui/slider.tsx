import * as React from "react"
import { cn } from "@/lib/utils"

interface SliderProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  min: number
  max: number
  value: number
  onChange: (value: number) => void
  label?: string
}

function Slider({
  className,
  min,
  max,
  value,
  onChange,
  disabled,
  ...props
}: SliderProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
        className={cn(
          "slider-input h-2 w-full cursor-pointer appearance-none rounded-full bg-input transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          disabled && "cursor-not-allowed opacity-50"
        )}
        {...props}
      />
      <span className="min-w-[2ch] text-center text-sm font-semibold tabular-nums">
        {value}
      </span>
    </div>
  )
}

export { Slider }
