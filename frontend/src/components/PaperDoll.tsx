import { useState, useCallback } from "react";
import type { Character, EquipmentItem } from "../types/character";
import { RACES, CLASSES, CLASS_COLORS, SLOT_CONFIG, SLOT_CONFIG_RIGHT, WEAPON_SLOTS } from "../utils/constants";
import ItemSlot from "./ItemSlot";
import ItemTooltip from "./ItemTooltip";
import StatsPanel from "./StatsPanel";
import ModelViewer from "./ModelViewer";

interface Props {
  character: Character;
}

export default function PaperDoll({ character }: Props) {
  const [tooltipItem, setTooltipItem] = useState<EquipmentItem | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  const equipMap = new Map(character.equipment.map((e) => [e.slot, e]));

  const classColor = CLASS_COLORS[character.class] ?? "#ffffff";
  const raceName = RACES[character.race] ?? "Unknown";
  const className = CLASSES[character.class] ?? "Unknown";

  const handleHover = useCallback(
    (item: EquipmentItem | null, rect: DOMRect | null) => {
      setTooltipItem(item);
      if (rect) {
        setTooltipPos({ x: rect.right + 5, y: rect.top });
      } else {
        setTooltipPos(null);
      }
    },
    []
  );

  return (
    <>
      <div className="character-header">
        <div className="char-name-title" style={{ color: classColor }}>
          {character.name}
        </div>
        <div className="char-subtitle">
          Level {character.level} {raceName} {className}
        </div>
      </div>

      <div className="armory-layout">
        {/* Left Column */}
        <div className="equipment-column">
          {SLOT_CONFIG.map((s) => (
            <ItemSlot
              key={s.slot}
              label={s.label}
              emoji={s.emoji}
              item={equipMap.get(s.slot)}
              onHover={handleHover}
            />
          ))}
        </div>

        {/* Center - Model + Stats */}
        <div className="character-display">
          <ModelViewer character={character} />
          <StatsPanel character={character} />
        </div>

        {/* Right Column */}
        <div className="equipment-column">
          {SLOT_CONFIG_RIGHT.map((s) => (
            <ItemSlot
              key={s.slot}
              label={s.label}
              emoji={s.emoji}
              item={equipMap.get(s.slot)}
              onHover={handleHover}
            />
          ))}
        </div>
      </div>

      {/* Weapon Slots */}
      <div className="weapons-row">
        {WEAPON_SLOTS.map((s) => (
          <ItemSlot
            key={s.slot}
            label={s.label}
            emoji={s.emoji}
            item={equipMap.get(s.slot)}
            onHover={handleHover}
          />
        ))}
      </div>

      <ItemTooltip item={tooltipItem} position={tooltipPos} />
    </>
  );
}
