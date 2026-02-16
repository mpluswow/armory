#!/usr/bin/env python3
"""
AzerothCore Armory - Full Featured
With item icons, tooltips, 3D character model, and official Blizzard armory layout
"""

from flask import Flask, jsonify, request, render_template_string
import pymysql
import sys

app = Flask(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'acore',
    'password': 'kulka34',
    'database': 'acore_characters',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

WORLD_DB_NAME = 'acore_world'

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Armory - AzerothCore</title>
    <link rel="stylesheet" href="https://wow.zamimg.com/css/basic.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Verdana', sans-serif;
            background: #000 url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAIklEQVQYV2NkYGD4z8DAwMgABXAGLAYxQAkYBowCRgEjAwB0CAQBzp9u9wAAAABJRU5ErkJggg==');
            color: #f8f8f8;
            min-height: 100vh;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        .armory-header {
            background: linear-gradient(to bottom, rgba(0,0,0,0.95), rgba(0,0,0,0.8));
            border: 1px solid #3d3226;
            border-radius: 5px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.8);
        }

        .search-bar {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }

        .search-input {
            flex: 1;
            padding: 12px;
            background: rgba(0,0,0,0.6);
            border: 1px solid #5c4a3a;
            color: #fff;
            border-radius: 3px;
            font-size: 15px;
        }

        .btn {
            padding: 12px 25px;
            background: linear-gradient(to bottom, #8b7355, #5c4a3a);
            border: 1px solid #3d3226;
            color: #f8f8f8;
            border-radius: 3px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
        }

        .btn:hover {
            background: linear-gradient(to bottom, #9d8566, #6d5645);
        }

        .character-header {
            background: rgba(0,0,0,0.8);
            border: 1px solid #3d3226;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }

        .char-name-title {
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 8px;
            text-shadow: 2px 2px 4px #000;
        }

        .char-subtitle {
            font-size: 16px;
            color: #daa520;
        }

        .armory-layout {
            display: grid;
            grid-template-columns: 240px 1fr 240px;
            gap: 15px;
            background: rgba(0,0,0,0.8);
            border: 1px solid #3d3226;
            border-radius: 5px;
            padding: 20px;
        }

        .equipment-column {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .item-slot {
            background: rgba(0,0,0,0.6);
            border: 1px solid #404040;
            border-radius: 3px;
            padding: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
            min-height: 50px;
        }

        .item-slot:hover {
            background: rgba(139,115,85,0.3);
            border-color: #8b7355;
        }

        .item-slot.empty {
            opacity: 0.5;
        }

        .item-icon-container {
            width: 36px;
            height: 36px;
            border: 1px solid #404040;
            border-radius: 2px;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .item-icon {
            width: 100%;
            height: 100%;
            border-radius: 2px;
        }

        .item-icon-empty {
            font-size: 24px;
            opacity: 0.3;
        }

        .item-details {
            flex: 1;
            overflow: hidden;
        }

        .slot-label {
            font-size: 10px;
            color: #999;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .item-name {
            font-size: 13px;
            font-weight: bold;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            text-shadow: 1px 1px 2px #000;
        }

        .item-level {
            font-size: 11px;
            color: #ffd700;
        }

        /* Item quality colors */
        .q0 { color: #9d9d9d; border-color: #9d9d9d !important; }
        .q1 { color: #ffffff; border-color: #ffffff !important; }
        .q2 { color: #1eff00; border-color: #1eff00 !important; }
        .q3 { color: #0070dd; border-color: #0070dd !important; }
        .q4 { color: #a335ee; border-color: #a335ee !important; }
        .q5 { color: #ff8000; border-color: #ff8000 !important; }
        .q6 { color: #e6cc80; border-color: #e6cc80 !important; }
        .q7 { color: #00ccff; border-color: #00ccff !important; }

        .character-display {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .model-viewer {
            width: 100%;
            height: 550px;
            background: radial-gradient(circle, rgba(50,40,30,0.3), rgba(0,0,0,0.8));
            border: 1px solid #3d3226;
            border-radius: 5px;
            margin-bottom: 15px;
            position: relative;
        }

        .stats-panel {
            width: 100%;
            background: rgba(0,0,0,0.6);
            border: 1px solid #3d3226;
            border-radius: 3px;
            padding: 15px;
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid rgba(139,115,85,0.2);
            font-size: 13px;
        }

        .stat-row:last-child {
            border-bottom: none;
        }

        .stat-label {
            color: #999;
        }

        .stat-value {
            color: #fff;
            font-weight: bold;
        }

        /* Tooltip styling */
        .item-tooltip {
            position: fixed;
            background: linear-gradient(to bottom, rgba(15,15,15,0.98), rgba(5,5,5,0.98));
            border: 2px solid #8b7355;
            border-radius: 4px;
            padding: 12px;
            z-index: 10000;
            pointer-events: none;
            min-width: 250px;
            max-width: 350px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.9);
            display: none;
        }

        .tooltip-item-name {
            font-size: 15px;
            font-weight: bold;
            margin-bottom: 4px;
        }

        .tooltip-item-type {
            font-size: 12px;
            color: #ffd700;
            margin-bottom: 8px;
        }

        .tooltip-stats {
            font-size: 12px;
            color: #1eff00;
            margin: 4px 0;
        }

        .tooltip-flavor {
            font-size: 11px;
            color: #ffd700;
            font-style: italic;
            margin-top: 8px;
        }

        .weapons-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 15px;
        }

        .weapon-slot {
            min-height: 60px;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #ffd700;
        }

        .error {
            background: rgba(139,0,0,0.3);
            border: 1px solid #8b0000;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }

        @media (max-width: 1024px) {
            .armory-layout {
                grid-template-columns: 1fr;
            }
            
            .equipment-column {
                flex-direction: row;
                flex-wrap: wrap;
            }
            
            .item-slot {
                flex: 1;
                min-width: 45%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="armory-header">
            <div class="search-bar">
                <input type="text" class="search-input" id="searchInput" 
                       placeholder="Enter character name..." 
                       onkeypress="if(event.key==='Enter')searchCharacter()">
                <button class="btn" onclick="searchCharacter()">Search</button>
                <button class="btn" onclick="toggleCharList()">Character List</button>
            </div>
            <div id="charListPanel" style="display: none;">
                <div id="charList"></div>
            </div>
        </div>

        <div id="characterPanel" style="display: none;">
            <div class="character-header">
                <div class="char-name-title" id="charName"></div>
                <div class="char-subtitle" id="charSubtitle"></div>
            </div>

            <div class="armory-layout">
                <!-- Left Column -->
                <div class="equipment-column">
                    <div class="item-slot empty" data-slot="0">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">🪖</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Head</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="1">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">📿</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Neck</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="2">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">🦾</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Shoulders</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="14">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">🧥</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Back</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="4">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">👕</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Chest</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="18">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">🏴</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Tabard</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="8">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">⌚</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Wrist</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                </div>

                <!-- Center - Character Model -->
                <div class="character-display">
                    <div class="model-viewer" id="modelViewer">
                        <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #ffd700;">
                            Loading 3D Model...
                        </div>
                    </div>
                    <div class="stats-panel">
                        <div class="stat-row">
                            <span class="stat-label">Race</span>
                            <span class="stat-value" id="statRace">-</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Class</span>
                            <span class="stat-value" id="statClass">-</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Gender</span>
                            <span class="stat-value" id="statGender">-</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Faction</span>
                            <span class="stat-value" id="statFaction">-</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Average Item Level</span>
                            <span class="stat-value" id="statItemLevel">-</span>
                        </div>
                    </div>
                </div>

                <!-- Right Column -->
                <div class="equipment-column">
                    <div class="item-slot empty" data-slot="9">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">🧤</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Hands</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="5">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">🥋</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Waist</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="6">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">👖</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Legs</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="7">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">🥾</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Feet</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="10">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">💍</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Finger 1</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="11">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">💍</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Finger 2</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="12">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">🔮</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Trinket 1</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                    <div class="item-slot empty" data-slot="13">
                        <div class="item-icon-container">
                            <span class="item-icon-empty">🔮</span>
                        </div>
                        <div class="item-details">
                            <div class="slot-label">Trinket 2</div>
                            <div class="item-name">Empty</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Weapon Slots -->
            <div class="weapons-row">
                <div class="item-slot weapon-slot empty" data-slot="15">
                    <div class="item-icon-container">
                        <span class="item-icon-empty">⚔️</span>
                    </div>
                    <div class="item-details">
                        <div class="slot-label">Main Hand</div>
                        <div class="item-name">Empty</div>
                    </div>
                </div>
                <div class="item-slot weapon-slot empty" data-slot="16">
                    <div class="item-icon-container">
                        <span class="item-icon-empty">🛡️</span>
                    </div>
                    <div class="item-details">
                        <div class="slot-label">Off Hand</div>
                        <div class="item-name">Empty</div>
                    </div>
                </div>
                <div class="item-slot weapon-slot empty" data-slot="17">
                    <div class="item-icon-container">
                        <span class="item-icon-empty">🏹</span>
                    </div>
                    <div class="item-details">
                        <div class="slot-label">Ranged</div>
                        <div class="item-name">Empty</div>
                    </div>
                </div>
            </div>
        </div>

        <div id="loadingMsg" class="loading" style="display: none;">Loading...</div>
        <div id="errorMsg" class="error" style="display: none;"></div>
    </div>

    <!-- Tooltip -->
    <div class="item-tooltip" id="itemTooltip"></div>

    <!-- Load jQuery first -->
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://wow.zamimg.com/modelviewer/live/viewer/viewer.min.js"></script>
    <script>
        const RACES = {
            1: 'Human', 2: 'Orc', 3: 'Dwarf', 4: 'Night Elf', 5: 'Undead',
            6: 'Tauren', 7: 'Gnome', 8: 'Troll', 10: 'Blood Elf', 11: 'Draenei'
        };

        const CLASSES = {
            1: 'Warrior', 2: 'Paladin', 3: 'Hunter', 4: 'Rogue', 5: 'Priest',
            6: 'Death Knight', 7: 'Shaman', 8: 'Mage', 9: 'Warlock', 11: 'Druid'
        };

        const CLASS_COLORS = {
            1: '#C79C6E', 2: '#F58CBA', 3: '#ABD473', 4: '#FFF569', 5: '#FFFFFF',
            6: '#C41F3B', 7: '#0070DE', 8: '#69CCF0', 9: '#9482C9', 11: '#FF7D0A'
        };

        let currentCharacter = null;
        let modelViewer = null;
        let itemIconCache = {};

        // Function to get item icon from Wowhead
        function getItemIcon(itemId) {
            // This will be cached or fetched via Wowhead's tooltip system
            return `inv_misc_questionmark`; // Fallback, Wowhead will replace
        }

        // Initialize Wowhead tooltips
        if (typeof $WowheadPower !== 'undefined') {
            $WowheadPower.refreshLinks();
        }

        async function searchCharacter() {
            const name = document.getElementById('searchInput').value.trim();
            if (!name) return;

            document.getElementById('loadingMsg').style.display = 'block';
            document.getElementById('errorMsg').style.display = 'none';
            document.getElementById('characterPanel').style.display = 'none';

            try {
                const response = await fetch(`/api/character?name=${encodeURIComponent(name)}`);
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error);
                }
                
                const data = await response.json();
                currentCharacter = data;
                displayCharacter(data);
            } catch (error) {
                document.getElementById('errorMsg').textContent = error.message;
                document.getElementById('errorMsg').style.display = 'block';
            } finally {
                document.getElementById('loadingMsg').style.display = 'none';
            }
        }

        function displayCharacter(data) {
            document.getElementById('characterPanel').style.display = 'block';
            
            const className = CLASSES[data.class] || 'Unknown';
            const raceName = RACES[data.race] || 'Unknown';
            const classColor = CLASS_COLORS[data.class] || '#ffffff';
            
            document.getElementById('charName').textContent = data.name;
            document.getElementById('charName').style.color = classColor;
            document.getElementById('charSubtitle').textContent = 
                `Level ${data.level} ${raceName} ${className}`;

            // Update stats
            document.getElementById('statRace').textContent = raceName;
            document.getElementById('statClass').textContent = className;
            document.getElementById('statClass').style.color = classColor;
            document.getElementById('statGender').textContent = data.gender === 0 ? 'Male' : 'Female';
            
            const isAlliance = [1, 3, 4, 7, 11].includes(data.race);
            const factionElem = document.getElementById('statFaction');
            factionElem.textContent = isAlliance ? 'Alliance' : 'Horde';
            factionElem.style.color = isAlliance ? '#0070dd' : '#ff0000';

            // Calculate average item level
            const itemLevels = data.equipment.filter(i => i.itemLevel).map(i => i.itemLevel);
            const avgILevel = itemLevels.length > 0 
                ? Math.round(itemLevels.reduce((a,b) => a+b, 0) / itemLevels.length) 
                : 0;
            document.getElementById('statItemLevel').textContent = avgILevel || '-';

            // Clear all slots
            document.querySelectorAll('.item-slot').forEach(slot => {
                slot.classList.add('empty');
                slot.removeAttribute('data-item-id');
                const iconContainer = slot.querySelector('.item-icon-container');
                iconContainer.innerHTML = '<span class="item-icon-empty">' + 
                    iconContainer.querySelector('.item-icon-empty').textContent + '</span>';
                const nameElem = slot.querySelector('.item-name');
                nameElem.textContent = 'Empty';
                nameElem.className = 'item-name';
                const levelElem = slot.querySelector('.item-level');
                if (levelElem) levelElem.remove();
            });

            // Fill equipped items
            data.equipment.forEach(item => {
                const slot = document.querySelector(`[data-slot="${item.slot}"]`);
                if (!slot) return;

                slot.classList.remove('empty');
                slot.setAttribute('data-item-id', item.entry);
                slot.setAttribute('data-item-data', JSON.stringify(item));

                // Add item icon - using Wowhead's system with item links
                const iconContainer = slot.querySelector('.item-icon-container');
                
                // Create a hidden Wowhead link to get the icon
                const wowheadLink = document.createElement('a');
                wowheadLink.href = `https://www.wowhead.com/wotlk/item=${item.entry}`;
                wowheadLink.rel = 'item=' + item.entry;
                wowheadLink.style.display = 'none';
                document.body.appendChild(wowheadLink);
                
                // Fetch icon from Wowhead
                fetch(`https://nether.wowhead.com/tooltip/item/${item.entry}?dataEnv=1&locale=0`)
                    .then(response => response.json())
                    .then(data => {
                        if (data && data.icon) {
                            iconContainer.innerHTML = `<img src="https://wow.zamimg.com/images/wow/icons/large/${data.icon}.jpg" 
                                                           class="item-icon">`;
                        } else {
                            // Fallback: try common icon patterns
                            iconContainer.innerHTML = `<img src="https://wotlk.murlocvillage.com/items/icon_image.php?item=${item.entry}" 
                                                           class="item-icon"
                                                           onerror="this.src='https://wow.zamimg.com/images/wow/icons/large/inv_misc_questionmark.jpg'">`;
                        }
                    })
                    .catch(() => {
                        // Fallback icon method
                        iconContainer.innerHTML = `<img src="https://wotlk.murlocvillage.com/items/icon_image.php?item=${item.entry}" 
                                                       class="item-icon"
                                                       onerror="this.src='https://wow.zamimg.com/images/wow/icons/large/inv_misc_questionmark.jpg'">`;
                    });
                
                iconContainer.classList.add(`q${item.quality}`);

                // Update item name
                const nameElem = slot.querySelector('.item-name');
                nameElem.textContent = item.name;
                nameElem.className = `item-name q${item.quality}`;

                // Add item level
                if (item.itemLevel) {
                    let levelElem = slot.querySelector('.item-level');
                    if (!levelElem) {
                        levelElem = document.createElement('div');
                        levelElem.className = 'item-level';
                        slot.querySelector('.item-details').appendChild(levelElem);
                    }
                    levelElem.textContent = `iLvl ${item.itemLevel}`;
                }
            });

            // Initialize tooltips
            initTooltips();

            // Render 3D model
            render3DModel(data);
        }

        function render3DModel(data) {
            const container = document.getElementById('modelViewer');
            container.innerHTML = '';

            try {
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

                if (typeof WH !== 'undefined' && WH.ModelViewer) {
                    WH.ModelViewer.generateModels(1, '#modelViewer', character);
                } else {
                    container.innerHTML = `
                        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; padding: 20px; text-align: center;">
                            <div style="font-size: 80px; margin-bottom: 20px; color: ${CLASS_COLORS[data.class]};">⚔️</div>
                            <div style="font-size: 24px; color: ${CLASS_COLORS[data.class]}; font-weight: bold;">${data.name}</div>
                            <div style="font-size: 18px; color: #ffd700; margin-top: 10px;">Level ${data.level} ${RACES[data.race]}</div>
                            <div style="font-size: 14px; color: #999; margin-top: 20px;">3D Model viewer unavailable</div>
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Model viewer error:', error);
                container.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #ffd700;">
                        Character loaded - Model viewer not available
                    </div>
                `;
            }
        }

        function initTooltips() {
            const tooltip = document.getElementById('itemTooltip');
            
            document.querySelectorAll('.item-slot:not(.empty)').forEach(slot => {
                slot.addEventListener('mouseenter', (e) => {
                    const itemData = JSON.parse(slot.getAttribute('data-item-data'));
                    showTooltip(e, itemData);
                });

                slot.addEventListener('mouseleave', () => {
                    tooltip.style.display = 'none';
                });

                slot.addEventListener('mousemove', (e) => {
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                });
            });
        }

        function showTooltip(event, item) {
            const tooltip = document.getElementById('itemTooltip');
            
            let html = `
                <div class="tooltip-item-name q${item.quality}">${item.name}</div>
            `;

            if (item.itemLevel) {
                html += `<div style="color: #ffd700; font-size: 12px; border-bottom: 1px solid #404040; padding-bottom: 4px; margin-bottom: 6px;">Item Level ${item.itemLevel}</div>`;
            }

            // Item binding
            html += `<div style="color: #fff; font-size: 11px;">Binds when equipped</div>`;

            // Item type
            if (item.itemType) {
                html += `<div class="tooltip-item-type">${item.itemType}</div>`;
            }

            // Display all stats
            if (item.stats && item.stats.length > 0) {
                html += `<div style="border-top: 1px solid #404040; margin-top: 6px; padding-top: 6px;">`;
                item.stats.forEach(stat => {
                    html += `<div class="tooltip-stats">${stat}</div>`;
                });
                html += `</div>`;
            }

            // Required level
            if (item.requiredLevel && item.requiredLevel > 1) {
                html += `<div style="color: #fff; font-size: 11px; margin-top: 6px;">Requires Level ${item.requiredLevel}</div>`;
            }

            // Item description/flavor text
            if (item.description) {
                html += `<div class="tooltip-flavor">"${item.description}"</div>`;
            }

            tooltip.innerHTML = html;
            tooltip.style.display = 'block';
            tooltip.style.left = (event.clientX + 15) + 'px';
            tooltip.style.top = (event.clientY + 15) + 'px';
        }

        async function loadCharacterList() {
            try {
                const response = await fetch('/api/characters');
                const data = await response.json();
                displayCharList(data.characters);
            } catch (error) {
                console.error('Error loading characters:', error);
            }
        }

        function displayCharList(characters) {
            const list = document.getElementById('charList');
            list.innerHTML = characters.map(char => {
                const className = CLASSES[char.class] || 'Unknown';
                const raceName = RACES[char.race] || 'Unknown';
                const classColor = CLASS_COLORS[char.class] || '#ffffff';
                return `
                    <div style="padding: 10px; margin: 5px 0; background: rgba(0,0,0,0.5); border: 1px solid #3d3226; border-radius: 3px; cursor: pointer; transition: all 0.3s;"
                         onmouseover="this.style.background='rgba(139,115,85,0.3)'"
                         onmouseout="this.style.background='rgba(0,0,0,0.5)'"
                         onclick="selectChar('${char.name}')">
                        <span style="color: ${classColor}; font-weight: bold;">${char.name}</span>
                        <span style="color: #999; margin-left: 10px;">- Level ${char.level} ${raceName} ${className}</span>
                    </div>
                `;
            }).join('');
        }

        function selectChar(name) {
            document.getElementById('searchInput').value = name;
            toggleCharList();
            searchCharacter();
        }

        function toggleCharList() {
            const panel = document.getElementById('charListPanel');
            if (panel.style.display === 'none') {
                loadCharacterList();
                panel.style.display = 'block';
            } else {
                panel.style.display = 'none';
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            window.CONTENT_PATH = 'https://wow.zamimg.com/modelviewer/live/';
        });
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/character')
def get_character():
    char_name = request.args.get('name', '').strip()
    if not char_name:
        return jsonify({'error': 'Character name required'}), 400
    
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            # Get character
            sql = """
                SELECT guid, name, race, class, gender, level, skin, face, 
                       hairStyle, hairColor, facialStyle
                FROM characters WHERE name = %s LIMIT 1
            """
            cursor.execute(sql, (char_name,))
            character = cursor.fetchone()
            
            if not character:
                return jsonify({'error': f'Character "{char_name}" not found'}), 404
            
            # Get equipment with more details including stats
            sql = f"""
                SELECT 
                    ci.slot,
                    ii.itemEntry as entry,
                    it.displayid,
                    it.name,
                    it.Quality as quality,
                    it.ItemLevel,
                    it.InventoryType,
                    it.RequiredLevel,
                    it.stat_type1, it.stat_value1,
                    it.stat_type2, it.stat_value2,
                    it.stat_type3, it.stat_value3,
                    it.stat_type4, it.stat_value4,
                    it.stat_type5, it.stat_value5,
                    it.stat_type6, it.stat_value6,
                    it.stat_type7, it.stat_value7,
                    it.stat_type8, it.stat_value8,
                    it.stat_type9, it.stat_value9,
                    it.stat_type10, it.stat_value10,
                    it.armor,
                    it.block,
                    it.holy_res,
                    it.fire_res,
                    it.nature_res,
                    it.frost_res,
                    it.shadow_res,
                    it.arcane_res,
                    it.delay,
                    it.dmg_min1, it.dmg_max1, it.dmg_type1,
                    it.dmg_min2, it.dmg_max2, it.dmg_type2,
                    it.bonding,
                    it.description
                FROM character_inventory ci
                INNER JOIN item_instance ii ON ci.item = ii.guid
                INNER JOIN {WORLD_DB_NAME}.item_template it ON ii.itemEntry = it.entry
                WHERE ci.guid = %s AND ci.bag = 0 AND ci.slot < 19
                ORDER BY ci.slot
            """
            
            try:
                cursor.execute(sql, (character['guid'],))
                equipment = cursor.fetchall()
                print(f"✓ Loaded {character['name']} with {len(equipment)} items")
            except Exception as e:
                print(f"⚠ Equipment error: {e}")
                equipment = []
            
            # Stat type mapping
            STAT_TYPES = {
                0: 'Mana', 1: 'Health', 3: 'Agility', 4: 'Strength', 5: 'Intellect',
                6: 'Spirit', 7: 'Stamina', 12: 'Defense Rating', 13: 'Dodge Rating',
                14: 'Parry Rating', 15: 'Block Rating', 16: 'Hit Melee Rating',
                17: 'Hit Ranged Rating', 18: 'Hit Spell Rating', 19: 'Crit Melee Rating',
                20: 'Crit Ranged Rating', 21: 'Crit Spell Rating', 22: 'Hit Taken Melee Rating',
                23: 'Hit Taken Ranged Rating', 24: 'Hit Taken Spell Rating', 
                25: 'Crit Taken Melee Rating', 26: 'Crit Taken Ranged Rating',
                27: 'Crit Taken Spell Rating', 28: 'Haste Melee Rating',
                29: 'Haste Ranged Rating', 30: 'Haste Spell Rating', 31: 'Hit Rating',
                32: 'Crit Rating', 33: 'Hit Taken Rating', 34: 'Crit Taken Rating',
                35: 'Resilience Rating', 36: 'Haste Rating', 37: 'Expertise Rating',
                38: 'Attack Power', 39: 'Ranged Attack Power', 40: 'Versatility',
                41: 'Spell Healing Done', 42: 'Spell Damage Done', 43: 'Mana Regeneration',
                44: 'Armor Penetration Rating', 45: 'Spell Power', 46: 'Health Regen',
                47: 'Spell Penetration', 48: 'Block Value'
            }
            
            # Format equipment with stats
            formatted_equipment = []
            for item in equipment:
                stats = []
                
                # Add armor
                if item.get('armor', 0) > 0:
                    stats.append(f"+{item['armor']} Armor")
                
                # Add primary stats
                for i in range(1, 11):
                    stat_type = item.get(f'stat_type{i}')
                    stat_value = item.get(f'stat_value{i}')
                    if stat_type and stat_value:
                        stat_name = STAT_TYPES.get(stat_type, f'Stat {stat_type}')
                        stats.append(f"+{stat_value} {stat_name}")
                
                # Add resistances
                resistances = []
                if item.get('holy_res', 0) > 0:
                    resistances.append(f"+{item['holy_res']} Holy Resistance")
                if item.get('fire_res', 0) > 0:
                    resistances.append(f"+{item['fire_res']} Fire Resistance")
                if item.get('nature_res', 0) > 0:
                    resistances.append(f"+{item['nature_res']} Nature Resistance")
                if item.get('frost_res', 0) > 0:
                    resistances.append(f"+{item['frost_res']} Frost Resistance")
                if item.get('shadow_res', 0) > 0:
                    resistances.append(f"+{item['shadow_res']} Shadow Resistance")
                if item.get('arcane_res', 0) > 0:
                    resistances.append(f"+{item['arcane_res']} Arcane Resistance")
                
                stats.extend(resistances)
                
                # Add weapon damage
                if item.get('dmg_min1') and item.get('dmg_max1'):
                    dmg_types = {0: 'Physical', 1: 'Holy', 2: 'Fire', 3: 'Nature', 
                                4: 'Frost', 5: 'Shadow', 6: 'Arcane'}
                    dmg_type = dmg_types.get(item.get('dmg_type1', 0), 'Physical')
                    stats.append(f"{item['dmg_min1']}-{item['dmg_max1']} {dmg_type} Damage")
                    if item.get('delay'):
                        speed = item['delay'] / 1000.0
                        stats.append(f"Speed {speed:.2f}")
                
                # Get inventory type name
                inv_types = {
                    0: 'Non-equippable', 1: 'Head', 2: 'Neck', 3: 'Shoulder', 4: 'Shirt',
                    5: 'Chest', 6: 'Waist', 7: 'Legs', 8: 'Feet', 9: 'Wrist', 10: 'Hands',
                    11: 'Finger', 12: 'Trinket', 13: 'One-Hand', 14: 'Shield', 15: 'Ranged',
                    16: 'Back', 17: 'Two-Hand', 18: 'Bag', 19: 'Tabard', 20: 'Chest',
                    21: 'Main Hand', 22: 'Off Hand', 23: 'Holdable', 24: 'Ammo',
                    25: 'Thrown', 26: 'Ranged', 28: 'Relic'
                }
                inv_type_name = inv_types.get(item.get('InventoryType', 0), 'Item')
                
                formatted_equipment.append({
                    'slot': int(item['slot']),
                    'entry': int(item['entry']),
                    'displayId': int(item['displayid']),
                    'name': item['name'],
                    'quality': int(item['quality']),
                    'itemLevel': int(item['ItemLevel']) if item.get('ItemLevel') else None,
                    'requiredLevel': int(item['RequiredLevel']) if item.get('RequiredLevel') else None,
                    'itemType': inv_type_name,
                    'stats': stats,
                    'description': item.get('description', ''),
                    'icon': str(item['entry'])  # Use item entry ID for icon lookup
                })
            
            return jsonify({
                'guid': character['guid'],
                'name': character['name'],
                'race': int(character['race']),
                'class': int(character['class']),
                'gender': int(character['gender']),
                'level': int(character['level']),
                'skin': int(character['skin']),
                'face': int(character['face']),
                'hairStyle': int(character['hairStyle']),
                'hairColor': int(character['hairColor']),
                'facialStyle': int(character['facialStyle']),
                'equipment': formatted_equipment
            })
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if connection:
            connection.close()


@app.route('/api/characters')
def list_characters():
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            sql = """
                SELECT name, race, class, level,
                CASE WHEN race IN (1,3,4,7,11) THEN 'Alliance' ELSE 'Horde' END as faction
                FROM characters ORDER BY level DESC, name LIMIT 100
            """
            cursor.execute(sql)
            return jsonify({'count': cursor.rowcount, 'characters': cursor.fetchall()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if connection:
            connection.close()


if __name__ == '__main__':
    print("=" * 70)
    print("🏰 AzerothCore Armory - Full Featured")
    print("=" * 70)
    
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM characters")
            count = cursor.fetchone()['count']
            print(f"\n✓ Database connected ({count} characters)")
        conn.close()
    except Exception as e:
        print(f"\n✗ Database error: {e}")
        sys.exit(1)
    
    print("\n🌐 Server: http://localhost:5000")
    print("=" * 70 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
