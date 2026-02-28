from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from app import db
from app.models import AdventureSite, Session, Tag, get_or_create_tags
from app.shortcode import process_shortcodes, clear_mentions, resolve_mentions_for_target

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

    all_tags = sorted(
        {t for s in AdventureSite.query.filter_by(campaign_id=campaign_id).all() for t in s.tags},
        key=lambda t: t.name
    )

    return render_template('adventure_sites/list.html', sites=sites,
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
        )

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
    campaign_id = get_active_campaign_id()
    site = AdventureSite.query.filter_by(id=site_id, campaign_id=campaign_id).first_or_404()
    mentions = resolve_mentions_for_target('site', site_id)
    return render_template('adventure_sites/detail.html', site=site, mentions=mentions)


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
