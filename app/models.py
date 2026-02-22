from app import db
from datetime import datetime

# Association table: NPC ↔ Location (many-to-many "notable" appearances)
# Separate from home_location, which is a single FK.
# This lets an NPC be linked to multiple locations they frequent.
npc_location_link = db.Table('npc_location_link',
    db.Column('npc_id', db.Integer, db.ForeignKey('npcs.id'), primary_key=True),
    db.Column('location_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True)
)

# Association table: Location ↔ Location (many-to-many connections)
# e.g. a road between two towns. Stored one direction only (a_id < b_id
# is not enforced, so we query both sides when displaying).
location_connection = db.Table('location_connection',
    db.Column('location_a_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True),
    db.Column('location_b_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True)
)


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
    # Locations connected to this one (e.g. roads, passages).
    # primaryjoin/secondaryjoin tell SQLAlchemy which column is "this side".
    # connected_from is the backref for the other direction.
    connected_locations = db.relationship(
        'Location',
        secondary=location_connection,
        primaryjoin='Location.id == location_connection.c.location_a_id',
        secondaryjoin='Location.id == location_connection.c.location_b_id',
        backref='connected_from'
    )

    @property
    def all_connected_locations(self):
        """Return all connected locations regardless of which side of the link they're on."""
        return list(self.connected_locations) + list(self.connected_from)

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
    # Locations this NPC is associated with (separate from home)
    connected_locations = db.relationship('Location', secondary=npc_location_link,
                                          backref='notable_npcs')

    def __repr__(self):
        return f'<NPC {self.name}>'