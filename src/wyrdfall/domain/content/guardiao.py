"""The Guardião Arquétipo Base's concrete class: high HP/defense, low
speed, protective abilities. Two branches -- Resistência, Retaliação --
converge on one keystone. NODES/EDGES exported for
domain/content/specializations.py to graft onto."""

from wyrdfall.domain.character import ResourceKind, ClassDef
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
    # -- Resistência branch ----------------------------------------------
    TalentNode(
        id="rs1",
        name="Constituição de Ferro",
        description="+8 de PV máximo.",
        cost=1,
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=8, source="rs1")],
    ),
    TalentNode(
        id="rs1b",
        name="Casca Dura",
        description="+2 de Defesa.",
        cost=1,
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=2, source="rs1b")],
    ),
    TalentNode(
        id="rs2",
        name="Muralha",
        description="+20% de Defesa.",
        cost=1,
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.PERCENT, value=0.20, source="rs2")],
    ),
    # -- Retaliação branch ---------------------------------------------------
    TalentNode(
        id="rt1",
        name="Postura Firme",
        description="+10% de resistência a status.",
        cost=1,
        modifiers=[Modifier(stat=Stat.STATUS_RESIST, kind=ModifierKind.FLAT, value=0.10, source="rt1")],
    ),
    TalentNode(
        id="rt1b",
        name="Contragolpe",
        description="Sofrer dano acerta o atacante de volta.",
        cost=1,
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TAKE_DAMAGE,
                effect=Effect(kind=EffectKind.DAMAGE, amount=1.0, scales_with=Stat.DEFENSE, scale_factor=0.4),
                applies_to="context",
                source="rt1b",
            )
        ],
    ),
    TalentNode(
        id="rt2",
        name="Escudo Reforçado",
        description="Desbloqueia a habilidade Bulwark Slam.",
        cost=1,
        grants_ability="bulwark_slam",
    ),
    # -- Keystone --------------------------------------------------------------
    TalentNode(
        id="keystone",
        name="Inabalável",
        description="Cura 3 de PV no início de cada um dos seus turnos.",
        cost=3,
        is_keystone=True,
        require_all_prerequisites=True,
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TURN_START,
                effect=Effect(kind=EffectKind.HEAL, amount=3.0),
                applies_to="self",
                source="keystone",
            )
        ],
    ),
]

EDGES = [
    ("rs1", "rs2"), ("rs1", "rs1b"),
    ("rt1", "rt2"), ("rt1", "rt1b"),
    ("rs2", "keystone"), ("rt2", "keystone"),
]

GUARDIAO_TALENT_TREE = TalentTree(
    TalentTreeDef(id="guardiao_path", name="Caminho do Guardião", nodes=NODES, edges=EDGES)
)

GUARDIAO_CLASS = ClassDef(
    resource_kind=ResourceKind.ADRENALINE,
    id="guardiao",
    name="Guardião",
    description="Uma muralha viva de alto PV e Defesa, lenta mas quase impossível de derrubar.",
    base_stats=StatBlock(
        max_hp=42, attack=4, defense=6, speed=4, crit_chance=0.03, crit_mult=1.5, max_resource=4
    ),
    starting_abilities=["shield_bash", "taunt", "guard", "focus"],
    talent_tree_id="guardiao_path",
    base_archetype=Archetype.GUARDIAO,
)
