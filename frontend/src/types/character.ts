export interface EquipmentItem {
  slot: number;
  entry: number;
  displayId: number;
  name: string;
  quality: number;
  itemLevel: number | null;
  requiredLevel: number | null;
  itemType: string;
  stats: string[];
  description: string;
  icon: string;
}

export interface Character {
  guid: number;
  name: string;
  race: number;
  class: number;
  gender: number;
  level: number;
  skin: number;
  face: number;
  hairStyle: number;
  hairColor: number;
  facialStyle: number;
  equipment: EquipmentItem[];
}

export interface CharacterListItem {
  name: string;
  race: number;
  class: number;
  level: number;
  faction: string;
}

export interface CharacterListResponse {
  count: number;
  characters: CharacterListItem[];
}
