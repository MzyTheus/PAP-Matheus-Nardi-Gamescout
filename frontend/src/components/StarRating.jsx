import { Star } from "lucide-react";
import { useState } from "react";

export default function StarRating({ value = 0, max = 10, size = 22, onChange = null, testId = "star-rating" }) {
  const [hover, setHover] = useState(0);
  const interactive = !!onChange;
  const display = hover || value;
  return (
    <div data-testid={testId} className="inline-flex items-center gap-1">
      {Array.from({ length: max }).map((_, i) => {
        const idx = i + 1;
        const filled = idx <= display;
        return (
          <button
            type="button"
            key={idx}
            disabled={!interactive}
            data-testid={`${testId}-star-${idx}`}
            onMouseEnter={() => interactive && setHover(idx)}
            onMouseLeave={() => interactive && setHover(0)}
            onClick={() => interactive && onChange(idx)}
            className={interactive ? "transition-transform hover:scale-110" : "pointer-events-none"}
            aria-label={`${idx} de ${max}`}
          >
            <Star
              size={size}
              strokeWidth={1.6}
              className={filled ? "fill-primary text-primary" : "text-muted-foreground/40"}
            />
          </button>
        );
      })}
      <span className="ml-2 font-mono text-sm font-bold">{value || "—"}/{max}</span>
    </div>
  );
}
