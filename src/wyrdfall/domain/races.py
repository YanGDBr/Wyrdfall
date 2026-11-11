"""Playable races (docs/design/04-racas.md): attribute bonus/penalty, a
unique trait, and an elemental profile -- all reducible to the same two
primitives as everything else, Modifier and TriggeredEffect, exactly
like attributes.py and talents.py. In-run evolutions and the permanent-
upgrade tree are deferred (docs/design/09-roadmap.md Fase 3's scope
note): this covers each race's always-on identity plus its unlock
condition, which is what actually makes "escolher raça muda a run" true.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from wyrdfall.domain.attributes import Atributo, attribute_modifiers_for
from wyrdfall.domain.combat import CombatState
from wyrdfall.domain.dungeon import EncounterDef
from wyrdfall.domain.models import Effect, EffectKind, Modifier, ModifierKind, Stat, TriggerEvent, TriggeredEffect

_ORC_FURY_PER_HIT = 1.0

# Fase 7 -- docs/design/04-racas.md's Renascido unlock ("acumule um
# número alto de mortes totais"). First-guess balance number, like
# every other rate in this corpus.
RENASCIDO_DEATH_THRESHOLD = 5


# Construto's initiative penalty (04-racas.md "age quase sempre por último")
CONSTRUTO_SPEED_PENALTY = -20.0


class RaceDef(BaseModel):
    id: str
    name: str
    description: str
    attribute_bonus: dict[Atributo, int] = Field(default_factory=dict)
    elemental_resist: dict[Stat, float] = Field(default_factory=dict)
    trait_modifiers: list[Modifier] = Field(default_factory=list)
    trait_triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    grants_cheat_death: bool = False
    # Abilities every character of this race knows from creation (Renascido's
    # "Abraçar a Morte", 04-racas.md) -- universal, so never a slot.
    granted_abilities: list[str] = Field(default_factory=list)
    # Fase 7 -- categorical immunity to specific status ids (see
    # Character.status_immunities). "fear" has no StatusEffectDef
    # anywhere yet (no event/status content generates it before Fase 8)
    # -- correctly modeled, not yet reachable, same disclosed pattern as
    # everywhere else in this corpus.
    status_immunities: set[str] = Field(default_factory=set)
    # Fase 7 -- creature-identity tags (see Character.tags). Only
    # Renascido carries one today (docs/design/02-elementos.md's
    # Sagrado "dano bônus contra tags undead/cursed" names Renascido
    # explicitly as the target).
    tags: set[str] = Field(default_factory=set)
    unlock_description: str = ""
    # Raça de prestígio (04-racas.md Meio-celestial): bought in the Guild for
    # Ecos once this many OTHER races have been unlocked AND evolved in a run
    # (MetaProgressionState.evolved_races) -- None for every other race.
    prestige_cost: int | None = None
    prestige_evolved_races_required: int = 0


# 04-racas.md: "custo alto de Ecos" -- 4x the Parry unlock, adjustable in balancing
MEIO_CELESTIAL_COST = 60

RACE_DEFS: dict[str, RaceDef] = {
    "human": RaceDef(
        id="human",
        name="Humano",
        description="O adaptável -- sem pico, sem buraco.",
        attribute_bonus={a: 1 for a in Atributo},
        grants_cheat_death=True,
        unlock_description="Já disponível desde o início.",
    ),
    "dwarf": RaceDef(
        id="dwarf",
        name="Anão",
        description="O inabalável -- construído pra durar, forjado pro fogo.",
        attribute_bonus={Atributo.CONSTITUTION: 3, Atributo.STRENGTH: 2, Atributo.DEXTERITY: -2},
        elemental_resist={Stat.FIRE_RESIST: 0.25, Stat.ICE_RESIST: -0.15},
        trait_modifiers=[
            Modifier(stat=Stat.STATUS_RESIST, kind=ModifierKind.FLAT, value=0.15, source="race_dwarf_trait"),
        ],
        unlock_description="Derrote um chefe sem usar nenhuma habilidade de cura durante o combate.",
    ),
    "elf": RaceDef(
        id="elf",
        name="Elfo",
        description="O preciso -- rápido, arcano, frágil.",
        attribute_bonus={Atributo.DEXTERITY: 3, Atributo.INTELLIGENCE: 2, Atributo.CONSTITUTION: -2},
        elemental_resist={Stat.ARCANE_RESIST: 0.20, Stat.SHADOW_RESIST: -0.15},
        trait_modifiers=[
            Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.10, source="race_elf_trait"),
        ],
        unlock_description="Derrote um chefe sem sofrer nenhum dano elemental (só dano físico é permitido).",
    ),
    "orc": RaceDef(
        id="orc",
        name="Orc",
        description="O implacável -- quanto mais apanha, mais bate.",
        attribute_bonus={Atributo.STRENGTH: 3, Atributo.CONSTITUTION: 2, Atributo.INTELLIGENCE: -2},
        elemental_resist={Stat.POISON_RESIST: 0.20, Stat.ARCANE_RESIST: -0.15},
        trait_triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TAKE_DAMAGE,
                effect=Effect(kind=EffectKind.RESTORE_RESOURCE, amount=_ORC_FURY_PER_HIT),
                applies_to="self",
                source="race_orc_trait",
            ),
        ],
        unlock_description="Vença um combate contra um grupo (3+ inimigos) sem nenhum aliado vivo além de si mesmo.",
    ),
    # -- Fase 7 -- docs/design/04-racas.md's remaining races. Meio-
    # celestial is deferred entirely (needs a new in-combat form-switch
    # action, and its own doc says it should be implemented last). Fada
    # and Construto below have no check_race_unlock case -- correctly
    # modeled, not yet reachable, pending a random-event system and the
    # Ferreiro respectively (neither exists yet).
    "fada": RaceDef(
        id="fada",
        name="Fada",
        description="O caótico -- sorte grande, corpo pequeno.",
        attribute_bonus={Atributo.LUCK: 3, Atributo.INTELLIGENCE: 2, Atributo.CONSTITUTION: -3},
        elemental_resist={Stat.HOLY_RESIST: 0.25},
        trait_modifiers=[
            Modifier(stat=Stat.PROC_CHANCE_PERCENT, kind=ModifierKind.FLAT, value=0.25, source="race_fada_trait"),
            Modifier(
                stat=Stat.PHYSICAL_VULNERABILITY_PERCENT, kind=ModifierKind.FLAT, value=0.20,
                source="race_fada_elemental",
            ),
        ],
        unlock_description="Evento raro: encontre e interaja com um Portal Feérico numa run.",
    ),
    "meio_celestial": RaceDef(
        id="meio_celestial",
        name="Meio-celestial",
        description="Nem luz, nem sombra -- as duas, por escolha. Natureza Dual: assuma a forma Sagrada ou Sombria uma vez por combate.",
        attribute_bonus={Atributo.INTELLIGENCE: 2, Atributo.WISDOM: 2, Atributo.CONSTITUTION: -2},
        granted_abilities=["assumir_forma_sagrada", "assumir_forma_sombria"],
        unlock_description=f"Raça de prestígio: {MEIO_CELESTIAL_COST} Ecos, após desbloquear e evoluir 2 outras raças.",
        prestige_cost=MEIO_CELESTIAL_COST,
        prestige_evolved_races_required=2,
    ),
    "renascido": RaceDef(
        id="renascido",
        name="Renascido",
        description="O que já morreu -- e voltou sabendo o preço.",
        attribute_bonus={Atributo.STRENGTH: 2, Atributo.INTELLIGENCE: 2, Atributo.WISDOM: -2},
        elemental_resist={Stat.SHADOW_RESIST: 0.30, Stat.HOLY_RESIST: -0.30},
        trait_modifiers=[
            Modifier(
                stat=Stat.HEALING_RECEIVED_PERCENT, kind=ModifierKind.FLAT, value=-0.30, source="race_renascido_trait",
            ),
        ],
        status_immunities={"poisoned", "fear"},
        tags={"undead", "cursed"},
        granted_abilities=["abracar_a_morte"],
        unlock_description="Acumule um número alto de mortes totais (contador permanente).",
    ),
    "construto": RaceDef(
        id="construto",
        name="Construto",
        description="O que foi feito, não nascido.",
        attribute_bonus={Atributo.CONSTITUTION: 5, Atributo.STRENGTH: 2, Atributo.DEXTERITY: -3},
        elemental_resist={Stat.POISON_RESIST: 0.30, Stat.LIGHTNING_RESIST: -0.25},
        trait_modifiers=[
            # "Age quase sempre por último" -- Speed is only ever consumed
            # by combat.py's turn-order sort. -20 puts a Construto behind
            # every enemy in the bestiary (speeds run 1..9) while leaving
            # room for the race's permanent tree to "reduzir a penalidade
            # de iniciativa" (04-racas.md) node by node.
            Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=CONSTRUTO_SPEED_PENALTY, source="race_construto_trait"),
        ],
        status_immunities={"poisoned", "bleeding", "fear"},
        unlock_description="Construído pelo Ferreiro no hub usando materiais raros de crafting.",
    ),
    "licantropo": RaceDef(
        id="licantropo",
        name="Licantropo",
        description="O que cresce dentro da luta.",
        attribute_bonus={Atributo.STRENGTH: 2, Atributo.DEXTERITY: 2, Atributo.INTELLIGENCE: -2},
        elemental_resist={Stat.HOLY_RESIST: -0.25},
        trait_modifiers=[
            Modifier(stat=Stat.PHYSICAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.15, source="race_licantropo_elemental"),
        ],
        trait_triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TURN_START,
                effect=Effect(
                    kind=EffectKind.APPLY_STATUS, status_id="instinto_selvagem", duration=2, stacks=1,
                ),
                applies_to="self",
                source="race_licantropo_trait",
            ),
        ],
        unlock_description="Vença sozinho (sem aliados na run) um combate contra um grupo (3+ inimigos).",
    ),
}


def race_modifiers_for(race_id: str) -> list[Modifier]:
    race = RACE_DEFS.get(race_id)
    if race is None:
        return []
    modifiers = attribute_modifiers_for(race.attribute_bonus)
    for stat, value in race.elemental_resist.items():
        modifiers.append(Modifier(stat=stat, kind=ModifierKind.FLAT, value=value, source=f"race_{race_id}_elemental"))
    modifiers.extend(race.trait_modifiers)
    return modifiers


def race_triggered_effects_for(race_id: str) -> list[TriggeredEffect]:
    race = RACE_DEFS.get(race_id)
    return list(race.trait_triggered_effects) if race is not None else []


def check_race_unlock(race_id: str, *, encounter: EncounterDef, combat_state: CombatState, participant_id: str | None = None) -> bool:
    """Evaluate a victory condition for a participant or a legacy party query.

    Companion/summon bodies never replace actual players for solo and
    sole-survivor requirements. Event and profile unlocks live elsewhere.
    """
    party = [cid for cid in combat_state.party_ids() if not combat_state.combatants[cid].is_companion]
    if participant_id is not None and participant_id not in party:
        return False
    if race_id == "dwarf":
        used_heal = combat_state.used_heal_this_encounter if participant_id is None else participant_id in combat_state.healing_participants
        return encounter.is_boss and not used_heal
    if race_id == "elf":
        took_damage = combat_state.took_elemental_damage_this_encounter if participant_id is None else participant_id in combat_state.elemental_damage_recipients
        return encounter.is_boss and not took_damage
    if race_id == "orc":
        alive_party = sum(1 for cid in party if combat_state.alive(cid))
        # "3+" is the enemy group size; needing >=2 party members means this
        # is only reachable in co-op, matching the design's "sem nenhum
        # aliado vivo além de si mesmo" (there must have been an ally to lose).
        return len(combat_state.enemy_ids()) >= 3 and len(party) >= 2 and alive_party == 1 and (participant_id is None or combat_state.alive(participant_id))
    if race_id == "licantropo":
        # "Vença sozinho" read literally as *true solo* -- distinct from
        # Orc's "had allies, all but one died" condition per the design
        # doc's own note flagging the two shouldn't collide.
        return len(combat_state.enemy_ids()) >= 3 and len(party) == 1
    return False


def check_meta_race_unlock(race_id: str, *, total_deaths: int) -> bool:
    """Companion to check_race_unlock for races whose unlock condition
    isn't a per-encounter combat outcome -- Renascido reads accumulated
    meta-progression state instead (see WyrdfallApp.bank_run_reward,
    called once per finished run). Takes total_deaths directly rather
    than a MetaProgressionState so this module stays free of a
    persistence-layer dependency, the same boundary every other domain
    module already respects."""
    if race_id == "renascido":
        return total_deaths >= RENASCIDO_DEATH_THRESHOLD
    return False
