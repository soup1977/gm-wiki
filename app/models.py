from app import db
from datetime import datetime

class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    system = db.Column(db.String(100))         # Free text — "D&D 5e", "ICRPG", whatever
    status = db.Column(db.String(50), default='active')   # active / on hiatus / complete
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Campaign {self.name}>'


class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(100))              # city / dungeon / wilderness / etc (free text)
    description = db.Column(db.Text)
    gm_notes = db.Column(db.Text)                 # GM-only — never shown to players
    notes = db.Column(db.Text)                    # General notes (markdown in Phase 4)
    is_player_visible = db.Column(db.Boolean, default=False)  # Used in Phase 6

    # Self-referencing parent (region > city > district)
    parent_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    # Relationships
    campaign = db.relationship('Campaign', backref='locations')
    parent_location = db.relationship(
        'Location',
        remote_side='Location.id',
        backref='child_locations',
        foreign_keys=[parent_location_id]
    )

    def __repr__(self):
        return f'<Location {self.name}>'


class NPC(db.Model):
    __tablename__ = 'npcs'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200))              # e.g. "blacksmith", "villain"
    status = db.Column(db.String(50), default='alive')  # alive / dead / unknown / missing
    faction = db.Column(db.String(200))           # plain text for now
    physical_description = db.Column(db.Text)
    personality = db.Column(db.Text)
    secrets = db.Column(db.Text)                  # GM-only — never shown to players
    notes = db.Column(db.Text)                    # General notes (markdown in Phase 4)
    is_player_visible = db.Column(db.Boolean, default=False)  # Used in Phase 6

    # Foreign key to Location (NPC's home)
    home_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    # Relationships
    campaign = db.relationship('Campaign', backref='npcs')
    home_location = db.relationship('Location', backref='npcs_living_here', foreign_keys=[home_location_id])

    def __repr__(self):
        return f'<NPC {self.name}>'