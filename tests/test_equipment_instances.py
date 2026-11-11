import json
import random

import pytest

from tests.test_items import make_full_session
from tests.test_net_integration import two_player_clients, wait_until
from wyrdfall.domain.content import TALENT_TREES
from wyrdfall.domain.dungeon import EncounterDef
from wyrdfall.domain.inventory import add_equipment, equipment_comparison, sync_equipment
from wyrdfall.domain.items import EQUIPMENT_DEFS, Rarity, equipped_item_ids
from wyrdfall.domain.loot import BOSS_REWARDS, boss_reward_for, roll_encounter_drops
from wyrdfall.domain.models import DamageElement, TriggerEvent
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import GameSession, _talent_tree_id_for
from wyrdfall.net.protocol import ClientTransferEquipment, decode_client_message, encode
from wyrdfall.persistence.checkpoint import RunCheckpoint


def forge(session):
    session.dungeon = session.dungeon.model_copy(update={"encounters": [EncounterDef(id="forge", name="Forja", room_type="forge")]})
    session.run.currency_earned = 100
    session.run.materials = {Rarity.RARO: 5, Rarity.COMUM: 5}


def pair():
    session = make_full_session()
    ally = session.run.party[0].model_copy(deep=True)
    ally.id, ally.name = "ally", "Aliado"
    session.run.party.append(ally)
    return session


def test_two_identical_pieces_keep_independent_enchantments_and_owner():
    s = pair()
    a = add_equipment(s.run, "guardian_helm")
    b = add_equipment(s.run, "guardian_helm")
    assert a.id != b.id
    assert not s.equip_armor("hero", "head", "guardian_helm")  # ambiguous
    assert s.equip_armor("hero", "head", a.id)
    before = s.run.model_dump_json()
    assert not s.equip_armor("ally", "head", a.id)
    assert s.run.model_dump_json() == before
    assert s.equip_armor("ally", "head", b.id)
    forge(s)
    assert s.socket_enchantment("hero", a.id, "ench_power")
    assert s.socket_enchantment("ally", b.id, "ench_ward")
    restored = RunState.model_validate_json(s.run.model_dump_json())
    assert restored.equipment_instances[a.id].enchantments == ["ench_power"]
    assert restored.equipment_instances[b.id].enchantments == ["ench_ward"]
    assert restored.party[0].equipment_instances[a.id].enchantments == ["ench_power"]


def test_unequip_transfer_reequip_keeps_affixes_and_removes_sender_bonus():
    s = pair()
    piece = add_equipment(s.run, "traveler_cap", enchantments=["ench_swiftness"])
    sender, recipient = s.run.party
    speed = sender.computed_stats(s.ruleset).speed
    assert s.equip_armor(sender.id, "head", piece.id)
    assert sender.computed_stats(s.ruleset).speed == speed + 2
    assert s.transfer_equipment(sender.id, recipient.id, piece.id)
    assert not sender.equipped_armor
    assert sender.computed_stats(s.ruleset).speed == speed
    assert not recipient.equipped_armor
    assert s.equip_armor(recipient.id, "head", piece.id)
    assert piece.enchantments == ["ench_swiftness"]
    before = s.run.model_dump_json()
    assert not s.transfer_equipment(sender.id, recipient.id, piece.id)
    assert not s.equip_armor(sender.id, "head", piece.id)
    assert s.run.model_dump_json() == before


def test_same_definition_accessories_are_three_separate_slots():
    s = make_full_session()
    pieces = [add_equipment(s.run, "ring_of_focus") for _ in range(4)]
    for p in pieces[:3]:
        assert s.equip_accessory("hero", p.id)
    assert not s.equip_accessory("hero", pieces[0].id)
    assert not s.equip_accessory("hero", pieces[3].id)


def test_engraving_cost_phase_capacity_and_duplicate_are_atomic():
    s = make_full_session()
    p = add_equipment(s.run, "traveler_cap")
    s.equip_armor("hero", "head", p.id)
    before = s.run.model_dump_json()
    assert not s.socket_enchantment("hero", p.id, "ench_power")
    assert s.run.model_dump_json() == before
    forge(s)
    assert s.socket_enchantment("hero", p.id, "ench_power")
    assert s.run.currency_earned == 90 and s.run.materials[Rarity.COMUM] == 4
    before = s.run.model_dump_json()
    assert not s.socket_enchantment("hero", p.id, "ench_power")
    assert not s.socket_enchantment("hero", p.id, "ench_ward")
    assert s.run.model_dump_json() == before


def test_reroll_only_changes_selected_slot_and_survives_resume():
    s = make_full_session()
    p = add_equipment(s.run, "guardian_helm", enchantments=["ench_power", "ench_ward"])
    s.equip_armor("hero", "head", p.id)
    forge(s)
    checkpoint = RunCheckpoint.model_validate_json(RunCheckpoint.from_session(s, mode="solo").model_dump_json())
    restored = checkpoint.restore_session(s.ruleset)
    for session in (s, restored):
        before = session.run.model_dump_json()
        assert not session.reroll_enchantment("hero", p.id, -1)
        assert not session.reroll_enchantment("hero", p.id, 2)
        assert session.run.model_dump_json() == before
        assert session.reroll_enchantment("hero", p.id, 1)
        assert session.run.equipment_instances[p.id].enchantments[0] == "ench_power"
        assert session.run.equipment_instances[p.id].enchantments[1] != "ench_ward"
    assert s.run == restored.run


def test_legacy_duplicates_migrate_once_preserving_each_owners_enchantments():
    s = pair()
    payload = s.run.model_dump(mode="json")
    payload.pop("equipment_instances")
    payload["inventory"] = ["guardian_helm", "guardian_helm", "traveler_cap"]
    for hero, enchant in zip(payload["party"], ("ench_power", "ench_ward")):
        hero["equipped_armor"] = {"head": "guardian_helm"}
        hero["item_enchantments"] = {"guardian_helm": [enchant]}
    migrated = RunState.model_validate(payload)
    ids = [h.equipped_armor["head"] for h in migrated.party]
    assert ids[0] != ids[1]
    assert migrated.equipment_instances[ids[0]].enchantments == ["ench_power"]
    assert migrated.equipment_instances[ids[1]].enchantments == ["ench_ward"]
    assert RunState.model_validate_json(migrated.model_dump_json()) == migrated


def test_v1_combat_checkpoint_migrates_both_projections_without_changing_turn():
    s = make_full_session()
    s.equip_weapon("hero", "staff")
    s.start_current_encounter()
    old = RunCheckpoint.from_session(s, mode="solo").model_dump(mode="json")
    old["schema_version"] = 1
    old["run"].pop("equipment_instances")
    old["run"].pop("equipment_initialized_for")
    old["run"]["inventory"] = ["traveler_cap"]
    for hero in (old["run"]["party"][0], old["combat"]["combatants"]["hero"]):
        hero["equipped_armor"] = {"head": "traveler_cap"}
        hero["item_enchantments"] = {"traveler_cap": ["ench_swiftness"]}
        hero.pop("equipment_instances")
        hero.pop("equipped_weapon_id")
    checkpoint = RunCheckpoint.model_validate(old)
    restored = checkpoint.restore_session(s.ruleset)
    hero = restored.run.party[0]
    actor = restored.combat_state.combatants["hero"]
    assert hero.equipped_armor == actor.equipped_armor
    assert hero.equipped_weapon_id == actor.equipped_weapon_id
    assert actor.current_hp == s.combat_state.combatants["hero"].current_hp
    assert restored.combat_state.turn_index == s.combat_state.turn_index
    assert restored.combat_engine.rng.getstate() == s.combat_engine.rng.getstate()


@pytest.mark.parametrize("boss,item", BOSS_REWARDS.items())
def test_boss_theme_and_sealed_fallback(boss, item):
    s = make_full_session()
    encounter = EncounterDef(id="boss", name="Boss", enemy_ids=[boss], is_boss=True)
    assert boss_reward_for(encounter, s.run.party) == item
    required = EQUIPMENT_DEFS[item].required_element
    if required:
        s.run.party[0].sealed_elements.add(required)
        fallback = boss_reward_for(encounter, s.run.party)
        assert fallback in ("amulet_of_vigor", "crown_of_ages")
        assert EQUIPMENT_DEFS[fallback].rarity == EQUIPMENT_DEFS[item].rarity


def test_equipment_drops_are_deterministic_and_do_not_drop_basic_or_boss_weapons():
    encounter = EncounterDef(id="elite", name="Elite", is_boss=True)
    for seed in range(50):
        a = roll_encounter_drops(encounter, 3, 5, random.Random(seed))
        assert a == roll_encounter_drops(encounter, 3, 5, random.Random(seed))
        assert all(EQUIPMENT_DEFS[d].random_drop for d in a[0])


def test_every_authored_boss_has_a_thematic_reward():
    from wyrdfall.domain.content import MVP_DUNGEON
    bosses = [e for e in MVP_DUNGEON.encounters if e.is_boss]
    assert len(bosses) == 12
    assert all(any(enemy in BOSS_REWARDS for enemy in e.enemy_ids) for e in bosses)


@pytest.mark.parametrize("sid", ["windrunner", "weaver"])
def test_new_set_behavior_resolves_in_combat(sid):
    from tests.test_group_triggers import _ruleset, _hero
    from wyrdfall.domain.combat import CombatEngine, Action
    from wyrdfall.domain.models import ActiveStatus
    s = make_full_session()
    wearer = s.run.party[0]
    for slot in ("head", "body", "legs"):
        p = add_equipment(s.run, f"{sid}_{slot}")
        s.equip_armor(wearer.id, slot, p.id)
    triggers = [e for e in wearer.passive_triggered_effects if e.source == f"{sid}_3"]
    ruleset = _ruleset()
    hero, enemy = _hero("a", triggers), _hero("enemy", is_player=False, hp=100, speed=1)
    hero.base_stats.crit_chance = 1 if sid == "windrunner" else 0
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero, _hero("b", speed=9)], [enemy])
    if sid == "weaver":
        state.combatants[enemy.id].statuses.append(ActiveStatus(status_id="mark", remaining_duration=2, source_id="b"))
    state.combatants[hero.id].current_resource = 0
    engine.resolve(state, Action(actor_id=hero.id, ability_id="strike", target_ids=[enemy.id]))
    if sid == "windrunner":
        assert state.combatants[hero.id].current_resource == 1
    else:
        assert state.combatants[hero.id].shield_hp == 5


@pytest.mark.parametrize("sid,trigger", [("windrunner", TriggerEvent.ON_CRIT), ("weaver", TriggerEvent.ON_TEAM_COMBO)])
def test_new_sets_gain_and_lose_behavior_exactly_once(sid, trigger):
    s = make_full_session()
    hero = s.run.party[0]
    for slot in ("head", "body", "legs"):
        p = add_equipment(s.run, f"{sid}_{slot}")
        assert s.equip_armor("hero", slot, p.id)
    effects = [e for e in hero.passive_triggered_effects if e.source == f"{sid}_3"]
    assert len(effects) == 1 and effects[0].trigger == trigger
    s._refresh_equipment(hero)
    assert len([e for e in hero.passive_triggered_effects if e.source == f"{sid}_3"]) == 1
    assert s.unequip_armor("hero", "head")
    assert not [e for e in hero.passive_triggered_effects if e.source == f"{sid}_3"]


def test_weapon_type_and_piece_are_independent_and_affixes_follow_piece():
    s = make_full_session(class_id="mistico")
    p = add_equipment(s.run, "forged_bow", enchantments=["ench_precision"])
    assert s.equip_weapon("hero", p.id)
    hero = s.run.party[0]
    assert hero.equipped_weapon_id == p.id and hero.equipped_weapon_type == "bow"
    assert "weapon_shot" in hero.abilities
    crit = hero.computed_stats(s.ruleset).crit_chance
    assert s.equip_weapon("hero", "bow")
    assert hero.computed_stats(s.ruleset).crit_chance == pytest.approx(crit - .04)
    assert p.enchantments == ["ench_precision"]


def test_comparison_is_read_only_and_keeps_talent_effects():
    s = make_full_session()
    hero = s.run.party[0]
    p = add_equipment(s.run, "traveler_cap", enchantments=["ench_swiftness"])
    before = s.run.model_dump_json()
    text = equipment_comparison(s.run, hero, p.id, s.ruleset, TALENT_TREES[_talent_tree_id_for(hero)])
    assert "Velocidade: +2.0" in text
    assert s.run.model_dump_json() == before


async def test_remote_transfer_is_authoritative_and_preserves_affixes(two_player_clients):
    server, host, guest = two_player_clients
    p = add_equipment(server.session.run, "guardian_helm", owner_id=guest.player_id, enchantments=["ench_power"])
    assert server.session.equip_armor(guest.player_id, "head", p.id)
    await server._broadcast_state()
    await wait_until(lambda: p.id in guest.get_run().equipment_instances)
    await guest.transfer_equipment(guest.player_id, "host", p.id)
    await wait_until(lambda: guest.get_run().equipment_instances[p.id].owner_id == "host")
    assert not next(h for h in host.get_run().party if h.id == guest.player_id).equipped_armor
    await host.equip_armor("host", "head", p.id)
    await wait_until(lambda: guest.get_run().party[0].equipped_armor.get("head") == p.id)
    assert guest.get_run().equipment_instances[p.id].enchantments == ["ench_power"]
    with pytest.raises(Exception, match="próprio personagem"):
        await guest.transfer_equipment("host", guest.player_id, p.id)


def test_transfer_protocol_round_trip():
    command = ClientTransferEquipment(character_id="hero", recipient_id="ally", item_id="gear_123", revision="r")
    assert decode_client_message(encode(command)) == command


def test_sealed_affixes_cannot_be_equipped_given_or_engraved_and_reroll_filters():
    s = pair()
    hero, ally = s.run.party
    ally.sealed_elements = set(DamageElement) - {DamageElement.PHYSICAL}
    p = add_equipment(s.run, "guardian_helm", owner_id=hero.id, enchantments=["ench_fire"])
    before = s.run.model_dump_json()
    assert not s.transfer_equipment(hero.id, ally.id, p.id)
    assert not s.equip_armor(ally.id, "head", p.id)
    assert s.run.model_dump_json() == before
    q = add_equipment(s.run, "guardian_helm", owner_id=ally.id, enchantments=["ench_power"])
    assert s.equip_armor(ally.id, "head", q.id)
    forge(s)
    before = s.run.model_dump_json()
    assert not s.socket_enchantment(ally.id, q.id, "ench_fire")
    assert s.run.model_dump_json() == before
    for _ in range(4):
        assert s.reroll_enchantment(ally.id, q.id, 0)
        assert q.enchantments[0] in {"ench_power", "ench_ward", "ench_vitality", "ench_swiftness", "ench_precision", "ench_resolve"}


def test_boss_reward_reaches_inventory_once_with_matching_material_and_enchantment():
    from tests.test_session import make_boss_only_session, play_encounter_to_completion
    s = make_boss_only_session()
    play_encounter_to_completion(s)
    assert s.encounter_victory
    s.dungeon.encounters[0].enemy_ids = ["hollow_knight"]  # isolate the reward table from boss difficulty
    s.collect_victory_reward_and_advance()
    pieces = [p for p in s.run.equipment_instances.values() if p.definition_id == "hollow_aegis"]
    assert len(pieces) == 1 and len(pieces[0].enchantments) == 1
    assert s.run.materials[Rarity.RARO] == 2
    before = s.run.model_dump_json()
    from wyrdfall.engine.session import SessionError
    with pytest.raises(SessionError):
        s.collect_victory_reward_and_advance()
    assert s.run.model_dump_json() == before


async def test_spent_materials_are_not_banked_after_abandon_or_duplicate_credit(tmp_path, monkeypatch):
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.persistence.store import load_meta_progression
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    client = app.start_new_run()
    s = client.session
    forge(s)
    piece = add_equipment(s.run, "guardian_helm")
    assert s.equip_armor(s.run.party[0].id, "head", piece.id)
    assert s.socket_enchantment(s.run.party[0].id, piece.id, "ench_power")
    assert s.reroll_enchantment(s.run.party[0].id, piece.id, 0)
    await client.abandon_run()
    app.bank_run_reward()
    app.bank_run_reward()
    saved = load_meta_progression(tmp_path / "profile.db")
    assert saved.materials[Rarity.RARO] == 3


def test_guild_unlock_produces_fresh_independent_pieces_each_run(tmp_path, monkeypatch):
    from wyrdfall.app import WyrdfallApp
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    app.meta.starting_gear = ["guardian_helm"]
    a = app.start_new_run().get_run()
    first = next(p for p in a.equipment_instances.values() if p.definition_id == "guardian_helm")
    first.enchantments.append("ench_ward")
    # Independent fresh session from the same unlocked catalog entry.
    b = RunState(run_id="another", seed=a.seed, dungeon_id=a.dungeon_id, party=[a.party[0].model_copy(deep=True)])
    second = add_equipment(b, app.meta.starting_gear[0], owner_id=b.party[0].id)
    assert first.id != second.id and not second.enchantments
    assert app.meta.starting_gear == ["guardian_helm"]


def test_future_equipment_and_checkpoint_versions_are_rejected():
    s = make_full_session()
    payload = s.run.model_dump(mode="json")
    payload["equipment_version"] = 2
    with pytest.raises(ValueError):
        RunState.model_validate(payload)
    checkpoint = RunCheckpoint.from_session(s, mode="solo").model_dump(mode="json")
    checkpoint["schema_version"] = 3
    with pytest.raises(ValueError):
        RunCheckpoint.model_validate(checkpoint)


async def test_duplicate_remote_engraving_charges_only_once(two_player_clients):
    from wyrdfall.net.protocol import ClientSocketEnchantment
    server, host, guest = two_player_clients
    forge(server.session)
    p = add_equipment(server.session.run, "guardian_helm", owner_id=guest.player_id)
    server.session.equip_armor(guest.player_id, "head", p.id)
    await server._broadcast_state()
    message = ClientSocketEnchantment(character_id=guest.player_id, item_id=p.id,
                                     enchantment_id="ench_power", revision=server._state_revision)
    await server._handle_client_message(guest.player_id, message)
    after = server.session.run.model_dump_json()
    await server._handle_client_message(guest.player_id, message)
    assert server.session.run.model_dump_json() == after
    assert server.session.run.currency_earned == 90
    assert p.enchantments == ["ench_power"]
