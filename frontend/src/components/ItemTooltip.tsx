import type { EquipmentItem } from "../types/character";
import { qualityColor } from "../utils/quality";

interface Props {
  item: EquipmentItem | null;
  position: { x: number; y: number } | null;
}

export default function ItemTooltip({ item, position }: Props) {
  if (!item || !position) return null;

  return (
    <div
      className="item-tooltip"
      style={{ left: position.x + 15, top: position.y }}
    >
      <div className="tooltip-item-name" style={{ color: qualityColor(item.quality) }}>
        {item.name}
      </div>
      {item.itemLevel && (
        <div className="tooltip-item-level">Item Level {item.itemLevel}</div>
      )}
      <div className="tooltip-binding">Binds when equipped</div>
      {item.itemType && <div className="tooltip-item-type">{item.itemType}</div>}
      {item.stats.length > 0 && (
        <div className="tooltip-stats-section">
          {item.stats.map((stat, i) => (
            <div key={i} className="tooltip-stat">
              {stat}
            </div>
          ))}
        </div>
      )}
      {item.requiredLevel != null && item.requiredLevel > 1 && (
        <div className="tooltip-req-level">
          Requires Level {item.requiredLevel}
        </div>
      )}
      {item.description && (
        <div className="tooltip-flavor">&ldquo;{item.description}&rdquo;</div>
      )}
    </div>
  );
}
