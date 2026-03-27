import * as React from "react"
import { cn } from "@/lib/cn"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  )
}

function ShimmerSkeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="shimmer-skeleton"
      className={cn("animate-shimmer rounded-md", className)}
      {...props}
    />
  )
}

export { Skeleton, ShimmerSkeleton }
