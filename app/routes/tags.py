from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required
from app import db
from app.models import Tag, NPC, Location, Quest, Item, Session as GameSession
from sqlalchemy import func

tags_bp = Blueprint('tags', __name__, url_prefix='/tags')


def get_active_campaign_id():
    return session.get('active_campaign_id')


@tags_bp.route('/')
@login_required
def list_tags():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Please select a campaign first.', 'warning')
        return redirect(url_for('main.index'))

    tags = Tag.query.filter_by(campaign_id=campaign_id).order_by(Tag.name).all()

    # Build usage count for each tag — count linked entities across all 5 types
    # Each tag may appear on NPCs, Locations, Quests, Items, and Sessions
    usage = {}
    for tag in tags:
        count = (
            NPC.query.filter(NPC.campaign_id == campaign_id, NPC.tags.contains(tag)).count() +
            Location.query.filter(Location.campaign_id == campaign_id, Location.tags.contains(tag)).count() +
            Quest.query.filter(Quest.campaign_id == campaign_id, Quest.tags.contains(tag)).count() +
            Item.query.filter(Item.campaign_id == campaign_id, Item.tags.contains(tag)).count() +
            GameSession.query.filter(GameSession.campaign_id == campaign_id, GameSession.tags.contains(tag)).count()
        )
        usage[tag.id] = count

    return render_template('tags/list.html', tags=tags, usage=usage)


@tags_bp.route('/<int:tag_id>/rename', methods=['POST'])
@login_required
def rename_tag(tag_id):
    campaign_id = get_active_campaign_id()
    tag = Tag.query.get_or_404(tag_id)

    if tag.campaign_id != campaign_id:
        flash('Tag not found in this campaign.', 'danger')
        return redirect(url_for('tags.list_tags'))

    new_name = request.form.get('name', '').strip().lower()
    if not new_name:
        flash('Tag name cannot be empty.', 'danger')
        return redirect(url_for('tags.list_tags'))

    # Check for name collision with another existing tag in this campaign
    existing = Tag.query.filter_by(name=new_name, campaign_id=campaign_id).first()
    if existing and existing.id != tag.id:
        flash(f'A tag named "{new_name}" already exists.', 'danger')
        return redirect(url_for('tags.list_tags'))

    old_name = tag.name
    tag.name = new_name
    db.session.commit()

    flash(f'Tag "{old_name}" renamed to "{new_name}".', 'success')
    return redirect(url_for('tags.list_tags'))


@tags_bp.route('/<int:tag_id>/delete', methods=['POST'])
@login_required
def delete_tag(tag_id):
    campaign_id = get_active_campaign_id()
    tag = Tag.query.get_or_404(tag_id)

    if tag.campaign_id != campaign_id:
        flash('Tag not found in this campaign.', 'danger')
        return redirect(url_for('tags.list_tags'))

    name = tag.name
    db.session.delete(tag)
    db.session.commit()

    flash(f'Tag "{name}" deleted and removed from all entries.', 'warning')
    return redirect(url_for('tags.list_tags'))
