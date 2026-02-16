import type { Character, CharacterListResponse } from "../types/character";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export async function fetchCharacter(name: string): Promise<Character> {
  const res = await fetch(`${API_BASE}/api/character?name=${encodeURIComponent(name)}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? body.error ?? "Unknown error");
  }
  return res.json();
}

export async function fetchCharacters(): Promise<CharacterListResponse> {
  const res = await fetch(`${API_BASE}/api/characters`);
  if (!res.ok) throw new Error("Failed to load character list");
  return res.json();
}
