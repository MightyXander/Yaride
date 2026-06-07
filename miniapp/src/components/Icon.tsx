interface IconProps {
  name: string;
  className?: string;
  filled?: boolean;
  size?: number;
}

// Обёртка над Material Symbols Outlined (как в макетах Stitch).
export function Icon({ name, className = "", filled = false, size }: IconProps) {
  return (
    <span
      className={`material-symbols-outlined ${filled ? "filled" : ""} ${className}`}
      style={size ? { fontSize: size } : undefined}
    >
      {name}
    </span>
  );
}
