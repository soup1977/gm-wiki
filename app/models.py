from app import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

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

adventure_site_session = db.Table('adventure_site_session',
    db.Column('adventure_site_id', db.Integer, db.ForeignKey('adventure_site.id'), primary_key=True),
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True)
)

adventure_site_tags = db.Table('adventure_site_tags',
    db.Column('adventure_site_id', db.Integer, db.ForeignKey('adventure_site.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(256), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    campaigns = db.relationship('Campaign', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    system = db.Column(db.String(100))         # Free text — "D&D 5e", "ICRPG", whatever
    status = db.Column(db.String(50), default='active')   # active / on hiatus / complete
    description = db.Column(db.Text)
    image_style_prompt = db.Column(db.Text)   # prepended to all SD image generation prompts
    ai_world_context = db.Column(db.Text)    # injected into AI Generate Entry system prompts
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Campaign {self.name}>'


class Faction(db.Model):
    """A named faction or organization within a campaign.
    NPCs, Locations, and Quests can be linked to a faction."""
    __tablename__ = 'factions'

    id          = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    name        = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    disposition = db.Column(db.String(50))  # friendly|neutral|hostile|unknown
    gm_notes    = db.Column(db.Text)

    campaign = db.relationship('Campaign', backref='factions')

    def __repr__(self):
        return f'<Faction {self.name}>'


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

    race_or_ancestry = db.Column(db.String(200))  # "Elf", "Android", "Human"
    description = db.Column(db.Text)              # Physical appearance, personality
    backstory = db.Column(db.Text)               # Player-provided character background
    gm_hooks = db.Column(db.Text)                # Private GM notes on story hooks
    notes = db.Column(db.Text)                   # Ongoing GM notes
    portrait_filename = db.Column(db.String(255))

    home_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = db.relationship('Campaign', backref='player_characters')
    home_location = db.relationship('Location', backref='pcs_based_here', foreign_keys=[home_location_id])
    claimed_by = db.relationship('User', backref='claimed_characters', foreign_keys=[user_id])
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
    faction_id = db.Column(db.Integer, db.ForeignKey('factions.id'), nullable=True)

    # Self-referencing parent (region > city > district)
    parent_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    # Home story arc (set when created via genesis wizard; nullable for manually created locations)
    story_arc_id = db.Column(db.Integer, db.ForeignKey('adventure_site.id'), nullable=True)

    # Relationships
    campaign = db.relationship('Campaign', backref='locations')
    story_arc = db.relationship('AdventureSite', backref='arc_locations', foreign_keys=[story_arc_id])
    faction = db.relationship('Faction', backref='locations', foreign_keys=[faction_id])
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
    faction = db.Column(db.String(200))           # legacy text field (kept for backward compat)
    faction_id = db.Column(db.Integer, db.ForeignKey('factions.id'), nullable=True)
    physical_description = db.Column(db.Text)
    personality = db.Column(db.Text)
    secrets = db.Column(db.Text)                  # GM-only — never shown to players
    notes = db.Column(db.Text)                    # General notes (markdown in Phase 4)
    is_player_visible = db.Column(db.Boolean, default=False)  # Used in Phase 6

    portrait_filename = db.Column(db.String(255))  # stored filename in static/uploads/

    # Foreign key to Location (NPC's home)
    home_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    # Home story arc (set when created via genesis wizard; nullable for manually created NPCs)
    story_arc_id = db.Column(db.Integer, db.ForeignKey('adventure_site.id'), nullable=True)

    # Relationships
    campaign = db.relationship('Campaign', backref='npcs')
    story_arc = db.relationship('AdventureSite', backref='arc_npcs', foreign_keys=[story_arc_id])
    faction_rel = db.relationship('Faction', backref='npcs', foreign_keys=[faction_id])
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
    faction_id = db.Column(db.Integer, db.ForeignKey('factions.id'), nullable=True)

    # Home story arc (set when created via genesis wizard; nullable for manually created quests)
    story_arc_id = db.Column(db.Integer, db.ForeignKey('adventure_site.id'), nullable=True)

    campaign = db.relationship('Campaign', backref='quests')
    faction = db.relationship('Faction', backref='quests', foreign_keys=[faction_id])
    story_arc = db.relationship('AdventureSite', backref='arc_quests', foreign_keys=[story_arc_id])
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
    image_filename = db.Column(db.String(255))
    is_player_visible = db.Column(db.Boolean, default=False)  # Phase 6

    # Who owns it — null means the party owns it
    owner_npc_id = db.Column(db.Integer, db.ForeignKey('npcs.id'), nullable=True)
    # Where it came from — null means unknown
    origin_location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)

    # Home story arc (set when created via genesis wizard; nullable for manually created items)
    story_arc_id = db.Column(db.Integer, db.ForeignKey('adventure_site.id'), nullable=True)

    campaign = db.relationship('Campaign', backref='items')
    story_arc = db.relationship('AdventureSite', backref='arc_items', foreign_keys=[story_arc_id])
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
    prep_notes = db.Column(db.Text)          # Pre-session planning notes (shown in Session Mode)
    summary = db.Column(db.Text)             # What happened this session (post-session)
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


class RandomTable(db.Model):
    """A rollable table of random results.
    campaign_id=NULL means it's a built-in table visible to all campaigns.
    Custom tables belong to one campaign (campaign_id set)."""
    __tablename__ = 'random_tables'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)

    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))    # "Names", "Encounters", "Weather", etc.
    description = db.Column(db.Text)
    is_builtin = db.Column(db.Boolean, default=False)   # True for system-supplied tables

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = db.relationship('Campaign', backref='random_tables')
    rows = db.relationship('TableRow', backref='table', cascade='all, delete-orphan',
                           order_by='TableRow.display_order')

    def __repr__(self):
        return f'<RandomTable {self.name}>'


class TableRow(db.Model):
    """One entry in a RandomTable. weight > 1 makes this entry more likely."""
    __tablename__ = 'table_rows'

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('random_tables.id'), nullable=False)

    content = db.Column(db.Text, nullable=False)
    weight = db.Column(db.Integer, default=1)       # Higher = more likely to be rolled
    display_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TableRow {self.id}: {self.content[:40]}>'


# Association table: Session ↔ MonsterInstance (many-to-many)
# A session can feature many monster instances; an instance can appear in many sessions.
session_monsters = db.Table('session_monsters',
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.id'), primary_key=True),
    db.Column('monster_instance_id', db.Integer, db.ForeignKey('monster_instances.id'), primary_key=True)
)


class BestiaryEntry(db.Model):
    """A global creature/monster template. Not tied to any campaign.
    GMs create these once and spawn instances per campaign."""
    __tablename__ = 'bestiary_entries'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    system = db.Column(db.String(50))           # "D&D 5e", "ICRPG", etc. (optional)
    cr_level = db.Column(db.String(20))         # "CR 1/4", "Level 3", etc. (optional)
    stat_block = db.Column(db.Text, nullable=False)  # Markdown-supported
    image_path = db.Column(db.String(255))      # Portrait/token image filename
    source = db.Column(db.String(100))          # "Monster Manual p.166", "Homebrew"
    visible_to_players = db.Column(db.Boolean, default=False)
    tags = db.Column(db.Text)                   # Comma-separated: "humanoid,goblinoid,forest"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Cascade delete: removing a Bestiary Entry also removes all its spawned instances
    instances = db.relationship('MonsterInstance', backref='bestiary_entry',
                                lazy=True, cascade='all, delete-orphan')

    def get_tags_list(self):
        """Return tags as a Python list, or empty list if none."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    def __repr__(self):
        return f'<BestiaryEntry {self.name}>'


class MonsterInstance(db.Model):
    """A specific creature spawned from a BestiaryEntry, scoped to one campaign.
    E.g. 'Goblin 1', 'Goblin 2' are two instances of the 'Goblin' BestiaryEntry."""
    __tablename__ = 'monster_instances'

    id = db.Column(db.Integer, primary_key=True)
    bestiary_entry_id = db.Column(db.Integer, db.ForeignKey('bestiary_entries.id'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)

    instance_name = db.Column(db.String(100), nullable=False)   # "Goblin 1", "Snarl"
    status = db.Column(db.String(20), default='alive')          # alive / dead / fled / unknown
    notes = db.Column(db.Text)                                  # GM-only notes about this creature

    # Set when this instance has been promoted to a full NPC
    promoted_to_npc_id = db.Column(db.Integer, db.ForeignKey('npcs.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = db.relationship('Campaign', backref='monster_instances')
    promoted_npc = db.relationship('NPC', backref='original_monster_instance',
                                   foreign_keys=[promoted_to_npc_id])
    sessions = db.relationship('Session', secondary=session_monsters,
                               backref='monsters_encountered')

    def __repr__(self):
        return f'<MonsterInstance {self.instance_name}>'


class Encounter(db.Model):
    """A pre-planned encounter for a session — combat, loot, trap, social, or other."""
    __tablename__ = 'encounters'

    id             = db.Column(db.Integer, primary_key=True)
    campaign_id    = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    session_id     = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=True)
    name           = db.Column(db.String(200), nullable=False)
    encounter_type = db.Column(db.String(50), default='combat')   # combat|loot|social|trap|other
    status         = db.Column(db.String(50), default='planned')  # planned|used|skipped
    description    = db.Column(db.Text)
    gm_notes       = db.Column(db.Text)
    loot_table_id  = db.Column(db.Integer, db.ForeignKey('random_tables.id'), nullable=True)

    story_arc_id = db.Column(db.Integer, db.ForeignKey('adventure_site.id'), nullable=True)

    campaign   = db.relationship('Campaign',      backref='encounters')
    session    = db.relationship('Session',       backref='encounters', foreign_keys=[session_id])
    story_arc  = db.relationship('AdventureSite', backref='arc_encounters')
    loot_table = db.relationship('RandomTable',   backref='encounters')
    monsters   = db.relationship('EncounterMonster', backref='encounter',
                                 cascade='all, delete-orphan', order_by='EncounterMonster.id')

    def __repr__(self):
        return f'<Encounter {self.name}>'


class EncounterMonster(db.Model):
    """One row per creature type in an Encounter, with a count."""
    __tablename__ = 'encounter_monster'

    id                = db.Column(db.Integer, primary_key=True)
    encounter_id      = db.Column(db.Integer, db.ForeignKey('encounters.id'), nullable=False)
    bestiary_entry_id = db.Column(db.Integer, db.ForeignKey('bestiary_entries.id'), nullable=False)
    count             = db.Column(db.Integer, default=1, nullable=False)
    notes             = db.Column(db.String(200))

    bestiary_entry = db.relationship('BestiaryEntry', backref='encounter_slots')

    def __repr__(self):
        return f'<EncounterMonster {self.bestiary_entry_id} ×{self.count}>'


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


class AdventureSite(db.Model):
    """A planned adventure area — dungeon, town, region, or any self-contained
    location designed to be run at the table. Holds a full Markdown body so the
    GM can write everything (zones, encounters, boss stats, loot, GM notes) in
    one navigable document instead of scattering it across multiple entities.
    """
    __tablename__ = 'adventure_site'

    id                 = db.Column(db.Integer, primary_key=True)
    campaign_id        = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    name               = db.Column(db.String(200), nullable=False)
    subtitle           = db.Column(db.String(300))        # one-line tagline
    status             = db.Column(db.String(50), default='Planned')  # Planned / Active / Completed
    estimated_sessions = db.Column(db.Integer)
    content            = db.Column(db.Text)               # full Markdown body
    sort_order         = db.Column(db.Integer, default=0)
    is_player_visible  = db.Column(db.Boolean, default=False)
    milestones         = db.Column(db.Text)               # JSON list: [{"label": "...", "done": false}, ...]
    progress_pct       = db.Column(db.Integer, default=0) # 0-100, auto-calculated from milestones

    campaign = db.relationship('Campaign', backref='adventure_sites')
    tags     = db.relationship('Tag', secondary=adventure_site_tags, backref='adventure_sites')
    sessions = db.relationship('Session', secondary=adventure_site_session, backref='adventure_sites')

    def get_milestones(self):
        """Parse milestones JSON string into a Python list."""
        if not self.milestones:
            return []
        import json
        try:
            return json.loads(self.milestones)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_milestones(self, milestone_list):
        """Set milestones from a Python list and update progress_pct."""
        import json
        self.milestones = json.dumps(milestone_list) if milestone_list else None
        self.update_progress()

    def update_progress(self):
        """Recalculate progress_pct from milestones."""
        items = self.get_milestones()
        if not items:
            self.progress_pct = 0
            return
        done = sum(1 for m in items if m.get('done'))
        self.progress_pct = round((done / len(items)) * 100)

    def __repr__(self):
        return f'<AdventureSite {self.name}>'


class AppSetting(db.Model):
    """Key-value store for application settings (AI provider, URLs, etc.).

    Settings are stored in the database so they can be changed from the
    browser without editing .env files or restarting the app.
    """
    __tablename__ = 'app_settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get(key, default=None):
        """Get a setting value by key, returning default if not found."""
        row = AppSetting.query.get(key)
        if row is None:
            return default
        return row.value

    @staticmethod
    def set(key, value):
        """Set a setting value, creating or updating the row."""
        row = AppSetting.query.get(key)
        if row:
            row.value = value
        else:
            row = AppSetting(key=key, value=value)
            db.session.add(row)
        db.session.commit()

    @staticmethod
    def get_all_dict():
        """Return all settings as a plain dict."""
        return {s.key: s.value for s in AppSetting.query.all()}

    def __repr__(self):
        return f'<AppSetting {self.key}={self.value}>'


# ═══════════════════════════════════════════════════════════════════════════
# ICRPG CATALOG MODELS (Global base + Campaign-scoped homebrew)
#
# All catalog models use the same scope pattern:
#   is_builtin=True,  campaign_id=NULL  → official ICRPG content, read-only
#   is_builtin=False, campaign_id=<id>  → homebrew for that campaign
# Query pattern:
#   Model.query.filter(or_(Model.is_builtin == True, Model.campaign_id == X))
# ═══════════════════════════════════════════════════════════════════════════

class ICRPGWorld(db.Model):
    """An ICRPG world/setting (Alfheim, Warp Shell, Ghost Mountain, etc.)."""
    __tablename__ = 'icrpg_worlds'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_builtin  = db.Column(db.Boolean, default=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    basic_loot_count = db.Column(db.Integer, default=4)
    include_world_loot = db.Column(db.JSON, nullable=True)  # e.g. ["Alfheim"]

    campaign    = db.relationship('Campaign', backref='icrpg_homebrew_worlds')
    life_forms  = db.relationship('ICRPGLifeForm', backref='world', lazy=True)
    types       = db.relationship('ICRPGType', backref='world', lazy=True)
    loot_defs   = db.relationship('ICRPGLootDef', backref='world', lazy=True)

    def __repr__(self):
        return f'<ICRPGWorld {self.name}>'


class ICRPGLifeForm(db.Model):
    """A race/life form. Each grants stat bonuses and/or effort bonuses.
    Bonuses stored as JSON: {"STR": 1, "CON": 1} or {"DEX": 1, "GUN_EFFORT": 1}.
    Non-stat bonuses like innate abilities: {"ABILITY": "Claw weapons, walk on any surface"}."""
    __tablename__ = 'icrpg_life_forms'

    id          = db.Column(db.Integer, primary_key=True)
    world_id    = db.Column(db.Integer, db.ForeignKey('icrpg_worlds.id'), nullable=False)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    bonuses     = db.Column(db.JSON)
    is_builtin  = db.Column(db.Boolean, default=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)

    campaign    = db.relationship('Campaign', backref='icrpg_homebrew_life_forms')

    def __repr__(self):
        return f'<ICRPGLifeForm {self.name}>'


class ICRPGType(db.Model):
    """A class/type (Warrior, Mage, Pilot, etc.). Belongs to a world."""
    __tablename__ = 'icrpg_types'

    id          = db.Column(db.Integer, primary_key=True)
    world_id    = db.Column(db.Integer, db.ForeignKey('icrpg_worlds.id'), nullable=False)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_builtin  = db.Column(db.Boolean, default=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)

    campaign    = db.relationship('Campaign', backref='icrpg_homebrew_types')
    abilities   = db.relationship('ICRPGAbility', backref='type_ref',
                                  cascade='all, delete-orphan', lazy=True)
    starting_loot = db.relationship('ICRPGStartingLoot', backref='type_ref',
                                    cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<ICRPGType {self.name}>'


class ICRPGAbility(db.Model):
    """An ability (starting, milestone, or mastery) tied to a Type.
    ability_kind: 'starting' | 'milestone' | 'mastery'."""
    __tablename__ = 'icrpg_abilities'

    id            = db.Column(db.Integer, primary_key=True)
    type_id       = db.Column(db.Integer, db.ForeignKey('icrpg_types.id'), nullable=False)
    name          = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text)
    ability_kind  = db.Column(db.String(20), nullable=False)
    is_builtin    = db.Column(db.Boolean, default=False)
    campaign_id   = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    display_order = db.Column(db.Integer, default=0)

    campaign      = db.relationship('Campaign', backref='icrpg_homebrew_abilities')

    def __repr__(self):
        return f'<ICRPGAbility {self.name} ({self.ability_kind})>'


class ICRPGLootDef(db.Model):
    """A reusable loot definition in the ICRPG catalog.
    This is the 'blueprint'; when a PC equips it, an ICRPGCharLoot row is created.
    Effects stored as JSON: {"DEFENSE": 2} or {"WEAPON_EFFORT": 1, "note": "silver"}."""
    __tablename__ = 'icrpg_loot_defs'

    id          = db.Column(db.Integer, primary_key=True)
    world_id    = db.Column(db.Integer, db.ForeignKey('icrpg_worlds.id'), nullable=True)
    name        = db.Column(db.String(200), nullable=False)
    loot_type   = db.Column(db.String(50))      # Weapon, Armor, Shield, Pack, Tool, Spell, Item, Augment
    description = db.Column(db.Text)
    effects     = db.Column(db.JSON)            # mechanical bonuses
    slot_cost   = db.Column(db.Integer, default=1)
    coin_cost   = db.Column(db.Integer, nullable=True)
    is_starter  = db.Column(db.Boolean, default=False)   # available as starting loot pick
    is_builtin  = db.Column(db.Boolean, default=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    source      = db.Column(db.String(100))

    campaign    = db.relationship('Campaign', backref='icrpg_homebrew_loot')

    def __repr__(self):
        return f'<ICRPGLootDef {self.name}>'


class ICRPGStartingLoot(db.Model):
    """Links a Type to its starting loot options (choose 1).
    Can reference a LootDef or a Spell."""
    __tablename__ = 'icrpg_starting_loot'

    id          = db.Column(db.Integer, primary_key=True)
    type_id     = db.Column(db.Integer, db.ForeignKey('icrpg_types.id'), nullable=False)
    loot_def_id = db.Column(db.Integer, db.ForeignKey('icrpg_loot_defs.id'), nullable=True)
    spell_id    = db.Column(db.Integer, db.ForeignKey('icrpg_spells.id'), nullable=True)

    loot_def    = db.relationship('ICRPGLootDef')
    spell       = db.relationship('ICRPGSpell')

    @property
    def display_name(self):
        if self.loot_def:
            return self.loot_def.name
        if self.spell:
            return self.spell.name
        return 'Unknown'

    def __repr__(self):
        return f'<ICRPGStartingLoot type={self.type_id}>'


class ICRPGSpell(db.Model):
    """An ICRPG spell catalog entry. Spells are loot (occupy inventory slots)
    but have extra metadata (type, casting stat, level)."""
    __tablename__ = 'icrpg_spells'

    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(200), nullable=False)
    spell_type   = db.Column(db.String(50))      # "Arcane", "Holy", "Infernal"
    casting_stat = db.Column(db.String(10))       # "INT", "WIS"
    level        = db.Column(db.Integer, default=1)
    target       = db.Column(db.String(100))
    duration     = db.Column(db.String(100))
    description  = db.Column(db.Text)
    is_builtin   = db.Column(db.Boolean, default=False)
    campaign_id  = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    source       = db.Column(db.String(100))

    campaign     = db.relationship('Campaign', backref='icrpg_homebrew_spells')

    def __repr__(self):
        return f'<ICRPGSpell {self.name}>'


class ICRPGMilestonePath(db.Model):
    """One of the 5 milestone paths (Iron, Smoke, Amber, Oak, Hawk).
    Tiers stored as JSON: [{"tier": 1, "rewards": [{"name": "...", "description": "..."}]}, ...]."""
    __tablename__ = 'icrpg_milestone_paths'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    tiers       = db.Column(db.JSON)
    is_builtin  = db.Column(db.Boolean, default=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)

    campaign    = db.relationship('Campaign', backref='icrpg_homebrew_paths')

    def __repr__(self):
        return f'<ICRPGMilestonePath {self.name}>'


# ═══════════════════════════════════════════════════════════════════════════
# ICRPG CHARACTER SHEET (linked 1:1 to PlayerCharacter)
# ═══════════════════════════════════════════════════════════════════════════

class ICRPGCharacterSheet(db.Model):
    """ICRPG-specific character data, linked 1:1 to PlayerCharacter.
    Only created for PCs in campaigns where system contains 'ICRPG'."""
    __tablename__ = 'icrpg_character_sheets'

    id              = db.Column(db.Integer, primary_key=True)
    pc_id           = db.Column(db.Integer, db.ForeignKey('player_characters.id'),
                                nullable=False, unique=True)

    # Catalog references
    world_id        = db.Column(db.Integer, db.ForeignKey('icrpg_worlds.id'), nullable=True)
    life_form_id    = db.Column(db.Integer, db.ForeignKey('icrpg_life_forms.id'), nullable=True)
    type_id         = db.Column(db.Integer, db.ForeignKey('icrpg_types.id'), nullable=True)

    story           = db.Column(db.String(500))    # one-line character concept

    # Core Stats — base allocation by player (6 points total)
    stat_str        = db.Column(db.Integer, default=0)
    stat_dex        = db.Column(db.Integer, default=0)
    stat_con        = db.Column(db.Integer, default=0)
    stat_int        = db.Column(db.Integer, default=0)
    stat_wis        = db.Column(db.Integer, default=0)
    stat_cha        = db.Column(db.Integer, default=0)

    # Effort — base allocation by player (4 points total)
    effort_basic    = db.Column(db.Integer, default=0)    # d4
    effort_weapons  = db.Column(db.Integer, default=0)    # d6
    effort_guns     = db.Column(db.Integer, default=0)    # d8
    effort_magic    = db.Column(db.Integer, default=0)    # d10
    effort_ultimate = db.Column(db.Integer, default=0)    # d12

    # Status
    hearts_max      = db.Column(db.Integer, default=1)    # total hearts (starts at 1)
    hp_current      = db.Column(db.Integer, default=10)   # current HP
    hero_coin       = db.Column(db.Boolean, default=False)
    dying_timer     = db.Column(db.Integer, default=0)    # 0 = not dying

    # Mastery tracking
    nat20_count     = db.Column(db.Integer, default=0)    # total natural 20s rolled
    mastery_count   = db.Column(db.Integer, default=0)    # masteries earned (0-3)

    # Coin
    coin            = db.Column(db.Integer, default=0)

    # Permission toggle — when True, the owning player can adjust base stats/efforts
    allow_player_edit = db.Column(db.Boolean, default=False)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pc              = db.relationship('PlayerCharacter',
                        backref=db.backref('icrpg_sheet', uselist=False,
                                           cascade='all, delete-orphan'))
    world           = db.relationship('ICRPGWorld')
    life_form       = db.relationship('ICRPGLifeForm')
    char_type       = db.relationship('ICRPGType')
    loot_items      = db.relationship('ICRPGCharLoot', backref='sheet',
                        cascade='all, delete-orphan', order_by='ICRPGCharLoot.display_order')
    char_abilities  = db.relationship('ICRPGCharAbility', backref='sheet',
                        cascade='all, delete-orphan', order_by='ICRPGCharAbility.display_order')

    # ── Computed stat helpers ────────────────────────────────────
    STAT_KEYS = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']
    EFFORT_KEYS = ['basic', 'weapons', 'guns', 'magic', 'ultimate']
    EFFORT_DICE = {'basic': 'd4', 'weapons': 'd6', 'guns': 'd8',
                   'magic': 'd10', 'ultimate': 'd12'}

    def _lf_bonus(self, key):
        """Get life form bonus for a stat/effort key."""
        if not self.life_form or not self.life_form.bonuses:
            return 0
        return self.life_form.bonuses.get(key, 0)

    def _loot_bonus(self, key):
        """Sum all equipped loot bonuses for a stat/effort key."""
        total = 0
        for cl in self.loot_items:
            if cl.slot == 'equipped' and cl.loot_def and cl.loot_def.effects:
                total += cl.loot_def.effects.get(key, 0)
        return total

    def total_stat(self, key):
        """BASE + LIFE FORM bonus + LOOT bonus, capped at 10."""
        base = getattr(self, f'stat_{key.lower()}', 0) or 0
        return min(base + self._lf_bonus(key) + self._loot_bonus(key), 10)

    def total_effort(self, key):
        """BASE + LIFE FORM effort bonus + LOOT bonus, capped at 10."""
        effort_key = key.upper() + '_EFFORT'   # e.g. "MAGIC_EFFORT"
        base = getattr(self, f'effort_{key}', 0) or 0
        return min(base + self._lf_bonus(effort_key) + self._loot_bonus(effort_key), 10)

    @property
    def defense(self):
        """CON total + loot DEFENSE bonuses, capped at 10."""
        con = self.total_stat('CON')
        loot_def = self._loot_bonus('DEFENSE')
        return min(con + loot_def, 10)

    @property
    def total_hearts(self):
        """Hearts base + loot HEARTS bonus."""
        return self.hearts_max + self._loot_bonus('HEARTS')

    @property
    def hp_max(self):
        """Maximum HP = total hearts * 10."""
        return self.total_hearts * 10

    @property
    def equipped_loot(self):
        return [cl for cl in self.loot_items if cl.slot == 'equipped']

    @property
    def carried_loot(self):
        return [cl for cl in self.loot_items if cl.slot == 'carried']

    @property
    def equipped_slots_max(self):
        return 10 + self._loot_bonus('EQUIPPED_SLOTS')

    @property
    def carried_slots_max(self):
        return 10 + self._loot_bonus('CARRIED_SLOTS')

    @property
    def equipped_slots_used(self):
        return sum((cl.loot_def.slot_cost or 1) if cl.loot_def else 1 for cl in self.equipped_loot)

    @property
    def carried_slots_used(self):
        return sum((cl.loot_def.slot_cost or 1) if cl.loot_def else 1 for cl in self.carried_loot)

    def __repr__(self):
        return f'<ICRPGCharacterSheet pc={self.pc_id}>'


class ICRPGCharLoot(db.Model):
    """One loot item or spell on a character's sheet (equipped or carried).
    Can reference a catalog LootDef, a Spell, or be a custom one-off item."""
    __tablename__ = 'icrpg_char_loot'

    id            = db.Column(db.Integer, primary_key=True)
    sheet_id      = db.Column(db.Integer, db.ForeignKey('icrpg_character_sheets.id'), nullable=False)
    loot_def_id   = db.Column(db.Integer, db.ForeignKey('icrpg_loot_defs.id'), nullable=True)
    spell_id      = db.Column(db.Integer, db.ForeignKey('icrpg_spells.id'), nullable=True)
    slot          = db.Column(db.String(20), default='carried')   # 'equipped' | 'carried'
    custom_name   = db.Column(db.String(200))    # for one-off items not in catalog
    custom_desc   = db.Column(db.Text)           # for one-off items
    display_order = db.Column(db.Integer, default=0)

    loot_def      = db.relationship('ICRPGLootDef')
    spell         = db.relationship('ICRPGSpell')

    @property
    def display_name(self):
        if self.custom_name:
            return self.custom_name
        if self.loot_def:
            return self.loot_def.name
        if self.spell:
            return self.spell.name
        return 'Unknown'

    @property
    def display_description(self):
        if self.custom_desc:
            return self.custom_desc
        if self.loot_def:
            return self.loot_def.description
        if self.spell:
            return self.spell.description
        return ''

    def __repr__(self):
        return f'<ICRPGCharLoot {self.display_name}>'


class ICRPGCharAbility(db.Model):
    """An ability on a character's sheet (starting, milestone, or mastery).
    Can reference a catalog Ability or be a custom homebrew ability."""
    __tablename__ = 'icrpg_char_abilities'

    id            = db.Column(db.Integer, primary_key=True)
    sheet_id      = db.Column(db.Integer, db.ForeignKey('icrpg_character_sheets.id'), nullable=False)
    ability_id    = db.Column(db.Integer, db.ForeignKey('icrpg_abilities.id'), nullable=True)
    custom_name   = db.Column(db.String(200))
    custom_desc   = db.Column(db.Text)
    ability_kind  = db.Column(db.String(20))     # 'starting' | 'milestone' | 'mastery'
    display_order = db.Column(db.Integer, default=0)

    ability       = db.relationship('ICRPGAbility')

    @property
    def display_name(self):
        if self.custom_name:
            return self.custom_name
        if self.ability:
            return self.ability.name
        return 'Unknown'

    @property
    def display_description(self):
        if self.custom_desc:
            return self.custom_desc
        if self.ability:
            return self.ability.description
        return ''

    def __repr__(self):
        return f'<ICRPGCharAbility {self.display_name}>'


class EntityMention(db.Model):
    """Tracks which entity text fields reference other entities via #shortcodes.

    Created automatically when a #type[Name] shortcode is processed on save.
    Used to display "Referenced by" back-links on entity detail pages.
    """
    __tablename__ = 'entity_mention'

    id          = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    source_type = db.Column(db.String(50), nullable=False)  # 'npc','loc','item','quest','comp','session'
    source_id   = db.Column(db.Integer, nullable=False)
    target_type = db.Column(db.String(50), nullable=False)
    target_id   = db.Column(db.Integer, nullable=False)
