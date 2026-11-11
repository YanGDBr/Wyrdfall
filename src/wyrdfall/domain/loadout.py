"""What one player brings into a run (docs/design/14-estrutura-da-run.md
§1: Personagem = Raça + Arquétipo Base, Selamentos; docs/design/
09-roadmap.md Fase 5a: co-op players pick *different* archetypes).

Solo builds it from the local Guild state; in co-op every joiner sends
theirs in ClientHello and the host builds each character from its own
loadout. Pactos/Ascensão are deliberately *not* here -- those stay
lobby-wide (the host's), see net/server.py.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from wyrdfall.domain.character import Character, Ruleset
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Archetype, DamageElement, Modifier, TriggeredEffect
from wyrdfall.domain.pacts import pact_modifiers_for


class PlayerLoadout(BaseModel):
    class_id: str = "runeguard"
    race_id: str = "human"
    sealed_archetypes: set[Archetype] = Field(default_factory=set)
    sealed_elements: set[DamageElement] = Field(default_factory=set)
    # meta-progression perks the player's own Guild granted them
    can_parry: bool = False
    starting_gear: list[str] = Field(default_factory=list)
    starting_runes: list[str] = Field(default_factory=list)
    companion_id: str | None = None
    bonus_talent_points: int = 0
    permanent_modifiers: list[Modifier] = Field(default_factory=list)
    permanent_triggered_effects: list[TriggeredEffect] = Field(default_factory=list)


def build_character_from_loadout(
    instance_id: str, name: str, loadout: PlayerLoadout, ruleset: Ruleset, *, pacts: list[str] | None = None,
) -> Character:
    class_def = CLASS_DEFS.get(loadout.class_id) or CLASS_DEFS["runeguard"]
    tree = TALENT_TREES[class_def.talent_tree_id]
    return create_player_character(
        instance_id,
        name,
        class_def,
        tree,
        ruleset=ruleset,
        starting_talent_points=1 + loadout.bonus_talent_points,
        can_parry=loadout.can_parry,
        race_id=loadout.race_id,
        # Fase 8: an equipped Pacto do Wyrd is just more permanent
        # Modifiers on every party member, same channel as the trees
        permanent_modifiers=[*loadout.permanent_modifiers, *pact_modifiers_for(list(pacts or []))],
        permanent_triggered_effects=list(loadout.permanent_triggered_effects),
        sealed_archetypes=set(loadout.sealed_archetypes),
        sealed_elements=set(loadout.sealed_elements),
    )
