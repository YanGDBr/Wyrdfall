"""Socketed runes: body bonuses are global; ability bonuses resolve per cast.

Runes are acquired as drops or crafted, and consumed from the run inventory
while socketed. The same tier upgrade preserves scope and effect identity.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from wyrdfall.domain.character import Character
from wyrdfall.domain.models import Effect, EffectKind, Modifier, ModifierKind, Stat, TriggeredEffect, TriggerEvent

BODY_RUNE_SLOTS = 2
ABILITY_RUNE_SLOTS_PER_ABILITY = 1


class RuneDef(BaseModel):
    id: str
    name: str
    description: str
    modifiers: list[Modifier] = Field(default_factory=list)
    triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    # 08-itens-crafting.md Forja de Campo: "combinar 2 runas numa runa
    # seguinte (upgrade simples, não troca de identidade do efeito)"
    tier: int = 1
    upgrades_to: str | None = None


RUNE_DEFS: dict[str, RuneDef] = {
    "rune_might": RuneDef(
        id="rune_might", name="Runa do Vigor",
        description="+3 de Ataque.",
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=3, source="rune_might")],
    ),
    "rune_bulwark": RuneDef(
        id="rune_bulwark", name="Runa da Muralha",
        description="+3 de Defesa.",
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=3, source="rune_bulwark")],
    ),
    "rune_haste": RuneDef(
        id="rune_haste", name="Runa da Pressa",
        description="+2 de Velocidade.",
        modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=2, source="rune_haste")],
    ),
    "rune_focus": RuneDef(
        id="rune_focus", name="Runa do Foco",
        description="+8% de chance de Crítico.",
        modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.08, source="rune_focus")],
    ),
    "rune_vitality": RuneDef(
        id="rune_vitality", name="Runa da Vitalidade",
        description="+10 de PV máximo.",
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=10, source="rune_vitality")],
    ),
    "rune_leech": RuneDef(
        id="rune_leech", name="Runa do Sanguessuga",
        description="+8% de Roubo de Vida.",
        modifiers=[Modifier(stat=Stat.LIFESTEAL_PERCENT, kind=ModifierKind.FLAT, value=0.08, source="rune_leech")],
    ),
    "rune_ember": RuneDef(
        id="rune_ember", name="Runa da Brasa",
        description="Recupera 1 de Resolução ao acertar um golpe.",
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_HIT,
                effect=Effect(kind=EffectKind.RESTORE_RESOURCE, amount=1.0),
                applies_to="self",
                source="rune_ember",
            )
        ],
    ),
}


def _upgraded(rune: RuneDef) -> RuneDef:
    """The tier-2 twin: same identity, doubled numbers, name + ' II'."""
    return RuneDef(
        id=f"{rune.id}_2", name=f"{rune.name} II", description=f"{rune.description} (x2)", tier=2,
        modifiers=[m.model_copy(update={"value": m.value * 2, "source": f"{rune.id}_2"}) for m in rune.modifiers],
        triggered_effects=[
            t.model_copy(update={
                "effect": t.effect.model_copy(update={"amount": t.effect.amount * 2}), "source": f"{rune.id}_2",
            })
            for t in rune.triggered_effects
        ],
    )


for _base in list(RUNE_DEFS.values()):
    _second = _upgraded(_base)
    RUNE_DEFS[_second.id] = _second
    _base.upgrades_to = _second.id

# what encounters can drop (08-itens-crafting.md "Drops: Runas"): tier 1 only
RUNE_DROP_POOL: list[str] = [rune_id for rune_id, rune in RUNE_DEFS.items() if rune.tier == 1]


def _all_socketed_rune_ids(character: Character, ability_id: str | None = None) -> list[str]:
    if ability_id is not None:
        return list(character.ability_rune_slots.get(ability_id, []))
    ids = list(character.body_rune_slots)
    if character.absorbed_rune_id is not None:  # Construto (04-racas.md), session.absorb_rune
        ids.append(character.absorbed_rune_id)
    return ids


def rune_modifiers_for(character: Character, ability_id: str | None = None) -> list[Modifier]:
    modifiers: list[Modifier] = []
    for rune_id in _all_socketed_rune_ids(character, ability_id):
        rune = RUNE_DEFS.get(rune_id)
        if rune is not None:
            modifiers.extend(rune.modifiers)
    return modifiers


def rune_triggered_effects_for(character: Character, ability_id: str | None = None) -> list[TriggeredEffect]:
    effects: list[TriggeredEffect] = []
    for rune_id in _all_socketed_rune_ids(character, ability_id):
        rune = RUNE_DEFS.get(rune_id)
        if rune is not None:
            effects.extend(rune.triggered_effects)
    return effects


def supports_ability_socket(rune: RuneDef) -> bool:
    """Only outgoing action stats have a meaningful ability-local scope."""
    allowed = {Stat.ATTACK, Stat.CRIT_CHANCE, Stat.LIFESTEAL_PERCENT}
    return all(mod.stat in allowed for mod in rune.modifiers)
