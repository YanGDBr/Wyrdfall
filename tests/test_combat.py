import random

import pytest

from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.character import Character, EnemyPhase, Ruleset
from wyrdfall.domain.combat import Action, CombatEngine, CombatError, ParryResult
from wyrdfall.domain.models import (
    Archetype,
    DamageElement,
    Effect,
    EffectKind,
    Stat,
    StatBlock,
    StatusEffectDef,
    TriggerEvent,
    TriggeredEffect,
)


def make_ruleset() -> Ruleset:
    strike = Ability(
        id="strike",
        name="Strike",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4, scales_with=Stat.ATTACK, scale_factor=1.0)],
        archetype_weight={Archetype.GUERREIRO: 1.0},
    )
    bite = Ability(
        id="bite",
        name="Bite",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2, scales_with=Stat.ATTACK, scale_factor=1.0)],
        tags=["melee"],
    )
    fireball = Ability(
        id="fireball",
        name="Fireball",
        resource_cost=3,
        target_mode=TargetMode.ALL_ENEMIES,
        effects=[
            Effect(
                kind=EffectKind.DAMAGE,
                amount=3,
                scales_with=Stat.ATTACK,
                scale_factor=0.5,
                damage_element=DamageElement.FIRE,
            )
        ],
        archetype_weight={Archetype.MISTICO: 1.0},
    )
    poise_strike = Ability(
        id="poise_strike",
        name="Poise Strike",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=1, poise_damage=5.0)],
    )
    return Ruleset(
        abilities={"strike": strike, "bite": bite, "fireball": fireball, "poise_strike": poise_strike}, statuses={}
    )


def make_hero(resource: float = 0) -> Character:
    stats = StatBlock(max_hp=30, attack=5, defense=1, speed=10, crit_chance=0.0, crit_mult=1.5, max_resource=resource)
    return Character(
        id="hero", name="Hero", class_id="warrior", base_stats=stats,
        current_hp=30, current_resource=resource, abilities=["strike", "fireball"],
        equipped_abilities=["strike", "fireball"],
    )


def make_goblin(instance_id: str = "goblin") -> Character:
    stats = StatBlock(max_hp=10, attack=2, defense=0, speed=5, crit_chance=0.0, crit_mult=1.5, max_resource=0)
    return Character(
        id=instance_id, name="Goblin", class_id="goblin", base_stats=stats,
        current_hp=10, current_resource=0, abilities=["bite"], is_player=False,
        equipped_abilities=["bite"],
    )


def test_faster_combatant_acts_first():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([make_hero()], [make_goblin()])
    assert state.current_actor_id() == "hero"


def test_full_fight_resolves_to_victory():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([make_hero()], [make_goblin()])

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    assert state.combatants["goblin"].current_hp == 1  # 4 + 5 attack - 0 defense = 9 dmg
    assert not state.is_over

    engine.resolve_ai_turn(state)  # goblin bites back
    assert state.combatants["hero"].current_hp == 27  # 2 + 2 attack - 1 defense = 3 dmg
    assert not state.is_over

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    assert state.is_over
    assert state.victory is True
    assert state.combatants["goblin"].current_hp == 0


def test_acting_out_of_turn_raises():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([make_hero()], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    with pytest.raises(CombatError):
        engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))


def test_insufficient_resource_raises():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([make_hero(resource=0)], [make_goblin()])
    with pytest.raises(CombatError):
        engine.resolve(state, Action(actor_id="hero", ability_id="fireball", target_ids=[]))


def test_all_enemies_target_mode_hits_every_living_enemy():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero(resource=3)
    state = engine.start_encounter([hero], [make_goblin("g1"), make_goblin("g2")])
    engine.resolve(state, Action(actor_id="hero", ability_id="fireball", target_ids=[]))
    # 3 + 5*0.5 = 5.5 raw - 0 defense = 5.5 -> max(1, 5.5) applied to both goblins
    assert state.combatants["g1"].current_hp == pytest.approx(4.5)
    assert state.combatants["g2"].current_hp == pytest.approx(4.5)


def test_defeat_when_party_wiped():
    engine = CombatEngine(make_ruleset(), rng=random.Random(7))
    hero = make_hero()
    hero.current_hp = 1
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    engine.resolve_ai_turn(state)
    assert state.is_over
    assert state.victory is False


# -- Fase 2: esquiva, bloqueio/escudo, roubo de vida, resistência a status ------


def test_dodge_avoids_damage_and_fires_on_dodge():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.base_stats.dodge_chance = 1.0
    hero.base_stats.max_resource = 5
    hero.current_resource = 0
    hero.passive_triggered_effects = [
        TriggeredEffect(
            trigger=TriggerEvent.ON_DODGE,
            effect=Effect(kind=EffectKind.RESTORE_RESOURCE, amount=1.0),
            applies_to="self",
        )
    ]
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    engine.resolve_ai_turn(state)  # goblin bites hero, hero always dodges
    assert state.combatants["hero"].current_hp == 30
    assert state.combatants["hero"].current_resource == 1  # ON_DODGE trigger restored 1


def test_block_reduces_damage_by_block_percent():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    goblin = make_goblin()
    goblin.base_stats.block_chance = 1.0
    goblin.base_stats.block_percent = 0.5
    state = engine.start_encounter([hero], [goblin])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # 4 + 5 attack - 0 defense = 9 raw, blocked -> 9 * 0.5 = 4.5
    assert state.combatants["goblin"].current_hp == pytest.approx(10 - 4.5)


def test_shield_absorbs_damage_before_hp():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    goblin = make_goblin()
    goblin.shield_hp = 5.0
    state = engine.start_encounter([hero], [goblin])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # 9 raw damage, 5 absorbed by the shield, 4 spills over to HP
    assert state.combatants["goblin"].shield_hp == 0.0
    assert state.combatants["goblin"].current_hp == 6.0


def test_lifesteal_heals_source_by_percent_of_damage_dealt():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.base_stats.lifesteal_percent = 0.5
    hero.current_hp = 20  # leave room to heal below the 30 max
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # 9 damage dealt -> heals 4.5
    assert state.combatants["hero"].current_hp == pytest.approx(24.5)


def test_status_resist_blocks_status_application():
    poison_bite = Ability(
        id="poison_bite",
        name="Poison Bite",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=3, stacks=1)],
    )
    ruleset = Ruleset(
        abilities={"poison_bite": poison_bite},
        statuses={"poisoned": StatusEffectDef(id="poisoned", name="Envenenado", max_stacks=3)},
    )
    attacker = Character(
        id="attacker", name="Attacker", class_id="x", base_stats=StatBlock(speed=10),
        current_hp=10, current_resource=0, abilities=["poison_bite"],
        equipped_abilities=["poison_bite"],
    )
    target = Character(
        id="target", name="Target", class_id="y", base_stats=StatBlock(speed=5, status_resist=1.0),
        current_hp=10, current_resource=0, abilities=[], is_player=False,
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([attacker], [target])
    engine.resolve(state, Action(actor_id="attacker", ability_id="poison_bite", target_ids=["target"]))
    assert state.combatants["target"].statuses == []


def test_status_immunity_blocks_application_even_with_zero_status_resist():
    poison_bite = Ability(
        id="poison_bite",
        name="Poison Bite",
        resource_cost=0,
        target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=3, stacks=1)],
    )
    ruleset = Ruleset(
        abilities={"poison_bite": poison_bite},
        statuses={"poisoned": StatusEffectDef(id="poisoned", name="Envenenado", max_stacks=3)},
    )
    attacker = Character(
        id="attacker", name="Attacker", class_id="x", base_stats=StatBlock(speed=10),
        current_hp=10, current_resource=0, abilities=["poison_bite"],
        equipped_abilities=["poison_bite"],
    )
    target = Character(
        id="target", name="Target", class_id="y", base_stats=StatBlock(speed=5),
        current_hp=10, current_resource=0, abilities=[], is_player=False,
        status_immunities={"poisoned"},
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([attacker], [target])
    engine.resolve(state, Action(actor_id="attacker", ability_id="poison_bite", target_ids=["target"]))
    assert state.combatants["target"].statuses == []


def test_resource_regen_restores_at_turn_start():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero(resource=0)
    hero.base_stats.resource_regen_per_turn = 2.0
    hero.base_stats.max_resource = 5.0
    state = engine.start_encounter([hero], [make_goblin()])
    # start_encounter already ran _begin_turn for the first actor (hero is faster)
    assert state.combatants["hero"].current_resource == 2.0


def test_drain_resource_moves_resource_from_target_to_source():
    drain = Ability(
        id="drain", name="Drain", resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DRAIN_RESOURCE, amount=3.0)],
    )
    ruleset = Ruleset(abilities={"drain": drain}, statuses={})
    leech = Character(
        id="leech", name="Leech", class_id="x", base_stats=StatBlock(speed=10, max_resource=10),
        current_hp=10, current_resource=0, abilities=["drain"],
        equipped_abilities=["drain"],
    )
    victim = Character(
        id="victim", name="Victim", class_id="y", base_stats=StatBlock(speed=5, max_resource=10),
        current_hp=10, current_resource=5, abilities=[], is_player=False,
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([leech], [victim])
    engine.resolve(state, Action(actor_id="leech", ability_id="drain", target_ids=["victim"]))
    assert state.combatants["victim"].current_resource == 2.0
    assert state.combatants["leech"].current_resource == 3.0


def test_drain_resource_caps_at_the_targets_remaining_resource():
    drain = Ability(
        id="drain", name="Drain", resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DRAIN_RESOURCE, amount=3.0)],
    )
    ruleset = Ruleset(abilities={"drain": drain}, statuses={})
    leech = Character(
        id="leech", name="Leech", class_id="x", base_stats=StatBlock(speed=10, max_resource=10),
        current_hp=10, current_resource=0, abilities=["drain"],
        equipped_abilities=["drain"],
    )
    victim = Character(
        id="victim", name="Victim", class_id="y", base_stats=StatBlock(speed=5, max_resource=10),
        current_hp=10, current_resource=1, abilities=[], is_player=False,
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([leech], [victim])
    engine.resolve(state, Action(actor_id="leech", ability_id="drain", target_ids=["victim"]))
    assert state.combatants["victim"].current_resource == 0.0
    assert state.combatants["leech"].current_resource == 1.0  # only what was actually there to steal


def test_bonus_vs_tags_amplifies_damage_against_a_tagged_target():
    smite = Ability(
        id="smite", name="Smite", resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=10.0, bonus_vs_tags=["undead"], bonus_vs_tags_bonus=0.5)],
    )
    ruleset = Ruleset(abilities={"smite": smite}, statuses={})
    caster = Character(
        id="caster", name="Caster", class_id="x", base_stats=StatBlock(speed=10),
        current_hp=10, current_resource=0, abilities=["smite"],
        equipped_abilities=["smite"],
    )
    undead_target = Character(
        id="target", name="Target", class_id="y", base_stats=StatBlock(speed=5, max_hp=30, defense=0),
        current_hp=30, current_resource=0, abilities=[], is_player=False, tags={"undead"},
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([caster], [undead_target])
    engine.resolve(state, Action(actor_id="caster", ability_id="smite", target_ids=["target"]))
    # raw 10 * 1.5 (bonus_vs_tags) = 15, -0 defense = 15
    assert state.combatants["target"].current_hp == pytest.approx(30.0 - 15.0)


def test_bonus_vs_tags_no_bonus_against_an_untagged_target():
    smite = Ability(
        id="smite", name="Smite", resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=10.0, bonus_vs_tags=["undead"], bonus_vs_tags_bonus=0.5)],
    )
    ruleset = Ruleset(abilities={"smite": smite}, statuses={})
    caster = Character(
        id="caster", name="Caster", class_id="x", base_stats=StatBlock(speed=10),
        current_hp=10, current_resource=0, abilities=["smite"],
        equipped_abilities=["smite"],
    )
    plain_target = Character(
        id="target", name="Target", class_id="y", base_stats=StatBlock(speed=5, max_hp=30, defense=0),
        current_hp=30, current_resource=0, abilities=[], is_player=False,
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([caster], [plain_target])
    engine.resolve(state, Action(actor_id="caster", ability_id="smite", target_ids=["target"]))
    assert state.combatants["target"].current_hp == pytest.approx(30.0 - 10.0)


def test_proc_chance_percent_can_guarantee_a_partial_chance_trigger():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.base_stats.proc_chance_percent = 1.0  # doubles effective chance
    hero.base_stats.max_resource = 5
    hero.current_resource = 0
    hero.passive_triggered_effects = [
        TriggeredEffect(
            trigger=TriggerEvent.ON_HIT,
            effect=Effect(kind=EffectKind.RESTORE_RESOURCE, amount=1.0),
            chance=0.5,
            applies_to="self",
        )
    ]
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # base chance 0.5 boosted by +100% proc bonus -> effective 1.0, guaranteed proc
    assert state.combatants["hero"].current_resource == 1.0


def test_healing_done_percent_amplifies_heal_amount():
    heal = Ability(
        id="heal", name="Heal", resource_cost=0, target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.HEAL, amount=4.0)],
    )
    ruleset = Ruleset(abilities={"heal": heal}, statuses={})
    healer = Character(
        id="healer", name="Healer", class_id="x",
        base_stats=StatBlock(speed=10, healing_done_percent=0.5, max_hp=30),
        current_hp=20, current_resource=0, abilities=["heal"],
        equipped_abilities=["heal"],
    )
    dummy = Character(
        id="dummy", name="Dummy", class_id="y", base_stats=StatBlock(speed=1),
        current_hp=1, current_resource=0, abilities=[], is_player=False,
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([healer], [dummy])
    engine.resolve(state, Action(actor_id="healer", ability_id="heal", target_ids=[]))
    # base heal 4 * 1.5 = 6
    assert state.combatants["healer"].current_hp == pytest.approx(26.0)


def test_healing_received_percent_dampens_heal_amount_on_the_target():
    heal_ally = Ability(
        id="heal_ally", name="Heal Ally", resource_cost=0, target_mode=TargetMode.SINGLE_ALLY,
        effects=[Effect(kind=EffectKind.HEAL, amount=10.0)],
    )
    ruleset = Ruleset(abilities={"heal_ally": heal_ally}, statuses={})
    healer = Character(
        id="healer", name="Healer", class_id="x", base_stats=StatBlock(speed=10, max_hp=30),
        current_hp=30, current_resource=0, abilities=["heal_ally"],
        equipped_abilities=["heal_ally"],
    )
    # Renascido's own -30% penalty (docs/design/04-racas.md) is exactly
    # this stat's real content source.
    ally = Character(
        id="ally", name="Ally", class_id="y",
        base_stats=StatBlock(speed=5, max_hp=30, healing_received_percent=-0.30),
        current_hp=10, current_resource=0, abilities=[],
        equipped_abilities=[],
    )
    goblin = make_goblin()
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([healer, ally], [goblin])
    engine.resolve(state, Action(actor_id="healer", ability_id="heal_ally", target_ids=["ally"]))
    # base heal 10 * (1 - 0.30) = 7
    assert state.combatants["ally"].current_hp == pytest.approx(17.0)


def test_physical_vulnerability_percent_amplifies_physical_damage_taken():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    goblin = make_goblin()
    goblin.base_stats.max_hp = 30
    goblin.current_hp = 30
    # Fada's own +20% (docs/design/04-racas.md's "-20% Físico") is
    # exactly this stat's real content source.
    goblin.base_stats.physical_vulnerability_percent = 0.20
    state = engine.start_encounter([hero], [goblin])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # raw 9 - 0 defense = 9, * 1.2 = 10.8
    assert state.combatants["goblin"].current_hp == pytest.approx(30 - 10.8)


def test_armor_penetration_percent_reduces_effective_defense():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.base_stats.armor_penetration_percent = 0.5
    goblin = make_goblin()
    goblin.base_stats.defense = 4.0
    state = engine.start_encounter([hero], [goblin])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # raw 9, effective defense = 4*(1-0.5)=2, damage = 7
    assert state.combatants["goblin"].current_hp == pytest.approx(3.0)


def test_crit_resist_can_fully_cancel_crit_chance():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.base_stats.crit_chance = 0.9
    hero.base_stats.crit_mult = 3.0
    goblin = make_goblin()
    goblin.base_stats.crit_resist = 0.9
    state = engine.start_encounter([hero], [goblin])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # effective crit chance = 0.9 - 0.9 = 0 -> never crits -> raw 9 - 0 defense = 9
    assert state.combatants["goblin"].current_hp == pytest.approx(1.0)


# -- Fase 2: elementos Fogo e Gelo -----------------------------------------------


def test_fire_resistance_reduces_elemental_damage():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero(resource=3)
    goblin = make_goblin()
    goblin.base_stats.fire_resist = 0.5
    state = engine.start_encounter([hero], [goblin])
    # fireball vs a lone enemy: 3 + 5*0.5 = 5.5 raw, halved by 50% fire resist
    engine.resolve(state, Action(actor_id="hero", ability_id="fireball", target_ids=[]))
    assert state.combatants["goblin"].current_hp == pytest.approx(10 - 2.75)


def test_fire_weakness_amplifies_elemental_damage():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero(resource=3)
    goblin = make_goblin()
    goblin.base_stats.fire_resist = -0.5  # weak to fire
    state = engine.start_encounter([hero], [goblin])
    engine.resolve(state, Action(actor_id="hero", ability_id="fireball", target_ids=[]))
    assert state.combatants["goblin"].current_hp == pytest.approx(10 - 8.25)


def test_parry_pauses_combat_instead_of_resolving_damage():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.can_parry = True
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    hp_before = state.combatants["hero"].current_hp

    engine.resolve_ai_turn(state)  # goblin's "bite" is melee vs a can_parry hero

    assert state.pending_parry is not None
    assert state.pending_parry.attacker_id == "goblin"
    assert state.pending_parry.defender_id == "hero"
    assert state.pending_parry.ability_id == "bite"
    assert state.combatants["hero"].current_hp == hp_before  # nothing resolved yet
    assert not state.is_over  # the turn hasn't advanced either


def test_parry_success_cancels_damage_and_counter_attacks():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.can_parry = True
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # goblin is now at 10 - 9 = 1 HP
    engine.resolve_ai_turn(state)
    assert state.pending_parry is not None

    engine.resolve_parry(state, ParryResult.SUCCESS)

    assert state.pending_parry is None
    assert state.combatants["hero"].current_hp == 30  # attack fully cancelled
    # counter: hero's 5 ATTACK vs goblin's 1 remaining HP -> defeated
    assert state.combatants["goblin"].current_hp == 0
    assert state.is_over
    assert state.victory is True


def test_parry_failure_applies_damage_with_penalty():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.can_parry = True
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    engine.resolve_ai_turn(state)
    assert state.pending_parry is not None

    engine.resolve_parry(state, ParryResult.FAILURE)

    assert state.pending_parry is None
    # bite: (2 + 2 attack) * 1.20 fail penalty = 4.8, - 1 defense = 3.8
    assert state.combatants["hero"].current_hp == pytest.approx(30 - 3.8)


def test_parry_declined_applies_damage_normally():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.can_parry = True
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    engine.resolve_ai_turn(state)
    assert state.pending_parry is not None

    engine.resolve_parry(state, ParryResult.DECLINED)

    assert state.pending_parry is None
    # bite: 2 + 2 attack - 1 defense = 3, no penalty or bonus
    assert state.combatants["hero"].current_hp == 27


def test_non_parrying_target_never_pauses_combat():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()  # can_parry defaults to False
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))

    engine.resolve_ai_turn(state)

    assert state.pending_parry is None
    assert state.combatants["hero"].current_hp == 27  # bite resolved immediately, as before Parry existed


def test_resolve_parry_without_a_pending_one_raises():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([make_hero()], [make_goblin()])
    with pytest.raises(CombatError):
        engine.resolve_parry(state, ParryResult.DECLINED)


def test_elemental_damage_percent_amplifies_before_resistance():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero(resource=3)
    hero.base_stats.elemental_damage_percent = 0.5
    goblin = make_goblin()
    state = engine.start_encounter([hero], [goblin])
    # 5.5 raw * 1.5 = 8.25, no resistance
    engine.resolve(state, Action(actor_id="hero", ability_id="fireball", target_ids=[]))
    assert state.combatants["goblin"].current_hp == pytest.approx(10 - 8.25)


# -- Fase 4: postura/stagger, fases de chefe -------------------------------------


def test_breaking_poise_stuns_the_target_for_exactly_one_turn():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.abilities = ["poise_strike"]
    hero.equipped_abilities = ["poise_strike"]
    goblin = make_goblin()
    goblin.base_stats.max_poise = 5.0
    goblin.current_poise = 5.0
    state = engine.start_encounter([hero], [goblin])
    assert state.current_actor_id() == "hero"

    engine.resolve(state, Action(actor_id="hero", ability_id="poise_strike", target_ids=["goblin"]))
    # poise_strike deals exactly 5 poise damage -- breaks and resets to max
    assert state.combatants["goblin"].current_poise == pytest.approx(5.0)
    # the goblin's turn was skipped entirely and consumed -- back to hero already
    assert state.current_actor_id() == "hero"
    assert state.combatants["goblin"].stunned_turns == 0


def test_poise_damage_is_a_no_op_against_a_target_with_no_poise_bar():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.abilities = ["poise_strike"]
    hero.equipped_abilities = ["poise_strike"]
    goblin = make_goblin()  # max_poise defaults to 0.0 -- no poise bar at all
    state = engine.start_encounter([hero], [goblin])

    engine.resolve(state, Action(actor_id="hero", ability_id="poise_strike", target_ids=["goblin"]))
    assert state.combatants["goblin"].current_poise == 0.0
    assert state.combatants["goblin"].stunned_turns == 0
    # the goblin's turn was never skipped -- it still gets to act normally
    assert state.current_actor_id() == "goblin"


def make_phased_boss(instance_id: str = "boss", max_hp: float = 18.0) -> Character:
    stats = StatBlock(max_hp=max_hp, attack=1, defense=0, speed=1, crit_chance=0.0, crit_mult=1.5, max_resource=0)
    phases = [
        EnemyPhase(hp_ceiling=1.0, abilities=["bite"]),
        EnemyPhase(hp_ceiling=0.5, abilities=["strike"]),
    ]
    return Character(
        id=instance_id, name="Boss", class_id="boss", base_stats=stats,
        current_hp=max_hp, current_resource=0, abilities=["bite"], enemy_phases=phases, is_player=False,
        equipped_abilities=["bite"],
    )


def test_boss_swaps_moveset_when_crossing_its_hp_phase_threshold():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    boss = make_phased_boss()
    state = engine.start_encounter([hero], [boss])
    assert state.combatants["boss"].current_phase_index == 0
    assert state.combatants["boss"].abilities == ["bite"]

    # strike deals exactly 9 (4 + 5 attack - 0 defense, see test_full_fight_resolves_to_victory) --
    # 18 - 9 = 9, exactly half of max_hp, landing right on the phase-2 threshold.
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["boss"]))
    boss_after = state.combatants["boss"]
    assert boss_after.current_hp == pytest.approx(9.0)
    assert boss_after.current_phase_index == 1
    assert boss_after.abilities == ["strike"]


def test_a_phaseless_enemy_never_transitions():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    goblin = make_goblin()  # enemy_phases defaults to [] -- untouched by the phase system
    state = engine.start_encounter([hero], [goblin])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    assert state.combatants["goblin"].current_phase_index == 0
    assert state.combatants["goblin"].abilities == ["bite"]


def test_on_death_all_enemies_trigger_fires_against_the_opposite_team():
    ruleset = make_ruleset()
    engine = CombatEngine(ruleset, rng=random.Random(1))
    hero = make_hero()
    goblin = make_goblin()
    goblin.current_hp = 9  # exactly one "strike" (9 dmg) away from death
    goblin.passive_triggered_effects = [
        TriggeredEffect(
            trigger=TriggerEvent.ON_DEATH,
            effect=Effect(kind=EffectKind.DAMAGE, amount=3.0),
            applies_to="all_enemies",
            source="test_explosion",
        )
    ]
    state = engine.start_encounter([hero], [goblin])

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    assert not state.combatants["goblin"].is_alive
    # the dying goblin's explosion should have hit the hero (its "enemy"):
    # 3 raw - 1 defense = 2 damage.
    assert state.combatants["hero"].current_hp == pytest.approx(28.0)


def test_dead_combatants_still_fire_on_death_but_nothing_else():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    goblin = make_goblin()
    goblin.current_hp = 9
    goblin.passive_triggered_effects = [
        TriggeredEffect(
            trigger=TriggerEvent.ON_TURN_START,
            effect=Effect(kind=EffectKind.RESTORE_RESOURCE, amount=1.0),
            applies_to="self",
        )
    ]
    state = engine.start_encounter([hero], [goblin])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # the goblin died mid-round -- ON_TURN_START must never fire for a corpse
    assert state.combatants["goblin"].current_resource == 0


# -- Fase 5: afinidade por uso (archetype_usage / elemental_usage) --------------


def test_casting_an_ability_adds_its_archetype_weight_exactly_once():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    goblin = make_goblin()
    state = engine.start_encounter([hero], [goblin])

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    assert state.combatants["hero"].archetype_usage == {Archetype.GUERREIRO: 1.0}


def test_an_all_enemies_ability_still_only_adds_its_archetype_weight_once():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero(resource=3)
    state = engine.start_encounter([hero], [make_goblin("g1"), make_goblin("g2")])

    engine.resolve(state, Action(actor_id="hero", ability_id="fireball", target_ids=[]))
    # fireball hit 2 targets but the archetype weight is per-cast, not per-target
    assert state.combatants["hero"].archetype_usage == {Archetype.MISTICO: 1.0}


def test_a_declined_parry_still_counts_the_attackers_cast():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.can_parry = True
    goblin = make_goblin()
    goblin.abilities = ["bite"]  # melee -> parryable, but bite carries no archetype_weight
    state = engine.start_encounter([hero], [goblin])

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    engine.resolve_ai_turn(state)  # goblin's bite pauses on a pending parry
    assert state.pending_parry is not None
    engine.resolve_parry(state, ParryResult.DECLINED)
    # the goblin's bite was still "cast" even though it carries no weight itself --
    # this test only needs the hero's own strike to have registered.
    assert state.combatants["hero"].archetype_usage == {Archetype.GUERREIRO: 1.0}


def test_elemental_usage_accumulates_by_damage_dealt_including_from_a_triggered_effect():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero(resource=3)
    hero.passive_triggered_effects = [
        TriggeredEffect(
            trigger=TriggerEvent.ON_HIT,
            effect=Effect(kind=EffectKind.DAMAGE, amount=2.0, damage_element=DamageElement.ICE),
            applies_to="context",
            source="test_frost_rider",
        )
    ]
    goblin = make_goblin()
    state = engine.start_encounter([hero], [goblin])

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    usage = state.combatants["hero"].elemental_usage
    assert usage.get(DamageElement.PHYSICAL) == pytest.approx(9.0)  # strike's own damage
    assert usage.get(DamageElement.ICE) == pytest.approx(2.0)  # the ON_HIT rider, not from an ability cast


# -- Fase 5c: armas e runas -------------------------------------------------------


def test_weapon_locked_ability_is_excluded_from_the_pool_until_equipped():
    ruleset = make_ruleset()
    ruleset.abilities["bow_shot"] = Ability(
        id="bow_shot", name="Bow Shot", resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2, scales_with=Stat.ATTACK, scale_factor=1.0)],
        required_weapon_type="bow",
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    hero = make_hero()
    hero.abilities = ["bow_shot"]
    hero.equipped_abilities = ["bow_shot"]
    state = engine.start_encounter([hero], [make_goblin()])

    assert engine.legal_abilities(state, "hero") == []
    state.combatants["hero"].equipped_weapon_type = "bow"
    assert [a.id for a in engine.legal_abilities(state, "hero")] == ["bow_shot"]
    state.combatants["hero"].equipped_weapon_type = "staff"
    assert engine.legal_abilities(state, "hero") == []


def test_casting_a_weapon_locked_ability_without_the_right_weapon_raises():
    ruleset = make_ruleset()
    ruleset.abilities["bow_shot"] = Ability(
        id="bow_shot", name="Bow Shot", resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2, scales_with=Stat.ATTACK, scale_factor=1.0)],
        required_weapon_type="bow",
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    hero = make_hero()
    hero.abilities = ["bow_shot"]
    hero.equipped_abilities = ["bow_shot"]
    state = engine.start_encounter([hero], [make_goblin()])

    with pytest.raises(CombatError):
        engine.resolve(state, Action(actor_id="hero", ability_id="bow_shot", target_ids=["goblin"]))


def test_weapon_damage_percent_applies_universally_regardless_of_element():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.base_stats.weapon_damage_percent = 0.5
    goblin = make_goblin()
    goblin.base_stats.max_hp = 30.0
    goblin.current_hp = 30.0
    state = engine.start_encounter([hero], [goblin])

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    # strike: 4 + 5 attack = 9 raw * 1.5 (weapon) = 13.5, -0 defense = 13.5
    assert state.combatants["goblin"].current_hp == pytest.approx(30.0 - 13.5)


def test_chain_percent_hits_a_second_random_target_on_the_same_side():
    ruleset = make_ruleset()
    ruleset.abilities["chain_bolt"] = Ability(
        id="chain_bolt", name="Chain Bolt", resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=10, damage_element=DamageElement.LIGHTNING, chain_percent=0.5)],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    hero = make_hero()
    hero.abilities = ["chain_bolt"]
    hero.equipped_abilities = ["chain_bolt"]
    goblin1 = make_goblin("goblin1")
    goblin1.base_stats.max_hp = 30
    goblin1.current_hp = 30
    goblin2 = make_goblin("goblin2")
    goblin2.base_stats.max_hp = 30
    goblin2.current_hp = 30
    state = engine.start_encounter([hero], [goblin1, goblin2])

    engine.resolve(state, Action(actor_id="hero", ability_id="chain_bolt", target_ids=["goblin1"]))
    assert state.combatants["goblin1"].current_hp == pytest.approx(20.0)
    # chain: 50% of the 10 dealt to goblin1 also hits goblin2
    assert state.combatants["goblin2"].current_hp == pytest.approx(25.0)


def test_chain_percent_is_a_no_op_with_no_other_living_target():
    ruleset = make_ruleset()
    ruleset.abilities["chain_bolt"] = Ability(
        id="chain_bolt", name="Chain Bolt", resource_cost=0, target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=10, damage_element=DamageElement.LIGHTNING, chain_percent=0.5)],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    hero = make_hero()
    hero.abilities = ["chain_bolt"]
    hero.equipped_abilities = ["chain_bolt"]
    goblin = make_goblin()
    goblin.base_stats.max_hp = 30
    goblin.current_hp = 30
    state = engine.start_encounter([hero], [goblin])

    engine.resolve(state, Action(actor_id="hero", ability_id="chain_bolt", target_ids=["goblin"]))
    assert state.combatants["goblin"].current_hp == pytest.approx(20.0)
