import { useEffect, useState } from "react";

function getInitial() {
  if (typeof window === "undefined") return "dark";
  const saved = localStorage.getItem("gs-theme");
  if (saved) return saved;
  return "dark";
}

export function useTheme() {
  const [theme, setTheme] = useState(getInitial);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    localStorage.setItem("gs-theme", theme);
  }, [theme]);

  return { theme, setTheme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}
