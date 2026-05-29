import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/10 text-primary",
        secondary: "border-transparent bg-[var(--border)] text-gray-400",
        outline: "text-foreground",
        success: "border-transparent bg-green-500/20 text-green-400",
        warning: "border-transparent bg-yellow-500/20 text-yellow-400",
        danger: "border-transparent bg-red-500/20 text-red-400",
        mode_normal: "border-transparent bg-green-500/20 text-green-400",
        mode_degraded: "border-transparent bg-yellow-500/20 text-yellow-400",
        mode_protected: "border-transparent bg-orange-500/20 text-orange-400",
        mode_read_only: "border-transparent bg-purple-500/20 text-purple-400",
        mode_emergency_stop: "border-transparent bg-red-500/20 text-red-400",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
