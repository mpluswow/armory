import { useState, useCallback } from "react";
import type { Character } from "../types/character";
import { fetchCharacter } from "../api/character";

export function useCharacter() {
  const [character, setCharacter] = useState<Character | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async (name: string) => {
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    setCharacter(null);
    try {
      const data = await fetchCharacter(name);
      setCharacter(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  return { character, loading, error, search };
}
