"""
The Descent — Campaign Import Script
=====================================

A Flask CLI command that reads The Descent Obsidian vault and creates a
fully linked campaign in The War Table, with:

  • 1 Campaign (The Descent, ICRPG system)
  • 5 Factions (major sponsors) + 4 minor sponsor NPCs
  • 11 Story Arcs (Floor 0–10), each with full Markdown content
  • Locations (parent floor + child zones) linked to their Story Arc
  • NPCs linked to factions and Story Arcs where appropriate
  • Campaign-wide NPCs (The Construct, Vex, etc.) without arc links
  • Compendium entries for all rules, character options, GM tools
  • Random Tables for sponsor boxes, encounters, chaos factor
  • Placeholder Sessions (2 per floor) linked to their Story Arc
  • Encounters extracted from floor documents, linked to arcs

USAGE (inside Docker container):
  docker exec -it war-table flask import-descent /app/descent-vault

  Or from Unraid SSH:
  docker exec -it war-table flask import-descent /app/descent-vault

VAULT MOUNT: Add a volume to docker-compose.yml:
  volumes:
    - /mnt/user/appdata/gm-wiki/The_Descent_2:/app/descent-vault:ro

  Then rebuild: docker compose up -d --build

The :ro flag makes it read-only inside the container (safe).
"""

import os
import re
import sys
import json
import click
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────

def read_md(filepath):
    """Read a markdown file → (title, body). Title from first H1 or filename."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    title = None
    body_start = 0
    for i, line in enumerate(lines):
        m = re.match(r'^#\s+(.+)', line)
        if m:
            title = m.group(1).strip()
            body_start = i + 1
            break
    if title is None:
        title = Path(filepath).stem
    body = '\n'.join(lines[body_start:]).strip()
    return title, body


def extract_overview_table(body):
    """Extract key-value pairs from a markdown overview table.
    Returns dict of lowercase-key → value, with ** stripped."""
    data = {}
    in_table = False
    for line in body.split('\n'):
        line = line.strip()
        if re.match(r'^\|[\s\-:]+\|[\s\-:]+\|$', line):
            in_table = True
            continue
        if re.match(r'^\|.*\|.*\|$', line) and in_table:
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 2:
                key = re.sub(r'\*\*', '', cells[0]).strip().lower()
                value = cells[1].strip()
                data[key] = value
        elif in_table and not line.startswith('|'):
            break
    return data


def extract_sections(body):
    """Split body into {heading_lower: content} by ## headings."""
    sections = {}
    current = None
    lines = []
    for line in body.split('\n'):
        m = re.match(r'^##\s+(.+)', line)
        if m:
            if current is not None:
                sections[current.lower()] = '\n'.join(lines).strip()
            current = m.group(1).strip()
            lines = []
        else:
            lines.append(line)
    if current is not None:
        sections[current.lower()] = '\n'.join(lines).strip()
    return sections


def strip_wiki_links(text):
    """Convert [[Target|Display]] and [[Target]] to plain text."""
    if not text:
        return ''
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    return text.strip()


def convert_wiki_links_to_shortcodes(text, entity_lookup):
    """Convert [[wiki links]] to #type[Name] shortcodes where possible.

    entity_lookup is a dict of { lowercase_name: (shortcode_type, display_name) }
    e.g. { 'flameo inc': ('npc', 'Flameo Inc'), 'floor 1 ...': ('site', '...') }
    """
    if not text:
        return text

    def replacer(match):
        target = match.group(1).strip()
        display = match.group(3).strip() if match.group(3) else target
        key = target.lower()
        if key in entity_lookup:
            sc_type, sc_name = entity_lookup[key]
            return f'#{sc_type}[{sc_name}]'
        return display

    # Match [[Target|Display]] and [[Target]]
    return re.sub(r'\[\[([^\]|]+)(\|([^\]]+))?\]\]', replacer, text)


def extract_child_zones(sections):
    """Extract child location names from floor documents.

    Tries multiple strategies:
    1. Bold-name table rows from Key Locations tables (Floor 1 format)
    2. ### sub-headings within sections (most floors)
    3. ### Zone headings in encounter sections

    Filters out stat-table rows (HEARTS, ARMOR, etc.) and overview tables.
    """
    children = []
    seen = set()

    # Skip these — they're stat blocks or overview table keys, not zone names
    skip_names = {
        'hearts', 'armor', 'effort', 'flags', 'boss', 'theme', 'milestones',
        'timer', 'timer type', 'timer mechanic', 'stat', 'hearts', 'hp',
        'room (map position)',
    }

    # Strategy 1: Bold-name table rows from Key Locations sections
    for key in ('key locations', 'key locations & encounters'):
        text = sections.get(key, '')
        if not text:
            continue
        for line in text.split('\n'):
            # Match: | **Name** (optional parens) | rest... |
            m = re.match(r'^\|\s*\*\*(.+?)\*\*\s*(?:\([^)]*\))?\s*\|(.+)', line)
            if m:
                raw_name = m.group(1).strip()
                if raw_name.lower() in skip_names:
                    continue
                rest = m.group(2).strip().rstrip('|')
                cells = [c.strip() for c in rest.split('|')]
                desc = ' — '.join(c for c in cells if c and '---' not in c)
                if raw_name not in seen:
                    children.append({'name': raw_name, 'description': desc})
                    seen.add(raw_name)

    # Strategy 2: ### sub-headings in key location/encounter sections
    for key in ('key locations & encounters', 'key locations', 'encounters',
                'zones', 'key areas', 'areas'):
        text = sections.get(key, '')
        if not text:
            continue
        for m in re.finditer(r'^###\s+(.+)', text, re.MULTILINE):
            name = m.group(1).strip()
            # Strip leading "Zone N:" prefix
            name = re.sub(r'^Zone\s+\d+:\s*', '', name)
            # Strip trailing quotes like: "Fresh Meat Orientation"
            clean = re.sub(r':\s*["\u201c].+["\u201d]$', '', name).strip()
            if clean.lower() not in skip_names and clean not in seen:
                children.append({'name': clean, 'description': ''})
                seen.add(clean)

    # Strategy 3: ### headings in other sections (environment, etc.)
    if not children:
        for key, text in sections.items():
            if key in ('overview',):
                continue
            for m in re.finditer(r'^###\s+(.+)', text, re.MULTILINE):
                name = m.group(1).strip()
                name = re.sub(r'^Zone\s+\d+:\s*', '', name)
                if name.lower() not in skip_names and name not in seen:
                    children.append({'name': name, 'description': ''})
                    seen.add(name)

    return children


# ── Main Import Logic ────────────────────────────────────────────────────

def register_import_command(app):
    """Register the 'flask import-descent' CLI command."""

    @app.cli.command('import-descent')
    @click.argument('vault_path')
    @click.option('--username', default=None,
                  help='Owner username (default: first admin user)')
    @click.option('--dry-run', is_flag=True,
                  help='Show what would be created without writing to DB')
    def import_descent(vault_path, username, dry_run):
        """Import The Descent campaign from an Obsidian vault.

        VAULT_PATH is the path to the vault root INSIDE the container.
        Example: /app/descent-vault
        """
        from app import db
        from app.models import (
            User, Campaign, Faction, NPC, Location, CompendiumEntry,
            Quest, Item, Session, RandomTable, TableRow,
            AdventureSite, Tag, Encounter, BestiaryEntry,
            get_or_create_tags, ActivityLog,
        )

        # ── Validate vault path ──────────────────────────────────
        vault = Path(vault_path)
        if not vault.is_dir():
            click.echo(f'ERROR: Vault path not found: {vault_path}')
            click.echo('')
            click.echo('If running in Docker, make sure you mounted the vault:')
            click.echo('  docker-compose.yml volumes:')
            click.echo('    - /mnt/user/appdata/gm-wiki/The_Descent_2:/app/descent-vault:ro')
            click.echo('')
            click.echo('Then run:')
            click.echo('  docker exec -it war-table flask import-descent /app/descent-vault')
            sys.exit(1)

        # Check for expected folder structure
        expected_folders = ['00_Campaign_Hub', '01_Core_Rules', '02_World',
                            '03_Character_Options', '04_NPCs', '05_GM_Tools', '06_Floors']
        found = [f for f in expected_folders if (vault / f).is_dir()]
        if len(found) < 4:
            click.echo(f'ERROR: This doesn\'t look like The Descent vault.')
            click.echo(f'  Expected folders like 01_Core_Rules, 02_World, etc.')
            click.echo(f'  Found: {found}')
            sys.exit(1)

        click.echo('═══════════════════════════════════════════════════')
        click.echo('  THE DESCENT — Campaign Import')
        click.echo('═══════════════════════════════════════════════════')
        click.echo(f'  Vault:  {vault_path}')
        click.echo(f'  Mode:   {"DRY RUN" if dry_run else "LIVE IMPORT"}')
        click.echo('')

        # ── Resolve owner ────────────────────────────────────────
        if username:
            owner = User.query.filter_by(username=username).first()
            if not owner:
                click.echo(f'ERROR: User "{username}" not found.')
                sys.exit(1)
        else:
            owner = User.query.filter_by(is_admin=True).first()
            if not owner:
                owner = User.query.first()
            if not owner:
                click.echo('ERROR: No users exist. Create an admin account first.')
                sys.exit(1)

        click.echo(f'  Owner:  {owner.username}')
        click.echo('')

        # ── Check for existing campaign ──────────────────────────
        existing = Campaign.query.filter_by(name='The Descent').first()
        if existing:
            click.echo(f'WARNING: Campaign "The Descent" already exists (id={existing.id}).')
            if not dry_run:
                if not click.confirm('Delete it and re-import?'):
                    click.echo('Aborted.')
                    sys.exit(0)
                # Cascading delete of all campaign data
                _delete_campaign_data(db, existing.id)
                db.session.delete(existing)
                db.session.commit()
                click.echo('  Deleted existing campaign.\n')

        if dry_run:
            click.echo('[DRY RUN — nothing will be written to the database]\n')

        # ══════════════════════════════════════════════════════════
        # STEP 1: Create Campaign
        # ══════════════════════════════════════════════════════════
        click.echo('STEP 1: Creating campaign...')

        # Read the overview for campaign description
        overview_path = vault / '00_Campaign_Hub' / 'The Descent - Overview.md'
        if overview_path.exists():
            _, overview_body = read_md(overview_path)
            overview_sections = extract_sections(overview_body)
            premise = overview_sections.get('the premise', '')
        else:
            premise = ''

        campaign = Campaign(
            user_id=owner.id,
            name='The Descent',
            system='ICRPG',
            status='active',
            description='Ten floors. Ten bosses. One way out. '
                        'A survival horror ICRPG campaign inspired by Dungeon Crawler Carl.',
            ai_world_context=(
                'This is "The Descent," an ICRPG campaign blending survival horror with '
                'dark comedy. Kidnapped contestants fight through a 10-floor corporate-sponsored '
                'death dungeon broadcast to extraplanar audiences. Players start as baseline humans '
                'and earn Bioforms (race templates) and Types (class protocols) by surviving. '
                'Six major sponsor corporations send rewards and provide commentary. '
                'Tone: 70% tension/stakes, 30% dark humor. The comedy comes FROM the horror. '
                'System: ICRPG with modern/sci-fi reskins. Stats +0 to +6, HEARTS for HP, '
                'd4/d6/d8/d10/d12 EFFORT types. Timer mechanics on every floor.'
            ),
        )

        if not dry_run:
            db.session.add(campaign)
            db.session.flush()
            cid = campaign.id
        else:
            cid = 0  # placeholder for dry run

        click.echo(f'  ✓ Campaign "The Descent" (id={cid})')

        # ══════════════════════════════════════════════════════════
        # STEP 2: Create Factions (Sponsors)
        # ══════════════════════════════════════════════════════════
        click.echo('\nSTEP 2: Creating factions (sponsors)...')

        sponsor_defs = [
            ('Flameo Inc', 'Fire, destruction, spectacle', 'neutral'),
            ('Apex Predation Co', 'Hunting, efficiency, tactics', 'neutral'),
            ('The Inevitable Syndicate', 'Death, undeath, survival', 'neutral'),
            ('Glitterhoard Consortium', 'Wealth, collection, greed', 'neutral'),
            ('Mercy and Malice Ltd', 'Duality, morality, consequences', 'neutral'),
        ]

        factions = {}  # name → Faction object
        for name, desc, disposition in sponsor_defs:
            # Read the sponsor file for details
            sponsor_file = vault / '02_World' / 'Sponsors' / f'{name}.md'
            gm_notes = ''
            if sponsor_file.exists():
                _, body = read_md(sponsor_file)
                gm_notes = body  # full markdown as GM reference

            faction = Faction(
                campaign_id=cid,
                name=name,
                description=desc,
                disposition=disposition,
                gm_notes=gm_notes if len(gm_notes) < 10000 else gm_notes[:10000],
            )
            if not dry_run:
                db.session.add(faction)
                db.session.flush()
            factions[name.lower()] = faction
            click.echo(f'  ✓ Faction: {name}')

        # ══════════════════════════════════════════════════════════
        # STEP 3: Create Story Arcs (Floors 0–10)
        # ══════════════════════════════════════════════════════════
        click.echo('\nSTEP 3: Creating story arcs (floors)...')

        floor_files = _find_floor_files(vault)
        arcs = {}       # floor_number → AdventureSite
        arc_meta = {}   # floor_number → overview dict from the file

        for floor_num, filepath in sorted(floor_files.items()):
            title, body = read_md(filepath)
            overview = extract_overview_table(body)

            # Parse milestones from overview
            milestones_raw = overview.get('milestones', '')
            milestone_list = []
            if milestones_raw:
                milestone_list.append({'label': f'Enter {title}', 'done': False})
                milestone_list.append({'label': f'Mid-floor milestone', 'done': False})
                milestone_list.append({'label': f'Defeat boss / complete floor', 'done': False})

            # Determine estimated sessions
            est_sessions = 1 if floor_num == 0 else 2

            # Build subtitle from theme
            theme = overview.get('theme', '')
            subtitle = strip_wiki_links(theme)[:300] if theme else None

            arc = AdventureSite(
                campaign_id=cid,
                name=title,
                subtitle=subtitle,
                status='Planned',
                estimated_sessions=est_sessions,
                content=body,  # full markdown
                sort_order=floor_num,
                is_player_visible=False,
            )
            if milestone_list:
                arc.set_milestones(milestone_list)

            if not dry_run:
                db.session.add(arc)
                db.session.flush()

            arcs[floor_num] = arc
            arc_meta[floor_num] = overview
            click.echo(f'  ✓ Story Arc: {title} (sort_order={floor_num})')

        # ══════════════════════════════════════════════════════════
        # STEP 4: Create Locations (Floor → parent, Zones → children)
        # ══════════════════════════════════════════════════════════
        click.echo('\nSTEP 4: Creating locations...')

        locations = {}  # floor_number → parent Location

        for floor_num, filepath in sorted(floor_files.items()):
            title, body = read_md(filepath)
            overview = extract_overview_table(body)
            sections = extract_sections(body)

            # Parent location = the floor
            loc_type = 'Starting Area' if floor_num == 0 else 'Floor'
            desc_parts = []
            if overview:
                desc_parts.append(_format_overview_table(overview))
            env = sections.get('environment', '')
            if env:
                desc_parts.append(strip_wiki_links(env))

            # GM notes = boss info + timer + encounters summary
            gm_parts = []
            for key in sorted(sections.keys()):
                if any(kw in key for kw in ['boss', 'timer', 'encounter',
                                             'revelation', 'sponsor activity',
                                             'gm note', 'safe room', 'loot']):
                    gm_parts.append(f'## {key.title()}\n\n{strip_wiki_links(sections[key])}')

            parent = Location(
                campaign_id=cid,
                name=title,
                type=loc_type,
                description='\n\n'.join(desc_parts),
                gm_notes='\n\n---\n\n'.join(gm_parts) if gm_parts else '',
                is_player_visible=True,
                story_arc_id=arcs[floor_num].id if not dry_run else None,
            )
            if not dry_run:
                db.session.add(parent)
                db.session.flush()

            locations[floor_num] = parent
            click.echo(f'  ✓ Location: {title}')

            # Child zones
            children = extract_child_zones(sections)
            for child_data in children:
                child = Location(
                    campaign_id=cid,
                    name=child_data['name'],
                    type='Room/Zone',
                    description=strip_wiki_links(child_data.get('description', '')),
                    is_player_visible=True,
                    parent_location_id=parent.id if not dry_run else None,
                    story_arc_id=arcs[floor_num].id if not dry_run else None,
                )
                if not dry_run:
                    db.session.add(child)
                click.echo(f'    ↳ Zone: {child_data["name"]}')

        # ══════════════════════════════════════════════════════════
        # STEP 5: Create NPCs
        # ══════════════════════════════════════════════════════════
        click.echo('\nSTEP 5: Creating NPCs...')

        npc_dir = vault / '04_NPCs'
        # Files that are reference docs, not individual NPCs
        skip_npcs = {'npc overview', 'crawler groups', 'random crawler generator'}

        npcs_created = {}  # lowercase name → NPC

        if npc_dir.is_dir():
            for md_file in sorted(npc_dir.glob('*.md')):
                fname = md_file.stem.lower()
                if fname in skip_npcs:
                    continue

                title, body = read_md(md_file)
                overview = extract_overview_table(body)
                sections = extract_sections(body)

                role = overview.get('role', '')
                sponsor_raw = overview.get('sponsor', '')
                sponsor_name = strip_wiki_links(sponsor_raw).lower() if sponsor_raw else ''

                # Match faction
                faction_id = None
                for fkey, fobj in factions.items():
                    if fkey in sponsor_name or sponsor_name in fkey:
                        faction_id = fobj.id if not dry_run else None
                        break

                # Build fields
                appearance = sections.get('appearance', '')
                personality = sections.get('personality', '')
                secrets_parts = []
                notes_parts = []
                for key, content in sections.items():
                    if key in ('appearance', 'personality', 'overview'):
                        continue
                    if any(kw in key for kw in ['secret', 'gm note', 'weakness',
                                                 'true purpose', 'hidden']):
                        secrets_parts.append(f'## {key.title()}\n\n{content}')
                    else:
                        notes_parts.append(f'## {key.title()}\n\n{content}')

                npc = NPC(
                    campaign_id=cid,
                    name=title,
                    role=strip_wiki_links(role),
                    status='alive',
                    faction_id=faction_id,
                    physical_description=strip_wiki_links(appearance),
                    personality=strip_wiki_links(personality),
                    secrets='\n\n'.join(secrets_parts) if secrets_parts else '',
                    notes='\n\n'.join(notes_parts) if notes_parts else '',
                    is_player_visible=True,
                )
                if not dry_run:
                    db.session.add(npc)
                    db.session.flush()
                npcs_created[title.lower()] = npc
                click.echo(f'  ✓ NPC: {title} (faction: {sponsor_name or "none"})')

        # Create sponsor NPCs from the sponsor files (as organizational NPCs)
        sponsor_dir = vault / '02_World' / 'Sponsors'
        if sponsor_dir.is_dir():
            for md_file in sorted(sponsor_dir.glob('*.md')):
                fname = md_file.stem.lower()
                if 'overview' in fname or 'commentary' in fname or 'minor' in fname:
                    continue
                title, body = read_md(md_file)
                overview = extract_overview_table(body)
                sections = extract_sections(body)

                # Match to faction
                faction_id = None
                for fkey, fobj in factions.items():
                    if fkey == title.lower() or title.lower() in fkey:
                        faction_id = fobj.id if not dry_run else None
                        break

                theme = overview.get('theme', '')
                values = overview.get('values', '')
                colors = overview.get('colors', '')
                desc = f'**Theme:** {theme}\n**Values:** {values}\n**Colors:** {colors}'

                # Loot tables and commentary go into secrets
                secret_parts = []
                for key in sorted(sections.keys()):
                    if any(kw in key for kw in ['loot', 'signature', 'commentary', 'favored']):
                        secret_parts.append(f'## {key.title()}\n\n{sections[key]}')

                npc = NPC(
                    campaign_id=cid,
                    name=title,
                    role='Sponsor Corporation',
                    status='alive',
                    faction_id=faction_id,
                    physical_description=strip_wiki_links(desc),
                    personality=overview.get('personality', ''),
                    secrets=strip_wiki_links('\n\n---\n\n'.join(secret_parts)),
                    notes='',
                    is_player_visible=True,
                )
                if not dry_run:
                    db.session.add(npc)
                    db.session.flush()
                npcs_created[title.lower()] = npc
                click.echo(f'  ✓ Sponsor NPC: {title}')

        # ══════════════════════════════════════════════════════════
        # STEP 6: Create Compendium Entries
        # ══════════════════════════════════════════════════════════
        click.echo('\nSTEP 6: Creating compendium entries...')

        compendium_map = {
            # (folder, subfolder) → (category, is_gm_only)
            '01_Core_Rules': ('Core Rules', False),
            '03_Character_Options': ('Character Options', False),
            '05_GM_Tools': ('GM Tools', True),
        }

        # Subfolder overrides
        subfolder_categories = {
            'Bioforms': ('Bioforms', False),
            'Types': ('Types', False),
            'Equipment': ('Equipment', False),
            'Infrastructure': ('Infrastructure', False),
            'Sponsors': None,  # Skip — already imported as NPCs/factions
        }

        comp_count = 0
        for folder_name, (default_cat, default_gm) in compendium_map.items():
            folder = vault / folder_name
            if not folder.is_dir():
                continue
            for md_file in sorted(folder.rglob('*.md')):
                rel = md_file.relative_to(folder)
                # Check subfolder override
                if len(rel.parts) > 1:
                    subfolder = rel.parts[0]
                    if subfolder in subfolder_categories:
                        override = subfolder_categories[subfolder]
                        if override is None:
                            continue  # skip
                        category, is_gm = override
                    else:
                        category, is_gm = default_cat, default_gm
                else:
                    category, is_gm = default_cat, default_gm

                title, body = read_md(md_file)
                entry = CompendiumEntry(
                    campaign_id=cid,
                    title=title,
                    category=category,
                    content=strip_wiki_links(body),
                    is_gm_only=is_gm,
                )
                if not dry_run:
                    db.session.add(entry)
                comp_count += 1

            click.echo(f'  ✓ {folder_name} → {default_cat}')

        # Infrastructure docs
        infra_dir = vault / '02_World' / 'Infrastructure'
        if infra_dir.is_dir():
            for md_file in sorted(infra_dir.glob('*.md')):
                title, body = read_md(md_file)
                entry = CompendiumEntry(
                    campaign_id=cid,
                    title=title,
                    category='Infrastructure',
                    content=strip_wiki_links(body),
                    is_gm_only=False,
                )
                if not dry_run:
                    db.session.add(entry)
                comp_count += 1

        # World-level docs (Core Premise, Mystery Breadcrumbs)
        world_dir = vault / '02_World'
        if world_dir.is_dir():
            for md_file in sorted(world_dir.glob('*.md')):
                title, body = read_md(md_file)
                entry = CompendiumEntry(
                    campaign_id=cid,
                    title=title,
                    category='World',
                    content=strip_wiki_links(body),
                    is_gm_only=True,
                )
                if not dry_run:
                    db.session.add(entry)
                comp_count += 1

        # Reference docs from NPC folder
        for fname in ('NPC Overview', 'Crawler Groups', 'Random Crawler Generator'):
            fp = npc_dir / f'{fname}.md'
            if fp.exists():
                title, body = read_md(fp)
                entry = CompendiumEntry(
                    campaign_id=cid,
                    title=title,
                    category='NPCs',
                    content=strip_wiki_links(body),
                    is_gm_only=True,
                )
                if not dry_run:
                    db.session.add(entry)
                comp_count += 1

        # Sponsor reference docs
        for fname in ('Sponsors Overview', 'Sponsor Commentary Database', 'Minor Sponsors'):
            fp = sponsor_dir / f'{fname}.md'
            if fp.exists():
                title, body = read_md(fp)
                entry = CompendiumEntry(
                    campaign_id=cid,
                    title=title,
                    category='Sponsors',
                    content=strip_wiki_links(body),
                    is_gm_only=True,
                )
                if not dry_run:
                    db.session.add(entry)
                comp_count += 1

        # Floor Structure and Timers reference doc
        fst = vault / '06_Floors' / 'Floor Structure and Timers.md'
        if fst.exists():
            title, body = read_md(fst)
            entry = CompendiumEntry(
                campaign_id=cid,
                title=title,
                category='GM Tools',
                content=strip_wiki_links(body),
                is_gm_only=True,
            )
            if not dry_run:
                db.session.add(entry)
            comp_count += 1

        click.echo(f'  Total: {comp_count} compendium entries')

        # ══════════════════════════════════════════════════════════
        # STEP 7: Create Random Tables
        # ══════════════════════════════════════════════════════════
        click.echo('\nSTEP 7: Creating random tables...')

        tables_created = _create_random_tables(vault, cid, dry_run, db, RandomTable, TableRow)
        click.echo(f'  Total: {tables_created} tables')

        # ══════════════════════════════════════════════════════════
        # STEP 8: Create Sessions (2 per floor, linked to arcs)
        # ══════════════════════════════════════════════════════════
        click.echo('\nSTEP 8: Creating placeholder sessions...')

        session_num = 0
        for floor_num in sorted(arcs.keys()):
            arc = arcs[floor_num]
            num_sessions = 1 if floor_num == 0 else 2

            for s in range(num_sessions):
                session_num += 1
                part = '' if num_sessions == 1 else f' (Part {s + 1})'
                sess = Session(
                    campaign_id=cid,
                    number=session_num,
                    title=f'{arc.name}{part}',
                    prep_notes=f'Story Arc: {arc.name}\n\nSee Story Arc for full floor details.',
                    gm_notes='',
                    is_player_visible=False,
                )
                if not dry_run:
                    db.session.add(sess)
                    db.session.flush()
                    # Link session to story arc via many-to-many
                    arc.sessions.append(sess)

        click.echo(f'  ✓ {session_num} sessions created')

        # ══════════════════════════════════════════════════════════
        # STEP 9: Commit
        # ══════════════════════════════════════════════════════════
        if not dry_run:
            try:
                db.session.commit()
                click.echo('\n═══════════════════════════════════════════════════')
                click.echo('  IMPORT COMPLETE')
                click.echo('═══════════════════════════════════════════════════')
                click.echo(f'  Campaign ID:    {cid}')
                click.echo(f'  Factions:       {len(factions)}')
                click.echo(f'  Story Arcs:     {len(arcs)}')
                click.echo(f'  Locations:      {Location.query.filter_by(campaign_id=cid).count()}')
                click.echo(f'  NPCs:           {NPC.query.filter_by(campaign_id=cid).count()}')
                click.echo(f'  Compendium:     {comp_count}')
                click.echo(f'  Random Tables:  {tables_created}')
                click.echo(f'  Sessions:       {session_num}')
                click.echo('')
                click.echo('  Next steps:')
                click.echo('  1. Open The War Table in your browser')
                click.echo('  2. Switch to "The Descent" campaign')
                click.echo('  3. Review Story Arcs (Floors) — they have full content')
                click.echo('  4. Check Factions — sponsor details are in GM Notes')
                click.echo('  5. Run "flask seed-icrpg-catalog" if you haven\'t already')
                click.echo('     (loads Bioforms, Types, Loot into the ICRPG catalog)')
                click.echo('')
            except Exception as e:
                db.session.rollback()
                click.echo(f'\nERROR during commit: {e}')
                sys.exit(1)
        else:
            click.echo('\n[DRY RUN complete — no data written]')


# ── Helper Functions ─────────────────────────────────────────────────────

def _find_floor_files(vault):
    """Find all floor markdown files → {floor_number: filepath}."""
    floors_dir = vault / '06_Floors'
    result = {}

    if not floors_dir.is_dir():
        return result

    # Direct files: "Floor 0 - The Green Room.md"
    for md_file in floors_dir.glob('*.md'):
        m = re.match(r'Floor\s+(\d+)', md_file.stem)
        if m:
            result[int(m.group(1))] = md_file

    # Subfolder files: "01_Floor_TheProvingGrounds/Floor 1 - The Proving Grounds.md"
    for subdir in floors_dir.iterdir():
        if subdir.is_dir():
            for md_file in subdir.glob('*.md'):
                m = re.match(r'Floor\s+(\d+)', md_file.stem)
                if m:
                    result[int(m.group(1))] = md_file

    return result


def _format_overview_table(overview_dict):
    """Convert overview dict → markdown table."""
    if not overview_dict:
        return ''
    lines = ['| Attribute | Value |', '|-----------|-------|']
    for key, value in overview_dict.items():
        lines.append(f'| **{key.title()}** | {value} |')
    return '\n'.join(lines)


def _create_random_tables(vault, campaign_id, dry_run, db, RandomTable, TableRow):
    """Create random tables from vault content. Returns count of tables created."""
    count = 0

    # ── Sponsor Boxes ────────────────────────────────────────
    sponsor_boxes_file = vault / '02_World' / 'Infrastructure' / 'Sponsor Boxes.md'
    if sponsor_boxes_file.exists():
        _, body = read_md(sponsor_boxes_file)
        sections = extract_sections(body)

        box_tiers = {
            'bronze box contents (d6)': ('Bronze Sponsor Box', 6),
            'silver box contents (d8)': ('Silver Sponsor Box', 8),
            'gold box contents (d6)': ('Gold Sponsor Box', 6),
            'platinum box contents (d4)': ('Platinum Sponsor Box', 4),
        }

        for section_key, (table_name, _) in box_tiers.items():
            content = sections.get(section_key, '')
            if not content:
                continue
            table = RandomTable(
                campaign_id=campaign_id,
                name=table_name,
                category='Sponsor Boxes',
                description=f'Roll when awarding a {table_name.split(" ")[0].lower()} sponsor box.',
            )
            if not dry_run:
                db.session.add(table)
                db.session.flush()

            order = 0
            for line in content.split('\n'):
                m = re.match(r'^\d+\.\s+(.+)', line.strip())
                if m:
                    order += 1
                    row = TableRow(
                        table_id=table.id if not dry_run else 0,
                        content=strip_wiki_links(m.group(1).strip()),
                        weight=1,
                        display_order=order,
                    )
                    if not dry_run:
                        db.session.add(row)

            count += 1
            click.echo(f'  ✓ Table: {table_name} ({order} entries)')

    # ── Generic Random Encounters ────────────────────────────
    encounters_file = vault / '05_GM_Tools' / 'Random Encounters.md'
    if encounters_file.exists():
        _, body = read_md(encounters_file)
        sections = extract_sections(body)

        enc_table_text = sections.get('generic encounter table (d20)', '')
        if enc_table_text:
            table = RandomTable(
                campaign_id=campaign_id,
                name='Generic Random Encounters',
                category='Encounters',
                description='Works on any floor — adjust difficulty to match.',
            )
            if not dry_run:
                db.session.add(table)
                db.session.flush()

            order = 0
            for line in enc_table_text.split('\n'):
                m = re.match(r'^\|\s*(\d+)\s*\|(.+)\|', line.strip())
                if m:
                    order += 1
                    row = TableRow(
                        table_id=table.id if not dry_run else 0,
                        content=strip_wiki_links(m.group(2).strip()),
                        weight=1,
                        display_order=order,
                    )
                    if not dry_run:
                        db.session.add(row)

            count += 1
            click.echo(f'  ✓ Table: Generic Random Encounters ({order} entries)')

        # Enemy type sub-tables
        for key, content in sections.items():
            if 'enemy' not in key.lower() or not content.strip():
                continue
            table = RandomTable(
                campaign_id=campaign_id,
                name=f'Enemy Types: {key.title()}',
                category='Encounters',
                description=f'Roll for enemy type: {key}',
            )
            if not dry_run:
                db.session.add(table)
                db.session.flush()

            order = 0
            for line in content.split('\n'):
                m = re.match(r'^\|\s*(\d+)\s*\|(.+)\|', line.strip())
                if m:
                    order += 1
                    row_content = strip_wiki_links(m.group(2).strip())
                    # Combine remaining cells
                    cells = [c.strip() for c in row_content.split('|') if c.strip()]
                    row = TableRow(
                        table_id=table.id if not dry_run else 0,
                        content=' — '.join(cells),
                        weight=1,
                        display_order=order,
                    )
                    if not dry_run:
                        db.session.add(row)

            if order > 0:
                count += 1
                click.echo(f'  ✓ Table: Enemy Types - {key.title()} ({order} entries)')

    return count


def _delete_campaign_data(db, campaign_id):
    """Delete all data belonging to a campaign (for re-import)."""
    from app.models import (
        NPC, Location, Quest, Item, Session, CompendiumEntry,
        Faction, AdventureSite, RandomTable, Encounter, Tag,
        SessionAttendance, EntityMention, MonsterInstance,
    )

    # Order matters — delete referencing rows first
    EntityMention.query.filter_by(campaign_id=campaign_id).delete()
    SessionAttendance.query.filter(
        SessionAttendance.session_id.in_(
            db.session.query(Session.id).filter_by(campaign_id=campaign_id)
        )
    ).delete(synchronize_session=False)
    Encounter.query.filter_by(campaign_id=campaign_id).delete()
    MonsterInstance.query.filter_by(campaign_id=campaign_id).delete()

    # Clear many-to-many links on adventure_sites before deleting sessions
    for site in AdventureSite.query.filter_by(campaign_id=campaign_id).all():
        site.sessions = []
        site.tags = []
    db.session.flush()

    Session.query.filter_by(campaign_id=campaign_id).delete()
    Quest.query.filter_by(campaign_id=campaign_id).delete()
    Item.query.filter_by(campaign_id=campaign_id).delete()

    # Clear location self-references before delete
    for loc in Location.query.filter_by(campaign_id=campaign_id).all():
        loc.parent_location_id = None
        loc.connected_locations = []
        loc.tags = []
    db.session.flush()
    Location.query.filter_by(campaign_id=campaign_id).delete()

    for npc in NPC.query.filter_by(campaign_id=campaign_id).all():
        npc.tags = []
        npc.connected_locations = []
    db.session.flush()
    NPC.query.filter_by(campaign_id=campaign_id).delete()

    CompendiumEntry.query.filter_by(campaign_id=campaign_id).delete()
    RandomTable.query.filter_by(campaign_id=campaign_id).delete()
    AdventureSite.query.filter_by(campaign_id=campaign_id).delete()
    Faction.query.filter_by(campaign_id=campaign_id).delete()
    Tag.query.filter_by(campaign_id=campaign_id).delete()

    db.session.flush()
