"""12 of the 13 permanent Raça/Arquétipo trees (docs/design/10-sistemas-
de-build.md §6) -- one per race in domain/races.py (8: Meio-celestial is
deferred with its race) + guerreiro/patrulheiro/mistico/guardiao. Each
race's tree follows 04-racas.md's "Upgrade permanente" line: Fada
softens her CON penalty, Renascido his healing penalty, Construto its
initiative penalty, Licantropo speeds up Instinto.

Reuses TalentTree/TalentTreeDef exactly as-is (see domain/talents.py) --
the only thing that's actually different about a *permanent* tree is
where its allocated-node set lives (MetaProgressionState, not
Character) and what currency funds it (Ecos, not run talent points).
Each tree is a small 3-node linear chain, granting plain permanent
Modifiers -- no unique abilities, matching Fase 5b's "not full kit
polish yet" precedent for a first pass.
"""

from wyrdfall.domain.models import Effect, EffectKind, Modifier, ModifierKind, Stat, TriggerEvent, TriggeredEffect
from wyrdfall.domain.slots import LEGACY_SLOT_LEVEL
from wyrdfall.domain.talents import TalentNode, TalentTree, TalentTreeDef

PERMANENT_TREE_COST = 3  # flat Ecos per node, first-guess balance number


def _linear_tree(tree_id: str, name: str, nodes: list[TalentNode]) -> TalentTree:
    edges = [(nodes[i].id, nodes[i + 1].id) for i in range(len(nodes) - 1)]
    return TalentTree(TalentTreeDef(id=tree_id, name=name, nodes=nodes, edges=edges))


PERMANENT_TREES: dict[str, TalentTree] = {
    "permanent_human": _linear_tree(
        "permanent_human", "Legado Humano",
        [
            TalentNode(id="permanent_human_1", name="Versatilidade", description="+2% de chance de Crítico.",
                       modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.02, source="permanent_human_1")]),
            TalentNode(id="permanent_human_2", name="Determinação", description="+5 de PV máximo.",
                       modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=5, source="permanent_human_2")]),
            TalentNode(id="permanent_human_3", name="Adaptação", description="+1 de Velocidade.",
                       modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=1, source="permanent_human_3")]),
        ],
    ),
    "permanent_dwarf": _linear_tree(
        "permanent_dwarf", "Legado Anão",
        [
            TalentNode(id="permanent_dwarf_1", name="Ossos de Pedra", description="+3 de Defesa.",
                       modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=3, source="permanent_dwarf_1")]),
            TalentNode(id="permanent_dwarf_2", name="Sangue Firme", description="+10% de resistência a status.",
                       modifiers=[Modifier(stat=Stat.STATUS_RESIST, kind=ModifierKind.FLAT, value=0.10, source="permanent_dwarf_2")]),
            TalentNode(id="permanent_dwarf_3", name="Coração da Montanha", description="+8 de PV máximo.",
                       modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=8, source="permanent_dwarf_3")]),
        ],
    ),
    "permanent_elf": _linear_tree(
        "permanent_elf", "Legado Élfico",
        [
            TalentNode(id="permanent_elf_1", name="Passo Élfico", description="+3% de chance de Esquiva.",
                       modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.03, source="permanent_elf_1")]),
            TalentNode(id="permanent_elf_2", name="Olhar Élfico", description="+3% de chance de Crítico.",
                       modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.03, source="permanent_elf_2")]),
            TalentNode(id="permanent_elf_3", name="Sangue Antigo", description="+2 de Resolução máxima.",
                       modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=2, source="permanent_elf_3")]),
        ],
    ),
    "permanent_orc": _linear_tree(
        "permanent_orc", "Legado Orc",
        [
            TalentNode(id="permanent_orc_1", name="Punho Bruto", description="+3 de Ataque.",
                       modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=3, source="permanent_orc_1")]),
            TalentNode(id="permanent_orc_2", name="Pele Grossa", description="+6 de PV máximo.",
                       modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=6, source="permanent_orc_2")]),
            TalentNode(id="permanent_orc_3", name="Fúria Antiga", description="+10% de dano Crítico.",
                       modifiers=[Modifier(stat=Stat.CRIT_MULT, kind=ModifierKind.MORE, value=0.10, source="permanent_orc_3")]),
        ],
    ),
    "permanent_fada": _linear_tree(
        "permanent_fada", "Legado Feérico",
        [
            TalentNode(id="permanent_fada_1", name="Raízes Feéricas", description="+5 de PV máximo (amacia a penalidade de CON).",
                       modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=5, source="permanent_fada_1")]),
            TalentNode(id="permanent_fada_2", name="Asas Firmes", description="+2 de Defesa.",
                       modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=2, source="permanent_fada_2")]),
            TalentNode(id="permanent_fada_3", name="Sorte Antiga", description="+5% em chances de proc.",
                       modifiers=[Modifier(stat=Stat.PROC_CHANCE_PERCENT, kind=ModifierKind.FLAT, value=0.05, source="permanent_fada_3")]),
        ],
    ),
    "permanent_renascido": _linear_tree(
        "permanent_renascido", "Legado Renascido",
        [
            TalentNode(id="permanent_renascido_1", name="Memória de Vida", description="+10% de cura recebida (reduz a penalidade).",
                       modifiers=[Modifier(stat=Stat.HEALING_RECEIVED_PERCENT, kind=ModifierKind.FLAT, value=0.10, source="permanent_renascido_1")]),
            TalentNode(id="permanent_renascido_2", name="Segundo Fôlego", description="+10% de cura recebida (reduz a penalidade).",
                       modifiers=[Modifier(stat=Stat.HEALING_RECEIVED_PERCENT, kind=ModifierKind.FLAT, value=0.10, source="permanent_renascido_2")]),
            TalentNode(id="permanent_renascido_3", name="Pacto Velho", description="+5% de Roubo de Vida.",
                       modifiers=[Modifier(stat=Stat.LIFESTEAL_PERCENT, kind=ModifierKind.FLAT, value=0.05, source="permanent_renascido_3")]),
        ],
    ),
    "permanent_construto": _linear_tree(
        "permanent_construto", "Legado do Construto",
        [
            TalentNode(id="permanent_construto_1", name="Engrenagens Lubrificadas", description="+6 de Velocidade (reduz a penalidade de iniciativa).",
                       modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=6, source="permanent_construto_1")]),
            TalentNode(id="permanent_construto_2", name="Núcleo Polido", description="+6 de Velocidade (reduz a penalidade de iniciativa).",
                       modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=6, source="permanent_construto_2")]),
            TalentNode(id="permanent_construto_3", name="Chapa Reforçada", description="+3 de Defesa.",
                       modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=3, source="permanent_construto_3")]),
        ],
    ),
    "permanent_licantropo": _linear_tree(
        "permanent_licantropo", "Legado Licantropo",
        [
            TalentNode(id="permanent_licantropo_1", name="Instinto Aguçado", description="Ganha 1 stack extra de Instinto Selvagem por turno.",
                       triggered_effects=[TriggeredEffect(
                           trigger=TriggerEvent.ON_TURN_START,
                           effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="instinto_selvagem", duration=2, stacks=1),
                           applies_to="self", source="permanent_licantropo_1",
                       )]),
            TalentNode(id="permanent_licantropo_2", name="Pelo Espesso", description="+6 de PV máximo.",
                       modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=6, source="permanent_licantropo_2")]),
            TalentNode(id="permanent_licantropo_3", name="Presas", description="+2 de Ataque.",
                       modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=2, source="permanent_licantropo_3")]),
        ],
    ),
    "permanent_meio_celestial": _linear_tree(
        "permanent_meio_celestial", "Legado Meio-celestial",
        [
            TalentNode(id="permanent_meio_celestial_1", name="Natureza Plena", description="Pode trocar de forma 2x por combate em vez de 1x.",
                       modifiers=[Modifier(stat=Stat.EXTRA_USES_PER_COMBAT, kind=ModifierKind.FLAT, value=1, source="permanent_meio_celestial_1")]),
            TalentNode(id="permanent_meio_celestial_2", name="Corpo Caído", description="+5 de PV máximo (reduz a penalidade de CON).",
                       modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=5, source="permanent_meio_celestial_2")]),
            TalentNode(id="permanent_meio_celestial_3", name="Duas Naturezas", description="+5% de dano elemental.",
                       modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.05, source="permanent_meio_celestial_3")]),
        ],
    ),
    "permanent_guerreiro": _linear_tree(
        "permanent_guerreiro", "Legado do Guerreiro",
        [
            TalentNode(id="permanent_guerreiro_1", name="Disciplina Marcial", description="+2 de Ataque.",
                       modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=2, source="permanent_guerreiro_1")]),
            TalentNode(id="permanent_guerreiro_2", name="Fôlego de Batalha", description="+5 de PV máximo.",
                       modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=5, source="permanent_guerreiro_2")]),
            TalentNode(id="permanent_guerreiro_3", name="Golpe Treinado", description="+5% de chance de Crítico.",
                       modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.05, source="permanent_guerreiro_3")]),
        ],
    ),
    "permanent_patrulheiro": _linear_tree(
        "permanent_patrulheiro", "Legado do Patrulheiro",
        [
            TalentNode(id="permanent_patrulheiro_1", name="Passo Leve", description="+1 de Velocidade.",
                       modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=1, source="permanent_patrulheiro_1")]),
            TalentNode(id="permanent_patrulheiro_2", name="Olho Certeiro", description="+4% de chance de Crítico.",
                       modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.04, source="permanent_patrulheiro_2")]),
            TalentNode(id="permanent_patrulheiro_3", name="Reflexos", description="+3% de chance de Esquiva.",
                       modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.03, source="permanent_patrulheiro_3")]),
        ],
    ),
    "permanent_mistico": _linear_tree(
        "permanent_mistico", "Legado do Místico",
        [
            TalentNode(id="permanent_mistico_1", name="Reservas Arcanas", description="+3 de Resolução máxima.",
                       modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=3, source="permanent_mistico_1")]),
            TalentNode(id="permanent_mistico_2", name="Canalização Fluida", description="+0.3 de regeneração de Resolução por turno.",
                       modifiers=[Modifier(stat=Stat.RESOURCE_REGEN_PER_TURN, kind=ModifierKind.FLAT, value=0.3, source="permanent_mistico_2")]),
            TalentNode(id="permanent_mistico_3", name="Domínio Elemental", description="+5% de dano elemental.",
                       modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.05, source="permanent_mistico_3")]),
        ],
    ),
    "permanent_guardiao": _linear_tree(
        "permanent_guardiao", "Legado do Guardião",
        [
            TalentNode(id="permanent_guardiao_1", name="Muralha Pessoal", description="+2 de Defesa.",
                       modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=2, source="permanent_guardiao_1")]),
            TalentNode(id="permanent_guardiao_2", name="Resistência Duradoura", description="+8 de PV máximo.",
                       modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=8, source="permanent_guardiao_2")]),
            TalentNode(id="permanent_guardiao_3", name="Postura Inabalável", description="+5% de resistência a status.",
                       modifiers=[Modifier(stat=Stat.STATUS_RESIST, kind=ModifierKind.FLAT, value=0.05, source="permanent_guardiao_3")]),
        ],
    ),
}

# Each legacy keeps its existing progression and gains a thematic choice
# after the first purchase. Stored node IDs and their prerequisites stay valid.
_LEGACY_BRANCHES = (
    ("human", "Persistência", Stat.STATUS_RESIST, .04, "+4 p.p. de resistência a status."),
    ("dwarf", "Mãos de Ferreiro", Stat.ARMOR_PENETRATION_PERCENT, .05, "+5 p.p. de penetração de armadura."),
    ("elf", "Olhar Distante", Stat.CRIT_MULT, .08, "+8 p.p. de dano crítico."),
    ("orc", "Sede de Batalha", Stat.LIFESTEAL_PERCENT, .02, "+2 p.p. de roubo de vida."),
    ("fada", "Ritmo das Asas", Stat.RESOURCE_REGEN_PER_TURN, .20, "+0,2 de recurso por turno."),
    ("renascido", "Eco das Sombras", Stat.SHADOW_RESIST, .08, "+8 p.p. de resistência Sombria."),
    ("construto", "Reservatório", Stat.MAX_RESOURCE, 1, "+1 de recurso máximo."),
    ("licantropo", "Pele Noturna", Stat.DEFENSE, 2, "+2 de Defesa."),
    ("meio_celestial", "Luz Interior", Stat.HEALING_DONE_PERCENT, .08, "+8 p.p. de cura causada."),
    ("guerreiro", "Fôlego Marcial", Stat.LIFESTEAL_PERCENT, .02, "+2 p.p. de roubo de vida."),
    ("patrulheiro", "Ritmo de Caça", Stat.MAX_RESOURCE, 1, "+1 de recurso máximo."),
    ("mistico", "Mãos Brandas", Stat.HEALING_DONE_PERCENT, .08, "+8 p.p. de cura causada."),
    ("guardiao", "Recuperação de Campo", Stat.HEALING_RECEIVED_PERCENT, .08, "+8 p.p. de cura recebida."),
)
for _legacy, _name, _stat, _amount, _description in _LEGACY_BRANCHES:
    _tree_id = f"permanent_{_legacy}"
    _base = PERMANENT_TREES[_tree_id].definition
    _node_id = f"{_tree_id}_utility"
    _node = TalentNode(id=_node_id, name=_name, description=_description, modifiers=[
        Modifier(stat=_stat, kind=ModifierKind.FLAT, value=_amount, source=_node_id),
    ])
    PERMANENT_TREES[_tree_id] = TalentTree(TalentTreeDef(
        id=_tree_id, name=_base.name, nodes=[*_base.nodes, _node], edges=[*_base.edges, (f"{_tree_id}_1", _node_id)],
    ))

for _archetype in ("guerreiro", "patrulheiro", "mistico", "guardiao"):
    _tree_id = f"permanent_{_archetype}"
    _base = PERMANENT_TREES[_tree_id].definition
    _node_id = f"{_tree_id}_slot"
    _node = TalentNode(
        id=_node_id, name="Repertório",
        description=f"+1 slot de habilidade ativa a partir do nível {LEGACY_SLOT_LEVEL}, até o limite de 8.",
        modifiers=[Modifier(stat=Stat.EXTRA_ACTIVE_SLOTS, kind=ModifierKind.FLAT, value=1, source=_node_id)],
    )
    PERMANENT_TREES[_tree_id] = TalentTree(TalentTreeDef(
        id=_tree_id, name=_base.name, nodes=[*_base.nodes, _node], edges=[*_base.edges, (f"{_tree_id}_3", _node_id)],
    ))
