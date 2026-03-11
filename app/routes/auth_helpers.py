"""
auth_helpers.py — Role-based access control helpers for Phase 22.

Roles:
  gm       — full access to all campaign content
  asst_gm  — same as gm for content; excluded only from site-level admin (is_admin)
  player   — sees only their own PCs and GM-revealed/player-visible content

Usage:
  @gm_required          — route decorator; blocks player-role users
  is_gm_of(campaign)    — True if current_user is owner or gm/asst_gm of campaign
  is_player_of(campaign)— True if current_user is a player member of campaign
  campaign_role(campaign)— returns the user's effective role string for a campaign
"""

from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_login import current_user
from app.models import CampaignMembership


def _effective_role(campaign):
    """Return current_user's effective role for a campaign.

    Priority:
    1. is_admin → 'gm' (site admins always have full access)
    2. campaign.user_id == current_user.id → 'gm' (owner)
    3. CampaignMembership row → row.role
    4. current_user.role (site-level default)
    """
    if not current_user.is_authenticated:
        return None
    if current_user.is_admin:
        return 'gm'
    if campaign.user_id == current_user.id:
        return 'gm'
    membership = CampaignMembership.query.filter_by(
        campaign_id=campaign.id, user_id=current_user.id
    ).first()
    if membership:
        return membership.role
    return current_user.role  # site-level fallback


def is_gm_of(campaign):
    """True if current_user has GM or Asst GM access to this campaign."""
    return _effective_role(campaign) in ('gm', 'asst_gm')


def is_player_of(campaign):
    """True if current_user is a player member of this campaign."""
    return _effective_role(campaign) == 'player'


def campaign_role(campaign):
    """Return the effective role string for current_user in this campaign."""
    return _effective_role(campaign)


def gm_required(f):
    """Route decorator: allows gm and asst_gm; redirects player-role users."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        # Site admins always pass
        if current_user.is_admin:
            return f(*args, **kwargs)
        # Users with a site-level gm or asst_gm role pass unconditionally
        # (campaign-level check happens inside the route when needed)
        if current_user.role in ('gm', 'asst_gm'):
            return f(*args, **kwargs)
        # Player-role users are blocked
        flash('You do not have permission to access that page.', 'warning')
        return redirect(url_for('player.dashboard'))
    return decorated
