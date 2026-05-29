import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { SmilePlus } from "lucide-react";

/**
 * Compact reaction picker. Loads emojis (basic + admin custom) on first open
 * and calls onPick(emoji) when the user selects one.
 */
export default function ReactionPicker({ onPick, testIdPrefix = "react", small = false }) {
  const [emojis, setEmojis] = useState({ basic: ["👌","❤️","🤣","😊","😁","👍"], custom: [] });
  const [open, setOpen] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    if (open && !loaded.current) {
      loaded.current = true;
      api.get("/emojis").then((r) => setEmojis(r.data)).catch(() => null);
    }
  }, [open]);

  const handle = (e) => {
    onPick(e);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid={`${testIdPrefix}-open`}
          className={`opacity-0 group-hover/msg:opacity-100 group-hover/cmsg:opacity-100 group-hover/review:opacity-100 transition text-muted-foreground hover:text-primary p-1 rounded-sm ${small ? "" : ""}`}
          title="Reagir"
        >
          <SmilePlus size={small ? 13 : 14} />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-2 rounded-sm" align="end">
        <div className="flex flex-wrap gap-1 max-w-[240px]">
          {emojis.basic.map((e) => (
            <button key={e} type="button" data-testid={`${testIdPrefix}-emoji-${e}`} onClick={() => handle(e)} className="text-xl px-2 py-1 hover:bg-muted rounded-sm transition">{e}</button>
          ))}
          {emojis.custom.length > 0 && (
            <>
              <div className="w-full border-t border-border my-1" />
              {emojis.custom.map((c) => (
                <button key={c.emoji_id} type="button" data-testid={`${testIdPrefix}-emoji-${c.emoji}`} onClick={() => handle(c.emoji)} title={c.name} className="text-xl px-2 py-1 hover:bg-muted rounded-sm transition">{c.emoji}</button>
              ))}
            </>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
