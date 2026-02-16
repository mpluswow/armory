import { useEffect, useState } from "react";
import type { CharacterListItem } from "../types/character";
import { fetchCharacters } from "../api/character";
import { RACES, CLASSES, CLASS_COLORS } from "../utils/constants";

interface Props {
  visible: boolean;
  onSelect: (name: string) => void;
}

export default function CharacterList({ visible, onSelect }: Props) {
  const [characters, setCharacters] = useState<CharacterListItem[]>([]);

  useEffect(() => {
    if (!visible) return;
    fetchCharacters()
      .then((data) => setCharacters(data.characters))
      .catch(console.error);
  }, [visible]);

  if (!visible) return null;

  return (
    <div className="char-list-panel">
      {characters.map((char) => {
        const classColor = CLASS_COLORS[char.class] ?? "#ffffff";
        const raceName = RACES[char.race] ?? "Unknown";
        const className = CLASSES[char.class] ?? "Unknown";
        return (
          <div
            key={char.name}
            className="char-list-entry"
            onClick={() => onSelect(char.name)}
          >
            <span style={{ color: classColor, fontWeight: "bold" }}>
              {char.name}
            </span>
            <span style={{ color: "#999", marginLeft: 10 }}>
              - Level {char.level} {raceName} {className}
            </span>
          </div>
        );
      })}
    </div>
  );
}
