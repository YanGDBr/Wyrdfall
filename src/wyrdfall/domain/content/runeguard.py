"""The Runeguard: the Guerreiro Arquétipo Base's concrete class (see
domain/content/{patrulheiro,mistico,guardiao}.py for the other 3), built
entirely on the talent-tree build system (networkx-backed). Three
branches -- Offense, Defense, Resolve -- fan out from independent roots
and converge on one keystone, so a first run already has real allocation
choices to make. NODES/EDGES are exported (not private) so
domain/content/specializations.py can graft a Especialização branch onto
them without duplicating the base tree."""

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
    # -- Offense branch --------------------------------------------------
    TalentNode(
        id="o1",
        name="Lâmina Afiada",
        description="+2 de Ataque.",
        cost=1,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=2, source="o1")],
    ),
    TalentNode(
        id="o1b",
        name="Brutalidade",
        description="+5% de chance de Crítico.",
        cost=1,
        modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.05, source="o1b")],
    ),
    TalentNode(
        id="o2",
        name="Agressão",
        description="+15% de Ataque.",
        cost=1,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.15, source="o2")],
    ),
    TalentNode(
        id="o3",
        name="Golpe Fatal",
        description="Derrotar um inimigo cura 3 de PV.",
        cost=1,
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_KILL,
                effect=Effect(kind=EffectKind.HEAL, amount=3.0),
                applies_to="self",
                source="o3",
            )
        ],
    ),
    # -- Defense branch ---------------------------------------------------
    TalentNode(
        id="d1",
        name="Pele Grossa",
        description="+2 de Defesa.",
        cost=1,
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=2, source="d1")],
    ),
    TalentNode(
        id="d1b",
        name="Vitalidade",
        description="+5 de PV máximo.",
        cost=1,
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=5, source="d1b")],
    ),
    TalentNode(
        id="d2",
        name="Pele de Pedra",
        description="+20% de Defesa.",
        cost=1,
        modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.PERCENT, value=0.20, source="d2")],
    ),
    TalentNode(
        id="d3",
        name="Retaliação",
        description="Sofrer dano acerta o atacante de volta.",
        cost=1,
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TAKE_DAMAGE,
                effect=Effect(kind=EffectKind.DAMAGE, amount=1.0, scales_with=Stat.DEFENSE, scale_factor=0.3),
                applies_to="context",
                source="d3",
            )
        ],
    ),
    # -- Resolve branch -----------------------------------------------------
    TalentNode(
        id="r1",
        name="Meditação",
        description="+2 de Resolução máxima.",
        cost=1,
        modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=2, source="r1")],
    ),
    TalentNode(
        id="r1b",
        name="Mente Ágil",
        description="+1 de Velocidade.",
        cost=1,
        modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=1, source="r1b")],
    ),
    TalentNode(
        id="r2",
        name="Foco Rúnico",
        description="Desbloqueia a habilidade Rune Smash.",
        cost=1,
        grants_ability="rune_smash",
    ),
    TalentNode(
        id="r3",
        name="Fôlego Renovado",
        description="Cura 2 de PV no início de cada um dos seus turnos.",
        cost=1,
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TURN_START,
                effect=Effect(kind=EffectKind.HEAL, amount=2.0),
                applies_to="self",
                source="r3",
            )
        ],
    ),
    # -- Keystone --------------------------------------------------------------
    TalentNode(
        id="keystone",
        name="Tocado pelo Wyrd",
        description="+50% de dano Crítico. Acertos críticos Marcam o inimigo, enfraquecendo sua Defesa.",
        cost=3,
        is_keystone=True,
        require_all_prerequisites=True,
        modifiers=[Modifier(stat=Stat.CRIT_MULT, kind=ModifierKind.MORE, value=0.5, source="keystone")],
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_CRIT,
                effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="marked", duration=2, stacks=1),
                applies_to="context",
                source="keystone",
            )
        ],
    ),
]

EDGES = [
    ("o1", "o2"), ("o1", "o1b"), ("o2", "o3"),
    ("d1", "d2"), ("d1", "d1b"), ("d2", "d3"),
    ("r1", "r2"), ("r1", "r1b"), ("r2", "r3"),
    ("o3", "keystone"), ("d3", "keystone"), ("r3", "keystone"),
]

RUNEGUARD_TALENT_TREE = TalentTree(
    TalentTreeDef(id="runeguard_path", name="Caminho do Guardião das Runas", nodes=NODES, edges=EDGES)
)

RUNEGUARD_CLASS = ClassDef(
    resource_kind=ResourceKind.FURY,
    id="runeguard",
    name="Guardião das Runas",
    description="Um guerreiro protegido por runas que se defende, golpeia e canaliza Resolução em golpes rúnicos.",
    base_stats=StatBlock(
        max_hp=32, attack=6, defense=3, speed=8, crit_chance=0.08, crit_mult=1.5, max_resource=4
    ),
    starting_abilities=["strike", "guard", "focus"],
    talent_tree_id="runeguard_path",
    base_archetype=Archetype.GUERREIRO,
    build_system="talent_tree",
)
