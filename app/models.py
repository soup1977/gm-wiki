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

# Tag association tables — one per entity type that supports tagging
npc_tags = db.Table('npc_tags',
    db.Column('npc_id', db.Integer, db.ForeignKey('npcs.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

location_tags = db.Table('location_tags',
    db.Column('location_id', db.Integer, db.ForeignKey('locations.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

quest_tags = db.Table('quest_tags',
    db.Column('quest_id', db.Integer, db.ForeignKey('quests.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

item_tags = db.Table('item_tags',
    db.Column('item_id', db.Integer, db.ForeignKey('items.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

session_tags = db.Table('session_tags',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
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


class CampaignStatTemplate(db.Model):
    """Defines what PC stats are tracked in this campaign.
    Each row is one stat field (e.g. "Armor Class", "Max HP").
    The GM picks a preset when creating the campaign and can edit fields later."""
    __tablename__ = 'campaign_stat_template'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    stat_name = db.Column(db.String(100), nullable=False)
    display_order = db.Column(db.Integer, default=0)

    campaign = db.relationship('Campaign', backref='stat_template_fields')

    def __repr__(self):
        return f'<CampaignStatTemplate {self.stat_name}>'


class PlayerCharacter(db.Model):
    """A player character in a campaign. Separate from NPCs — different fields,
    different visibility rules, used by the Combat Tracker and Session Mode."""
    __tablename__ = 'player_characters'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)

    character_name = db.Column(db.String(200), nullable=False)
    player_name = db.Column(db.String(200), nullable=False)
    level_or_rank = db.Column(db.String(100))   # "Level 5", "CR 3", "Veteran"
    class_or_role = db.Column(db.String(200))   # "Fighter", "Hacker", "Pilot"
    status = db.Column(db.String(50), default='active')
    # Status values: active, inactive, retired, dead, npc

    notes = db.Column(db.Text)                   # Markdown GM notes
    portrait_filename = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = db.relationship('Campaign', backref='player_characters')
    stats = db.relationship('PlayerCharacterStat', backref='character',
                            cascade='all, delete-orphan')
    session_attendances = db.relationship('SessionAttendance', backref='character',
                                          cascade='all, delete-orphan')

    def __repr__(self):
        return f'<PlayerCharacter {self.character_name}>'


class PlayerCharacterStat(db.Model):
    """Stores one stat value for a PC, linked to a CampaignStatTemplate field.
    E.g. template_field='Armor Class (AC)', stat_value='16'."""
    __tablename__ = 'player_character_stats'

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('player_characters.id'), nullable=False)
    template_field_id = db.Column(db.Integer, db.ForeignKey('campaign_stat_template.id'),
                                  nullable=False)
    stat_value = db.Column(db.String(100))  # Stored as string: "16", "45", "1d8+3"

    template_field = db.relationship('CampaignStatTemplate')

    def __repr__(self):
        return f'<PlayerCharacterStat {self.template_field_id}={self.stat_value}>'


class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)

    campaign = db.relationship('Campaign', backref='tags')

    # Tag names are unique within a campaign
    __table_args__ = (db.UniqueConstraint('name', 'campaign_id', name='uq_tag_name_campaign'),)

    def __repr__(self):
        return f'<Tag {self.name}>'


class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(100))              # city / dungeon / wilderness / etc (free text)
    description = db.Column(db.Text)
    gm_notes = db.Column(db.Text)                 # GM-only — never shown to players
    notes = db.Column(db.Text)                    # General notes (markdown in Phase 4)
    map_filename = db.Column(db.String(255))       # stored filename in static/uploads/
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
    tags = db.relationship('Tag', secondary=location_tags)

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

    portrait_filename = db.Column(db.String(255))  # stored filename in static/uploads/

    # Foreign key to Location (NPC's home)
    home_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    # Relationships
    campaign = db.relationship('Campaign', backref='npcs')
    home_location = db.relationship('Location', backref='npcs_living_here', foreign_keys=[home_location_id])
    # Locations this NPC is associated with (separate from home)
    connected_locations = db.relationship('Location', secondary=npc_location_link,
                                          backref='notable_npcs')
    tags = db.relationship('Tag', secondary=npc_tags)

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
    tags = db.relationship('Tag', secondary=quest_tags)

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
    tags = db.relationship('Tag', secondary=item_tags)

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

    # Phase 5 — Session Mode fields
    pinned_npc_ids = db.Column(db.JSON)      # Array of NPC IDs pinned for this session
    active_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    campaign = db.relationship('Campaign', backref='sessions')
    npcs_featured = db.relationship('NPC', secondary=session_npc_link, backref='sessions')
    locations_visited = db.relationship('Location', secondary=session_location_link, backref='sessions')
    items_mentioned = db.relationship('Item', secondary=session_item_link, backref='sessions')
    quests_touched = db.relationship('Quest', secondary=session_quest_link, backref='sessions')
    tags = db.relationship('Tag', secondary=session_tags)
    active_location = db.relationship('Location', foreign_keys=[active_location_id])

    @property
    def attending_pcs(self):
        """Convenience property — returns the PlayerCharacter objects for this session."""
        return [a.character for a in self.attendances if a.character]

    def __repr__(self):
        return f'<Session {self.number}: {self.title}>'


class SessionAttendance(db.Model):
    """Records which Player Characters attended a given session."""
    __tablename__ = 'session_attendance'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey('player_characters.id'), nullable=False)

    # backref 'attendances' on Session; cascade so deleting a session cleans up rows
    session = db.relationship('Session',
                              backref=db.backref('attendances', cascade='all, delete-orphan'))
    # 'character' backref defined on PlayerCharacter.session_attendances above

    def __repr__(self):
        return f'<SessionAttendance session={self.session_id} char={self.character_id}>'


def get_or_create_tags(campaign_id, tag_string):
    """Parse a comma-separated tag string and return a list of Tag objects.
    Creates new Tag records as needed. Tags are stored lowercase and trimmed."""
    names = [t.strip().lower() for t in tag_string.split(',') if t.strip()]
    tags = []
    for name in names:
        tag = Tag.query.filter_by(name=name, campaign_id=campaign_id).first()
        if not tag:
            tag = Tag(name=name, campaign_id=campaign_id)
            db.session.add(tag)
        tags.append(tag)
    return tags