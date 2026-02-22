from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import CompendiumEntry

compendium_bp = Blueprint('compendium', __name__)


def get_active_campaign_id():
    return session.get('active_campaign_id')


@compendium_bp.route('/compendium')
def list_compendium():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))
    entries = (CompendiumEntry.query
               .filter_by(campaign_id=campaign_id)
               .order_by(CompendiumEntry.category, CompendiumEntry.title)
               .all())
    return render_template('compendium/list.html', entries=entries)


@compendium_bp.route('/compendium/new', methods=['GET', 'POST'])
def create_entry():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'danger')
            return render_template('compendium/form.html', entry=None)

        entry = CompendiumEntry(
            campaign_id=campaign_id,
            title=title,
            category=request.form.get('category', '').strip() or None,
            content=request.form.get('content', '').strip() or None,
            is_gm_only=bool(request.form.get('is_gm_only')),
        )
        db.session.add(entry)
        db.session.commit()
        flash(f'Entry "{entry.title}" created.', 'success')
        return redirect(url_for('compendium.entry_detail', entry_id=entry.id))

    return render_template('compendium/form.html', entry=None)


@compendium_bp.route('/compendium/<int:entry_id>')
def entry_detail(entry_id):
    campaign_id = get_active_campaign_id()
    entry = CompendiumEntry.query.filter_by(id=entry_id, campaign_id=campaign_id).first_or_404()
    return render_template('compendium/detail.html', entry=entry)


@compendium_bp.route('/compendium/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    campaign_id = get_active_campaign_id()
    entry = CompendiumEntry.query.filter_by(id=entry_id, campaign_id=campaign_id).first_or_404()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'danger')
            return render_template('compendium/form.html', entry=entry)

        entry.title = title
        entry.category = request.form.get('category', '').strip() or None
        entry.content = request.form.get('content', '').strip() or None
        entry.is_gm_only = bool(request.form.get('is_gm_only'))

        db.session.commit()
        flash(f'Entry "{entry.title}" updated.', 'success')
        return redirect(url_for('compendium.entry_detail', entry_id=entry.id))

    return render_template('compendium/form.html', entry=entry)


@compendium_bp.route('/compendium/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    campaign_id = get_active_campaign_id()
    entry = CompendiumEntry.query.filter_by(id=entry_id, campaign_id=campaign_id).first_or_404()
    title = entry.title
    db.session.delete(entry)
    db.session.commit()
    flash(f'Entry "{title}" deleted.', 'success')
    return redirect(url_for('compendium.list_compendium'))
