# AzerothCore Armory - Technical Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Installation & Setup](#installation--setup)
4. [Database Schema](#database-schema)
5. [Backend API](#backend-api)
6. [Frontend Components](#frontend-components)
7. [Features & Functionality](#features--functionality)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)
10. [Future Enhancements](#future-enhancements)

---

## Project Overview


### Goal
Reproduce https://worldofwarcraft.blizzard.com/en-gb/character/eu/ragnaros/Armory to use with azerothcore.
The AzerothCore Armory is a web-based character inspection tool for AzerothCore World of Warcraft private servers. It provides a visual interface to view character information, equipped items, and statistics in a layout similar to the official Blizzard World of Warcraft Armory.

### Key Objectives
- **Character Visualization**: Display characters with their equipped gear in a paper doll layout
- **Item Inspection**: Show detailed item information including stats, icons, and quality colors
- **3D Model Rendering**: Integrate 3D character models using Blizzard's asset CDN
- **Database Integration**: Direct connection to AzerothCore MySQL database
- **User-Friendly Interface**: Responsive design matching WoW's aesthetic

### Technology Stack
- **Backend**: Python 3.x with Flask web framework
- **Database**: MySQL/MariaDB (AzerothCore database)
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **External APIs**: 
  - Wowhead Model Viewer for 3D character rendering
  - Wowhead/Zamimg CDN for item icons
  - WotLK Murlocvillage for fallback icon support

---

## System Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Web Browser   │
│   (Client)      │
└────────┬────────┘
         │ HTTP Requests
         ▼
┌─────────────────┐
│  Flask Server   │
│  (Port 5000)    │
└────────┬────────┘
         │ SQL Queries
         ▼
┌─────────────────┐
│  MySQL Database │
│  - acore_chars  │
│  - acore_world  │
└─────────────────┘

External Services:
- Wowhead CDN (icons, 3D models)
- Murlocvillage (fallback icons)
```

### Application Flow

1. **Character Search Request**
   ```
   User Input → Flask Route → Database Query → JSON Response → Frontend Rendering
   ```

2. **Item Display Process**
   ```
   Character Data → Equipment Array → Icon Fetch (Wowhead) → Tooltip Generation → DOM Update
   ```

3. **3D Model Rendering**
   ```
   Character Data → Wowhead Viewer API → WebGL Canvas → Interactive 3D Model
   ```

---

## Installation & Setup

### Prerequisites

```bash
# System Requirements
- Python 3.7 or higher
- MySQL 5.7+ or MariaDB 10.3+
- AzerothCore server installation
- Modern web browser (Chrome, Firefox, Edge)

# Python Dependencies
pip install flask pymysql
```

### Installation Steps

1. **Download the Application**
   ```bash
   # Save azerothcore_armory_full.py to your server
   wget https://your-server/azerothcore_armory_full.py
   ```

2. **Configure Database Credentials**
   ```python
   # Edit the DB_CONFIG section in the Python file
   DB_CONFIG = {
       'host': 'localhost',        # Database host
       'user': 'acore',            # Database user
       'password': 'your_password', # Database password
       'database': 'acore_characters', # Characters database
       'charset': 'utf8mb4',
       'cursorclass': pymysql.cursors.DictCursor
   }
   
   # Set your world database name
   WORLD_DB_NAME = 'acore_world'  # Adjust if different
   ```

3. **Verify Database Access**
   ```bash
   # Test database connection
   mysql -u acore -p -e "USE acore_characters; SELECT COUNT(*) FROM characters;"
   ```

4. **Run the Application**
   ```bash
   python azerothcore_armory_full.py
   ```

5. **Access the Armory**
   ```
   Open browser: http://localhost:5000
   Or from network: http://your-server-ip:5000
   ```

### Production Deployment

For production environments, use a WSGI server:

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 azerothcore_armory_full:app
```

Or use systemd service:

```ini
# /etc/systemd/system/armory.service
[Unit]
Description=AzerothCore Armory
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/armory
ExecStart=/usr/bin/python3 azerothcore_armory_full.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Database Schema

### Required Tables

#### Characters Database (`acore_characters`)

**Table: `characters`**
```sql
-- Core character information
guid            INT         -- Unique character identifier
name            VARCHAR     -- Character name
race            TINYINT     -- Race ID (1-11)
class           TINYINT     -- Class ID (1-11)
gender          TINYINT     -- Gender (0=Male, 1=Female)
level           TINYINT     -- Character level (1-80)
skin            TINYINT     -- Skin color
face            TINYINT     -- Face style
hairStyle       TINYINT     -- Hair style
hairColor       TINYINT     -- Hair color
facialStyle     TINYINT     -- Facial hair style
```

**Table: `character_inventory`**
```sql
-- Character equipped items
guid            INT         -- Character GUID
item            INT         -- Item instance GUID
slot            TINYINT     -- Equipment slot (0-18)
bag             TINYINT     -- Bag number (0 for equipped)
```

**Table: `item_instance`**
```sql
-- Item instance data
guid            INT         -- Item instance GUID
itemEntry       INT         -- Item template ID
```

#### World Database (`acore_world`)

**Table: `item_template`**
```sql
-- Item definitions
entry           INT         -- Item ID
name            VARCHAR     -- Item name
displayid       INT         -- Display/model ID
Quality         TINYINT     -- Item quality (0-7)
ItemLevel       INT         -- Item level
RequiredLevel   INT         -- Required level
InventoryType   TINYINT     -- Equipment slot type
bonding         TINYINT     -- Binding type

-- Stats (1-10)
stat_type1      TINYINT
stat_value1     INT
... (stat_type2-10, stat_value2-10)

-- Defense
armor           INT
block           INT

-- Resistances
holy_res        INT
fire_res        INT
nature_res      INT
frost_res       INT
shadow_res      INT
arcane_res      INT

-- Weapon stats
delay           INT         -- Attack speed (milliseconds)
dmg_min1        FLOAT       -- Min damage
dmg_max1        FLOAT       -- Max damage
dmg_type1       TINYINT     -- Damage type

description     VARCHAR     -- Flavor text
```

### Equipment Slot Mapping

```python
SLOT_MAP = {
    0:  'Head',
    1:  'Neck',
    2:  'Shoulders',
    3:  'Shirt',
    4:  'Chest',
    5:  'Waist',
    6:  'Legs',
    7:  'Feet',
    8:  'Wrist',
    9:  'Hands',
    10: 'Finger 1',
    11: 'Finger 2',
    12: 'Trinket 1',
    13: 'Trinket 2',
    14: 'Back',
    15: 'Main Hand',
    16: 'Off Hand',
    17: 'Ranged',
    18: 'Tabard'
}
```

### Race & Class IDs

```python
RACES = {
    1: 'Human',      # Alliance
    2: 'Orc',        # Horde
    3: 'Dwarf',      # Alliance
    4: 'Night Elf',  # Alliance
    5: 'Undead',     # Horde
    6: 'Tauren',     # Horde
    7: 'Gnome',      # Alliance
    8: 'Troll',      # Horde
    10: 'Blood Elf', # Horde
    11: 'Draenei'    # Alliance
}

CLASSES = {
    1: 'Warrior',
    2: 'Paladin',
    3: 'Hunter',
    4: 'Rogue',
    5: 'Priest',
    6: 'Death Knight',
    7: 'Shaman',
    8: 'Mage',
    9: 'Warlock',
    11: 'Druid'
}
```

---

## Backend API

### Flask Application Structure

```python
app = Flask(__name__)

# Routes
@app.route('/')                    # Main page
@app.route('/api/character')       # Character data endpoint
@app.route('/api/characters')      # Character list endpoint
```

### API Endpoints

#### 1. GET `/`
**Purpose**: Serve the main HTML page

**Response**: HTML page with embedded CSS and JavaScript

---

#### 2. GET `/api/character?name={character_name}`

**Purpose**: Retrieve detailed character information including equipment

**Parameters**:
- `name` (required): Character name (case-sensitive)

**Response Format**:
```json
{
  "guid": 123,
  "name": "Testchar",
  "race": 1,
  "class": 4,
  "gender": 0,
  "level": 80,
  "skin": 4,
  "face": 0,
  "hairStyle": 5,
  "hairColor": 5,
  "facialStyle": 5,
  "equipment": [
    {
      "slot": 0,
      "entry": 40186,
      "displayId": 41628,
      "name": "Helm of the Lost Conqueror",
      "quality": 4,
      "itemLevel": 213,
      "requiredLevel": 80,
      "itemType": "Head",
      "stats": [
        "+1234 Armor",
        "+89 Stamina",
        "+67 Intellect",
        "+45 Critical Strike Rating"
      ],
      "description": "Placeholder flavor text",
      "icon": "40186"
    }
    // ... more items
  ]
}
```

**Error Responses**:
```json
// 400 Bad Request
{
  "error": "Character name required"
}

// 404 Not Found
{
  "error": "Character \"Name\" not found"
}

// 500 Internal Server Error
{
  "error": "Database connection error: ..."
}
```

**Query Process**:
1. Validate character name parameter
2. Query `characters` table for character data
3. Query `character_inventory` + `item_instance` for equipped items
4. Join with `item_template` for item details and stats
5. Parse and format stats (armor, resistances, weapon damage, etc.)
6. Return JSON response

---

#### 3. GET `/api/characters`

**Purpose**: List all characters in the database

**Response Format**:
```json
{
  "count": 150,
  "characters": [
    {
      "name": "Warlock",
      "race": 5,
      "class": 9,
      "level": 80,
      "faction": "Horde"
    },
    {
      "name": "Paladin",
      "race": 1,
      "class": 2,
      "level": 75,
      "faction": "Alliance"
    }
    // ... up to 100 characters
  ]
}
```

**Features**:
- Returns top 100 characters by level
- Automatically determines faction based on race
- Sorted by level (descending), then name

---

### Stat Type Mapping System

The application translates numeric stat type IDs into readable stat names:

```python
STAT_TYPES = {
    0: 'Mana',
    1: 'Health', 
    3: 'Agility',
    4: 'Strength',
    5: 'Intellect',
    6: 'Spirit',
    7: 'Stamina',
    12: 'Defense Rating',
    13: 'Dodge Rating',
    14: 'Parry Rating',
    15: 'Block Rating',
    16: 'Hit Melee Rating',
    17: 'Hit Ranged Rating',
    18: 'Hit Spell Rating',
    19: 'Crit Melee Rating',
    20: 'Crit Ranged Rating',
    21: 'Crit Spell Rating',
    28: 'Haste Melee Rating',
    29: 'Haste Ranged Rating',
    30: 'Haste Spell Rating',
    31: 'Hit Rating',
    32: 'Crit Rating',
    35: 'Resilience Rating',
    36: 'Haste Rating',
    37: 'Expertise Rating',
    38: 'Attack Power',
    39: 'Ranged Attack Power',
    45: 'Spell Power',
    # ... and more
}
```

### Stat Processing Algorithm

```python
# For each item, process stats 1-10
for i in range(1, 11):
    stat_type = item[f'stat_type{i}']
    stat_value = item[f'stat_value{i}']
    
    if stat_type and stat_value:
        stat_name = STAT_TYPES.get(stat_type, f'Stat {stat_type}')
        stats.append(f"+{stat_value} {stat_name}")

# Add armor
if item['armor'] > 0:
    stats.insert(0, f"+{item['armor']} Armor")

# Add resistances
for res_type in ['holy', 'fire', 'nature', 'frost', 'shadow', 'arcane']:
    res_value = item[f'{res_type}_res']
    if res_value > 0:
        stats.append(f"+{res_value} {res_type.title()} Resistance")

# Add weapon damage
if item['dmg_min1'] and item['dmg_max1']:
    dmg_type = DAMAGE_TYPES.get(item['dmg_type1'], 'Physical')
    stats.append(f"{item['dmg_min1']}-{item['dmg_max1']} {dmg_type} Damage")
    
    if item['delay']:
        speed = item['delay'] / 1000.0
        stats.append(f"Speed {speed:.2f}")
```

---

## Frontend Components

### HTML Structure

```html
<body>
  <div class="container">
    <!-- Header with search -->
    <div class="armory-header">
      <div class="search-bar">
        <input id="searchInput">
        <button onclick="searchCharacter()">Search</button>
      </div>
      <div id="charListPanel">...</div>
    </div>

    <!-- Character display -->
    <div id="characterPanel">
      <!-- Character header -->
      <div class="character-header">...</div>

      <!-- Paper doll layout -->
      <div class="armory-layout">
        <!-- Left equipment column -->
        <div class="equipment-column">
          <div class="item-slot" data-slot="0">...</div>
          <!-- More slots -->
        </div>

        <!-- Center: 3D model -->
        <div class="character-display">
          <div id="modelViewer">...</div>
          <div class="stats-panel">...</div>
        </div>

        <!-- Right equipment column -->
        <div class="equipment-column">...</div>
      </div>

      <!-- Bottom: weapon slots -->
      <div class="weapons-row">...</div>
    </div>

    <!-- Status messages -->
    <div id="loadingMsg">...</div>
    <div id="errorMsg">...</div>
  </div>

  <!-- Floating tooltip -->
  <div id="itemTooltip">...</div>
</body>
```

### CSS Styling System

#### Color Scheme
```css
/* Item Quality Colors (WoW Standard) */
.q0 { color: #9d9d9d; } /* Poor (Gray) */
.q1 { color: #ffffff; } /* Common (White) */
.q2 { color: #1eff00; } /* Uncommon (Green) */
.q3 { color: #0070dd; } /* Rare (Blue) */
.q4 { color: #a335ee; } /* Epic (Purple) */
.q5 { color: #ff8000; } /* Legendary (Orange) */
.q6 { color: #e6cc80; } /* Artifact (Light Yellow) */
.q7 { color: #00ccff; } /* Heirloom (Light Blue) */

/* Class Colors */
Warrior:      #C79C6E
Paladin:      #F58CBA
Hunter:       #ABD473
Rogue:        #FFF569
Priest:       #FFFFFF
Death Knight: #C41F3B
Shaman:       #0070DE
Mage:         #69CCF0
Warlock:      #9482C9
Druid:        #FF7D0A
```

#### Layout System
```css
/* Paper Doll Grid */
.armory-layout {
  display: grid;
  grid-template-columns: 240px 1fr 240px;
  gap: 15px;
}

/* Left: Head, Neck, Shoulders, Back, Chest, Tabard, Wrist */
/* Center: 3D Model + Stats Panel */
/* Right: Hands, Waist, Legs, Feet, Rings, Trinkets */

/* Responsive breakpoint */
@media (max-width: 1024px) {
  .armory-layout {
    grid-template-columns: 1fr;
  }
}
```

### JavaScript Core Functions

#### 1. Character Search
```javascript
async function searchCharacter() {
  // Purpose: Fetch and display character data
  
  // Get input
  const name = document.getElementById('searchInput').value.trim();
  
  // Validate
  if (!name) return;
  
  // Show loading state
  showLoading(true);
  
  // API call
  const response = await fetch(`/api/character?name=${encodeURIComponent(name)}`);
  const data = await response.json();
  
  // Display character
  displayCharacter(data);
  
  // Hide loading
  showLoading(false);
}
```

#### 2. Character Display
```javascript
function displayCharacter(data) {
  // Purpose: Render character information and equipment
  
  // Update header
  document.getElementById('charName').textContent = data.name;
  document.getElementById('charName').style.color = CLASS_COLORS[data.class];
  
  // Update stats panel
  updateStatsPanel(data);
  
  // Clear all equipment slots
  clearAllSlots();
  
  // Populate equipped items
  data.equipment.forEach(item => {
    const slot = document.querySelector(`[data-slot="${item.slot}"]`);
    populateItemSlot(slot, item);
  });
  
  // Initialize tooltips
  initTooltips();
  
  // Render 3D model
  render3DModel(data);
}
```

#### 3. Item Slot Population
```javascript
function populateItemSlot(slot, item) {
  // Purpose: Fill equipment slot with item data
  
  // Mark as equipped
  slot.classList.remove('empty');
  slot.setAttribute('data-item-id', item.entry);
  slot.setAttribute('data-item-data', JSON.stringify(item));
  
  // Load icon
  const iconContainer = slot.querySelector('.item-icon-container');
  loadItemIcon(iconContainer, item.entry, item.quality);
  
  // Update item name
  const nameElem = slot.querySelector('.item-name');
  nameElem.textContent = item.name;
  nameElem.className = `item-name q${item.quality}`;
  
  // Add item level
  if (item.itemLevel) {
    const levelElem = document.createElement('div');
    levelElem.className = 'item-level';
    levelElem.textContent = `iLvl ${item.itemLevel}`;
    slot.querySelector('.item-details').appendChild(levelElem);
  }
}
```

#### 4. Icon Loading System
```javascript
function loadItemIcon(container, itemId, quality) {
  // Purpose: Fetch and display item icon
  
  // Method 1: Try Wowhead Tooltip API
  fetch(`https://nether.wowhead.com/tooltip/item/${itemId}?dataEnv=1&locale=0`)
    .then(response => response.json())
    .then(data => {
      if (data && data.icon) {
        // Success: Use Wowhead icon
        container.innerHTML = `<img src="https://wow.zamimg.com/images/wow/icons/large/${data.icon}.jpg" class="item-icon">`;
      } else {
        // Fallback to Method 2
        useFallbackIcon(container, itemId);
      }
    })
    .catch(() => {
      // Error: Use fallback
      useFallbackIcon(container, itemId);
    });
  
  // Add quality border color
  container.classList.add(`q${quality}`);
}

function useFallbackIcon(container, itemId) {
  // Method 2: Murlocvillage icon service (WotLK specific)
  container.innerHTML = `<img src="https://wotlk.murlocvillage.com/items/icon_image.php?item=${itemId}" 
                             class="item-icon"
                             onerror="this.src='https://wow.zamimg.com/images/wow/icons/large/inv_misc_questionmark.jpg'">`;
}
```

#### 5. Tooltip System
```javascript
function initTooltips() {
  // Purpose: Attach tooltip event listeners to equipped items
  
  const tooltip = document.getElementById('itemTooltip');
  
  document.querySelectorAll('.item-slot:not(.empty)').forEach(slot => {
    // Show tooltip on hover
    slot.addEventListener('mouseenter', (e) => {
      const itemData = JSON.parse(slot.getAttribute('data-item-data'));
      showTooltip(e, itemData);
    });
    
    // Hide tooltip on leave
    slot.addEventListener('mouseleave', () => {
      tooltip.style.display = 'none';
    });
    
    // Follow cursor
    slot.addEventListener('mousemove', (e) => {
      tooltip.style.left = (e.clientX + 15) + 'px';
      tooltip.style.top = (e.clientY + 15) + 'px';
    });
  });
}

function showTooltip(event, item) {
  // Purpose: Generate and display item tooltip
  
  const tooltip = document.getElementById('itemTooltip');
  
  // Build tooltip HTML
  let html = `
    <div class="tooltip-item-name q${item.quality}">${item.name}</div>
    <div style="color: #ffd700;">Item Level ${item.itemLevel}</div>
    <div class="tooltip-item-type">${item.itemType}</div>
  `;
  
  // Add stats
  if (item.stats && item.stats.length > 0) {
    html += '<div style="border-top: 1px solid #404040; margin-top: 6px; padding-top: 6px;">';
    item.stats.forEach(stat => {
      html += `<div class="tooltip-stats">${stat}</div>`;
    });
    html += '</div>';
  }
  
  // Add required level
  if (item.requiredLevel > 1) {
    html += `<div style="color: #fff; margin-top: 6px;">Requires Level ${item.requiredLevel}</div>`;
  }
  
  // Add flavor text
  if (item.description) {
    html += `<div class="tooltip-flavor">"${item.description}"</div>`;
  }
  
  // Display tooltip
  tooltip.innerHTML = html;
  tooltip.style.display = 'block';
  tooltip.style.left = (event.clientX + 15) + 'px';
  tooltip.style.top = (event.clientY + 15) + 'px';
}
```

#### 6. 3D Model Rendering
```javascript
function render3DModel(data) {
  // Purpose: Display 3D character model using Wowhead viewer
  
  const container = document.getElementById('modelViewer');
  container.innerHTML = '';
  
  try {
    // Prepare character data for Wowhead
    const character = {
      race: data.race,
      gender: data.gender,
      skin: data.skin || 0,
      face: data.face || 0,
      hairStyle: data.hairStyle || 0,
      hairColor: data.hairColor || 0,
      facialStyle: data.facialStyle || 0,
      items: data.equipment
        .filter(item => item.displayId)
        .map(item => [item.slot, item.displayId])
    };
    
    // Check if Wowhead viewer is available
    if (typeof WH !== 'undefined' && WH.ModelViewer) {
      // Generate 3D model
      WH.ModelViewer.generateModels(1, '#modelViewer', character);
    } else {
      // Fallback: Show static representation
      showFallbackModel(container, data);
    }
  } catch (error) {
    console.error('Model viewer error:', error);
    showFallbackModel(container, data);
  }
}

function showFallbackModel(container, data) {
  // Purpose: Display fallback when 3D viewer unavailable
  
  const classColor = CLASS_COLORS[data.class];
  const raceName = RACES[data.race];
  
  container.innerHTML = `
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;">
      <div style="font-size: 80px; color: ${classColor};">⚔️</div>
      <div style="font-size: 24px; color: ${classColor}; font-weight: bold;">${data.name}</div>
      <div style="font-size: 18px; color: #ffd700; margin-top: 10px;">Level ${data.level} ${raceName}</div>
      <div style="font-size: 14px; color: #999; margin-top: 20px;">3D Model viewer unavailable</div>
    </div>
  `;
}
```

#### 7. Character List
```javascript
async function loadCharacterList() {
  // Purpose: Fetch and display all available characters
  
  const response = await fetch('/api/characters');
  const data = await response.json();
  displayCharList(data.characters);
}

function displayCharList(characters) {
  // Purpose: Render character list with clickable entries
  
  const list = document.getElementById('charList');
  
  list.innerHTML = characters.map(char => {
    const className = CLASSES[char.class];
    const raceName = RACES[char.race];
    const classColor = CLASS_COLORS[char.class];
    
    return `
      <div class="char-list-item" onclick="selectChar('${char.name}')">
        <span style="color: ${classColor}; font-weight: bold;">${char.name}</span>
        <span style="color: #999;"> - Level ${char.level} ${raceName} ${className}</span>
      </div>
    `;
  }).join('');
}

function selectChar(name) {
  // Purpose: Select character from list and trigger search
  
  document.getElementById('searchInput').value = name;
  toggleCharList();  // Close list
  searchCharacter(); // Load character
}
```

---

## Features & Functionality

### Core Features

#### 1. Character Search
- **Input Method**: Text search bar with Enter key support
- **Validation**: Character name must match database exactly (case-sensitive)
- **Feedback**: Loading indicator during search, error messages on failure
- **Character List**: Browse all characters, click to load

#### 2. Character Display
- **Header**: Character name (class-colored) with level, race, and class
- **Paper Doll Layout**: Equipment slots arranged around central model
- **Stats Panel**: Race, class, gender, faction, average item level

#### 3. Equipment Visualization
- **Item Icons**: Fetched from Blizzard CDN or fallback services
- **Quality Colors**: Border colors match WoW item quality system
- **Item Names**: Displayed with quality-colored text
- **Item Levels**: Shown below item names (if applicable)
- **Empty Slots**: Grayed out with placeholder icons

#### 4. Item Tooltips
**Hover over any equipped item to see:**
- Item name (quality-colored)
- Item level
- Binds when equipped
- Item type (Head, Chest, Weapon, etc.)
- All stats:
  - Armor value
  - Primary stats (Strength, Agility, Stamina, Intellect, Spirit)
  - Secondary stats (Hit, Crit, Haste, Expertise, etc.)
  - Resistances (Holy, Fire, Nature, Frost, Shadow, Arcane)
  - Weapon damage and speed
- Required level
- Flavor text/description

#### 5. 3D Character Model
- **Primary**: Wowhead Model Viewer integration
- **Rendering**: WebGL-based 3D model with character customization
- **Equipment Display**: Shows all equipped gear on model
- **Fallback**: Static display if 3D viewer unavailable

#### 6. Responsive Design
- **Desktop**: Full paper doll layout (3-column)
- **Tablet**: Stacked layout with wrapped equipment slots
- **Mobile**: Single column, touch-friendly interface

---

## Configuration

### Database Configuration

```python
# Primary database (characters)
DB_CONFIG = {
    'host': 'localhost',        # Change for remote database
    'user': 'acore',            # Database username
    'password': 'your_password',# Database password
    'database': 'acore_characters',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# World database name
WORLD_DB_NAME = 'acore_world'

# Common database name variations:
# - acore_characters / acore_world
# - ac_characters / ac_world
# - characters / world
```

### Server Configuration

```python
# Flask server settings
if __name__ == '__main__':
    app.run(
        debug=True,              # Set to False in production
        host='0.0.0.0',          # Bind to all interfaces
        port=5000                # Port number
    )
```

**Production Settings:**
```python
app.run(
    debug=False,
    host='0.0.0.0',
    port=5000,
    threaded=True  # Enable threading for concurrent requests
)
```

### Security Configuration

**Recommended for production:**

1. **Use Environment Variables**
```python
import os

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'acore'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'acore_characters')
}
```

2. **Enable HTTPS**
```python
# Use nginx/Apache as reverse proxy with SSL
# Or use Flask-Talisman for HTTPS
from flask_talisman import Talisman
Talisman(app)
```

3. **Add Rate Limiting**
```python
from flask_limiter import Limiter

limiter = Limiter(app, default_limits=["100 per hour"])

@app.route('/api/character')
@limiter.limit("30 per minute")
def get_character():
    # ...
```

4. **Input Sanitization**
```python
# Already implemented via parameterized queries
cursor.execute(sql, (char_name,))  # Prevents SQL injection
```

### Customization Options

#### 1. Character Limit
```python
# In list_characters() function
sql = """
    SELECT name, race, class, level, faction
    FROM characters 
    ORDER BY level DESC, name 
    LIMIT 100  # Change this value
"""
```

#### 2. Default Port
```python
app.run(host='0.0.0.0', port=8080)  # Change port
```

#### 3. Color Scheme
```css
/* Edit HTML_TEMPLATE CSS section */
body {
    background: #000000;  /* Change background color */
}

.item-slot {
    border: 1px solid #custom-color;  /* Customize borders */
}
```

#### 4. 3D Model Settings
```javascript
// In render3DModel() function
const character = {
    race: data.race,
    gender: data.gender,
    // Add custom model options here
    zoom: 1.5,  // Model zoom level
    rotation: 0 // Initial rotation
};
```

---

## Troubleshooting

### Common Issues

#### 1. "Character not found" Error

**Symptom**: 404 error when searching for character

**Causes**:
- Character name is case-sensitive
- Character doesn't exist in database
- Wrong database name configured

**Solutions**:
```bash
# Verify character exists
mysql -u acore -p acore_characters -e "SELECT name FROM characters WHERE name='YourCharName';"

# List available characters
mysql -u acore -p acore_characters -e "SELECT name FROM characters LIMIT 10;"

# Check database name
mysql -u acore -p -e "SHOW DATABASES;"
```

#### 2. Database Connection Failed

**Symptom**: "Database connection error" on startup

**Causes**:
- Wrong credentials
- MySQL server not running
- Firewall blocking connection

**Solutions**:
```bash
# Test MySQL connection
mysql -u acore -p -h localhost

# Check MySQL status
sudo systemctl status mysql

# Check firewall (Ubuntu)
sudo ufw status
sudo ufw allow 3306/tcp

# Grant remote access if needed
mysql -u root -p
GRANT ALL PRIVILEGES ON *.* TO 'acore'@'%' IDENTIFIED BY 'password';
FLUSH PRIVILEGES;
```

#### 3. Items Showing Red Question Marks

**Symptom**: All items display as red question mark icons

**Causes**:
- Icon API unreachable
- Item IDs not in Wowhead database
- Network/firewall blocking external requests

**Solutions**:
```javascript
// Check browser console for errors
// F12 → Console tab

// Verify icon URL manually
https://wotlk.murlocvillage.com/items/icon_image.php?item=40186

// Check if Wowhead is accessible
https://wow.zamimg.com/images/wow/icons/large/inv_helmet_74.jpg

// Fallback: Use local icon storage
// Download icons and serve locally
```

#### 4. No Equipment Displayed

**Symptom**: Character loads but equipment slots are empty

**Causes**:
- Character has no equipped items
- Wrong world database name
- Item template data missing

**Solutions**:
```sql
-- Check if character has equipment
SELECT ci.slot, ci.item 
FROM character_inventory ci 
WHERE ci.guid = YOUR_CHAR_GUID AND ci.bag = 0;

-- Verify world database
USE acore_world;
SELECT COUNT(*) FROM item_template;

-- Check database name in config
SHOW DATABASES LIKE '%world%';
```

#### 5. Tooltips Not Showing

**Symptom**: Hovering over items doesn't display tooltip

**Causes**:
- JavaScript error
- Event listeners not initialized
- CSS z-index issue

**Solutions**:
```javascript
// Check console for errors (F12)

// Verify tooltip element exists
console.log(document.getElementById('itemTooltip'));

// Manual initialization
initTooltips();

// CSS fix - ensure tooltip is on top
#itemTooltip {
    z-index: 10000 !important;
}
```

#### 6. 3D Model Not Loading

**Symptom**: "Loading 3D Model..." never completes

**Causes**:
- Wowhead API blocked
- WH object not loaded
- CORS policy blocking

**Solutions**:
```javascript
// Check if Wowhead is loaded
console.log(typeof WH);

// Check browser console for CORS errors

// Verify script loaded
<script src="https://wow.zamimg.com/modelviewer/live/viewer/viewer.min.js"></script>

// Fallback is automatic, but can be triggered manually
showFallbackModel(container, characterData);
```

#### 7. Stats Not Showing in Tooltips

**Symptom**: Tooltips show item name but no stats

**Causes**:
- stat_type/stat_value columns missing from query
- Database schema mismatch

**Solutions**:
```sql
-- Verify item_template structure
DESCRIBE acore_world.item_template;

-- Check if stat columns exist
SHOW COLUMNS FROM acore_world.item_template LIKE 'stat_%';

-- Verify sample item has stats
SELECT name, stat_type1, stat_value1, armor 
FROM acore_world.item_template 
WHERE entry = 40186;
```

### Performance Issues

#### Slow Character Loading

**Optimization 1: Add database indexes**
```sql
-- Index on character name
CREATE INDEX idx_char_name ON characters(name);

-- Index on inventory
CREATE INDEX idx_inventory_guid ON character_inventory(guid, bag);

-- Index on item entry
CREATE INDEX idx_item_entry ON item_instance(itemEntry);
```

**Optimization 2: Connection pooling**
```python
from flask_sqlalchemy import SQLAlchemy

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://user:pass@localhost/acore_characters'
app.config['SQLALCHEMY_POOL_SIZE'] = 10
db = SQLAlchemy(app)
```

**Optimization 3: Enable caching**
```python
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/api/characters')
@cache.cached(timeout=300)  # Cache for 5 minutes
def list_characters():
    # ...
```

### Debugging Tips

#### Enable Debug Mode
```python
# In Python file
app.run(debug=True)

# This enables:
# - Detailed error messages
# - Auto-reload on code changes
# - Interactive debugger
```

#### Browser Console
```javascript
// Check for errors
// F12 → Console tab

// Useful debug commands
console.log(currentCharacter);
console.log(document.querySelectorAll('.item-slot'));

// Test API directly
fetch('/api/character?name=TestChar')
  .then(r => r.json())
  .then(console.log);
```

#### Network Tab
```
F12 → Network tab
- See all API requests
- Check response codes
- Inspect response data
- Identify slow queries
```

---

## Future Enhancements

### Planned Features

#### 1. Advanced Search
```python
# Search by level, class, race
@app.route('/api/characters/search')
def search_characters():
    level_min = request.args.get('level_min', 1)
    level_max = request.args.get('level_max', 80)
    char_class = request.args.get('class')
    race = request.args.get('race')
    # ...
```

#### 2. Guild Display
```sql
-- Show guild information
SELECT g.name, g.info, gm.rank
FROM guild_member gm
JOIN guild g ON gm.guildid = g.guildid
WHERE gm.guid = CHARACTER_GUID;
```

#### 3. Achievement Tracking
```sql
-- Display achievements
SELECT ca.achievement, ca.date
FROM character_achievement ca
WHERE ca.guid = CHARACTER_GUID
ORDER BY ca.date DESC;
```

#### 4. Talent Specialization
```sql
-- Show talent build
SELECT spec, talents
FROM character_talent
WHERE guid = CHARACTER_GUID;
```

#### 5. PvP Statistics
```sql
-- Display arena/battleground stats
SELECT totalKills, honorableKills, arenaPoints
FROM characters
WHERE guid = CHARACTER_GUID;
```

#### 6. Item Comparison
```javascript
// Compare equipped item vs. mouseover item
function compareItems(equippedItem, newItem) {
    // Show stat differences
    // Highlight upgrades/downgrades
}
```

#### 7. Export Character Data
```python
@app.route('/api/character/export')
def export_character():
    # Generate JSON/XML export
    # For use in simulators or other tools
```

#### 8. Gear Score Calculation
```python
def calculate_gear_score(equipment):
    score = 0
    for item in equipment:
        score += item['itemLevel'] * SLOT_MULTIPLIERS[item['slot']]
    return score
```

#### 9. Enchantment Display
```sql
-- Show item enchantments
SELECT ii.guid, ie.enchantments
FROM item_instance ii
JOIN item_enchantments ie ON ii.guid = ie.item_guid;
```

#### 10. Character History
```sql
-- Track character changes over time
CREATE TABLE armory_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guid INT,
    snapshot_date TIMESTAMP,
    equipment_data JSON,
    stats_data JSON
);
```

### Integration Possibilities

#### 1. Discord Bot
```python
# Post character data to Discord
import discord
from discord.ext import commands

@bot.command()
async def armory(ctx, char_name):
    data = fetch_character(char_name)
    embed = create_character_embed(data)
    await ctx.send(embed=embed)
```

#### 2. Mobile App
```kotlin
// Android app using the API
class ArmoryService {
    suspend fun getCharacter(name: String): Character {
        return retrofit.get("/api/character?name=$name")
    }
}
```

#### 3. Website Integration
```html
<!-- Embed in guild website -->
<iframe src="http://armory.yourserver.com/?char=PlayerName" 
        width="800" height="600"></iframe>
```

#### 4. Database Replication
```python
# Read-only replica for armory
DB_CONFIG_REPLICA = {
    'host': 'replica.db.server',
    'user': 'readonly',
    'password': 'password'
}
```

---

## Technical Specifications

### System Requirements

**Minimum:**
- CPU: 1 core, 1 GHz
- RAM: 512 MB
- Storage: 100 MB
- Python: 3.7+
- MySQL: 5.7+

**Recommended:**
- CPU: 2+ cores, 2 GHz
- RAM: 2 GB
- Storage: 500 MB
- Python: 3.9+
- MariaDB: 10.5+

### Browser Compatibility

| Browser | Version | Support |
|---------|---------|---------|
| Chrome | 90+ | Full |
| Firefox | 88+ | Full |
| Edge | 90+ | Full |
| Safari | 14+ | Full |
| Opera | 76+ | Full |
| IE | Any | Not supported |

### API Performance

**Expected Response Times:**
- Character search: 50-200ms
- Character list: 100-300ms
- Icon loading: 200-500ms (external)
- 3D model: 1-3 seconds (first load)

**Throughput:**
- ~50 requests/second (single thread)
- ~200 requests/second (4 workers)

### Database Query Performance

```sql
-- Character query: ~10-50ms
-- Equipment query: ~20-100ms
-- Character list: ~50-150ms

-- Optimization: Add indexes
CREATE INDEX idx_char_name ON characters(name);
CREATE INDEX idx_inv_guid ON character_inventory(guid, bag);
```

---

## License & Credits

### Credits

**Technologies:**
- Flask - Python web framework
- PyMySQL - MySQL connector
- Wowhead - Item icons and 3D model viewer
- Blizzard Entertainment - World of Warcraft assets
- AzerothCore - WoW server emulator

### Attribution

This armory tool is designed for use with AzerothCore private servers. All World of Warcraft assets, icons, and data belong to Blizzard Entertainment.

**External Services:**
- `wow.zamimg.com` - Wowhead CDN
- `wotlk.murlocvillage.com` - WotLK icon service

---

## Support & Contact

### Getting Help

1. **Check documentation** - Review this document
2. **Check logs** - Enable debug mode and check console
3. **Test database** - Verify database connectivity
4. **Browser console** - Check for JavaScript errors

### Common Resources

- AzerothCore Wiki: https://www.azerothcore.org/wiki/
- AzerothCore Discord: https://discord.gg/gkt4y2x
- WoW Database: https://wotlk.evowow.com/

---

## Changelog

### Version 1.0 (Current)
- Initial release
- Character search and display
- Equipment visualization
- Item tooltips with stats
- 3D model integration
- Responsive design
- Character list

### Planned Updates
- Version 1.1: Guild support
- Version 1.2: Achievement display
- Version 1.3: Talent tree viewer
- Version 2.0: Full rewrite with React

---

**Document Version:** 1.0  
**Last Updated:** February 2026  
**Author:** AzerothCore Armory Development Team
