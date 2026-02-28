import json as _json
import os
from collections import defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required
from app import db
from app.models import CompendiumEntry
from app.shortcode import process_shortcodes, clear_mentions, resolve_mentions_for_target

compendium_bp = Blueprint('compendium', __name__)


def get_active_campaign_id():
    return session.get('active_campaign_id')


@compendium_bp.route('/compendium')
@login_required
def list_compendium():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    # Build the full list of categories for the sidebar
    all_entries = (CompendiumEntry.query
                   .filter_by(campaign_id=campaign_id)
                   .order_by(CompendiumEntry.category, CompendiumEntry.title)
                   .all())

    categories = sorted({e.category or 'Uncategorized' for e in all_entries})

    # Filter by category if one is selected
    active_category = request.args.get('category', '').strip() or None

    if active_category:
        if active_category == 'Uncategorized':
            entries = [e for e in all_entries if not e.category]
        else:
            entries = [e for e in all_entries if e.category == active_category]
    else:
        entries = all_entries

    # Count entries per category for badge display
    cat_counts = defaultdict(int)
    for e in all_entries:
        cat_counts[e.category or 'Uncategorized'] += 1

    return render_template('compendium/list.html', entries=entries,
                           categories=categories, cat_counts=cat_counts,
                           active_category=active_category)


@compendium_bp.route('/compendium/new', methods=['GET', 'POST'])
@login_required
def create_entry():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    existing_categories = sorted({e.category for e in
        CompendiumEntry.query.filter_by(campaign_id=campaign_id).all()
        if e.category})

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'danger')
            return render_template('compendium/form.html', entry=None,
                                   existing_categories=existing_categories)

        entry = CompendiumEntry(
            campaign_id=campaign_id,
            title=title,
            category=request.form.get('category', '').strip() or None,
            content=request.form.get('content', '').strip() or None,
            is_gm_only=bool(request.form.get('is_gm_only')),
        )
        db.session.add(entry)
        db.session.flush()

        if entry.content:
            processed, mentions = process_shortcodes(entry.content, campaign_id, 'comp', entry.id)
            entry.content = processed
            for m in mentions:
                db.session.add(m)

        db.session.commit()
        flash(f'Entry "{entry.title}" created.', 'success')
        return redirect(url_for('compendium.entry_detail', entry_id=entry.id))

    return render_template('compendium/form.html', entry=None,
                           existing_categories=existing_categories)


@compendium_bp.route('/compendium/<int:entry_id>')
@login_required
def entry_detail(entry_id):
    campaign_id = get_active_campaign_id()
    entry = CompendiumEntry.query.filter_by(id=entry_id, campaign_id=campaign_id).first_or_404()
    mentions = resolve_mentions_for_target('comp', entry_id)
    return render_template('compendium/detail.html', entry=entry, mentions=mentions)


@compendium_bp.route('/compendium/<int:entry_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    campaign_id = get_active_campaign_id()
    entry = CompendiumEntry.query.filter_by(id=entry_id, campaign_id=campaign_id).first_or_404()

    existing_categories = sorted({e.category for e in
        CompendiumEntry.query.filter_by(campaign_id=campaign_id).all()
        if e.category})

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'danger')
            return render_template('compendium/form.html', entry=entry,
                                   existing_categories=existing_categories)

        entry.title = title
        entry.category = request.form.get('category', '').strip() or None
        entry.content = request.form.get('content', '').strip() or None
        entry.is_gm_only = bool(request.form.get('is_gm_only'))

        clear_mentions('comp', entry.id)
        if entry.content:
            processed, mentions = process_shortcodes(entry.content, campaign_id, 'comp', entry.id)
            entry.content = processed
            for m in mentions:
                db.session.add(m)

        db.session.commit()
        flash(f'Entry "{entry.title}" updated.', 'success')
        return redirect(url_for('compendium.entry_detail', entry_id=entry.id))

    return render_template('compendium/form.html', entry=entry,
                           existing_categories=existing_categories)


@compendium_bp.route('/compendium/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_entry(entry_id):
    campaign_id = get_active_campaign_id()
    entry = CompendiumEntry.query.filter_by(id=entry_id, campaign_id=campaign_id).first_or_404()
    title = entry.title
    db.session.delete(entry)
    db.session.commit()
    flash(f'Entry "{title}" deleted.', 'success')
    return redirect(url_for('compendium.list_compendium'))


@compendium_bp.route('/compendium/seed-icrpg', methods=['POST'])
@login_required
def seed_icrpg_compendium():
    """Load ICRPG rules and spells into the active campaign's compendium.
    (Loot tables, roll tables, and starter loot go into Rollable Tables instead.)"""
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    imported = 0
    skipped = 0

    def _add(title, category, content):
        nonlocal imported, skipped
        if CompendiumEntry.query.filter_by(
            campaign_id=campaign_id, title=title, category=category
        ).first():
            skipped += 1
            return
        db.session.add(CompendiumEntry(
            campaign_id=campaign_id, title=title,
            category=category, content=content,
        ))
        imported += 1

    seed_dir = os.path.join(current_app.root_path, 'seed_data')

    # --- Rules + Classes ---
    rules_path = os.path.join(seed_dir, 'icrpg_compendium.json')
    if os.path.exists(rules_path):
        with open(rules_path) as f:
            for entry in _json.load(f):
                _add(entry['title'], entry.get('category', 'ICRPG - Rule'), entry['content'])

    # --- Spells ---
    spells_path = os.path.join(seed_dir, 'icrpg_spells.json')
    if os.path.exists(spells_path):
        with open(spells_path) as f:
            for sp in _json.load(f):
                content = f"**Type:** {sp['type']}  \n"
                content += f"**Level:** {sp['level']}  \n"
                if sp.get('target'):
                    content += f"**Target:** {sp['target']}  \n"
                if sp.get('duration'):
                    content += f"**Duration:** {sp['duration']}  \n"
                content += f"\n{sp['description']}"
                if sp.get('flavor'):
                    content += f"\n\n*{sp['flavor']}*"
                _add(sp['name'], f"ICRPG - Spell ({sp['type']})", content)

    db.session.commit()
    msg = f'Imported {imported} ICRPG compendium entries.'
    if skipped:
        msg += f' Skipped {skipped} duplicates.'
    flash(msg, 'success')
    return redirect(url_for('compendium.list_compendium'))


@compendium_bp.route('/compendium/clear-icrpg', methods=['POST'])
@login_required
def clear_icrpg_compendium():
    """Delete all ICRPG-seeded compendium entries from the active campaign."""
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    count = CompendiumEntry.query.filter(
        CompendiumEntry.campaign_id == campaign_id,
        CompendiumEntry.category.like('ICRPG%')
    ).delete(synchronize_session=False)

    db.session.commit()
    flash(f'Deleted {count} ICRPG compendium entries.', 'success')
    return redirect(url_for('compendium.list_compendium'))
