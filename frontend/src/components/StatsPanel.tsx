import type { Character } from "../types/character";
import { RACES, CLASSES, CLASS_COLORS, ALLIANCE_RACES } from "../utils/constants";

interface Props {
  character: Character;
}

export default function StatsPanel({ character }: Props) {
  const raceName = RACES[character.race] ?? "Unknown";
  const className = CLASSES[character.class] ?? "Unknown";
  const classColor = CLASS_COLORS[character.class] ?? "#ffffff";
  const isAlliance = ALLIANCE_RACES.includes(character.race);

  const itemLevels = character.equipment
    .filter((i) => i.itemLevel)
    .map((i) => i.itemLevel!);
  const avgILevel =
    itemLevels.length > 0
      ? Math.round(itemLevels.reduce((a, b) => a + b, 0) / itemLevels.length)
      : 0;

  return (
    <div className="stats-panel">
      <div className="stat-row">
        <span className="stat-label">Race</span>
        <span className="stat-value">{raceName}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Class</span>
        <span className="stat-value" style={{ color: classColor }}>
          {className}
        </span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Gender</span>
        <span className="stat-value">
          {character.gender === 0 ? "Male" : "Female"}
        </span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Faction</span>
        <span
          className="stat-value"
          style={{ color: isAlliance ? "#0070dd" : "#ff0000" }}
        >
          {isAlliance ? "Alliance" : "Horde"}
        </span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Average Item Level</span>
        <span className="stat-value">{avgILevel || "-"}</span>
      </div>
    </div>
  );
}
