# War Table App Refinement: GM Workflow and UX Overview

This document compiles ideas for enhancing the user experience (UX) and process flow in the War Table app, focusing on the Game Master's (GM) perspective. It builds on the existing architecture, emphasizing intuitive organization, seamless prep-to-runtime transitions, and integration of AI assistance to aid creativity and efficiency. The goal is to make campaign building, adventure planning, session running, and follow-up feel fluid and supportive, turning freeform documents (like Adventure Sites) into actionable tools.

Key principles:
- **Hierarchy**: Modular and contextual, radiating from Campaign to entities.
- **Workflow**: Guided, cyclical process with prompts/checklists.
- **Dashboard-Centric Runtime**: A "digital GM screen" for quick access during play.
- **AI Integration**: Embedded where it helps with ideas/creation, using the existing Claude API (configurable via AppSettings).
- **Assumptions**: Minimal backend changes (e.g., add relationships like progress fields); leverage shortcodes, Quick Create, and existing features.

**Note on Hierarchy Adjustment**: To simplify the structure and avoid adding a new "Adventures" (Arcs) entity type, merge the concept into Adventure Sites. Enhance Adventure Sites with self-nesting (e.g., parent_site_id for grouping related sites into arcs, like "Floor 1" as a child of "The Descent"). This keeps the core entity intact while allowing logical groupings without extra layers.

---

## Overall Hierarchy and Navigation

The hierarchy organizes entities logically from a GM's view, starting broad (Campaign) and narrowing to specifics (Sessions/Entities). It's not rigid—use bidirectional links (via EntityMentions/shortcodes) for easy jumping. This ensures everything "ties together" without scattering content.

- **Core Hierarchy**:
  - **Campaign** (Top-level container: Overview of plot, world, stats templates. All data scoped here.)
    - **Adventure Site** (Freeform Markdown hub: Full scenario with locations, encounters, NPCs via shortcodes. Supports self-nesting via parent_site_id for arcs/groupings, e.g., "The Descent" as parent with "Floor 1" and "Floor 2" as children. Can span multiple sessions.)
      - **Linked Sessions** (Many-to-many: Sessions pull from Site content; unfinished elements carry over.)
        - **Entities** (NPCs, Quests, Locations, Items, Encounters, Monsters—auto-linked via shortcodes or manual associations. Backrefs show "Referenced In" for context.)

- **Navigation Elements**:
  - **Global Sidebar**: Collapsible tree view of the hierarchy. Supports drag-and-drop reorganization (e.g., move a Quest between Sites).
  - **Contextual Breadcrumbs**: Top of every page, e.g., *Campaign: SyscoGen Ascension > Site: The Descent > Sub-Site: Floor 1 > Session 3: Core Forge Battle*.
  - **Quick Access Bar**: Persistent bottom navbar with icons: Global Search (filters by type/tag/campaign), Quick Create (entity from name), Dice Roller, AI Assist (contextual generation), Switch Campaign.
  - **Search Integration**: Prominent search bar on all views; results grouped by hierarchy level (e.g., "NPCs in this Site"). Use tags for filtering (e.g., "hostile" for bosses).
  - **Visual Cues**: Color-coding (Green: Completed, Yellow: In Progress, Red: Planned). Progress bars on Sites based on milestones.

This structure makes Campaigns the "broad overview" of plot points/sites/quests, while Sessions are flexible "slices" (one or many per Site).

---

## GM Process Flow

A guided, cyclical workflow to support campaign building, adventure/session planning, runtime, and follow-up. The app provides soft guidance via wizards, checklists, modals, and buttons (e.g., "Next Step: Plan Session"). AI integrations are embedded where they help generate ideas, fill content, or suggest refinements—always optional, with GM edit/approval. Triggers use buttons or auto-prompts after saves.

### Step 1: Campaign Building (Broad Setup)
Start here for new campaigns. Focus on high-level structure.

- **Key Actions**:
  - Edit Campaign overview: Write description, set system/theme, upload world map.
  - Add global elements: Create Factions, major Quests, Locations (e.g., world regions), BestiaryEntries (shared monsters).
  - Organize via Kanban Board: Columns like "Backstory Ideas," "Major Arcs," "Key Entities." Drag to group (e.g., link Factions to Quests).
- **App Guidance**: Initial wizard modal: "Campaign Setup Checklist: [ ] Add Plot Hooks [ ] Define Factions [ ] Set AI Context."
- **AI Assistance**:
  - **Generate Overviews/Plot Hooks**: Button: “Brainstorm Arcs.” Prompt: “Generate 3–5 high-level arcs based on theme: [description/system/ai_world_context]. Include factions, big bads, tone.” (Helps blank-page start.)
  - **Faction/Lore Seed**: On Faction create: AI button expands short input into full details (name, description, goals, GM notes). Prompt: “Expand: [input].”
- **Transition**: Button to "Start New Site" creates an Adventure Site.
- **Time Estimate**: 1-2 hours initial; iterative.

### Step 2: Adventure Planning (Drill Down)
Build detailed scenarios using Adventure Sites as the creative hub.

- **Key Actions**:
  - Create/Edit Adventure Site: Markdown editor for freeform content (e.g., Overview, Locations, Encounters, Mobs). Use ## headings for auto-ToC. Nest sites via parent_site_id for arcs (e.g., group "Floor 1–3" under "The Descent").
  - Inline Creation: Text-selection tool to create/link NPCs/Quests/Locations/Items via shortcodes (replaces text automatically).
  - Add Milestones/Breakpoints: Fields for progress tracking (e.g., checkboxes: "Sorting Bay Cleared").
  - Link Entities: Manual associations (e.g., tag with Factions) or auto via shortcodes/EntityMentions.
- **App Guidance**: Editor sidebar checklist: "[ ] Add Sections [ ] Link Entities [ ] Estimate Sessions."
- **AI Assistance**:
  - **Smart Fill Sections**: Button in editor: Fills gaps. Prompt: “Suggest details/hazards/loot for sections: [headings]. Theme: [site theme].”
  - **Generate Room/Encounter Ideas**: Sidebar: “Generate Rooms.” Prompt: “Suggest 4–6 ideas with threat/loot/quips for [theme].”
  - **Mob/Boss Stats**: On NPC/Bestiary create: AI generates blocks. Prompt: “Create ICRPG stats for [description]. Include moves.”
  - **Milestone Suggestions**: After save: “Suggest Session Splits.” Prompt: “Suggest breakpoints/milestones from content.”
- **Transition**: Button "Link to Session" auto-creates a Session with pre-pulled elements (e.g., pinned NPCs).
- **Time Estimate**: Variable; 1-3 hours per Site.

### Step 3: Session Planning (Focused Prep)
Refine for a specific play session, pulling from linked Sites.

- **Key Actions**:
  - Edit Session: Set date/title, add prep notes, pin NPCs/Locations/Items, set active location.
  - Customize: Add Encounters (from Bestiary), link Quests, estimate hazards/timers.
  - Player Integration: Mark PC attendance, quick-view stats.
- **App Guidance**: Checklist modal: "[ ] Pin Key Elements [ ] Add Encounters [ ] Set Hazards."
- **AI Assistance**:
  - **Prep Notes Generation**: Button: “Generate Prep.” Prompt: “Write notes from Site/previous summary: [context]. Include twists/hazards.”
  - **Pinned Suggestions**: Sidebar: Suggests elements. Prompt: “Suggest 4–6 pins from Site/Session: [context].”
- **Transition**: Button "Enter Run Mode" loads the dashboard.
- **Time Estimate**: 30-60 minutes.

### Step 4: Session Running (Real-Time Execution)
Switch to a dedicated dashboard for at-the-table use. Focus on quick access, no page reloads.

- **Key Actions**:
  - Navigate Content: Jump via ToC, click shortcodes for popups.
  - Track Progress: Update statuses (e.g., NPC dead), roll dice/hazards, take live notes.
  - Handle Combat: Init tracker, HP adjustments.
- **App Guidance**: None intrusive—focus on flow; optional "Pause for Notes" button.
- **AI Assistance**:
  - **Expanded Quick Chat**: Input for NPC responses or narrations. Prompt: “React as [NPC] to [player action].” Or: “Orb quip for [failure].”
  - **Dynamic Hazard Flavor**: On timer/roll: Generate description. Prompt: “Describe [event] in [situation]: sensory/complication.”
  - **On-the-Fly Encounters**: Button: “Improv Encounter.” Prompt: “Generate small combat for [location/context].”
- **Transition**: End button triggers follow-up modal.
- **Time Estimate**: Game session length.

### Step 5: Post-Session Follow-Up (Reflection & Update)
Wrap up and prepare for next.

- **Key Actions**:
  - Write summary, update statuses (e.g., Quest advanced, Items looted).
  - Propagate Changes: Auto-update linked entities (e.g., dead NPC hides in wiki).
  - Carry Over: Tag unfinished for next Session.
- **App Guidance**: Modal: "Update Checklist: [ ] Summary [ ] Statuses [ ] Carry Unfinished."
- **AI Assistance**:
  - **Summary Draft**: Button: “Draft Summary.” Prompt: “Write recap from notes/events: [input]. Style: [theme].”
  - **Consequence Suggestions**: In modal: Prompt: “Suggest 2–3 ripples from outcomes: [changes].”
- **Transition**: Button "Generate Next Session" clones carryovers.
- **Time Estimate**: 15-30 minutes.
- **Cyclical Loop**: Updates feed back to Campaign/Site overviews (e.g., roll-up progress).

---

## Session-Running Dashboard (Digital GM Screen)

A customizable, full-screen view (toggle from Session Mode) to make running suck less. Modular panels for fingertip access; drag to rearrange. Builds on existing Session Mode.

- **Layout**:
  - **Main Panel (50%)**: Rendered Adventure Site Markdown. Sticky ToC, section highlights, shortcode popups (e.g., NPC card).
  - **Toolkit Panel (30%)**: Pinned Entities (inline edits), PC Stats/Attendance, Encounter/Combat Tracker (initiatives, HP, rolls), Timers/Hazards (widgets for auto-rolls like 1d6 shift change).
  - **Controls Bar (20%)**: Prep/Live Notes (editable), AI Quick Chat, Dice Roller, Search.
  - **Overlays**: Map viewer (zoomable uploads), Wiki Preview (for players).

- **Features**:
  - Real-Time Sync: Changes save instantly (e.g., milestone check updates progress bar).
  - Customization: Presets (e.g., "Combat Mode" enlarges tracker).
  - Integration: Shortcodes are "live"—hover previews, click edits.

---

## Handling Multi-Session Adventures

To support Sites spanning sessions or sessions covering partial content:

- **Progress Tracking**: Add fields to Sites (e.g., milestone checkboxes, progress bar %). Sessions update these.
- **Carryover Logic**: Post-session, modal tags "Ongoing" elements; auto-add to next Session's pins/prep.
- **Suggestions**: After Site save, prompt splits (AI-assisted). In hierarchy, show "Linked Sessions" with status.
- **Visuals**: Roll-up bars (e.g., Campaign: "Site: 60% Done"). Color-coded lists.

---

## UX Enhancements

- **Theming/Accessibility**: Dark mode (existing), high-contrast options.
- **Player Wiki Tie-In**: GM toggles visibility post-session; dashboard preview button.
- **Import/Export**: Expand Obsidian importer for workflows like your example doc.
- **Performance**: Lazy-load entities; use localStorage for runtime states (e.g., timers).
- **Testing/Iteration**: Prototype dashboard extensions in dev; user feedback loops.

This overview provides a foundation for refinement—focus on implementing one step (e.g., dashboard) first. For backend, prioritize adding self-nesting to Adventure Sites and progress fields.