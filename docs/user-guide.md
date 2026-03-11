# The War Table — User Guide

This guide walks through everything you need to know to use The War Table as a Game Master or player.

---

## Table of Contents

1. [First-Time Setup](#first-time-setup)
2. [Creating a Campaign](#creating-a-campaign)
3. [Adding Content](#adding-content)
4. [Cross-Linking with Shortcodes](#cross-linking-with-shortcodes)
5. [Tags and Filtering](#tags-and-filtering)
6. [Adventures & the Adventure Runner](#adventures--the-adventure-runner)
7. [Combat Tracker](#combat-tracker)
8. [Dice Roller](#dice-roller)
9. [Player Access](#player-access)
10. [Import Tools](#import-tools)
11. [AI Features](#ai-features)
12. [Admin Features](#admin-features)
13. [Keyboard and Navigation Tips](#keyboard-and-navigation-tips)
14. [Settings Reference](#settings-reference)

---

## First-Time Setup

When you access The War Table for the first time, there are no users in the database. You'll be redirected to the **Setup** page to create the first admin account.

1. Go to `http://your-server:5001`
2. You'll see the **First-Run Setup** form
3. Enter a username (3+ characters) and password (8+ characters)
4. Click **Create Admin Account**
5. You're logged in and ready to go

This first account is automatically an admin. You can create additional users later from the Admin panel.

### Additional Users

- **Admin creates users:** Go to the user menu (top right) > **User Management** > **New User**
- **Self-registration:** If enabled in Settings, users can sign up at `/signup`

---

## Creating a Campaign

Campaigns are the top-level container for all your content. Each campaign is independent — NPCs, locations, quests, etc. belong to one campaign only.

1. Click **Campaigns** in the user menu (top right)
2. Click **New Campaign**
3. Fill in:
   - **Name** (required) — e.g., "Curse of the Iron Crown"
   - **System** — e.g., "D&D 5e", "ICRPG", "Pathfinder 2e" (freeform text)
   - **Status** — Active or Inactive
   - **Description** — overview of the campaign (supports Markdown)
   - **Stat Preset** — choose a preset to auto-create stat fields for player characters (STR, DEX, CON, etc.), or choose None/Custom
4. Click **Create Campaign** — you'll land on the New Adventure page to create your first adventure.

### Switching Campaigns

Click any campaign name on the Campaigns page to switch to it. All entity lists (NPCs, Quests, etc.) filter to the active campaign.

### Editing Campaign Settings

From the campaign detail page, click **Edit** to change:
- Campaign name, system, status, and description
- **Stat template fields** — add, rename, reorder, or delete stat fields (these define what stats PCs track)
- **AI world context** — background text about your world that AI Smart Fill uses for better suggestions
- **Image style prompt** — a style prefix for AI-generated images (e.g., "dark fantasy oil painting")

---

## Adding Content

All entity types follow the same pattern: navigate to the list page, click **New**, fill in the form, and save. Detail pages show all fields with links to related entities.

### NPCs

NPCs are the characters your players interact with.

- **Name** (required), Role, Status (alive/dead/unknown/missing)
- **Faction** — select existing or use the quick-create button (+) to make a new one inline
- **Home Location** — where the NPC lives
- **Connected Locations** — other places the NPC is associated with
- **Physical Description, Personality, Notes** — all support Markdown
- **Secrets** — GM-only field, never shown to players
- **Portrait** — upload an image or generate one with Stable Diffusion
- **Tags** — comma-separated or quick-add from existing campaign tags
- **Player Visible** — toggle whether this NPC appears in the player campaign view

### Player Characters (PCs)

PCs represent the players' characters. They're separate from NPCs with different fields.

- **Character Name, Player Name** (required), Race/Ancestry, Class/Role, Level
- **Status** — active, inactive, retired, dead, or NPC (for converted characters)
- **Stats** — dynamic fields based on your campaign's stat template (e.g., STR 16, DEX 14)
- **Description, Backstory** — visible to the player who owns the character
- **GM Hooks, Notes** — GM-only fields
- **Claim/Unclaim** — players can claim unclaimed characters, linking their user account

#### ICRPG Characters

For ICRPG campaigns, character creation uses an **8-step Character Wizard** instead of the basic form. Players (or GMs) access it from the campaign home page.

The wizard covers:
1. **World** — Alfheim, Warp Shell, Ghost Mountain, etc.
2. **Life Form** — race/ancestry for the chosen world
3. **Type** — class equivalent, determines starting abilities and milestone options
4. **Starting Abilities** — chosen from the type's ability list
5. **Basic Loot** — starting gear picks from the world's loot table
6. **Stats** — BODY, MIND, WILL, FORT, DEX, INT; Hearts and Hero Coins
7. **Name & Bio** — character name, description, backstory
8. **Review & Create**

The **ICRPG Character Sheet** has five tabs:
- **Loot** — Equipped (slotted) and Carried items with slot tracking
- **Effects** — active bonuses and penalties from equipped loot and abilities
- **Abilities** — Starting, Milestone, and Mastery abilities
- **Bio** — Description and Backstory (readable by both GM and player)
- **Notes** — freeform player notes (editable inline)
- **Mastery Progress** — tracks Natural 20s toward Mastery stars (always visible below the tabs)

### Locations

Locations support a parent/child hierarchy for nesting (e.g., Kingdom > City > Tavern).

- **Parent Location** — creates nesting; the list page groups by parent
- **Connected Locations** — bidirectional links (selecting A as connected to B also shows B connected to A)
- **Map Image** — upload a map for this location

### Quests

Quests track story threads with status tracking.

- **Status** — Active, On Hold, Completed, or Failed
- The list page groups quests by status
- **Hook** — the inciting event or rumor
- **Involved NPCs / Locations** — multi-select to link related entities
- **Outcome** — fill in when the quest resolves

### Sessions

Sessions are your game session logs.

- **Session Number** — auto-increments if left blank
- **Date Played** — date picker
- **Prep Notes** — GM-only, for pre-session planning
- **Summary** — what happened during the session
- **Linked Entities** — select NPCs, locations, items, quests, and monsters that appeared
- **Attended PCs** — track which player characters were present

### Story Arcs

Story Arcs are free-form Markdown documents for planning and running adventure areas. Each arc is a hub for one adventure location, storyline, or dungeon.

- **Name** (required), **Subtitle** — a one-line tagline
- **Status** — Planned, Active, or Completed
- **Content** — full Markdown. Use `## Headings` for sections; the page auto-generates a sticky table of contents from them
- **Run State** — per-section progress tracking (mark zones explored or cleared)
- **AI tools** built in to Story Arc detail pages:
  - **Brainstorm Arcs** — generate 3–5 arc ideas from your campaign context
  - **Suggest Ideas** — generate 4–6 new areas/encounters to add to the current arc
  - **Generate Prep** — create session prep notes from the arc content and previous session summary
  - **Draft Summary** — turn GM notes into a polished player-facing session recap

**Entity-from-selection:** In the arc editor, highlight any text and choose a type (NPC, Location, etc.) to instantly create that entity and insert a shortcode. The text is replaced with a live link.

**Shortcode:** `#site[Arc Name]` — links to a Story Arc from any Markdown field.

### Items

Items are objects of note in your campaign.

- **Type** — weapon, armor, potion, artifact, etc. (freeform)
- **Rarity** — common, uncommon, rare, very rare, legendary
- **Owner** — which NPC currently holds it
- **Origin Location** — where it was found or created

### Factions

Factions are organizations, guilds, or groups.

- **Disposition** — Friendly, Neutral, Hostile, or Unknown
- The list page groups by disposition
- Linked to NPCs, Locations, and Quests throughout the app
- **Adventures** — link factions to an adventure from its Entities tab. Linked factions appear in the Adventure Runner's Session tab with color-coded disposition badges (green=friendly, yellow=neutral, red=hostile).

### Compendium

The Compendium stores custom rules, lore, and reference material.

- **Category** — group entries (e.g., "House Rules", "World Lore", "Magic System")
- **GM Only** — toggle to hide from players
- Content supports full Markdown

### Bestiary

The Bestiary is **global** (not campaign-scoped) — the same monster can be used across campaigns.

- **System** — what game system the stat block is for
- **Stat Block** — full stat block in Markdown
- **CR/Level** — challenge rating or level
- **Spawn** — click to create a **Monster Instance** in your active campaign (copies stats, allows per-encounter customization)

### Random Tables

Create rollable tables for loot, encounters, weather, etc.

- **Rows** — each row has content (Markdown) and a weight (higher weight = more likely to roll)
- **Roll** — click the dice button to get a random result
- ICRPG seed data can be loaded from Settings

### Encounters

Encounters link monsters to sessions and can include loot tables.

- Add monsters from the bestiary or from campaign monster instances
- Set monster count per encounter
- Link a random table for loot

---

## Cross-Linking with Shortcodes

Any text field that supports Markdown also supports **shortcodes** — inline references to other entities.

### Syntax

```
#npc[Character Name]
#loc[Location Name]
#item[Item Name]
#quest[Quest Name]
#faction[Faction Name]
#site[Story Arc Name]
```

When you save an entity with shortcodes, The War Table:
1. Looks up the referenced entity by name
2. Creates a clickable link in the rendered text
3. Records a "mention" so the referenced entity shows a **"Referenced by"** badge on its detail page

If the referenced entity doesn't exist yet, a stub is automatically created so you can fill in the details later.

---

## Tags and Filtering

Tags help organize entities within a campaign.

- Tags are **campaign-scoped** — each campaign has its own tag list
- Add tags to NPCs, Locations, Quests, Items, and Sessions
- On list pages, use the **tag filter dropdown** to show only entities with a specific tag
- Manage all tags from **Reference > Tags** in the navbar

**Bestiary tags** work differently — they're stored as comma-separated text on each entry (since the bestiary is global, not per-campaign).

---

## Adventures & the Adventure Runner

Adventures are the primary tool for planning and running your game sessions. Each Adventure is structured as a hierarchy: **Adventure → Acts → Scenes → Rooms**.

### Structure

- **Adventure** — the top-level container (e.g., "The Sunken Temple of Kael"). Has a name, hook, status (Planned / Active / Complete), and linked entities.
- **Acts** — major story phases within the adventure (e.g., "Act 1: The Approach")
- **Scenes** — specific situations or areas within an act (e.g., "The Gatehouse")
- **Rooms** — individual encounter spaces within a scene, each with a name, description, and optional monster/loot content

### Creating an Adventure

1. Click **Adventures** in the navbar
2. Click **New Adventure**
3. Fill in the name, hook (a one-sentence premise), and status
4. Save — then add Acts from the detail page

### The Adventure Detail Page

The detail page has tabs:

- **Overview** — summary, linked factions, status
- **Entities** — link NPCs, Party PCs, and Factions to this adventure. Linked factions show their disposition badge.
- **Structure** — manage Acts, Scenes, and Rooms

### Launching the Runner

From the Adventure detail page, click **Run** to open the **Adventure Runner** — a live game dashboard optimized for use at the table.

The Runner has four panels:

| Panel | Contents |
|-------|----------|
| **Session** | Active quests, linked factions (with disposition color), timestamped notes |
| **Rooms** | All rooms in the adventure. Click a room to expand it; mark rooms as **Revealed** to share them with players. |
| **NPCs** | All NPCs linked to this adventure. Shows name, role, and faction badge. |
| **Party** | PCs attending this adventure with HP, Hero Coins, and quick-edit controls. |

### Room Reveals

Marking a room as **Revealed** makes it visible to players on their Campaign Home page under Locations (if the room is linked to a location). This is the primary way to share explored areas with players in real time.

### Post-Session Wrap-Up

From the Runner, click **Wrap Up Session** to:
- Update quest statuses in bulk (completed, failed, on hold)
- Update NPC statuses (alive, dead, missing)
- Add notes to items

---

## Combat Tracker

The Combat Tracker helps manage combat encounters.

1. Click the **shield icon** in the navbar
2. Set a session for context
3. Add combatants:
   - PCs from the active session's attendance list
   - Monsters from the bestiary (quick-add)
4. Track initiative order, HP, and conditions

---

## Dice Roller

Click the **dice icon** in the navbar to open the dice roller drawer.

- **Quick buttons** for common dice (d4, d6, d8, d10, d12, d20, d100)
- **Custom expression** field — type `2d6+3`, `4d8`, `d20`, etc.
- **Modes** — Normal, Advantage (roll twice, take higher), Disadvantage (roll twice, take lower)
- **History** — last 20 rolls are saved in the drawer (persists within the browser session)

---

## Player Access

Players have their own login-based experience, separate from the GM interface.

### Setting Up Player Accounts

Admins create player accounts in **User Management > New User**. Set the **Role** to **Player**. Players can also self-register at `/signup` if that setting is enabled.

- **GM role** — full access to all content management tools, adventure builder, runner, and admin pages
- **Player role** — sees only the player dashboard and their own campaign content; cannot access GM pages

### Player Dashboard

When a player logs in, they land on the **Player Dashboard**, which shows:
- Campaigns they belong to
- Their characters across all campaigns

### Joining a Campaign

1. From the Player Dashboard, click **Browse Campaigns**
2. Public campaigns are listed — click **Join** to become a member
3. The campaign now appears on the Player Dashboard

GMs can also add players directly by inviting them or giving them the campaign's public link.

### Campaign Home

Clicking a campaign on the Player Dashboard opens the **Campaign Home** — the player's view of that campaign. It shows only content the GM has marked as player-visible:

- **Locations** — places the party has been to or that the GM has revealed
- **People (NPCs)** — characters the GM has made visible
- **Quests** — active and completed quests shared with the party
- **Items & Loot** — party treasure and any items assigned to the player's characters

### Creating a Character

From the Campaign Home, click **New Character**:
- **ICRPG campaigns** — launches the 8-step Character Wizard (see [ICRPG Characters](#icrpg-characters))
- **Other campaigns** — opens the standard character form

Characters appear on the Campaign Home under **My Characters** once created.

### What Players Never See

- NPC Secrets
- GM Notes (on any entity)
- GM Hooks (on PCs)
- Prep Notes (on Sessions)
- Compendium entries marked GM Only
- Other players' characters (only their own)
- Adventure structure, room details, or runner tools

---

## Import Tools

### Obsidian Vault Import

Import Markdown files from an Obsidian vault as NPCs, Locations, or Compendium entries.

1. Go to **User Menu > Obsidian Import**
2. Enter the path to your vault folder (on the server filesystem)
3. Preview detected files and adjust type mappings
4. Run the import

YAML frontmatter and `[[wiki-links]]` are parsed and converted.

### D&D 5e SRD Import

Browse and import monsters, spells, and items from the Open5e API.

1. Go to **User Menu > D&D 5e SRD Import**
2. Browse available content by category
3. Select entries to import into your bestiary or compendium

### ICRPG Seed Data

Pre-built bestiary entries and random tables for ICRPG.

1. Go to **Compendium** or **Random Tables**
2. Click **Seed ICRPG Data** to load entries
3. Use **Clear ICRPG Data** to remove them if no longer needed

---

## AI Features

AI features are optional and require configuration in Settings (Anthropic API key or local Ollama).

### Smart Fill

On any entity create/edit form, click **Smart Fill**, paste raw text (session notes, character descriptions, brainstormed ideas), and the AI extracts structured data to fill in the form fields.

### Generate Entry

On any entity create form, click **Generate**, enter a short concept (e.g., "a grizzled dwarf blacksmith who secretly works for the thieves' guild"), and the AI generates a complete entity with all fields populated.

> **Story Arc Generate** is tuned to create a focused 300–500 word arc overview — key scenes, central conflict, major NPCs, climax, and possible outcomes. Not a full campaign document.

### Campaign Assistant

Each campaign has a **Campaign Assistant** chat panel. Ask it anything about your world — it has access to the campaign's world context. The chat history persists within the session.

### Story Arc AI Tools

Story Arc detail pages have a toolbar with:

| Button | What it does |
|--------|-------------|
| **Brainstorm Arcs** | Generates 3–5 new story arc ideas based on your existing campaign content |
| **Suggest Ideas** | Generates 4–6 new areas, rooms, or encounters to add to the current arc |
| **Generate Prep** | Creates session prep notes from the arc content and the previous session's summary |
| **Draft Summary** | Turns your post-session GM notes into a polished player-facing recap |

### Adventure Runner AI

During a live session in the Runner:
- **Improv Encounter** — generates a quick combat encounter on the fly
- **Hazard Flavor** — generates sensory descriptions for timers or environmental events
- **Suggest Consequences** — after wrap-up, suggests 2–3 narrative ripple effects from the session
- **NPC Chat** — in-character dialogue for any linked NPC

### Image Generation

With a Stable Diffusion instance configured in Settings, click **Generate Image** on entity forms. The AI creates a portrait or scene image based on the entity's description. Campaign-level style prompts are automatically prepended.

### Per-Feature Provider

If both Anthropic and Ollama are configured, you can assign each AI feature to a specific provider in **Settings > AI Provider**. Use a fast cloud model for real-time features and a local model for longer generation tasks.

### Editable AI Prompts

**Settings > AI Prompts** (collapsed by default — Advanced section) shows the system prompt sent to the AI for each feature. You can customize any prompt for your campaign's tone or game system. Click **Reset** to restore the built-in default.

---

## Admin Features

Admin users have access to additional tools.

### User Management

**User Menu > User Management**
- View all registered users
- Create new users — set the **Role** to control their experience:
  - **GM** — full access to all content management, adventures, runner, and settings
  - **Player** — logs in to the player dashboard; can join campaigns, create characters, and view player-visible content only
- Reset user passwords
- Delete users (cannot delete yourself)

### Settings

**User Menu > Settings**
- Toggle **Allow Signup** — enable or disable self-registration
- Configure AI and image generation providers (Anthropic API key, Ollama URL/model)
- Configure Stable Diffusion (URL, model, sampler, dimensions)
- **Per-feature AI provider** — assign each feature to Anthropic or Ollama when both are set up
- **AI Prompts (Advanced)** — edit or reset the system prompt for each AI feature

---

## Settings Reference

| Setting | Where | Description |
|---------|-------|-------------|
| Allow Signup | Settings | Show/hide the signup link on the login page |
| AI Provider | Settings | Global AI backend: None, Ollama (local), or Anthropic (cloud) |
| Anthropic API Key | Settings | Your key from console.anthropic.com |
| Ollama URL / Model | Settings | URL and model name for local Ollama instance |
| Per-Feature Provider | Settings | Override global AI provider per feature (Smart Fill, Generate, etc.) |
| AI World Context | Campaign Edit | Campaign background text — AI uses this for tone and setting |
| Image Style Prompt | Campaign Edit | Style prefix for AI-generated images (e.g., "dark fantasy oil painting") |
| AI Prompts | Settings (Advanced) | System prompts for each AI feature — edit or reset to default |
| SD URL / Model | Settings | Stable Diffusion connection and model selection |
| SD Parameters | Settings | Steps, CFG scale, sampler, dimensions, negative prompt |

---

## Keyboard and Navigation Tips

- **Global Search** — type in the search box in the navbar to search across all entity types. Use arrow keys to navigate results, Enter to select, Escape to close.
- **Quick Create** — when filling out dropdowns (Faction, Location, etc.), click the **+** button to create a new entity without leaving the form.
- **Breadcrumbs** — detail pages show breadcrumbs for navigation. Players are always returned to their Campaign Home, never to GM list pages.
- **Campaign Banner** — the colored banner below the navbar shows your active campaign name and system at all times.
