"""
Seed built-in random tables.

Run once from the project root:
    python3 seed_builtin_tables.py

Safe to re-run — skips tables that already exist by name.
"""

from app import create_app, db
from app.models import RandomTable, TableRow

BUILTIN_TABLES = [
    {
        'name': 'NPC Names (Male)',
        'category': 'NPCs',
        'description': 'Fantasy male given names for quick NPC generation.',
        'rows': [
            'Aldric', 'Bram', 'Caius', 'Dorin', 'Edwyn', 'Faolan', 'Gareth',
            'Hadwin', 'Isarn', 'Jorin', 'Kell', 'Lorcan', 'Maeris', 'Nedric',
            'Oswin', 'Piran', 'Quillan', 'Rowan', 'Saben', 'Taren', 'Ulric',
            'Vael', 'Wulfric', 'Xander', 'Yoren', 'Zavan',
        ],
    },
    {
        'name': 'NPC Names (Female)',
        'category': 'NPCs',
        'description': 'Fantasy female given names for quick NPC generation.',
        'rows': [
            'Adora', 'Brynn', 'Celyn', 'Dara', 'Elowen', 'Faye', 'Gwen',
            'Halla', 'Idris', 'Jora', 'Kaela', 'Liriel', 'Mira', 'Nessa',
            'Orina', 'Petra', 'Quill', 'Reva', 'Senna', 'Talia', 'Ula',
            'Vessa', 'Wren', 'Xyla', 'Yara', 'Zola',
        ],
    },
    {
        'name': 'Weather',
        'category': 'Environment',
        'description': 'Random weather conditions for overland travel or scene-setting.',
        'rows': [
            'Clear skies, warm sun',
            'Partly cloudy, light breeze',
            'Overcast and grey',
            'Patchy fog in low areas',
            'Light drizzle',
            'Steady rain',
            'Heavy downpour, poor visibility',
            'Thunderstorm — lightning and thunder',
            'Dense fog, visibility under 30 feet',
            'Hot and humid, no wind',
            'Cold snap — frost on the ground',
            'Light snowfall',
            'Heavy snow, drifting',
            'Strong winds, difficult travel',
            'Hail',
            'Unseasonably warm for the season',
            'Unnaturally still — not a breath of wind',
            'Blood-red sunset, ominous clouds',
        ],
    },
    {
        'name': 'Tavern Names',
        'category': 'Locations',
        'description': 'Evocative tavern and inn names for quick world-building.',
        'rows': [
            'The Broken Antler',
            'The Gilded Flagon',
            'The Wandering Wyvern',
            'The Rusty Nail',
            'The Sleeping Fox',
            'The Crow and Candle',
            'The Moonlit Crossing',
            'The Salt and Saber',
            'The Last Ember',
            'The Hollow Oak',
            'The Black Boar',
            'The Dagger and Lantern',
            'The Traveler\'s Rest',
            'The Mended Net',
            'The Painted Skull',
            'The Hearthside',
            'The Sunken Stone',
            'The Three Faces',
            'The Amber Keep',
            'The Dusty Road',
        ],
    },
    {
        'name': 'Dungeon Features',
        'category': 'Dungeon',
        'description': 'Details to add flavor and texture to dungeon rooms.',
        'rows': [
            'A rusted iron door, slightly ajar',
            'Faded murals depicting a forgotten king',
            'The smell of sulfur and old smoke',
            'A dry fountain, basin cracked and stained',
            'Scratched graffiti in an unknown language',
            'Webbing in the corners — something large made it',
            'A pile of gnawed bones',
            'A collapsed section of ceiling, rubble everywhere',
            'Water seeping through the walls, pooling on the floor',
            'A single torch still burning in a wall sconce',
            'Claw marks on the door, from the inside',
            'A rotting wooden chest, empty',
            'Faint chanting echoing from somewhere ahead',
            'The floor is suspiciously clean in one spot',
            'A crude altar to an unknown deity',
            'Broken shackles bolted to the wall',
            'A trapdoor, sealed with a heavy lock',
            'The skeleton of an adventurer, gear long looted',
            'A narrow ventilation shaft, too small to crawl through',
            'Strange symbols carved into every stone block',
        ],
    },
    {
        'name': 'Random Encounters',
        'category': 'Encounters',
        'description': 'Generic overland random encounter seeds — adapt to your setting.',
        'rows': [
            'A merchant caravan looking for an escort',
            'Bandits demand a toll',
            'A wounded traveler by the roadside',
            'A patrol of soldiers, suspicious of the party',
            'A lone hermit who knows more than he lets on',
            'Wild animals — a pack hunting nearby',
            'An abandoned campsite, still warm',
            'A signpost — one arm pointing somewhere it shouldn\'t',
            'A group of refugees fleeing from the direction you\'re heading',
            'A bounty hunter tracking someone who looks like one of the PCs',
            'Strange lights in the sky',
            'A river crossing — the bridge is out',
            'A child alone on the road, lost and frightened',
            'Evidence of a recent battle — bodies not yet cold',
            'A friendly rival adventuring party',
            'A traveling entertainer with a mysterious act',
            'Thick unnatural fog rolls in suddenly',
            'A shrine to an obscure saint, recently vandalized',
        ],
    },
]


def seed():
    app = create_app()
    with app.app_context():
        added = 0
        skipped = 0
        for table_data in BUILTIN_TABLES:
            existing = RandomTable.query.filter_by(
                name=table_data['name'], is_builtin=True
            ).first()
            if existing:
                skipped += 1
                print(f"  SKIP  {table_data['name']}")
                continue

            table = RandomTable(
                campaign_id=None,
                name=table_data['name'],
                category=table_data.get('category'),
                description=table_data.get('description'),
                is_builtin=True,
            )
            db.session.add(table)
            db.session.flush()  # get table.id before adding rows

            for i, content in enumerate(table_data['rows']):
                db.session.add(TableRow(
                    table_id=table.id,
                    content=content,
                    weight=1,
                    display_order=i,
                ))
            db.session.commit()
            added += 1
            print(f"  ADDED {table_data['name']} ({len(table_data['rows'])} entries)")

        print(f"\nDone — {added} table(s) added, {skipped} skipped.")


if __name__ == '__main__':
    seed()
