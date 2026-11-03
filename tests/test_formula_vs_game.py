import pytest
from scripts.wf_data_indexer import WFDataIndexer
from scripts.warframe_damage_engine import WarframeDamageEngine

# Module-scope fixture
@pytest.fixture(scope="module")
def idx():
    return WFDataIndexer()

# Constant tolerance
TOL = 0.015

# Test cases
CASES = [
    ('Arca Titron', ['Crushing Ruin', 'Galvanized Reflex', 'Primed Pressure Point', 'Blood Rush', 'Galvanized Steel', 'Shocking Touch', 'Galvanized Elementalist', 'Organ Shatter', 'Seismic Wave'], dict(final_dmg=1812.6, final_cc=0.504, final_cd=3.8)),
    ('Vulkar', ['Vital Sense', 'Rupture'], dict(final_dmg=387.0, final_cc=0.20, final_cd=4.4)),
    ('Stropha', ['Sacrificial Pressure', 'Corrupt Charge', 'Gladiator Might', 'Voltaic Strike', 'Sacrificial Steel', 'Amalgam Organ Shatter', 'Killing Blow', 'Volcanic Edge'], dict(final_dmg=1149.5, final_cc=1.125, final_cd=5.9)),
    ('Reaper Prime', ['Sacrificial Pressure', 'Killing Blow', 'Sacrificial Steel', 'Primed Reach', 'Organ Shatter', 'Gladiator Might', 'Corrupt Charge'], dict(final_cc=1.313, final_cd=6.3)),
    ('Glaive Prime', ['Volatile Quick Return', 'Gladiator Might', 'Killing Blow', 'Corrupt Charge', 'Sacrificial Pressure', 'Sacrificial Steel', 'Amalgam Organ Shatter', 'Power Throw'], dict(final_cc=0.825, final_cd=4.9)),
    ('Kuva Zarr', ['Galvanized Chamber', 'Hunter Munitions', 'Critical Delay', 'Amalgam Serration', 'Rifle Ammo Mutation', 'Vital Sense', 'Heavy Caliber', 'Vigilante Armaments', 'Primed Cryo Rounds'], dict(final_ms=2.4, final_cc=0.75, final_cd=5.5, final_fr=1.73))
]

# Parametrized test
@pytest.mark.parametrize("weapon, mods, expected", CASES, ids=[case[0] for case in CASES])
def test_matches_game_panel(idx, weapon, mods, expected):
    w = idx.fuzzy_match_weapon(weapon)
    mod_objs = [idx.mods_index[n.lower()] for n in mods]
    r = WarframeDamageEngine().compute_metrics(w, mod_objs=mod_objs)
    for key, value in expected.items():
        assert r[key] == pytest.approx(value, rel=TOL), key