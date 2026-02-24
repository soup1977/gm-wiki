"""Obsidian Vault Import — routes for scanning, previewing, and importing
an Obsidian vault into GM Wiki as NPCs, Locations, and Compendium entries.

Three-step flow:
  1. /obsidian-import          — Enter vault folder path
  2. /obsidian-import/preview  — Review auto-mapped files, adjust mappings
  3. /obsidian-import/execute  — Run the import, show results
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session as flask_session, current_app
)
from app import db
from app.models import Campaign, NPC, Location, CompendiumEntry, Tag
from app.obsidian_parser import (
    scan_vault, scan_images, parse_npc, parse_npc_faction,
    parse_location, parse_compendium, copy_image_to_uploads,
)
import os
import json

obsidian_import_bp = Blueprint('obsidian_import', __name__)


@obsidian_import_bp.route('/obsidian-import', methods=['GET', 'POST'])
def select_vault():
    """Step 1: User enters the path to their Obsidian vault folder."""
    campaigns = Campaign.query.order_by(Campaign.name).all()

    if request.method == 'POST':
        vault_path = request.form.get('vault_path', '').strip()
        campaign_id = request.form.get('campaign_id')
        new_campaign_name = request.form.get('new_campaign_name', '').strip()

        if not vault_path or not os.path.isdir(vault_path):
            flash('Please enter a valid folder path.', 'danger')
            return render_template('obsidian_import/select.html', campaigns=campaigns)

        # Store in session for next step
        flask_session['obsidian_vault_path'] = vault_path
        flask_session['obsidian_campaign_id'] = campaign_id
        flask_session['obsidian_new_campaign_name'] = new_campaign_name

        return redirect(url_for('obsidian_import.preview'))

    return render_template('obsidian_import/select.html', campaigns=campaigns)


@obsidian_import_bp.route('/obsidian-import/preview', methods=['GET', 'POST'])
def preview():
    """Step 2: Show scanned files with auto-mappings. User can adjust."""
    vault_path = flask_session.get('obsidian_vault_path')
    if not vault_path:
        flash('Please select a vault folder first.', 'warning')
        return redirect(url_for('obsidian_import.select_vault'))

    try:
        entries = scan_vault(vault_path)
        images = scan_images(vault_path)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('obsidian_import.select_vault'))

    if request.method == 'POST':
        # Collect user overrides from the form
        mappings = []
        for i, entry in enumerate(entries):
            entity_type = request.form.get(f'type_{i}', entry['entity_type'])
            category = request.form.get(f'category_{i}', entry.get('category', ''))
            is_gm_only = request.form.get(f'gm_only_{i}') == 'on'
            mappings.append({
                'path': entry['path'],
                'filename': entry['filename'],
                'entity_type': entity_type,
                'category': category,
                'is_gm_only': is_gm_only,
            })

        # Store mappings for execute step
        flask_session['obsidian_mappings'] = json.dumps(mappings)
        flask_session['obsidian_images'] = json.dumps(images)
        return redirect(url_for('obsidian_import.execute'))

    # Group entries by folder for display
    grouped = {}
    for entry in entries:
        folder = entry['folder'] or 'Root'
        if folder not in grouped:
            grouped[folder] = []
        grouped[folder].append(entry)

    return render_template('obsidian_import/preview.html',
                           entries=entries,
                           grouped=grouped,
                           images=images,
                           vault_path=vault_path)


@obsidian_import_bp.route('/obsidian-import/execute', methods=['GET', 'POST'])
def execute():
    """Step 3: Run the import and show results."""
    vault_path = flask_session.get('obsidian_vault_path')
    mappings_json = flask_session.get('obsidian_mappings')
    images_json = flask_session.get('obsidian_images', '[]')

    if not vault_path or not mappings_json:
        flash('Import session expired. Please start over.', 'warning')
        return redirect(url_for('obsidian_import.select_vault'))

    mappings = json.loads(mappings_json)
    images = json.loads(images_json)

    # Determine campaign
    campaign_id = flask_session.get('obsidian_campaign_id')
    new_name = flask_session.get('obsidian_new_campaign_name', '')

    if new_name:
        campaign = Campaign(name=new_name, system='ICRPG', status='active')
        db.session.add(campaign)
        db.session.flush()  # get the ID
    elif campaign_id:
        campaign = Campaign.query.get(int(campaign_id))
        if not campaign:
            flash('Selected campaign not found.', 'danger')
            return redirect(url_for('obsidian_import.select_vault'))
    else:
        flash('Please select or create a campaign.', 'danger')
        return redirect(url_for('obsidian_import.select_vault'))

    # Set active campaign
    flask_session['active_campaign_id'] = campaign.id

    # Run the import
    results = {
        'npcs': [],
        'locations': [],
        'compendium': [],
        'skipped': [],
        'errors': [],
    }

    # Build a map of floor names to Location objects for child linking
    floor_locations = {}

    # First pass: import locations (floors) so we can link NPCs to them later
    for mapping in mappings:
        if mapping['entity_type'] != 'location':
            continue
        try:
            data = parse_location(mapping['path'])
            parent_data = data['parent']

            # Create parent location
            loc = Location(
                campaign_id=campaign.id,
                name=parent_data['name'],
                type=parent_data['type'],
                description=parent_data['description'],
                gm_notes=parent_data['gm_notes'],
                notes=parent_data.get('notes', ''),
                is_player_visible=parent_data['is_player_visible'],
            )

            # Attach first image found as map
            if data['images']:
                upload_folder = current_app.config['UPLOAD_FOLDER']
                new_filename = copy_image_to_uploads(data['images'][0], upload_folder)
                loc.map_filename = new_filename

            db.session.add(loc)
            db.session.flush()
            floor_locations[parent_data['name']] = loc
            results['locations'].append(parent_data['name'])

            # Create child locations
            for child_data in data['children']:
                child = Location(
                    campaign_id=campaign.id,
                    name=child_data['name'],
                    type=child_data['type'],
                    description=child_data['description'],
                    is_player_visible=child_data['is_player_visible'],
                    parent_location_id=loc.id,
                )
                db.session.add(child)
                results['locations'].append(f"  ↳ {child_data['name']}")

        except Exception as e:
            results['errors'].append(f"Location error ({mapping['filename']}): {str(e)}")

    # Second pass: import NPCs and factions
    for mapping in mappings:
        if mapping['entity_type'] not in ('npc', 'npc_faction'):
            continue
        try:
            if mapping['entity_type'] == 'npc_faction':
                data = parse_npc_faction(mapping['path'])
            else:
                data = parse_npc(mapping['path'])

            npc = NPC(
                campaign_id=campaign.id,
                name=data['name'],
                role=data['role'],
                status=data['status'],
                faction=data['faction'],
                physical_description=data['physical_description'],
                personality=data['personality'],
                secrets=data['secrets'],
                notes=data['notes'],
                is_player_visible=data['is_player_visible'],
            )
            db.session.add(npc)
            results['npcs'].append(data['name'])

        except Exception as e:
            results['errors'].append(f"NPC error ({mapping['filename']}): {str(e)}")

    # Third pass: import Compendium entries
    for mapping in mappings:
        if mapping['entity_type'] != 'compendium':
            continue
        try:
            data = parse_compendium(
                mapping['path'],
                category=mapping.get('category', 'Uncategorized'),
                is_gm_only=mapping.get('is_gm_only', False),
            )
            entry = CompendiumEntry(
                campaign_id=campaign.id,
                title=data['title'],
                category=data['category'],
                content=data['content'],
                is_gm_only=data['is_gm_only'],
            )
            db.session.add(entry)
            results['compendium'].append(f"{data['title']} [{data['category']}]")

        except Exception as e:
            results['errors'].append(f"Compendium error ({mapping['filename']}): {str(e)}")

    # Track skipped files
    for mapping in mappings:
        if mapping['entity_type'] == 'skip':
            results['skipped'].append(mapping['filename'])

    # Commit everything
    try:
        db.session.commit()
        flash(f"Import complete! {len(results['npcs'])} NPCs, "
              f"{len(results['locations'])} locations, "
              f"{len(results['compendium'])} compendium entries created.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Database error during import: {str(e)}", 'danger')
        results['errors'].append(f"Database commit failed: {str(e)}")

    # Clean up session
    for key in ['obsidian_vault_path', 'obsidian_campaign_id',
                'obsidian_new_campaign_name', 'obsidian_mappings', 'obsidian_images']:
        flask_session.pop(key, None)

    return render_template('obsidian_import/results.html',
                           results=results, campaign=campaign)
