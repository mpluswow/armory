export const RACES: Record<number, string> = {
  1: "Human", 2: "Orc", 3: "Dwarf", 4: "Night Elf", 5: "Undead",
  6: "Tauren", 7: "Gnome", 8: "Troll", 10: "Blood Elf", 11: "Draenei",
};

export const CLASSES: Record<number, string> = {
  1: "Warrior", 2: "Paladin", 3: "Hunter", 4: "Rogue", 5: "Priest",
  6: "Death Knight", 7: "Shaman", 8: "Mage", 9: "Warlock", 11: "Druid",
};

export const CLASS_COLORS: Record<number, string> = {
  1: "#C79C6E", 2: "#F58CBA", 3: "#ABD473", 4: "#FFF569", 5: "#FFFFFF",
  6: "#C41F3B", 7: "#0070DE", 8: "#69CCF0", 9: "#9482C9", 11: "#FF7D0A",
};

export const ALLIANCE_RACES = [1, 3, 4, 7, 11];

export const SLOT_CONFIG: { slot: number; label: string; emoji: string }[] = [
  // Left column
  { slot: 0, label: "Head", emoji: "\uD83E\uDE96" },
  { slot: 1, label: "Neck", emoji: "\uD83D\uDCFF" },
  { slot: 2, label: "Shoulders", emoji: "\uD83E\uDDBE" },
  { slot: 14, label: "Back", emoji: "\uD83E\uDDE5" },
  { slot: 4, label: "Chest", emoji: "\uD83D\uDC55" },
  { slot: 18, label: "Tabard", emoji: "\uD83C\uDFF4" },
  { slot: 8, label: "Wrist", emoji: "\u231A" },
];

export const SLOT_CONFIG_RIGHT: { slot: number; label: string; emoji: string }[] = [
  { slot: 9, label: "Hands", emoji: "\uD83E\uDDE4" },
  { slot: 5, label: "Waist", emoji: "\uD83E\uDD4B" },
  { slot: 6, label: "Legs", emoji: "\uD83D\uDC56" },
  { slot: 7, label: "Feet", emoji: "\uD83E\uDD7E" },
  { slot: 10, label: "Finger 1", emoji: "\uD83D\uDC8D" },
  { slot: 11, label: "Finger 2", emoji: "\uD83D\uDC8D" },
  { slot: 12, label: "Trinket 1", emoji: "\uD83D\uDD2E" },
  { slot: 13, label: "Trinket 2", emoji: "\uD83D\uDD2E" },
];

export const WEAPON_SLOTS: { slot: number; label: string; emoji: string }[] = [
  { slot: 15, label: "Main Hand", emoji: "\u2694\uFE0F" },
  { slot: 16, label: "Off Hand", emoji: "\uD83D\uDEE1\uFE0F" },
  { slot: 17, label: "Ranged", emoji: "\uD83C\uDFF9" },
];
