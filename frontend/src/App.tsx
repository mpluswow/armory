import { useState, useCallback } from "react";
import { useCharacter } from "./hooks/useCharacter";
import CharacterSearch from "./components/CharacterSearch";
import CharacterList from "./components/CharacterList";
import PaperDoll from "./components/PaperDoll";
import "./styles/global.css";
import "./styles/paperdoll.css";
import "./styles/tooltip.css";

export default function App() {
  const { character, loading, error, search } = useCharacter();
  const [showList, setShowList] = useState(false);

  const handleSelect = useCallback(
    (name: string) => {
      setShowList(false);
      search(name);
    },
    [search]
  );

  return (
    <div className="container">
      <CharacterSearch
        onSearch={search}
        onToggleList={() => setShowList((v) => !v)}
      />
      <CharacterList visible={showList} onSelect={handleSelect} />

      {loading && <div className="loading">Loading...</div>}
      {error && <div className="error">{error}</div>}
      {character && <PaperDoll character={character} />}
    </div>
  );
}
