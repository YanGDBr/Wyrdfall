"""The Místico Arquétipo Base's concrete class: a conjurer leaning on
resource and elemental damage, low defense. Two branches -- Arcano,
Sabedoria -- converge on one keystone. NODES/EDGES exported for
domain/content/specializations.py to graft onto."""

from wyrdfall.domain.character import ClassDef
from wyrdfall.domain.models import (
    Archetype,
    Effect,
    EffectKind,
    Modifier,
    ModifierKind,
    Stat,
    StatBlock,
    TriggeredEffect,
    TriggerEvent,
)
from wyrdfall.domain.talents import TalentNode, TalentTree, TalentTreeDef

NODES = [
    # -- Arcano branch -------------------------------------------------------
    TalentNode(
        id="ar1",
        name="Canalização",
        description="+15% de dano elemental.",
        cost=1,
        modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.15, source="ar1")],
    ),
    TalentNode(
        id="ar1b",
        name="Foco Arcano",
        description="+2 de Ataque.",
        cost=1,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=2, source="ar1b")],
    ),
    TalentNode(
        id="ar2",
        name="Eco Mágico",
        description="Desbloqueia a habilidade Arcane Nova.",
        cost=1,
        grants_ability="arcane_nova",
    ),
    # -- Sabedoria branch ---------------------------------------------------
    TalentNode(
        id="sb1",
        name="Poço de Mana",
        description="+3 de Resolução máxima.",
        cost=1,
        modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=3, source="sb1")],
    ),
    TalentNode(
        id="sb1b",
        name="Fluxo Constante",
        description="+0.5 de regeneração de Resolução por turno.",
        cost=1,
        modifiers=[Modifier(stat=Stat.RESOURCE_REGEN_PER_TURN, kind=ModifierKind.FLAT, value=0.5, source="sb1b")],
    ),
    TalentNode(
        id="sb2",
        name="Escudo de Mana",
        description="Ao usar uma habilidade, ganha um pequeno escudo.",
        cost=1,
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_ABILITY_CAST,
                effect=Effect(kind=EffectKind.APPLY_SHIELD, amount=1.0),
                applies_to="self",
                source="sb2",
            )
        ],
    ),
    # -- Keystone --------------------------------------------------------------
    TalentNode(
        id="keystone",
        name="Tecelão de Feitiços",
        description="+20% de dano elemental adicional.",
        cost=3,
        is_keystone=True,
        require_all_prerequisites=True,
        modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.MORE, value=0.20, source="keystone")],
    ),
]

EDGES = [
    ("ar1", "ar2"), ("ar1", "ar1b"),
    ("sb1", "sb2"), ("sb1", "sb1b"),
    ("ar2", "keystone"), ("sb2", "keystone"),
]

MISTICO_TALENT_TREE = TalentTree(
    TalentTreeDef(id="mistico_path", name="Caminho do Místico", nodes=NODES, edges=EDGES)
)

MISTICO_CLASS = ClassDef(
    id="mistico",
    name="Místico",
    description="Um conjurador que gasta Resolução em feitiços elementais, frágil mas devastador.",
    base_stats=StatBlock(
        max_hp=26, attack=5, defense=2, speed=7, crit_chance=0.06, crit_mult=1.5, max_resource=8
    ),
    starting_abilities=["arcane_bolt", "guard", "focus"],
    talent_tree_id="mistico_path",
    base_archetype=Archetype.MISTICO,
)
