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
    """Load ICRPG compendium seed data into the active campaign."""
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    seed_path = os.path.join(current_app.root_path, 'seed_data', 'icrpg_compendium.json')
    with open(seed_path) as f:
        entries = _json.load(f)

    imported = 0
    skipped = 0
    for entry in entries:
        title = entry['title']
        category = entry.get('category', 'ICRPG')
        exists = CompendiumEntry.query.filter_by(
            campaign_id=campaign_id, category=category, title=title
        ).first()
        if exists:
            skipped += 1
            continue

        ce = CompendiumEntry(
            campaign_id=campaign_id,
            title=title,
            category=category,
            content=entry.get('content', ''),
            is_gm_only=entry.get('is_gm_only', False),
        )
        db.session.add(ce)
        imported += 1

    db.session.commit()
    msg = f'Imported {imported} ICRPG compendium entries.'
    if skipped:
        msg += f' Skipped {skipped} duplicates.'
    flash(msg, 'success')
    return redirect(url_for('compendium.list_compendium'))
