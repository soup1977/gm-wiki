from collections import defaultdict

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required
from app import db
from app.models import AdventureSite, Session, Tag, get_or_create_tags, Campaign
from app.shortcode import process_shortcodes, clear_mentions, resolve_mentions_for_target, resolve_mentions_for_source

adventure_sites_bp = Blueprint('adventure_sites', __name__)

STATUS_OPTIONS = ['Planned', 'Active', 'Completed']


def get_active_campaign_id():
    return session.get('active_campaign_id')


@adventure_sites_bp.route('/sites')
@login_required
def list_sites():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    status_filter = request.args.get('status', '').strip() or None
    tag_filter = request.args.get('tag', '').strip() or None

    query = AdventureSite.query.filter_by(campaign_id=campaign_id)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if tag_filter:
        query = query.join(AdventureSite.tags).filter(Tag.name == tag_filter)

    sites = query.order_by(AdventureSite.sort_order, AdventureSite.name).all()

    # Group sites by status in display order
    groups = defaultdict(list)
    for site in sites:
        groups[site.status or 'Planned'].append(site)
    grouped_sites = {
        status: groups[status]
        for status in STATUS_OPTIONS
        if groups[status]
    }

    all_tags = sorted(
        {t for s in AdventureSite.query.filter_by(campaign_id=campaign_id).all() for t in s.tags},
        key=lambda t: t.name
    )

    return render_template('adventure_sites/list.html', sites=sites,
                           grouped_sites=grouped_sites,
                           status_filter=status_filter, tag_filter=tag_filter,
                           all_tags=all_tags, status_options=STATUS_OPTIONS)


@adventure_sites_bp.route('/sites/new', methods=['GET', 'POST'])
@login_required
def create_site():
    campaign_id = get_active_campaign_id()
    if not campaign_id:
        flash('Select a campaign first.', 'warning')
        return redirect(url_for('campaigns.list_campaigns'))

    all_sessions = (Session.query
                    .filter_by(campaign_id=campaign_id)
                    .order_by(Session.number.desc())
                    .all())

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name is required.', 'danger')
            return render_template('adventure_sites/form.html', site=None,
                                   all_sessions=all_sessions, status_options=STATUS_OPTIONS)

        site = AdventureSite(
            campaign_id=campaign_id,
            name=name,
            subtitle=request.form.get('subtitle', '').strip() or None,
            status=request.form.get('status', 'Planned'),
            estimated_sessions=request.form.get('estimated_sessions') or None,
            content=request.form.get('content', '').strip() or None,
            sort_order=int(request.form.get('sort_order') or 0),
            is_player_visible='is_player_visible' in request.form,
        )

        # Parse milestones from form (one per line)
        milestones_raw = request.form.get('milestones', '').strip()
        if milestones_raw:
            milestone_list = [{'label': line.strip(), 'done': False}
                              for line in milestones_raw.splitlines() if line.strip()]
            site.set_milestones(milestone_list)

        site.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))
        site.sessions = Session.query.filter(
            Session.id.in_(request.form.getlist('linked_sessions')),
            Session.campaign_id == campaign_id
        ).all()

        db.session.add(site)
        db.session.flush()

        if site.content:
            processed, mentions = process_shortcodes(site.content, campaign_id, 'site', site.id)
            site.content = processed
            for m in mentions:
                db.session.add(m)

        db.session.commit()
        flash(f'Adventure Site "{site.name}" created.', 'success')
        return redirect(url_for('adventure_sites.site_detail', site_id=site.id))

    return render_template('adventure_sites/form.html', site=None,
                           all_sessions=all_sessions, status_options=STATUS_OPTIONS)


@adventure_sites_bp.route('/sites/<int:site_id>')
@login_required
def site_detail(site_id):
    from app.ai_provider import is_ai_enabled
    campaign_id = get_active_campaign_id()
    site = AdventureSite.query.filter_by(id=site_id, campaign_id=campaign_id).first_or_404()
    mentions = resolve_mentions_for_target('site', site_id)
    linked_entities = resolve_mentions_for_source('site', site_id)
    return render_template('adventure_sites/detail.html', site=site, mentions=mentions,
                           linked_entities=linked_entities, ai_enabled=is_ai_enabled())


@adventure_sites_bp.route('/sites/<int:site_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_site(site_id):
    campaign_id = get_active_campaign_id()
    site = AdventureSite.query.filter_by(id=site_id, campaign_id=campaign_id).first_or_404()

    all_sessions = (Session.query
                    .filter_by(campaign_id=campaign_id)
                    .order_by(Session.number.desc())
                    .all())

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name is required.', 'danger')
            return render_template('adventure_sites/form.html', site=site,
                                   all_sessions=all_sessions, status_options=STATUS_OPTIONS)

        site.name = name
        site.subtitle = request.form.get('subtitle', '').strip() or None
        site.status = request.form.get('status', 'Planned')
        site.estimated_sessions = request.form.get('estimated_sessions') or None
        site.content = request.form.get('content', '').strip() or None
        site.sort_order = int(request.form.get('sort_order') or 0)
        site.is_player_visible = 'is_player_visible' in request.form

        # Parse milestones from form (one per line), preserving existing done state
        milestones_raw = request.form.get('milestones', '').strip()
        existing = {m['label']: m.get('done', False) for m in site.get_milestones()}
        if milestones_raw:
            milestone_list = []
            for line in milestones_raw.splitlines():
                label = line.strip()
                if label:
                    milestone_list.append({'label': label, 'done': existing.get(label, False)})
            site.set_milestones(milestone_list)
        else:
            site.set_milestones([])

        site.tags = get_or_create_tags(campaign_id, request.form.get('tags', ''))
        site.sessions = Session.query.filter(
            Session.id.in_(request.form.getlist('linked_sessions')),
            Session.campaign_id == campaign_id
        ).all()

        clear_mentions('site', site.id)
        if site.content:
            processed, mentions = process_shortcodes(site.content, campaign_id, 'site', site.id)
            site.content = processed
            for m in mentions:
                db.session.add(m)

        db.session.commit()
        flash(f'Adventure Site "{site.name}" updated.', 'success')
        return redirect(url_for('adventure_sites.site_detail', site_id=site.id))

    return render_template('adventure_sites/form.html', site=site,
                           all_sessions=all_sessions, status_options=STATUS_OPTIONS)


@adventure_sites_bp.route('/sites/<int:site_id>/delete', methods=['POST'])
@login_required
def delete_site(site_id):
    campaign_id = get_active_campaign_id()
    site = AdventureSite.query.filter_by(id=site_id, campaign_id=campaign_id).first_or_404()
    name = site.name
    clear_mentions('site', site.id)
    db.session.delete(site)
    db.session.commit()
    flash(f'Adventure Site "{name}" deleted.', 'success')
    return redirect(url_for('adventure_sites.list_sites'))


@adventure_sites_bp.route('/sites/<int:site_id>/replace-text', methods=['POST'])
@login_required
def replace_text(site_id):
    """AJAX endpoint: find-and-replace a single occurrence in site content."""
    campaign_id = get_active_campaign_id()
    site = AdventureSite.query.filter_by(id=site_id, campaign_id=campaign_id).first_or_404()

    data = request.get_json(silent=True) or {}
    find = data.get('find', '')
    replace = data.get('replace', '')

    if not find:
        return jsonify({'error': 'find is required'}), 400

    if not site.content or find not in site.content:
        return jsonify({'error': 'Text not found in site content'}), 404

    site.content = site.content.replace(find, replace, 1)
    db.session.commit()
    return jsonify({'success': True})


@adventure_sites_bp.route('/sites/<int:site_id>/update-milestones', methods=['POST'])
@login_required
def update_milestones(site_id):
    """AJAX endpoint: update milestone done/undone state from the detail page."""
    campaign_id = get_active_campaign_id()
    site = AdventureSite.query.filter_by(id=site_id, campaign_id=campaign_id).first_or_404()

    data = request.get_json(silent=True) or {}
    milestones = data.get('milestones')

    if milestones is None:
        return jsonify({'error': 'milestones is required'}), 400

    if not isinstance(milestones, list):
        return jsonify({'error': 'milestones must be a list'}), 400

    cleaned = []
    for m in milestones:
        if isinstance(m, dict) and 'label' in m:
            cleaned.append({'label': str(m['label']), 'done': bool(m.get('done', False))})

    site.set_milestones(cleaned)
    db.session.commit()

    return jsonify({'success': True, 'progress_pct': site.progress_pct})


@adventure_sites_bp.route('/sites/<int:site_id>/suggest-milestones', methods=['POST'])
@login_required
def suggest_milestones(site_id):
    """Generate milestone suggestions from the adventure site's content."""
    from app.ai_provider import is_ai_enabled, ai_chat, AIProviderError, get_feature_provider

    if not is_ai_enabled():
        return jsonify({'error': 'AI is not configured. Check Settings.'}), 403

    campaign_id = get_active_campaign_id()
    if not campaign_id:
        return jsonify({'error': 'No active campaign.'}), 400

    site = AdventureSite.query.filter_by(id=site_id, campaign_id=campaign_id).first()
    if not site:
        return jsonify({'error': 'Adventure Site not found.'}), 404

    if not site.content:
        return jsonify({'error': 'This site has no content yet. Add some content first.'}), 400

    campaign = Campaign.query.get(campaign_id)

    context_parts = [f'Adventure Site: {site.name}']
    if site.subtitle:
        context_parts.append(f'Subtitle: {site.subtitle}')
    if site.status:
        context_parts.append(f'Status: {site.status}')
    context_parts.append(f'\nSite content:\n{site.content[:4000]}')

    system_prompt = (
        'You are a tabletop RPG adventure designer. '
        'Based on the adventure site content provided, suggest 5-7 key milestones or story beats '
        'that could be tracked as progress checkpoints for this adventure. '
        'Each milestone should represent a meaningful moment of completion or achievement — '
        'clearing an area, defeating a boss, finding a key item, triggering a plot revelation, etc. '
        'Format as a Markdown bullet list. Each milestone is one line, starting with a verb.'
    )
    if campaign and campaign.ai_world_context:
        system_prompt += f'\n\nWorld context: {campaign.ai_world_context}'

    messages = [{'role': 'user', 'content': '\n\n'.join(context_parts)}]

    try:
        response = ai_chat(system_prompt, messages, max_tokens=512,
                           provider=get_feature_provider('generate'))
        return jsonify({'milestones': response})
    except AIProviderError as e:
        return jsonify({'error': str(e)}), 502
