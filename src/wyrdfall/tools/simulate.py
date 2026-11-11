"""Headless playtest: seeded solo runs driven by a simple bot, so the
"primeiro palpite" numbers every design doc flags can be tuned against
data instead of feel (docs/design/00-README.md, 09-roadmap.md's
"playtest da Fase 5b").

    python -m wyrdfall.tools.simulate --runs 20 --portal portao_do_tumulo
    python -m wyrdfall.tools.simulate --classes mistico,guardiao --races elf,orc --seed 7

The bot is deliberately naive (no minigames, no parry attempts, greedy
ability choice, spends every talent/attribute point immediately) -- it
measures the floor of what the content allows, not skilled play. It is
pure engine: no Textual, no network, no save file.
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import uuid
from collections import Counter
from dataclasses import dataclass, field

from wyrdfall.domain.abilities import TargetMode
from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.combat import Action, ParryResult
from wyrdfall.domain.content import CLASS_DEFS, CONSUMABLE_DEFS, TALENT_TREES, build_dungeon_for_portal, build_ruleset
from wyrdfall.domain.contracts import contract_offer_for
from wyrdfall.domain.items import EQUIPMENT_DEFS
from wyrdfall.domain.loadout import PlayerLoadout, build_character_from_loadout
from wyrdfall.domain.models import Archetype, EffectKind
from wyrdfall.domain.races import RACE_DEFS
from wyrdfall.domain.run import RunState
from wyrdfall.domain.specializations import evolution_offers
from wyrdfall.domain.weapons import WEAPON_TYPE_DEFS
from wyrdfall.engine.session import EVOLUTION_LEVEL, EVOLUTION_STAGE2_LEVEL, GameSession, SessionError

# what a player of each archetype naturally invests in (03-atributos.md)
_ATTRIBUTE_PREFERENCE: dict[Archetype, list[Atributo]] = {
    Archetype.GUERREIRO: [Atributo.STRENGTH, Atributo.CONSTITUTION, Atributo.DEXTERITY, Atributo.LUCK, Atributo.INTELLIGENCE, Atributo.WISDOM],
    Archetype.PATRULHEIRO: [Atributo.DEXTERITY, Atributo.LUCK, Atributo.CONSTITUTION, Atributo.STRENGTH, Atributo.INTELLIGENCE, Atributo.WISDOM],
    Archetype.MISTICO: [Atributo.INTELLIGENCE, Atributo.WISDOM, Atributo.CONSTITUTION, Atributo.LUCK, Atributo.DEXTERITY, Atributo.STRENGTH],
    Archetype.GUARDIAO: [Atributo.CONSTITUTION, Atributo.STRENGTH, Atributo.WISDOM, Atributo.DEXTERITY, Atributo.LUCK, Atributo.INTELLIGENCE],
}
# a run that never ends (a bug, or an unkillable stalemate) must not hang the tool
MAX_TURNS_PER_ENCOUNTER = 300
HEAL_BELOW_FRACTION = 0.40
POTION_BELOW_FRACTION = 0.30
POTION_BETWEEN_FIGHTS_BELOW = 0.50


@dataclass(frozen=True)
class BotSkill:
    """How good the simulated player is at the reflex parts of the game.
    novato: no Parry unlocked, minigames at their floor. veterano: Parry
    unlocked and landed 70% of the time, minigames 70% scored."""

    name: str = "novato"
    can_parry: bool = False
    parry_success_rate: float = 0.0
    minigame_score: float = 0.0


NOVATO = BotSkill()
VETERANO = BotSkill(name="veterano", can_parry=True, parry_success_rate=0.7, minigame_score=0.7)
SKILLS = {"novato": NOVATO, "veterano": VETERANO}


@dataclass
class RunReport:
    class_id: str
    race_id: str
    seed: int
    victory: bool
    floor_reached: int
    total_floors: int
    died_at: str | None  # encounter id, None on victory
    level: int
    turns: int
    specialization_id: str | None
    stage2_id: str | None


@dataclass
class Aggregate:
    label: str
    reports: list[RunReport] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return sum(r.victory for r in self.reports) / max(1, len(self.reports))

    @property
    def mean_floor(self) -> float:
        return statistics.fmean(r.floor_reached for r in self.reports) if self.reports else 0.0

    @property
    def deaths_by_encounter(self) -> Counter:
        return Counter(r.died_at for r in self.reports if r.died_at is not None)


# -- the bot ---------------------------------------------------------------------


def _pick_action(session: GameSession, actor_id: str, skill: BotSkill = NOVATO) -> Action:
    """Greedy: heal if hurt and a heal is on the bar, else the damage
    ability with the biggest flat+scaled amount on the lowest-HP enemy,
    else whatever comes first (Defender at worst)."""
    engine = session.combat_engine
    state = session.combat_state
    actor = state.combatants[actor_id]
    stats = actor.computed_stats(session.ruleset)
    legal = engine.legal_abilities(state, actor_id)

    def targets_for(ability):
        ids = engine.legal_target_ids(state, actor_id, ability)
        if not ability.requires_target:
            return []
        if not ids:
            return None
        enemies = [cid for cid in ids if not state.combatants[cid].is_player]
        pool = enemies or ids
        return [min(pool, key=lambda cid: state.combatants[cid].current_hp)]

    hp_fraction = actor.current_hp / max(1.0, stats.max_hp)
    if hp_fraction < HEAL_BELOW_FRACTION:
        for ability in legal:
            if any(e.kind == EffectKind.HEAL for e in ability.effects) and ability.resource_cost <= actor.current_resource:
                allies = [cid for cid in engine.legal_target_ids(state, actor_id, ability) if state.combatants[cid].is_player]
                target = [actor_id] if actor_id in allies else allies[:1]
                return Action(actor_id=actor_id, ability_id=ability.id, target_ids=target if ability.requires_target else [])

    best, best_value, best_targets = None, -1.0, []
    for ability in legal:
        damage = sum(e.resolve_amount(stats) for e in ability.effects if e.kind == EffectKind.DAMAGE)
        if damage <= 0:
            continue
        targets = targets_for(ability)
        if targets is None:
            continue
        if ability.challenge is not None:  # the bot's minigame score scales the ability
            damage *= ability.challenge.min_factor + (1.0 - ability.challenge.min_factor) * skill.minigame_score
        if ability.target_mode == TargetMode.ALL_ENEMIES:
            damage *= sum(1 for cid in state.enemy_ids() if state.alive(cid))  # an AoE is worth its whole room
        if damage > best_value:
            best, best_value, best_targets = ability, damage, targets
    if best is not None:
        score = skill.minigame_score if best.challenge is not None else None
        return Action(actor_id=actor_id, ability_id=best.id, target_ids=best_targets, challenge_score=score)
    fallback = next((a for a in legal if a.universal), legal[0])
    targets = targets_for(fallback) or []
    return Action(actor_id=actor_id, ability_id=fallback.id, target_ids=targets)


def _maybe_drink(session: GameSession, actor_id: str) -> bool:
    actor = session.combat_state.combatants[actor_id]
    if actor.current_hp / max(1.0, actor.computed_stats(session.ruleset).max_hp) >= POTION_BELOW_FRACTION:
        return False
    for consumable_id in list(session.run.consumables):
        consumable = CONSUMABLE_DEFS.get(consumable_id)
        if consumable is None or consumable.teaches_ability:
            continue
        if consumable.heal_fraction > 0:
            try:
                session.use_consumable(actor_id, consumable_id)
                return True
            except SessionError:
                return False
    return False


def _spend_points(session: GameSession, character_id: str) -> None:
    character = next(c for c in session.run.party if c.id == character_id)
    for _ in range(20):
        offers = evolution_offers(character)
        level_needed = EVOLUTION_LEVEL if character.specialization_id is None else EVOLUTION_STAGE2_LEVEL
        if offers and character.level >= level_needed and session.evolve_specialization(character_id, offers[0].id):
            continue
        break
    for _ in range(50):
        if character.build.talent_tree.points_available <= 0:
            break
        tree = session.talent_trees.get(_tree_id(session, character))
        if tree is None:
            break
        nodes = tree.allocatable_nodes(character.build.talent_tree.allocated)
        if not nodes or not session.allocate_talent(character_id, nodes[0]):
            break
    preferred = _ATTRIBUTE_PREFERENCE.get(character.base_archetype, _ATTRIBUTE_PREFERENCE[Archetype.GUERREIRO])
    for _ in range(50):
        if character.attribute_points_available <= 0:
            break
        if not any(session.allocate_attribute(character_id, attribute) for attribute in preferred):
            break
    if character.card_offer:
        session.choose_card(character_id, character.card_offer[0])
    _manage_gear(session, character)


def _manage_gear(session: GameSession, character) -> None:
    """What any player does between fights: pick a weapon that scales with
    the class's main attribute, wear whatever dropped, socket owned runes
    into body slots, and fill free Active Ability Slots."""
    if character.equipped_weapon_type is None:
        main = _ATTRIBUTE_PREFERENCE.get(character.base_archetype, _ATTRIBUTE_PREFERENCE[Archetype.GUERREIRO])[0]
        weapon = max(WEAPON_TYPE_DEFS.values(), key=lambda w: w.scaling.get(main, 0.0))
        session.equip_weapon(character.id, weapon.id)
    run = session.run
    for item_id in list(run.inventory):
        from wyrdfall.domain.items import item_definition
        item = item_definition(run, item_id)
        if item is None:
            continue
        if item.slot == "accessory":
            session.equip_accessory(character.id, item_id)
        elif item.slot == "weapon":
            if item.weapon_type_id == character.equipped_weapon_type and not item.id.startswith("basic_"):
                session.equip_weapon(character.id, item_id)
        elif character.equipped_armor.get(item.slot) is None:
            session.equip_armor(character.id, item.slot, item_id)
    for rune_id in list(run.rune_inventory):
        if not session.socket_rune(character.id, rune_id):
            break
    for ability_id in list(character.abilities):
        if ability_id not in character.equipped_abilities:
            session.equip_ability(character.id, ability_id)


def _tree_id(session: GameSession, character) -> str | None:
    from wyrdfall.engine.session import _talent_tree_id_for

    return _talent_tree_id_for(character)


def _play_encounter(session: GameSession, hero_id: str, skill: BotSkill, rng: random.Random) -> int:
    state = session.start_current_encounter()
    turns = 0
    while not state.is_over and turns < MAX_TURNS_PER_ENCOUNTER:
        turns += 1
        if state.pending_parry is not None:
            if skill.parry_success_rate <= 0:
                result = ParryResult.DECLINED
            else:
                result = ParryResult.SUCCESS if rng.random() < skill.parry_success_rate else ParryResult.FAILURE
            session.resolve_parry_response(state.pending_parry.defender_id, result)
            continue
        actor = state.combatants[state.current_actor_id()]
        if actor.acts_automatically:
            session.resolve_ai_turn()
            continue
        if _maybe_drink(session, actor.id):
            continue
        session.submit_action(_pick_action(session, actor.id, skill))
    return turns


def _drink_between_fights(session: GameSession, hero_id: str) -> None:
    """Any player tops up before walking into the next room when hurt."""
    hero = next(c for c in session.run.party if c.id == hero_id)
    while session.run.consumables and hero.current_hp < POTION_BETWEEN_FIGHTS_BELOW * hero.computed_stats(session.ruleset).max_hp:
        potion = next((cid for cid in session.run.consumables if CONSUMABLE_DEFS[cid].heal_fraction > 0), None)
        if potion is None:
            return
        session.use_consumable(hero_id, potion)


def _resolve_non_combat_node(session: GameSession, hero_id: str) -> None:
    room = session.current_room_type
    hero = session.run.party[0]
    if room == "rest":
        hurt = hero.current_hp < 0.6 * hero.computed_stats(session.ruleset).max_hp
        session.resolve_rest("acampar" if hurt else "meditar")
    elif room == "event":
        event = session.current_event
        # the safest-looking option: no currency cost, first listed
        option = next((o for o in event.options if o.currency_delta >= 0), event.options[0])
        session.resolve_event(option.id)
    elif room in ("shop", "forge"):
        session.leave_node()
    else:
        raise SessionError(f"unknown room type {room!r}")


def simulate_run(
    class_id: str, race_id: str = "human", seed: int = 1, portal_id: str = "portao_do_tumulo",
    skill: BotSkill = NOVATO,
) -> RunReport:
    ruleset = build_ruleset()
    loadout = PlayerLoadout(class_id=class_id, race_id=race_id, can_parry=skill.can_parry)
    hero = build_character_from_loadout("hero", "Bot", loadout, ruleset)
    rng = random.Random(seed * 31 + 7)  # the bot's own reflexes, apart from the run's streams
    dungeon = build_dungeon_for_portal(portal_id)
    run = RunState(run_id=uuid.uuid4().hex[:8], seed=seed, dungeon_id=dungeon.id, party=[hero])
    run.contract_offer = contract_offer_for(run.seed)
    session = GameSession(run, ruleset, TALENT_TREES, dungeon=dungeon)
    session.decline_contracts()
    turns = 0
    died_at: str | None = None
    while not session.is_dungeon_cleared:
        _spend_points(session, "hero")
        _drink_between_fights(session, "hero")
        encounter = session.current_encounter
        if session.current_room_type == "combat":
            turns += _play_encounter(session, "hero", skill, rng)
            if not session.combat_state.is_over:
                died_at = f"{encounter.id} (stalemate)"
                break
            if not session.combat_state.victory:
                died_at = encounter.id
                break
            session.collect_victory_reward_and_advance()
        else:
            _resolve_non_combat_node(session, "hero")
    hero = session.run.party[0]
    return RunReport(
        class_id=class_id, race_id=race_id, seed=seed, victory=died_at is None,
        floor_reached=min(run.encounter_index, len(dungeon.encounters)), total_floors=len(dungeon.encounters),
        died_at=died_at, level=hero.level, turns=turns,
        specialization_id=hero.specialization_id, stage2_id=hero.stage2_specialization_id,
    )


def simulate_many(
    class_ids: list[str], race_ids: list[str], runs: int, seed: int = 1, portal_id: str = "portao_do_tumulo",
    skill: BotSkill = NOVATO,
) -> list[Aggregate]:
    aggregates = []
    for class_id in class_ids:
        for race_id in race_ids:
            aggregate = Aggregate(label=f"{CLASS_DEFS[class_id].name} / {RACE_DEFS[race_id].name} ({skill.name})")
            for i in range(runs):
                aggregate.reports.append(simulate_run(class_id, race_id, seed=seed + i, portal_id=portal_id, skill=skill))
            aggregates.append(aggregate)
    return aggregates


def format_report(aggregates: list[Aggregate]) -> str:
    lines = [f"{'Build':44} {'Vitórias':>9} {'Andar médio':>12} {'Nível médio':>12}  Mortes por encontro"]
    for aggregate in aggregates:
        deaths = ", ".join(f"{eid} x{n}" for eid, n in aggregate.deaths_by_encounter.most_common(3)) or "-"
        mean_level = statistics.fmean(r.level for r in aggregate.reports) if aggregate.reports else 0.0
        total = aggregate.reports[0].total_floors if aggregate.reports else 0
        lines.append(
            f"{aggregate.label:44} {aggregate.win_rate:>8.0%} {aggregate.mean_floor:>7.1f}/{total:<4} {mean_level:>12.1f}  {deaths}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # accented names on a cp1252 console
    parser = argparse.ArgumentParser(description="Headless seeded solo runs for balancing.")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--portal", default="portao_do_tumulo")
    parser.add_argument("--classes", default="all", help="comma-separated class ids, or 'all'")
    parser.add_argument("--races", default="human", help="comma-separated race ids, or 'all'")
    parser.add_argument("--skill", default="novato", choices=sorted(SKILLS), help="novato (sem Parry) ou veterano")
    args = parser.parse_args(argv)
    class_ids = list(CLASS_DEFS) if args.classes == "all" else args.classes.split(",")
    race_ids = list(RACE_DEFS) if args.races == "all" else args.races.split(",")
    print(format_report(simulate_many(class_ids, race_ids, args.runs, seed=args.seed, portal_id=args.portal, skill=SKILLS[args.skill])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
