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

    # Relationships
    campaign = db.relationship('Campaign', backref='locations')
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

    # Relationships
    campaign = db.relationship('Campaign', backref='npcs')
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

    campaign = db.relationship('Campaign', backref='quests')
    faction = db.relationship('Faction', backref='quests', foreign_keys=[faction_id])
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

    campaign   = db.relationship('Campaign',    backref='encounters')
    session    = db.relationship('Session',     backref='encounters', foreign_keys=[session_id])
    loot_table = db.relationship('RandomTable', backref='encounters')
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
