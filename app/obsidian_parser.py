"""Obsidian Vault Parser for GM Wiki Import.

Reads an Obsidian vault directory and extracts structured data
suitable for import into the GM Wiki database. Handles NPC extraction,
Location/Floor parsing, and Compendium content mapping.
"""

import os
import re
import shutil
from pathlib import Path


# ---------------------------------------------------------------------------
# Folder-to-entity mapping defaults
# ---------------------------------------------------------------------------

# Maps vault folder prefixes to (entity_type, compendium_category, is_gm_only)
# entity_type is one of: 'npc', 'location', 'compendium', 'skip'
DEFAULT_FOLDER_MAP = {
    '00_Campaign_Hub': ('skip', None, False),
    '01_Core_Rules': ('compendium', 'Rules', False),
    '02_World': ('compendium', 'World', False),
    '03_Character_Options': ('compendium', 'Character Options', False),
    '04_NPCs': ('npc', None, False),
    '05_GM_Tools': ('compendium', 'GM Tools', True),
    '06_Floors': ('location', None, False),
    '07_Templates': ('skip', None, False),
    '08_Session_Notes': ('skip', None, False),
}

# Subfolders that override the parent folder's mapping
SUBFOLDER_OVERRIDES = {
    'Sponsors': ('npc_faction', None, False),
    'Equipment': ('compendium', 'Equipment', False),
    'Bioforms': ('compendium', 'Character Options', False),
    'Types': ('compendium', 'Character Options', False),
    'Infrastructure': ('compendium', 'World', False),
}


def scan_vault(vault_path):
    """Scan an Obsidian vault and return a list of file entries with auto-mapping.

    Returns a list of dicts, each with:
        - path: absolute path to the .md file
        - relative_path: path relative to vault root
        - filename: just the filename without extension
        - folder: the top-level folder name (e.g. '04_NPCs')
        - subfolder: immediate subfolder name if any (e.g. 'Sponsors')
        - entity_type: auto-detected type ('npc', 'npc_faction', 'location', 'compendium', 'skip')
        - category: compendium category if applicable
        - is_gm_only: whether this should be GM-only
    """
    vault_path = Path(vault_path)
    if not vault_path.is_dir():
        raise ValueError(f"Vault path does not exist: {vault_path}")

    entries = []
    for md_file in sorted(vault_path.rglob('*.md')):
        rel = md_file.relative_to(vault_path)
        parts = rel.parts  # e.g. ('04_NPCs', 'Vex.md') or ('02_World', 'Sponsors', 'Flameo Inc.md')

        folder = parts[0] if len(parts) > 1 else ''
        subfolder = parts[1] if len(parts) > 2 else ''

        # Determine mapping: check subfolder override first, then folder default
        if subfolder and subfolder in SUBFOLDER_OVERRIDES:
            entity_type, category, is_gm_only = SUBFOLDER_OVERRIDES[subfolder]
        elif folder in DEFAULT_FOLDER_MAP:
            entity_type, category, is_gm_only = DEFAULT_FOLDER_MAP[folder]
        else:
            entity_type, category, is_gm_only = ('compendium', 'Uncategorized', False)

        # Smart overrides: overview/reference files in NPC or Location folders
        # should become Compendium entries, not individual NPCs/Locations
        fname_lower = md_file.stem.lower()
        overview_keywords = ['overview', 'random', 'generator', 'template',
                             'commentary database', 'structure and timers']
        if entity_type in ('npc', 'npc_faction', 'location'):
            if any(kw in fname_lower for kw in overview_keywords):
                # Remap to compendium with a sensible category
                if entity_type in ('npc', 'npc_faction'):
                    category = 'NPCs'
                else:
                    category = 'World'
                entity_type = 'compendium'
                is_gm_only = True

        entries.append({
            'path': str(md_file),
            'relative_path': str(rel),
            'filename': md_file.stem,  # filename without .md
            'folder': folder,
            'subfolder': subfolder if subfolder and not subfolder.endswith('.md') else '',
            'entity_type': entity_type,
            'category': category,
            'is_gm_only': is_gm_only,
        })

    return entries


def scan_images(vault_path):
    """Find all image files in the vault. Returns list of absolute paths."""
    vault_path = Path(vault_path)
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    images = []
    for f in vault_path.rglob('*'):
        if f.suffix.lower() in image_exts:
            images.append(str(f))
    return images


def read_md_file(filepath):
    """Read a markdown file and return (title, body).

    Title is extracted from the first # heading, or falls back to filename.
    Body is everything after the title line.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    # Find the first H1 heading
    title = None
    body_start = 0
    for i, line in enumerate(lines):
        match = re.match(r'^#\s+(.+)', line)
        if match:
            title = match.group(1).strip()
            body_start = i + 1
            break

    if title is None:
        title = Path(filepath).stem
        body_start = 0

    body = '\n'.join(lines[body_start:]).strip()
    return title, body


def extract_overview_table(body):
    """Extract key-value pairs from an Obsidian overview table.

    Looks for markdown tables like:
        | Attribute | Value |
        |-----------|-------|
        | **Role** | Some role |

    Returns a dict of lowercase-key → value pairs, with ** markup stripped.
    """
    table_data = {}
    in_table = False

    for line in body.split('\n'):
        line = line.strip()
        # Detect table row (has | separators)
        if re.match(r'^\|.*\|.*\|$', line):
            # Skip separator rows
            if re.match(r'^\|[\s\-:]+\|[\s\-:]+\|$', line):
                in_table = True
                continue
            if in_table:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if len(cells) >= 2:
                    key = re.sub(r'\*\*', '', cells[0]).strip().lower()
                    value = cells[1].strip()
                    table_data[key] = value
        else:
            if in_table:
                break  # End of table

    return table_data


def extract_sections(body):
    """Split markdown body into sections by ## headings.

    Returns a dict of heading_text → section_content.
    Content includes everything until the next ## heading.
    """
    sections = {}
    current_heading = None
    current_lines = []

    for line in body.split('\n'):
        match = re.match(r'^##\s+(.+)', line)
        if match:
            if current_heading is not None:
                sections[current_heading.lower()] = '\n'.join(current_lines).strip()
            current_heading = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections[current_heading.lower()] = '\n'.join(current_lines).strip()

    return sections


def parse_npc(filepath):
    """Parse an NPC markdown file into GM Wiki NPC fields.

    Returns a dict with keys matching the NPC model:
        name, role, status, faction, physical_description,
        personality, secrets, notes, is_player_visible
    """
    title, body = read_md_file(filepath)
    overview = extract_overview_table(body)
    sections = extract_sections(body)

    # Extract role from overview table
    role = overview.get('role', '')

    # Extract faction from overview (if present)
    faction = overview.get('faction', overview.get('sponsor', ''))
    # Clean wiki-links from faction value
    faction = re.sub(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', r'\1', faction)

    # Build physical description from Appearance section
    physical_description = sections.get('appearance', '')

    # Build personality from Personality section
    personality = sections.get('personality', '')

    # Secrets = backstory + stats + GM notes (GM-only content)
    secret_parts = []
    for key in ['backstory', 'stats (if needed)', 'stats', 'role in campaign',
                'possible fates', 'gm notes']:
        if key in sections:
            secret_parts.append(f"## {key.title()}\n\n{sections[key]}")
    secrets = '\n\n---\n\n'.join(secret_parts) if secret_parts else ''

    # Notes = overview + see also + any remaining sections
    notes_parts = []
    used_keys = {'overview', 'appearance', 'personality', 'backstory',
                 'stats (if needed)', 'stats', 'role in campaign',
                 'possible fates', 'gm notes', 'see also'}
    for key, content in sections.items():
        if key not in used_keys and content.strip():
            notes_parts.append(f"## {key.title()}\n\n{content}")
    notes = '\n\n'.join(notes_parts) if notes_parts else ''

    # Status defaults to alive
    status = overview.get('status', 'alive').lower()
    if status not in ('alive', 'dead', 'unknown', 'missing'):
        status = 'alive'

    return {
        'name': title,
        'role': role,
        'status': status,
        'faction': faction,
        'physical_description': physical_description,
        'personality': personality,
        'secrets': secrets,
        'notes': notes,
        'is_player_visible': True,
    }


def parse_npc_faction(filepath):
    """Parse a Sponsor/Faction markdown file into GM Wiki NPC fields.

    Sponsors become NPCs with role='Faction/Organization'.
    Their mechanical details (loot, commentary) go in secrets.
    """
    title, body = read_md_file(filepath)
    overview = extract_overview_table(body)
    sections = extract_sections(body)

    # Description = overview + what impresses them
    desc_parts = []
    for key in ['overview', 'what impresses ' + title.lower().split()[0],
                'what impresses flameo', 'what impresses them']:
        if key in sections:
            desc_parts.append(sections[key])
    # Try any "what impresses" section
    for key, content in sections.items():
        if 'what impresses' in key and content not in desc_parts:
            desc_parts.append(content)

    # Build a short description from overview table
    theme = overview.get('theme', '')
    values = overview.get('values', '')
    personality = overview.get('personality', '')
    colors = overview.get('colors', '')
    desc_text = ''
    if theme:
        desc_text += f"**Theme:** {theme}\n"
    if values:
        desc_text += f"**Values:** {values}\n"
    if colors:
        desc_text += f"**Colors:** {colors}\n"
    if personality:
        desc_text += f"**Personality:** {personality}\n"
    if desc_parts:
        desc_text += '\n' + '\n\n'.join(desc_parts)

    # Secrets = loot tables + commentary + favored bioforms/types (GM reference)
    secret_parts = []
    for key in sorted(sections.keys()):
        if key in ('overview',):
            continue
        if any(kw in key for kw in ['loot', 'commentary', 'favored', 'signature',
                                     'see also']):
            secret_parts.append(f"## {key.title()}\n\n{sections[key]}")

    secrets = '\n\n---\n\n'.join(secret_parts) if secret_parts else ''

    # Notes = everything else
    used_keys = {'overview'} | {k for k in sections if any(
        kw in k for kw in ['loot', 'commentary', 'favored', 'signature',
                           'what impresses', 'see also'])}
    notes_parts = []
    for key, content in sections.items():
        if key not in used_keys and content.strip():
            notes_parts.append(f"## {key.title()}\n\n{content}")
    notes = '\n\n'.join(notes_parts) if notes_parts else ''

    return {
        'name': title,
        'role': 'Faction/Organization',
        'status': 'alive',
        'faction': '',
        'physical_description': desc_text,
        'personality': personality,
        'secrets': secrets,
        'notes': notes,
        'is_player_visible': True,
    }


def parse_location(filepath):
    """Parse a Floor markdown file into a parent Location + child Locations.

    Returns a dict with:
        - parent: dict of Location fields for the floor itself
        - children: list of dicts for room/zone child locations
        - images: list of image filenames found nearby
    """
    title, body = read_md_file(filepath)
    overview = extract_overview_table(body)
    sections = extract_sections(body)

    # Parent location description = overview + environment
    desc_parts = []
    if overview:
        desc_parts.append(_format_overview_table(overview))
    if 'environment' in sections:
        desc_parts.append(sections['environment'])
    description = '\n\n'.join(desc_parts) if desc_parts else ''

    # GM notes = encounters + boss + timer mechanics + revelations + sponsor activity + gm notes
    gm_parts = []
    gm_keys = ['encounters', 'timer mechanics', 'revelations', 'sponsor activity',
                'gm notes', 'safe room', 'loot opportunities']
    for key in gm_keys:
        if key in sections:
            gm_parts.append(f"## {key.title()}\n\n{sections[key]}")

    # Also grab any boss section
    for key in sections:
        if 'boss' in key.lower() and key not in gm_keys:
            gm_parts.append(f"## {key.title()}\n\n{sections[key]}")

    gm_notes = '\n\n---\n\n'.join(gm_parts) if gm_parts else ''

    # Notes = see also + any remaining
    used_keys = {'overview', 'environment'} | set(gm_keys)
    used_keys |= {k for k in sections if 'boss' in k.lower()}
    notes_parts = []
    # Include key locations table as notes (not as children — see below)
    for key, content in sections.items():
        if key not in used_keys and key != 'key locations' and content.strip():
            notes_parts.append(f"## {key.title()}\n\n{content}")
    notes = '\n\n'.join(notes_parts) if notes_parts else ''

    # Determine location type
    loc_type = 'Floor'
    if 'green room' in title.lower():
        loc_type = 'Starting Area'

    parent = {
        'name': title,
        'type': loc_type,
        'description': description,
        'gm_notes': gm_notes,
        'notes': notes,
        'is_player_visible': True,
    }

    # Parse child locations from "Key Locations" table or Zone headings in encounters
    children = _extract_child_locations(sections)

    # Look for image files near this markdown file
    md_dir = Path(filepath).parent
    images = []
    for img in md_dir.iterdir():
        if img.suffix.lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
            images.append(str(img))

    return {
        'parent': parent,
        'children': children,
        'images': images,
    }


def _extract_child_locations(sections):
    """Extract child location entries from a floor's Key Locations table or encounter zones."""
    children = []

    # Try Key Locations table first
    key_locs = sections.get('key locations', '')
    if key_locs:
        for line in key_locs.split('\n'):
            match = re.match(r'^\|\s*\*\*(.+?)\*\*\s*\|(.+)\|', line)
            if match:
                name = match.group(1).strip()
                rest = match.group(2).strip().rstrip('|')
                # Combine remaining cells as description
                cells = [c.strip() for c in rest.split('|')]
                desc = ' — '.join(c for c in cells if c)
                children.append({
                    'name': name,
                    'type': 'Room/Zone',
                    'description': desc,
                    'is_player_visible': True,
                })

    # If no key locations table, try parsing encounter zone headings
    if not children:
        encounters = sections.get('encounters', '')
        for match in re.finditer(r'###\s+Zone\s+\d+:\s+(.+)', encounters):
            zone_name = match.group(1).strip()
            children.append({
                'name': zone_name,
                'type': 'Room/Zone',
                'description': '',
                'is_player_visible': True,
            })

    return children


def parse_compendium(filepath, category=None, is_gm_only=False):
    """Parse a markdown file into a Compendium entry.

    Returns a dict with:
        title, category, content, is_gm_only
    """
    title, body = read_md_file(filepath)
    return {
        'title': title,
        'category': category or 'Uncategorized',
        'content': body,
        'is_gm_only': is_gm_only,
    }


def _format_overview_table(overview_dict):
    """Convert an overview dict back to a markdown table."""
    if not overview_dict:
        return ''
    lines = ['| Attribute | Value |', '|-----------|-------|']
    for key, value in overview_dict.items():
        lines.append(f'| **{key.title()}** | {value} |')
    return '\n'.join(lines)


def copy_image_to_uploads(image_path, upload_folder):
    """Copy an image file to the app's upload folder with a unique name.

    Returns the new filename (not the full path).
    """
    import uuid
    src = Path(image_path)
    ext = src.suffix.lower()
    new_name = f"{uuid.uuid4().hex}{ext}"
    dest = Path(upload_folder) / new_name
    shutil.copy2(str(src), str(dest))
    return new_name
