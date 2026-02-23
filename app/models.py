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


# Association table: Quest ↔ NPC (many-to-many)
quest_npc_link = db.Table('quest_npc_link',
    db.Column('quest_id', db.Integer, db.ForeignKey('quests.id'), primary_key=True),
    db.Column('npc_id', db.Integer, db.ForeignKey('npcs.id'), primary_key=True)
)

# Association table: Quest ↔ Location (many-to-many)
quest_location_link = db.Table('quest_location_link',
    db.Column('quest_id', db.Integer, db.ForeignKey('quests.id'), primary_key=True),
    db.Column('location_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True)
)


class Quest(db.Model):
    __tablename__ = 'quests'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), default='active')  # active / completed / failed / on_hold
    hook = db.Column(db.Text)          # How the party got involved
    description = db.Column(db.Text)   # Full quest description
    outcome = db.Column(db.Text)       # What happened (fill in when resolved)
    gm_notes = db.Column(db.Text)      # GM-only, never shown to players
    is_player_visible = db.Column(db.Boolean, default=False)  # Phase 6

    campaign = db.relationship('Campaign', backref='quests')
    involved_npcs = db.relationship('NPC', secondary=quest_npc_link, backref='quests')
    involved_locations = db.relationship('Location', secondary=quest_location_link, backref='quests')

    def __repr__(self):
        return f'<Quest {self.name}>'


class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(100))      # weapon / armor / consumable / misc (free text)
    rarity = db.Column(db.String(50))     # common / uncommon / rare / very rare / legendary / unique
    description = db.Column(db.Text)
    gm_notes = db.Column(db.Text)         # GM-only, never shown to players
    is_player_visible = db.Column(db.Boolean, default=False)  # Phase 6

    # Who owns it — null means the party owns it
    owner_npc_id = db.Column(db.Integer, db.ForeignKey('npcs.id'), nullable=True)
    # Where it came from — null means unknown
    origin_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    campaign = db.relationship('Campaign', backref='items')
    owner_npc = db.relationship('NPC', backref='items_owned', foreign_keys=[owner_npc_id])
    origin_location = db.relationship('Location', backref='items_found_here', foreign_keys=[origin_location_id])

    def __repr__(self):
        return f'<Item {self.name}>'


class CompendiumEntry(db.Model):
    __tablename__ = 'compendium_entries'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))   # free text: "Combat", "Magic", "House Rules", etc.
    content = db.Column(db.Text)
    is_gm_only = db.Column(db.Boolean, default=False)  # hides entry in player view (Phase 6)

    campaign = db.relationship('Campaign', backref='compendium_entries')

    def __repr__(self):
        return f'<CompendiumEntry {self.title}>'


# Association tables for Session (defined before Session class)
session_npc_link = db.Table('session_npc_link',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('npc_id', db.Integer, db.ForeignKey('npcs.id'), primary_key=True)
)

session_location_link = db.Table('session_location_link',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('location_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True)
)

session_item_link = db.Table('session_item_link',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('item_id', db.Integer, db.ForeignKey('items.id'), primary_key=True)
)

session_quest_link = db.Table('session_quest_link',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('quest_id', db.Integer, db.ForeignKey('quests.id'), primary_key=True)
)


class Session(db.Model):
    __tablename__ = 'sessions'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    number = db.Column(db.Integer)           # e.g. 1, 2, 3...
    title = db.Column(db.String(200))        # optional short title
    date_played = db.Column(db.Date)
    summary = db.Column(db.Text)             # What happened this session
    gm_notes = db.Column(db.Text)            # GM-only notes
    is_player_visible = db.Column(db.Boolean, default=False)  # Phase 6

    campaign = db.relationship('Campaign', backref='sessions')
    npcs_featured = db.relationship('NPC', secondary=session_npc_link, backref='sessions')
    locations_visited = db.relationship('Location', secondary=session_location_link, backref='sessions')
    items_mentioned = db.relationship('Item', secondary=session_item_link, backref='sessions')
    quests_touched = db.relationship('Quest', secondary=session_quest_link, backref='sessions')

    def __repr__(self):
        return f'<Session {self.number}: {self.title}>'