import { rankFor } from "../lib/game-data";
import { Trophy } from "lucide-react";

export default function RankBadge({ points = 0, showProgress = true }) {
  const { current, next, pct } = rankFor(points);
  return (
    <div data-testid="rank-badge" className="space-y-2">
      <div className="flex items-center gap-2">
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm border border-primary/40 bg-primary/10 font-mono text-xs uppercase tracking-wider"
          style={{ color: current.color }}
        >
          <Trophy size={12} /> {current.name}
        </span>
        <span className="font-mono text-xs text-muted-foreground">{points} pts</span>
      </div>
      {showProgress && next && (
        <div>
          <div className="h-1.5 bg-muted rounded-none overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="mt-1 flex justify-between font-mono text-[10px] text-muted-foreground tracking-wider">
            <span>{current.min}</span>
            <span>{next.name} · {next.min}</span>
          </div>
        </div>
      )}
    </div>
  );
}
