#!/usr/bin/env python3
"""One-time script: parse structured effects and slot_cost from ICRPG loot
description text, then write the results back into the seed JSON files.

Run from the repo root:
    python3 scripts/parse_loot_effects.py

Produces a summary of what was parsed and flags ambiguous items.
"""

import json
import os
import re
import sys

SEED_DIR = os.path.join(os.path.dirname(__file__), '..', 'app', 'seed_data')

STAT_NAMES = {'STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'}
EFFORT_MAP = {
    'weapon effort': 'WEAPON_EFFORT',
    'weapon': 'WEAPON_EFFORT',
    'magic effort': 'MAGIC_EFFORT',
    'magical effort': 'MAGIC_EFFORT',
    'gun effort': 'GUN_EFFORT',
    'ultimate effort': 'ULTIMATE_EFFORT',
    'ultimate': 'ULTIMATE_EFFORT',
    'basic effort': 'BASIC_EFFORT',
    'effort': 'WEAPON_EFFORT',  # generic "Effort" most often means weapon
}

# Clause-level conditional words
CONDITIONAL_CLAUSE = re.compile(
    r'\b(when|while|if\s+you|if\s+hit|if\s+worn|if\s+the|if\s+a\s|if\s+they|'
    r'against|during|after|before|per round|'
    r'once per|on a natural|on natural|per turn|chance)\b',
    re.IGNORECASE
)

# Duration pattern — temporary effects
DURATION_PATTERN = re.compile(
    r'for \d+[Dd]?\d*\s+(?:ROUND|TURN|DAY|HOUR)',
    re.IGNORECASE
)

# Item types that are consumable/temporary by nature
CONSUMABLE_TYPES = {'Food', 'Trap', 'Potion', 'Grenade'}


def _get_clause(desc, match):
    """Get the clause containing a regex match.
    Splits on periods, semicolons, and commas."""
    s = match.start()
    e = match.end()
    while s > 0 and desc[s - 1] not in '.;,':
        s -= 1
    while e < len(desc) and desc[e] not in '.;,':
        e += 1
    return desc[s:e].strip()


def _is_conditional(desc, match, item_type=None):
    """Check if a bonus match is conditional/temporary."""
    clause = _get_clause(desc, match)

    # Clause-level conditional words
    if CONDITIONAL_CLAUSE.search(clause):
        return True, clause

    # Duration in the same clause
    if DURATION_PATTERN.search(clause):
        return True, clause

    # For consumables/spells, check if the full description has duration markers
    if DURATION_PATTERN.search(desc):
        is_spell = item_type and 'spell' in item_type.lower()
        is_consumable = item_type in CONSUMABLE_TYPES
        if is_spell or is_consumable:
            return True, f"[{item_type}] {clause} (duration in desc)"

    # "for N mile" pattern (range-limited)
    if re.search(r'for \d+\s+mile', clause, re.IGNORECASE):
        return True, clause

    # Consumables with limited uses
    if item_type in CONSUMABLE_TYPES:
        if re.search(r'\d+\s+(?:use|bite|charge|dose)', desc, re.IGNORECASE):
            return True, f"[{item_type}] {clause} (limited uses)"

    return False, ''


def parse_effects(desc, item_type=None):
    """Extract structured effects dict and slot_cost from a description string.

    Returns (effects_dict_or_None, slot_cost_or_None, warnings_list).
    Only extracts unconditional, permanent bonuses.
    """
    effects = {}
    slot_cost = None
    warnings = []

    if not desc:
        return None, None, warnings

    # --- Slot cost patterns ---
    m = re.search(r'(?:occupies?|equip)\s+(\d+)\s+(?:slot|space|inventor)', desc, re.IGNORECASE)
    if m:
        slot_cost = int(m.group(1))

    if re.search(r'(?:occupies?\s+no\s+(?:space|inventor)|no\s+inventory\s+space)', desc, re.IGNORECASE):
        slot_cost = 0

    # --- Defense bonus ---
    for m in re.finditer(r'\+(\d+)\s+DEFENSE', desc, re.IGNORECASE):
        bonus = int(m.group(1))
        cond, reason = _is_conditional(desc, m, item_type)
        if cond:
            warnings.append(f"Conditional DEFENSE +{bonus}: {reason}")
            continue
        effects['DEFENSE'] = effects.get('DEFENSE', 0) + bonus

    # --- Stat bonuses: +N STR, +N DEX, etc. ---
    for m in re.finditer(r'([+-]\d+)\s+(STR|DEX|CON|INT|WIS|CHA)\b', desc):
        bonus = int(m.group(1))
        stat = m.group(2)
        cond, reason = _is_conditional(desc, m, item_type)
        if cond:
            warnings.append(f"Conditional {stat} {bonus:+d}: {reason}")
            continue
        effects[stat] = effects.get(stat, 0) + bonus

    # --- Effort bonuses ---
    for m in re.finditer(
        r'\+(\d+)\s+(Weapon\s+Effort|Magic(?:al)?\s+Effort|Gun\s+Effort|'
        r'Ultimate\s+Effort|Basic\s+Effort|Effort)\b',
        desc, re.IGNORECASE
    ):
        bonus = int(m.group(1))
        kind = m.group(2).lower().strip()
        key = EFFORT_MAP.get(kind)
        if not key:
            warnings.append(f"Unknown effort type: '{kind}'")
            continue
        cond, reason = _is_conditional(desc, m, item_type)
        if cond:
            warnings.append(f"Conditional {key} +{bonus}: {reason}")
            continue
        effects[key] = effects.get(key, 0) + bonus

    # --- Hearts bonus ---
    for m in re.finditer(r'(?:\+|add\s+)(\d+)\s+hearts?\b', desc, re.IGNORECASE):
        bonus = int(m.group(1))
        cond, reason = _is_conditional(desc, m, item_type)
        if cond:
            warnings.append(f"Conditional HEARTS +{bonus}: {reason}")
            continue
        effects['HEARTS'] = effects.get('HEARTS', 0) + bonus

    return (effects if effects else None), slot_cost, warnings


def process_file(filepath):
    """Process a single seed JSON file. Returns (modified_data, summary)."""
    with open(filepath) as f:
        data = json.load(f)

    summary = {
        'file': os.path.basename(filepath),
        'total_entries': 0,
        'effects_added': 0,
        'slot_cost_added': 0,
        'warnings': [],
    }

    for table in data:
        for entry in table.get('entries', []):
            summary['total_entries'] += 1
            desc = entry.get('description', '')
            item_type = entry.get('type', '')
            effects, slot_cost, warnings = parse_effects(desc, item_type)

            if effects:
                entry['effects'] = effects
                summary['effects_added'] += 1
            if slot_cost is not None:
                entry['slot_cost'] = slot_cost
                summary['slot_cost_added'] += 1
            if warnings:
                for w in warnings:
                    summary['warnings'].append(f"  [{entry['name']}] {w}")

    return data, summary


def main():
    files = [
        os.path.join(SEED_DIR, 'icrpg_starter_loot.json'),
        os.path.join(SEED_DIR, 'icrpg_loot.json'),
    ]

    all_summaries = []

    for filepath in files:
        if not os.path.exists(filepath):
            print(f"SKIP: {filepath} not found")
            continue

        data, summary = process_file(filepath)
        all_summaries.append(summary)

        # Write back
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')

        print(f"\n{'=' * 60}")
        print(f"FILE: {summary['file']}")
        print(f"  Entries scanned: {summary['total_entries']}")
        print(f"  Effects added:   {summary['effects_added']}")
        print(f"  Slot costs set:  {summary['slot_cost_added']}")
        if summary['warnings']:
            print(f"  WARNINGS ({len(summary['warnings'])}):")
            for w in summary['warnings']:
                print(f"    {w}")

    # Final totals
    print(f"\n{'=' * 60}")
    total_effects = sum(s['effects_added'] for s in all_summaries)
    total_slots = sum(s['slot_cost_added'] for s in all_summaries)
    total_warnings = sum(len(s['warnings']) for s in all_summaries)
    print(f"TOTAL: {total_effects} effects, {total_slots} slot costs, {total_warnings} warnings")

    # List all items that got effects for review
    print(f"\n{'=' * 60}")
    print("ITEMS WITH PARSED EFFECTS:")
    for filepath in files:
        if not os.path.exists(filepath):
            continue
        with open(filepath) as f:
            data = json.load(f)
        for table in data:
            for entry in table.get('entries', []):
                parts = []
                if 'effects' in entry:
                    parts.append(f"effects={entry['effects']}")
                if 'slot_cost' in entry:
                    parts.append(f"slot_cost={entry['slot_cost']}")
                if parts:
                    print(f"  [{table.get('table_name', '?')}] {entry['name']}: {', '.join(parts)}")


if __name__ == '__main__':
    main()
