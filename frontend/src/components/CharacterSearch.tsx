import { useState, type KeyboardEvent } from "react";

interface Props {
  onSearch: (name: string) => void;
  onToggleList: () => void;
}

export default function CharacterSearch({ onSearch, onToggleList }: Props) {
  const [query, setQuery] = useState("");

  const handleKey = (e: KeyboardEvent) => {
    if (e.key === "Enter") onSearch(query);
  };

  return (
    <div className="armory-header">
      <div className="search-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Enter character name..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKey}
        />
        <button className="btn" onClick={() => onSearch(query)}>
          Search
        </button>
        <button className="btn" onClick={onToggleList}>
          Character List
        </button>
      </div>
    </div>
  );
}
