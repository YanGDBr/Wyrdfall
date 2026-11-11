"""The three group-play TriggerEvents of docs/design/11-habilidades.md §14:
ON_ALLY_DOWNED, ON_REVIVE, ON_TEAM_COMBO -- and the content that uses them."""

import random

import pytest

from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.cards import CARD_DEFS
from wyrdfall.domain.character import Character, Ruleset
from wyrdfall.domain.combat import Action, CombatEngine
from wyrdfall.domain.content import ENEMY_DEFS, build_ruleset
from wyrdfall.domain.enemies import instantiate_enemy
from wyrdfall.domain.models import (
    ActiveStatus,
    Effect,
    EffectKind,
    Modifier,
    ModifierKind,
    Stat,
    StatBlock,
    StatusEffectDef,
    TriggeredEffect,
    TriggerEvent,
)


def _ruleset() -> Ruleset:
    abilities = {
        "strike": Ability(id="strike", name="Strike", target_mode=TargetMode.SINGLE_ENEMY,
                          effects=[Effect(kind=EffectKind.DAMAGE, amount=4, scales_with=Stat.ATTACK, scale_factor=1.0)]),
        "revive": Ability(id="revive", name="Revive", target_mode=TargetMode.SINGLE_ALLY,
                          effects=[Effect(kind=EffectKind.REVIVE, amount=0.25)]),
    }
    statuses = {
        "strong": StatusEffectDef(id="strong", name="Strong", modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.2, source="strong")]),
        "mark": StatusEffectDef(id="mark", name="Mark", team_combo_bonus=0.5),
    }
    return Ruleset(abilities=abilities, statuses=statuses)


def _trigger(event: TriggerEvent, effect: Effect, source: str) -> TriggeredEffect:
    return TriggeredEffect(trigger=event, effect=effect, applies_to="self", source=source)


def _hero(cid, triggers=(), hp=30, speed=10, is_player=True):
    stats = StatBlock(max_hp=hp, attack=5, defense=0, speed=speed, crit_chance=0.0, max_resource=10)
    return Character(id=cid, name=cid.title(), class_id="w", base_stats=stats, current_hp=hp, current_resource=0,
                     abilities=["strike", "revive"], equipped_abilities=["strike", "revive"],
                     passive_triggered_effects=list(triggers), is_player=is_player)


def test_ally_downed_fires_on_the_survivors_of_the_downed_ones_side_only():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    strong = _trigger(TriggerEvent.ON_ALLY_DOWNED, Effect(kind=EffectKind.APPLY_STATUS, status_id="strong", duration=3), "t")
    a, b = _hero("a", (strong,)), _hero("b", (strong,), speed=9)
    enemy = _hero("goblin", (strong,), speed=1, is_player=False)
    enemy2 = _hero("goblin2", (strong,), speed=1, is_player=False)
    state = engine.start_encounter([a, b], [enemy, enemy2])
    # b goes down: a (same side) reacts, the enemies don't
    state.combatants["b"].current_hp = 1.0
    state.combatants["goblin"].base_stats.attack = 50
    state.turn_index = state.turn_order.index("goblin")
    engine._apply_effect(state, "goblin", "b", Effect(kind=EffectKind.DAMAGE, amount=50))
    assert state.combatants["b"].is_incapacitated
    assert any(s.status_id == "strong" for s in state.combatants["a"].statuses)
    assert not any(s.status_id == "strong" for s in state.combatants["goblin"].statuses)
    assert not any(s.status_id == "strong" for s in state.combatants["b"].statuses)  # not on the downed one
    # an enemy falling triggers its pack, not the party
    state.combatants["a"].statuses = []
    engine._apply_effect(state, "a", "goblin2", Effect(kind=EffectKind.DAMAGE, amount=500))
    assert not state.combatants["goblin2"].is_alive
    assert any(s.status_id == "strong" for s in state.combatants["goblin"].statuses)
    assert not any(s.status_id == "strong" for s in state.combatants["a"].statuses)


def test_on_revive_fires_on_the_revived_character():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    shield = _trigger(TriggerEvent.ON_REVIVE, Effect(kind=EffectKind.APPLY_SHIELD, amount=8), "t")
    healer, fighter = _hero("healer", speed=10), _hero("fighter", (shield,), speed=9)
    state = engine.start_encounter([healer, fighter], [_hero("goblin", speed=1, is_player=False)])
    state.combatants["fighter"].current_hp = 0.0
    engine.resolve(state, Action(actor_id="healer", ability_id="revive", target_ids=["fighter"]))
    assert state.combatants["fighter"].is_alive
    assert state.combatants["fighter"].shield_hp == pytest.approx(8)


def test_on_team_combo_fires_on_the_attacker_who_closed_the_combo():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    refund = _trigger(TriggerEvent.ON_TEAM_COMBO, Effect(kind=EffectKind.RESTORE_RESOURCE, amount=2), "t")
    a, b = _hero("a", (refund,), speed=10), _hero("b", speed=9)
    state = engine.start_encounter([a, b], [_hero("goblin", speed=1, is_player=False, hp=500)])
    goblin = state.combatants["goblin"]
    goblin.statuses.append(ActiveStatus(status_id="mark", remaining_duration=2, source_id="b"))
    state.combatants["a"].current_resource = 0
    engine.resolve(state, Action(actor_id="a", ability_id="strike", target_ids=["goblin"]))
    assert state.combatants["a"].current_resource == pytest.approx(2)
    assert not any(s.status_id == "mark" for s in goblin.statuses)
    # a's own mark never counts as a team combo, so nothing refunds
    goblin.statuses.append(ActiveStatus(status_id="mark", remaining_duration=2, source_id="a"))
    state.combatants["a"].current_resource = 0
    state.turn_index = state.turn_order.index("a")
    engine.resolve(state, Action(actor_id="a", ability_id="strike", target_ids=["goblin"]))
    assert state.combatants["a"].current_resource == 0


def test_the_content_wires_all_three_triggers():
    used = {t.trigger for card in CARD_DEFS.values() for t in card.triggered_effects}
    assert {TriggerEvent.ON_ALLY_DOWNED, TriggerEvent.ON_REVIVE, TriggerEvent.ON_TEAM_COMBO} <= used
    assert any(t.trigger == TriggerEvent.ON_ALLY_DOWNED for t in ENEMY_DEFS["lobo_de_gelo"].triggered_effects)
    # the pack in practice: two wolves, one falls, the other is Fortalecido
    ruleset = build_ruleset()
    engine = CombatEngine(ruleset, rng=random.Random(1))
    hero = _hero("hero")
    wolves = [instantiate_enemy(ENEMY_DEFS["lobo_de_gelo"], f"lobo_{i}") for i in range(2)]
    state = engine.start_encounter([hero], wolves)
    engine._apply_effect(state, "hero", "lobo_0", Effect(kind=EffectKind.DAMAGE, amount=500))
    assert not state.combatants["lobo_0"].is_alive
    assert any(s.status_id == "empowered" for s in state.combatants["lobo_1"].statuses)


def test_poise_break_and_combo_extend_fire_with_content_behind_them():
    ruleset = build_ruleset()
    engine = CombatEngine(ruleset, rng=random.Random(1))
    refund = _trigger(TriggerEvent.ON_POISE_BREAK, Effect(kind=EffectKind.RESTORE_RESOURCE, amount=3), "t")
    hero = _hero("hero", (refund,))
    hero.abilities = ["strike"]
    hero.equipped_abilities = ["strike"]
    target = instantiate_enemy(ENEMY_DEFS["goblin"], "goblin_0")
    target.base_stats.max_hp = 500
    target.current_hp = 500
    target.base_stats.max_poise = 1  # any poise damage breaks it
    state = engine.start_encounter([hero], [target])
    state.combatants["hero"].current_resource = 0
    state.turn_index = state.turn_order.index("hero")
    log = engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin_0"]))  # strike: poise_damage 3
    assert any("se quebra" in line for line in log)
    assert state.combatants["hero"].current_resource == pytest.approx(3)

    used = {t.trigger for card in CARD_DEFS.values() for t in card.triggered_effects}
    assert {TriggerEvent.ON_POISE_BREAK, TriggerEvent.ON_COMBO_EXTEND} <= used


def test_two_thorns_never_ping_pong_forever():
    # found by the headless bot: Espinhos on both sides recursed without end
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    thorns = TriggeredEffect(
        trigger=TriggerEvent.ON_TAKE_DAMAGE, effect=Effect(kind=EffectKind.DAMAGE, amount=1), applies_to="context", source="t",
    )
    a = _hero("a", (thorns,), hp=1000)
    b = _hero("goblin", (thorns,), hp=1000, speed=1, is_player=False)
    state = engine.start_encounter([a], [b])
    engine.resolve(state, Action(actor_id="a", ability_id="strike", target_ids=["goblin"]))
    # a bounded exchange happened, then it stopped
    assert 1000 - state.combatants["a"].current_hp <= 3
    assert state.combatants["goblin"].current_hp < 1000
