export const RANKS = [
  { name: "Novato", min: 0, color: "#A0A0A0" },
  { name: "Explorador", min: 50, color: "#FF8A65" },
  { name: "Aventureiro", min: 250, color: "#FF5722" },
  { name: "Avaliador", min: 1000, color: "#E64A19" },
  { name: "Apreciador de Obras", min: 5000, color: "#FFC107" },
];

export function rankFor(points = 0) {
  let current = RANKS[0];
  let next = null;
  for (let i = 0; i < RANKS.length; i++) {
    if (points >= RANKS[i].min) {
      current = RANKS[i];
      next = RANKS[i + 1] || null;
    }
  }
  const span = next ? next.min - current.min : 1;
  const within = next ? points - current.min : 1;
  const pct = next ? Math.min(100, Math.round((within / span) * 100)) : 100;
  return { current, next, pct };
}

export const PLATFORMS = [
  { id: "pc", label: "PC" },
  { id: "ps5", label: "PS5" },
  { id: "ps4", label: "PS4" },
  { id: "ps3", label: "PS3" },
  { id: "xbox-series-x", label: "Xbox Series X" },
  { id: "xbox-one", label: "Xbox One" },
  { id: "xbox-360", label: "Xbox 360" },
  { id: "switch", label: "Switch" },
  { id: "mobile", label: "Mobile" },
];

export const PLATFORM_LABEL = Object.fromEntries(PLATFORMS.map((p) => [p.id, p.label]));

export const GENRES = [
  "Ação", "Aventura", "RPG", "Terror", "FPS", "Estratégia",
  "Indie", "Desporto", "Luta", "Plataformas", "Sandbox", "MOBA",
  "Battle Royale", "Coop", "Sci-Fi", "Fantasia", "Souls-like",
];
