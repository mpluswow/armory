import type { EquipmentItem } from "../types/character";
import { useItemIcon } from "../hooks/useItemIcon";
import { qualityColor } from "../utils/quality";

interface Props {
  label: string;
  emoji: string;
  item?: EquipmentItem;
  onHover: (item: EquipmentItem | null, rect: DOMRect | null) => void;
}

export default function ItemSlot({ label, emoji, item, onHover }: Props) {
  const iconUrl = useItemIcon(item?.entry);
  const isEmpty = !item;

  const handleEnter = (e: React.MouseEvent) => {
    if (item) {
      onHover(item, (e.currentTarget as HTMLElement).getBoundingClientRect());
    }
  };

  return (
    <div
      className={`item-slot${isEmpty ? " empty" : ""}`}
      onMouseEnter={handleEnter}
      onMouseLeave={() => onHover(null, null)}
    >
      <div
        className={`item-icon-container${item ? ` q${item.quality}-border` : ""}`}
      >
        {item ? (
          <img
            className="item-icon"
            src={iconUrl}
            alt={item.name}
            onError={(e) => {
              (e.target as HTMLImageElement).src =
                "https://wow.zamimg.com/images/wow/icons/large/inv_misc_questionmark.jpg";
            }}
          />
        ) : (
          <span className="item-icon-empty">{emoji}</span>
        )}
      </div>
      <div className="item-details">
        <div className="slot-label">{label}</div>
        <div
          className="item-name"
          style={item ? { color: qualityColor(item.quality) } : undefined}
        >
          {item?.name ?? "Empty"}
        </div>
        {item?.itemLevel && <div className="item-level">iLvl {item.itemLevel}</div>}
      </div>
    </div>
  );
}
