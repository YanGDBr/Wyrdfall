"""The Patrulheiro Arquétipo Base's concrete class: a ranged specialist
leaning on speed and crit. Two branches -- Precisão, Instinto -- converge
on one keystone; smaller than Guerreiro's showcase tree (7 nodes instead
of 13) but the same real shape. NODES/EDGES exported for
domain/content/specializations.py to graft onto."""

from wyrdfall.domain.character import ResourceKind, ClassDef
from wyrdfall.domain.models import Archetype, Modifier, ModifierKind, Stat, StatBlock
from wyrdfall.domain.talents import TalentNode, TalentTree, TalentTreeDef

NODES = [
    # -- Precisão branch ---------------------------------------------------
    TalentNode(
        id="pr1",
        name="Mira Firme",
        description="+5% de chance de Crítico.",
        cost=1,
        modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.05, source="pr1")],
    ),
    TalentNode(
        id="pr1b",
        name="Ponto Fraco",
        description="+15% de dano Crítico.",
        cost=1,
        modifiers=[Modifier(stat=Stat.CRIT_MULT, kind=ModifierKind.MORE, value=0.15, source="pr1b")],
    ),
    TalentNode(
        id="pr2",
        name="Olho de Águia",
        description="+15% de Ataque.",
        cost=1,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.15, source="pr2")],
    ),
    # -- Instinto branch ------------------------------------------------------
    TalentNode(
        id="in1",
        name="Reflexos",
        description="+1 de Velocidade.",
        cost=1,
        modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=1, source="in1")],
    ),
    TalentNode(
        id="in1b",
        name="Passo Leve",
        description="+5% de chance de Esquiva.",
        cost=1,
        modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.05, source="in1b")],
    ),
    TalentNode(
        id="in2",
        name="Recarga Rápida",
        description="Desbloqueia a habilidade Piercing Shot.",
        cost=1,
        grants_ability="piercing_shot",
    ),
    # -- Keystone --------------------------------------------------------------
    TalentNode(
        id="keystone",
        name="Um Tiro, Uma Chance",
        description="+25% de dano contra alvos com PV cheio.",
        cost=3,
        is_keystone=True,
        require_all_prerequisites=True,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.MORE, value=0.25, source="keystone")],
    ),
]

EDGES = [
    ("pr1", "pr2"), ("pr1", "pr1b"),
    ("in1", "in2"), ("in1", "in1b"),
    ("pr2", "keystone"), ("in2", "keystone"),
]

PATRULHEIRO_TALENT_TREE = TalentTree(
    TalentTreeDef(id="patrulheiro_path", name="Caminho do Patrulheiro", nodes=NODES, edges=EDGES)
)

PATRULHEIRO_CLASS = ClassDef(
    resource_kind=ResourceKind.COMBO_POINTS,
    id="patrulheiro",
    name="Patrulheiro",
    description="Um especialista à distância, rápido e preciso, que joga com posicionamento e alvo.",
    base_stats=StatBlock(
        max_hp=28, attack=7, defense=2, speed=10, crit_chance=0.12, crit_mult=1.6, max_resource=4
    ),
    starting_abilities=["aimed_shot", "guard", "focus"],
    talent_tree_id="patrulheiro_path",
    base_archetype=Archetype.PATRULHEIRO,
)
