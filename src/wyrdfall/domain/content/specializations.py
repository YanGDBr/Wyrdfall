"""Grafted Classe trees for the 9 pure Especializações (Fase 5,
docs/design/10-sistemas-de-build.md §6): each is the matching Arquétipo
Base's own tree (domain/content/{runeguard,patrulheiro,mistico,
guardiao}.py's NODES/EDGES) plus a small 2-node branch -- a passive node
(no prerequisite, immediately allocatable the moment the character
evolves) and a capstone granting the Especialização's signature ability.

Reusing the exact same node ids for the shared base portion is what lets
Character.build.talent_tree.allocated survive the swap in
GameSession._talent_tree_id_for -- see domain/specializations.py for the
qualification logic and engine/session.py for the evolution hook.
"""

from wyrdfall.domain.content.guardiao import EDGES as GUARDIAO_EDGES, NODES as GUARDIAO_NODES
from wyrdfall.domain.content.mistico import EDGES as MISTICO_EDGES, NODES as MISTICO_NODES
from wyrdfall.domain.content.patrulheiro import EDGES as PATRULHEIRO_EDGES, NODES as PATRULHEIRO_NODES
from wyrdfall.domain.content.runeguard import EDGES as GUERREIRO_EDGES, NODES as GUERREIRO_NODES
from wyrdfall.domain.models import Effect, EffectKind, Modifier, ModifierKind, Stat, TriggerEvent, TriggeredEffect
from wyrdfall.domain.talents import TalentNode, TalentTree, TalentTreeDef


def _graft(
    tree_id: str,
    name: str,
    base_nodes: list[TalentNode],
    base_edges: list[tuple[str, str]],
    branch_node_1: TalentNode,
    branch_node_2: TalentNode,
) -> TalentTree:
    nodes = [*base_nodes, branch_node_1, branch_node_2]
    edges = [*base_edges, (branch_node_1.id, branch_node_2.id)]
    return TalentTree(TalentTreeDef(id=tree_id, name=name, nodes=nodes, edges=edges))


SPECIALIZATION_TREES: dict[str, TalentTree] = {
    "guerreiro_berserker_path": _graft(
        "guerreiro_berserker_path", "Caminho do Berserker", GUERREIRO_NODES, GUERREIRO_EDGES,
        TalentNode(
            id="berserker_1", name="Fúria Crescente", description="+25% de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.25, source="berserker_1")],
        ),
        TalentNode(
            id="berserker_keystone", name="Sem Limites", cost=2,
            description="Desbloqueia a habilidade Reckless Smash.", grants_ability="reckless_smash",
        ),
    ),
    "patrulheiro_arqueiro_path": _graft(
        "patrulheiro_arqueiro_path", "Caminho do Arqueiro", PATRULHEIRO_NODES, PATRULHEIRO_EDGES,
        TalentNode(
            id="arqueiro_1", name="Pontaria de Mestre", description="+10% de chance de Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.10, source="arqueiro_1")],
        ),
        TalentNode(
            id="arqueiro_keystone", name="Chuva de Flechas", cost=2,
            description="Desbloqueia a habilidade Multi Shot.", grants_ability="multi_shot",
        ),
    ),
    "patrulheiro_gunner_path": _graft(
        "patrulheiro_gunner_path", "Caminho do Gunner", PATRULHEIRO_NODES, PATRULHEIRO_EDGES,
        TalentNode(
            id="gunner_1", name="Gatilho Leve", description="+25% de dano Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_MULT, kind=ModifierKind.MORE, value=0.25, source="gunner_1")],
        ),
        TalentNode(
            id="gunner_keystone", name="Rajada Final", cost=2,
            description="Desbloqueia a habilidade Rapid Fire.", grants_ability="rapid_fire",
        ),
    ),
    "mistico_mago_path": _graft(
        "mistico_mago_path", "Caminho do Mago", MISTICO_NODES, MISTICO_EDGES,
        TalentNode(
            id="mago_1", name="Reservas Arcanas", description="+4 de Resolução máxima.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=4, source="mago_1")],
        ),
        TalentNode(
            id="mago_keystone", name="Convergência", cost=2,
            description="Desbloqueia a habilidade Meteor.", grants_ability="meteor",
        ),
    ),
    "guardiao_colosso_path": _graft(
        "guardiao_colosso_path", "Caminho do Colosso", GUARDIAO_NODES, GUARDIAO_EDGES,
        TalentNode(
            id="colosso_1", name="Peso da Montanha", description="+15 de PV máximo.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=15, source="colosso_1")],
        ),
        TalentNode(
            id="colosso_keystone", name="Imóvel", cost=2,
            description="Desbloqueia a habilidade Unshakable.", grants_ability="unshakable",
        ),
    ),
    "guerreiro_avatar_path": _graft(
        "guerreiro_avatar_path", "Caminho do Avatar da Guerra", GUERREIRO_NODES, GUERREIRO_EDGES,
        TalentNode(
            id="avatar_1", name="Encarnação da Batalha", description="+4 de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=4, source="avatar_1")],
        ),
        TalentNode(
            id="avatar_keystone", name="Guerra Pessoal", cost=2,
            description="Desbloqueia a habilidade Annihilate.", grants_ability="annihilate",
        ),
    ),
    "patrulheiro_predador_path": _graft(
        "patrulheiro_predador_path", "Caminho do Predador Absoluto", PATRULHEIRO_NODES, PATRULHEIRO_EDGES,
        TalentNode(
            id="predador_1", name="Instinto Assassino", description="+10% de chance de Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.10, source="predador_1")],
        ),
        TalentNode(
            id="predador_keystone", name="Nunca Visto", cost=2,
            description="Desbloqueia a habilidade True Strike.", grants_ability="true_strike",
        ),
    ),
    "mistico_tecelao_path": _graft(
        "mistico_tecelao_path", "Caminho do Tecelão do Véu", MISTICO_NODES, MISTICO_EDGES,
        TalentNode(
            id="tecelao_1", name="Véu Rasgado", description="+25% de dano elemental adicional.", cost=1,
            modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.MORE, value=0.25, source="tecelao_1")],
        ),
        TalentNode(
            id="tecelao_keystone", name="Só Magia Restou", cost=2,
            description="Desbloqueia a habilidade Arcane Devastation.", grants_ability="arcane_devastation",
        ),
    ),
    "guardiao_bastiao_path": _graft(
        "guardiao_bastiao_path", "Caminho do Bastião Eterno", GUARDIAO_NODES, GUARDIAO_EDGES,
        TalentNode(
            id="bastiao_1", name="Muralha Eterna", description="+30% de Defesa adicional.", cost=1,
            modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.MORE, value=0.30, source="bastiao_1")],
        ),
        TalentNode(
            id="bastiao_keystone", name="Nunca Cai", cost=2,
            description="Desbloqueia a habilidade Fortress.", grants_ability="fortress",
        ),
    ),
    # -- Fase 7 -- kits reais para as 7 Especializações Fase 5b genuinamente
    # alcançáveis hoje (ver domain/specializations.py's docstring). Mesmo
    # formato dos 9 acima: NODES/EDGES do Arquétipo base + 1 nó passivo +
    # 1 keystone concedendo a assinatura nova (content/abilities.py).
    "patrulheiro_atirador_path": _graft(
        "patrulheiro_atirador_path", "Caminho do Atirador", PATRULHEIRO_NODES, PATRULHEIRO_EDGES,
        TalentNode(
            id="atirador_1", name="Olho Certeiro", description="+15% de dano Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_MULT, kind=ModifierKind.MORE, value=0.15, source="atirador_1")],
        ),
        TalentNode(
            id="atirador_keystone", name="Tiro Fatal", cost=2,
            description="Desbloqueia a habilidade Tiro Calculado.", grants_ability="called_shot",
        ),
    ),
    "mistico_encantador_path": _graft(
        "mistico_encantador_path", "Caminho do Encantador", MISTICO_NODES, MISTICO_EDGES,
        TalentNode(
            id="encantador_1", name="Reservas de Apoio", description="+6 de Resolução máxima.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=6, source="encantador_1")],
        ),
        TalentNode(
            id="encantador_keystone", name="Convergência de Bênçãos", cost=2,
            description="Desbloqueia a habilidade Bênção Encantada.", grants_ability="enchanted_blessing",
        ),
    ),
    "guardiao_punho_de_granito_path": _graft(
        "guardiao_punho_de_granito_path", "Caminho do Punho de Granito", GUARDIAO_NODES, GUARDIAO_EDGES,
        TalentNode(
            id="punho_de_granito_1", name="Pele Mais Dura", description="+15% de resistência a status.", cost=1,
            modifiers=[Modifier(stat=Stat.STATUS_RESIST, kind=ModifierKind.FLAT, value=0.15, source="punho_de_granito_1")],
        ),
        TalentNode(
            id="punho_de_granito_keystone", name="Punho Inabalável", cost=2,
            description="Desbloqueia a habilidade Punho Inabalável.", grants_ability="steadfast_fist",
        ),
    ),
    "patrulheiro_arqueiro_elfico_path": _graft(
        "patrulheiro_arqueiro_elfico_path", "Caminho do Arqueiro Élfico", PATRULHEIRO_NODES, PATRULHEIRO_EDGES,
        TalentNode(
            id="arqueiro_elfico_1", name="Passo Leve", description="+10% de chance de Esquiva.", cost=1,
            modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.10, source="arqueiro_elfico_1")],
        ),
        TalentNode(
            id="arqueiro_elfico_keystone", name="Flecha Perfeita", cost=2,
            description="Desbloqueia a habilidade Flecha Élfica.", grants_ability="elven_arrow",
        ),
    ),
    "guerreiro_furia_orquica_path": _graft(
        "guerreiro_furia_orquica_path", "Caminho da Fúria Órquica", GUERREIRO_NODES, GUERREIRO_EDGES,
        TalentNode(
            id="furia_orquica_1", name="Músculo Bruto", description="+4 de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=4, source="furia_orquica_1")],
        ),
        TalentNode(
            id="furia_orquica_keystone", name="Fúria Sem Fim", cost=2,
            description="Desbloqueia a habilidade Fúria Desmedida.", grants_ability="unbridled_fury",
        ),
    ),
    "guerreiro_lamina_espectral_path": _graft(
        "guerreiro_lamina_espectral_path", "Caminho da Lâmina Espectral", GUERREIRO_NODES, GUERREIRO_EDGES,
        TalentNode(
            id="lamina_espectral_1", name="Fome Espectral", description="+10% de roubo de vida.", cost=1,
            modifiers=[Modifier(stat=Stat.LIFESTEAL_PERCENT, kind=ModifierKind.FLAT, value=0.10, source="lamina_espectral_1")],
        ),
        TalentNode(
            id="lamina_espectral_keystone", name="Fome Eterna", cost=2,
            description="Desbloqueia a habilidade Corte Espectral.", grants_ability="spectral_cut",
        ),
    ),
    "guerreiro_uivo_selvagem_path": _graft(
        "guerreiro_uivo_selvagem_path", "Caminho do Uivo Selvagem", GUERREIRO_NODES, GUERREIRO_EDGES,
        TalentNode(
            id="uivo_selvagem_1", name="Sangue Fervendo", description="+4 de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=4, source="uivo_selvagem_1")],
        ),
        TalentNode(
            id="uivo_selvagem_keystone", name="Chamado da Matilha", cost=2,
            description="Desbloqueia a habilidade Uivo Selvagem.", grants_ability="wild_howl",
        ),
    ),
    # -- Fase 7 -- assinaturas de Alinhamento (05b-classes-roster.md §7),
    # alcançáveis desde que Eventos escrevem alignment_score.
    "guardiao_guardiao_da_floresta_path": _graft(
        "guardiao_guardiao_da_floresta_path", "Caminho do Guardião da Floresta", GUARDIAO_NODES, GUARDIAO_EDGES,
        TalentNode(
            id="guardiao_da_floresta_1", name="Raízes Profundas", description="+20% de cura recebida.", cost=1,
            modifiers=[
                Modifier(stat=Stat.HEALING_RECEIVED_PERCENT, kind=ModifierKind.FLAT, value=0.20, source="guardiao_da_floresta_1")
            ],
        ),
        TalentNode(
            id="guardiao_da_floresta_keystone", name="Coração da Mata", cost=2,
            description="Desbloqueia a habilidade Abraço da Floresta.", grants_ability="forest_embrace",
        ),
    ),
    "guerreiro_cavaleiro_negro_path": _graft(
        "guerreiro_cavaleiro_negro_path", "Caminho do Cavaleiro Negro", GUERREIRO_NODES, GUERREIRO_EDGES,
        TalentNode(
            id="cavaleiro_negro_1", name="Malícia", description="+15% de dano físico.", cost=1,
            modifiers=[Modifier(stat=Stat.PHYSICAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.15, source="cavaleiro_negro_1")],
        ),
        TalentNode(
            id="cavaleiro_negro_keystone", name="Juramento Negro", cost=2,
            description="Desbloqueia a habilidade Golpe Maldito.", grants_ability="cursed_blow",
        ),
    ),
    "mistico_senhor_da_peste_path": _graft(
        "mistico_senhor_da_peste_path", "Caminho do Senhor da Peste", MISTICO_NODES, MISTICO_EDGES,
        TalentNode(
            id="senhor_da_peste_1", name="Atrição", description="+0.5 de Resolução por turno.", cost=1,
            modifiers=[Modifier(stat=Stat.RESOURCE_REGEN_PER_TURN, kind=ModifierKind.FLAT, value=0.5, source="senhor_da_peste_1")],
        ),
        TalentNode(
            id="senhor_da_peste_keystone", name="Portador da Peste", cost=2,
            description="Desbloqueia a habilidade Praga.", grants_ability="plague",
        ),
    ),
}


# -- Híbridos de par (Fase 5b's 17, kits authored now that Habilidades
# Exclusivas de Arma and Tomos make cross-archetype usage real): a hybrid
# can be reached from either of its archetypes, so its 2-node branch is
# grafted onto EACH of the 4 base trees -- "<archetype>_<spec>_path" --
# and engine/session.py::_talent_tree_id_for picks the one matching the
# character's own base archetype, keeping every allocated node.
_BASE_TREES: dict[str, tuple[list[TalentNode], list[tuple[str, str]]]] = {
    "guerreiro": (GUERREIRO_NODES, GUERREIRO_EDGES),
    "patrulheiro": (PATRULHEIRO_NODES, PATRULHEIRO_EDGES),
    "mistico": (MISTICO_NODES, MISTICO_EDGES),
    "guardiao": (GUARDIAO_NODES, GUARDIAO_EDGES),
}

_HYBRID_BRANCHES: dict[str, tuple[str, TalentNode, TalentNode]] = {
    "arqueiro_berserker": (
        "Caminho do Arqueiro-Berserker",
        TalentNode(
            id="arqueiro_berserker_1", name="Duas Mãos", description="+15% de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.15, source="arqueiro_berserker_1")],
        ),
        TalentNode(
            id="arqueiro_berserker_keystone", name="Fúria de Longe", cost=2,
            description="Desbloqueia a habilidade Rajada Selvagem.", grants_ability="hybrid_savage_volley",
        ),
    ),
    "gunner_berserker": (
        "Caminho do Gunner-Berserker",
        TalentNode(
            id="gunner_berserker_1", name="Pólvora no Sangue", description="+20% de dano Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_MULT, kind=ModifierKind.MORE, value=0.2, source="gunner_berserker_1")],
        ),
        TalentNode(
            id="gunner_berserker_keystone", name="Tiro Furioso", cost=2,
            description="Desbloqueia a habilidade Tiro Furioso.", grants_ability="hybrid_furious_shot",
        ),
    ),
    "paladino": (
        "Caminho do Paladino",
        TalentNode(
            id="paladino_1", name="Voto", description="+15% de cura causada.", cost=1,
            modifiers=[Modifier(stat=Stat.HEALING_DONE_PERCENT, kind=ModifierKind.FLAT, value=0.15, source="paladino_1")],
        ),
        TalentNode(
            id="paladino_keystone", name="Luz da Lâmina", cost=2,
            description="Desbloqueia a habilidade Golpe Sagrado.", grants_ability="hybrid_holy_strike",
        ),
    ),
    "mago_runico": (
        "Caminho do Mago Rúnico",
        TalentNode(
            id="mago_runico_1", name="Runas Gravadas", description="+15% de dano elemental.", cost=1,
            modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.15, source="mago_runico_1")],
        ),
        TalentNode(
            id="mago_runico_keystone", name="Lâmina Rúnica", cost=2,
            description="Desbloqueia a habilidade Lâmina Rúnica.", grants_ability="hybrid_rune_blade",
        ),
    ),
    "cavaleiro_arcano": (
        "Caminho do Cavaleiro Arcano",
        TalentNode(
            id="cavaleiro_arcano_1", name="Armadura Arcana", description="+3 de Defesa.", cost=1,
            modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=3, source="cavaleiro_arcano_1")],
        ),
        TalentNode(
            id="cavaleiro_arcano_keystone", name="Ímpeto Arcano", cost=2,
            description="Desbloqueia a habilidade Ímpeto Arcano.", grants_ability="hybrid_arcane_charge",
        ),
    ),
    "cavaleiro": (
        "Caminho do Cavaleiro",
        TalentNode(
            id="cavaleiro_1", name="Disciplina", description="+10% de chance de Bloqueio.", cost=1,
            modifiers=[Modifier(stat=Stat.BLOCK_CHANCE, kind=ModifierKind.FLAT, value=0.1, source="cavaleiro_1")],
        ),
        TalentNode(
            id="cavaleiro_keystone", name="Golpe do Cavaleiro", cost=2,
            description="Desbloqueia a habilidade Golpe do Cavaleiro.", grants_ability="hybrid_knight_strike",
        ),
    ),
    "cavaleiro_pesado": (
        "Caminho do Cavaleiro Pesado",
        TalentNode(
            id="cavaleiro_pesado_1", name="Couraça", description="+8 de PV máximo.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=8, source="cavaleiro_pesado_1")],
        ),
        TalentNode(
            id="cavaleiro_pesado_keystone", name="Peso da Armadura", cost=2,
            description="Desbloqueia a habilidade Esmagamento Blindado.", grants_ability="hybrid_armored_crush",
        ),
    ),
    "juggernaut": (
        "Caminho do Juggernaut",
        TalentNode(
            id="juggernaut_1", name="Imparável", description="+20% de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.2, source="juggernaut_1")],
        ),
        TalentNode(
            id="juggernaut_keystone", name="Avalanche", cost=2,
            description="Desbloqueia a habilidade Avalanche.", grants_ability="hybrid_juggernaut_rush",
        ),
    ),
    "domador": (
        "Caminho do Domador",
        TalentNode(
            id="domador_1", name="Laço com a Fera", description="+10% de Esquiva.", cost=1,
            modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.1, source="domador_1")],
        ),
        TalentNode(
            id="domador_keystone", name="Comando", cost=2,
            description="Desbloqueia a habilidade Comando da Fera.", grants_ability="hybrid_beast_command",
        ),
    ),
    "invocador": (
        "Caminho do Invocador",
        TalentNode(
            id="invocador_1", name="Vínculo", description="+4 de Resolução máxima.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=4, source="invocador_1")],
        ),
        TalentNode(
            id="invocador_keystone", name="Chamado Espectral", cost=2,
            description="Desbloqueia a habilidade Chamado Espectral.", grants_ability="hybrid_spectral_call",
        ),
    ),
    "cacador_arcano": (
        "Caminho do Caçador Arcano",
        TalentNode(
            id="cacador_arcano_1", name="Marca Arcana", description="+10% de chance de Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.1, source="cacador_arcano_1")],
        ),
        TalentNode(
            id="cacador_arcano_keystone", name="Flecha Encantada", cost=2,
            description="Desbloqueia a habilidade Flecha Encantada.", grants_ability="hybrid_spellbound_arrow",
        ),
    ),
    "arqueiro_mago": (
        "Caminho do Arqueiro-Mago",
        TalentNode(
            id="arqueiro_mago_1", name="Corda de Éter", description="+15% de dano elemental.", cost=1,
            modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.15, source="arqueiro_mago_1")],
        ),
        TalentNode(
            id="arqueiro_mago_keystone", name="Chuva de Éter", cost=2,
            description="Desbloqueia a habilidade Chuva de Éter.", grants_ability="hybrid_ether_rain",
        ),
    ),
    "sentinela": (
        "Caminho da Sentinela",
        TalentNode(
            id="sentinela_1", name="Vigília", description="+2 de Defesa.", cost=1,
            modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=2, source="sentinela_1")],
        ),
        TalentNode(
            id="sentinela_keystone", name="Tiro de Cobertura", cost=2,
            description="Desbloqueia a habilidade Tiro de Cobertura.", grants_ability="hybrid_covering_shot",
        ),
    ),
    "bastiao_movel": (
        "Caminho do Bastião Móvel",
        TalentNode(
            id="bastiao_movel_1", name="Passo Firme", description="+1 de Velocidade.", cost=1,
            modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=1, source="bastiao_movel_1")],
        ),
        TalentNode(
            id="bastiao_movel_keystone", name="Muralha em Marcha", cost=2,
            description="Desbloqueia a habilidade Muralha em Marcha.", grants_ability="hybrid_marching_wall",
        ),
    ),
    "avatar": (
        "Caminho do Avatar",
        TalentNode(
            id="avatar_1", name="Presença", description="+15% de cura recebida.", cost=1,
            modifiers=[Modifier(stat=Stat.HEALING_RECEIVED_PERCENT, kind=ModifierKind.FLAT, value=0.15, source="avatar_1")],
        ),
        TalentNode(
            id="avatar_keystone", name="Égide", cost=2,
            description="Desbloqueia a habilidade Égide.", grants_ability="hybrid_aegis",
        ),
    ),
    "guardiao_arcano": (
        "Caminho do Guardião Arcano",
        TalentNode(
            id="guardiao_arcano_1", name="Barreira", description="+10% de chance de Bloqueio.", cost=1,
            modifiers=[Modifier(stat=Stat.BLOCK_CHANCE, kind=ModifierKind.FLAT, value=0.1, source="guardiao_arcano_1")],
        ),
        TalentNode(
            id="guardiao_arcano_keystone", name="Selo Protetor", cost=2,
            description="Desbloqueia a habilidade Selo Protetor.", grants_ability="hybrid_warding_seal",
        ),
    ),
    "sacerdote_blindado": (
        "Caminho do Sacerdote Blindado",
        TalentNode(
            id="sacerdote_blindado_1", name="Fé de Ferro", description="+6 de PV máximo.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=6, source="sacerdote_blindado_1")],
        ),
        TalentNode(
            id="sacerdote_blindado_keystone", name="Prece Blindada", cost=2,
            description="Desbloqueia a habilidade Prece Blindada.", grants_ability="hybrid_armored_prayer",
        ),
    ),
    # -- triples, generalists, and the remaining signatures (same per-base graft)
    "lamina_do_crepusculo": (
        "Caminho da Lâmina do Crepúsculo",
        TalentNode(
            id="lamina_do_crepusculo_1", name="Três Ofícios", description="+10% de chance de Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.1, source="lamina_do_crepusculo_1")],
        ),
        TalentNode(
            id="lamina_do_crepusculo_keystone", name="Crepúsculo", cost=2,
            description="Desbloqueia a habilidade Gume do Crepúsculo.", grants_ability="triple_twilight_edge",
        ),
    ),
    "capitao_de_vanguarda": (
        "Caminho do Capitão de Vanguarda",
        TalentNode(
            id="capitao_de_vanguarda_1", name="Comando", description="+2 de Defesa.", cost=1,
            modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=2, source="capitao_de_vanguarda_1")],
        ),
        TalentNode(
            id="capitao_de_vanguarda_keystone", name="Ordem de Avanço", cost=2,
            description="Desbloqueia a habilidade Ordem de Avanço.", grants_ability="triple_vanguard_order",
        ),
    ),
    "campeao_runico": (
        "Caminho do Campeão Rúnico",
        TalentNode(
            id="campeao_runico_1", name="Runas na Pele", description="+15% de dano elemental.", cost=1,
            modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.15, source="campeao_runico_1")],
        ),
        TalentNode(
            id="campeao_runico_keystone", name="Juramento Rúnico", cost=2,
            description="Desbloqueia a habilidade Juramento Rúnico.", grants_ability="triple_runic_oath",
        ),
    ),
    "vigia_arcano": (
        "Caminho do Vigia Arcano",
        TalentNode(
            id="vigia_arcano_1", name="Vigília Longa", description="+10% de Esquiva.", cost=1,
            modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.1, source="vigia_arcano_1")],
        ),
        TalentNode(
            id="vigia_arcano_keystone", name="Sentinela Arcana", cost=2,
            description="Desbloqueia a habilidade Vigília Arcana.", grants_ability="triple_arcane_watch",
        ),
    ),
    "errante_do_wyrd": (
        "Caminho do Errante do Wyrd",
        TalentNode(
            id="errante_do_wyrd_1", name="Pau pra Toda Obra", description="+10% de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.1, source="errante_do_wyrd_1")],
        ),
        TalentNode(
            id="errante_do_wyrd_keystone", name="Improviso", cost=2,
            description="Desbloqueia a habilidade Improviso.", grants_ability="errante_improvise",
        ),
    ),
    "andarilho_do_caminho_cinza": (
        "Caminho do Andarilho do Caminho Cinza",
        TalentNode(
            id="andarilho_do_caminho_cinza_1", name="Equilíbrio", description="+5% em todas as resistências elementais.", cost=1,
            modifiers=[Modifier(stat=Stat.GENERAL_ELEMENTAL_RESIST, kind=ModifierKind.FLAT, value=0.05, source="andarilho_do_caminho_cinza_1")],
        ),
        TalentNode(
            id="andarilho_do_caminho_cinza_keystone", name="Passo Cinza", cost=2,
            description="Desbloqueia a habilidade Passo Cinza.", grants_ability="grey_path_step",
        ),
    ),
    "andarilho_versatil": (
        "Caminho do Andarilho Versátil",
        TalentNode(
            id="andarilho_versatil_1", name="Adaptável", description="+1 de Velocidade.", cost=1,
            modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=1, source="andarilho_versatil_1")],
        ),
        TalentNode(
            id="andarilho_versatil_keystone", name="Mil Ofícios", cost=2,
            description="Desbloqueia a habilidade Mil Ofícios.", grants_ability="versatile_trick",
        ),
    ),
    "justiceiro": (
        "Caminho do Justiceiro",
        TalentNode(
            id="justiceiro_1", name="Coração Reto", description="+20% de cura causada.", cost=1,
            modifiers=[Modifier(stat=Stat.HEALING_DONE_PERCENT, kind=ModifierKind.FLAT, value=0.2, source="justiceiro_1")],
        ),
        TalentNode(
            id="justiceiro_keystone", name="Julgamento", cost=2,
            description="Desbloqueia a habilidade Julgamento.", grants_ability="justiceiro_judgment",
        ),
    ),
    "chama_ferica": (
        "Caminho da Chama Feérica",
        TalentNode(
            id="chama_ferica_1", name="Sorte do Acaso", description="+10% em chances de proc.", cost=1,
            modifiers=[Modifier(stat=Stat.PROC_CHANCE_PERCENT, kind=ModifierKind.FLAT, value=0.1, source="chama_ferica_1")],
        ),
        TalentNode(
            id="chama_ferica_keystone", name="Fogo-Fátuo", cost=2,
            description="Desbloqueia a habilidade Fogo-Fátuo.", grants_ability="fae_flame",
        ),
    ),
    "avatar_dividido": (
        "Caminho do Avatar Dividido",
        TalentNode(
            id="avatar_dividido_1", name="Alternância", description="+1 troca de forma por combate.", cost=1,
            modifiers=[Modifier(stat=Stat.EXTRA_USES_PER_COMBAT, kind=ModifierKind.FLAT, value=1, source="avatar_dividido_1")],
        ),
        TalentNode(
            id="avatar_dividido_keystone", name="Luz e Sombra", cost=2,
            description="Desbloqueia a habilidade Luz e Sombra.", grants_ability="luz_e_sombra",
        ),
    ),
    "nucleo_de_batalha": (
        "Caminho do Núcleo de Batalha",
        TalentNode(
            id="nucleo_de_batalha_1", name="Chapa Grossa", description="+4 de Defesa.", cost=1,
            modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=4, source="nucleo_de_batalha_1")],
        ),
        TalentNode(
            id="nucleo_de_batalha_keystone", name="Núcleo Ativo", cost=2,
            description="Desbloqueia a habilidade Núcleo Ativo.", grants_ability="core_overdrive",
        ),
    ),
}

for _spec_id, (_name, _node_1, _keystone) in _HYBRID_BRANCHES.items():
    for _archetype, (_nodes, _edges) in _BASE_TREES.items():
        _tree = _graft(f"{_archetype}_{_spec_id}_path", _name, _nodes, _edges, _node_1, _keystone)
        SPECIALIZATION_TREES[_tree.definition.id] = _tree


# -- Estágio 2 (Fase 8, docs/design/05b-classes-roster.md §10 / 10-sistemas-
# de-build.md §6 "se houver um Estágio 2, o mesmo acontece de novo"): each
# Stage-2 tree is its Stage-1 tree -- base archetype nodes + the Stage-1
# branch -- plus a further 2-node branch, so every node id allocated
# through both evolutions survives the second swap exactly like the
# first. Keyed by the Stage-2 id in domain/specializations.py::STAGE2_DEFS;
# the tree id is "<archetype>_<stage2>_path" to match granted_tree_id.
# Optional alternatives to rushing the signature ability. Added before grafting
# Stage 2 so an investment here remains active after ascending.
_REFERENCE_TALENTS = (
    ("guerreiro_berserker_path", "berserker_1", "Ímpeto", Stat.ARMOR_PENETRATION_PERCENT, .08, "+8 p.p. de penetração de armadura."),
    ("guerreiro_avatar_path", "avatar_1", "Guarda de Guerra", Stat.DEFENSE, 3, "+3 de Defesa."),
    ("patrulheiro_arqueiro_path", "arqueiro_1", "Distância Segura", Stat.DODGE_CHANCE, .04, "+4 p.p. de Esquiva."),
    ("patrulheiro_atirador_path", "atirador_1", "Ponto Fraco", Stat.ARMOR_PENETRATION_PERCENT, .10, "+10 p.p. de penetração de armadura."),
    ("mistico_mago_path", "mago_1", "Pavio Longo", Stat.RESOURCE_REGEN_PER_TURN, .35, "+0,35 de Mana por turno."),
    ("mistico_encantador_path", "encantador_1", "Canal de Retorno", Stat.HEALING_DONE_PERCENT, .10, "+10 p.p. de cura causada."),
    ("guardiao_colosso_path", "colosso_1", "Peso do Escudo", Stat.ATTACK, 2, "+2 de Ataque."),
    ("guardiao_bastiao_path", "bastiao_1", "Fôlego da Muralha", Stat.HEALING_RECEIVED_PERCENT, .12, "+12 p.p. de cura recebida."),
)

for _tree_id, _parent, _name, _stat, _value, _description in _REFERENCE_TALENTS:
    _base = SPECIALIZATION_TREES[_tree_id].definition
    _node_id = f"{_parent}_alternative"
    _node = TalentNode(
        id=_node_id, name=_name, description=_description, cost=1,
        modifiers=[Modifier(stat=_stat, kind=ModifierKind.FLAT, value=_value, source=_node_id)],
    )
    SPECIALIZATION_TREES[_tree_id] = TalentTree(TalentTreeDef(
        id=_tree_id, name=_base.name, nodes=[*_base.nodes, _node], edges=[*_base.edges, (_parent, _node_id)],
    ))


_STAGE2_BRANCHES: dict[str, tuple[str, str, TalentNode, TalentNode]] = {
    "senhor_da_guerra": (
        "guerreiro_berserker_path", "Caminho do Senhor da Guerra",
        TalentNode(
            id="senhor_da_guerra_1", name="Fúria Dirigida", description="+10% de chance de Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.1, source="senhor_da_guerra_1")],
        ),
        TalentNode(
            id="senhor_da_guerra_keystone", name="Cadeia de Golpes", cost=2,
            description="Desbloqueia a habilidade Tempestade de Golpes.", grants_ability="storm_of_blows",
        ),
    ),
    "encarnacao_da_batalha": (
        "guerreiro_avatar_path", "Caminho da Encarnação da Batalha",
        TalentNode(
            id="encarnacao_da_batalha_1", name="Sem Medo", description="+30% de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.3, source="encarnacao_da_batalha_1")],
        ),
        TalentNode(
            id="encarnacao_da_batalha_keystone", name="Guerra Viva", cost=2,
            description="Desbloqueia a habilidade Guerra Encarnada.", grants_ability="war_incarnate",
        ),
    ),
    "lorde_da_ruina": (
        "guerreiro_cavaleiro_negro_path", "Caminho do Lorde da Ruína",
        TalentNode(
            id="lorde_da_ruina_1", name="Coroa Negra", description="+10% de Roubo de Vida.", cost=1,
            modifiers=[Modifier(stat=Stat.LIFESTEAL_PERCENT, kind=ModifierKind.FLAT, value=0.1, source="lorde_da_ruina_1")],
        ),
        TalentNode(
            id="lorde_da_ruina_keystone", name="Trono da Ruína", cost=2,
            description="Desbloqueia a habilidade Édito da Ruína.", grants_ability="ruinous_edict",
        ),
    ),
    "senhor_da_horda": (
        "guerreiro_furia_orquica_path", "Caminho do Senhor da Horda",
        TalentNode(
            id="senhor_da_horda_1", name="Voz da Horda", description="+6 de PV máximo.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=6, source="senhor_da_horda_1")],
        ),
        TalentNode(
            id="senhor_da_horda_keystone", name="Grito de Guerra", cost=2,
            description="Desbloqueia a habilidade Chamado da Horda.", grants_ability="horde_call",
        ),
    ),
    "ceifador_espectral": (
        "guerreiro_lamina_espectral_path", "Caminho do Ceifador Espectral",
        TalentNode(
            id="ceifador_espectral_1", name="Meio-Morto", description="+10% de Esquiva.", cost=1,
            modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.1, source="ceifador_espectral_1")],
        ),
        TalentNode(
            id="ceifador_espectral_keystone", name="A Foice", cost=2,
            description="Desbloqueia a habilidade Ceifar o Fio.", grants_ability="reap_the_thread",
        ),
    ),
    "alfa": (
        "guerreiro_uivo_selvagem_path", "Caminho do Alfa",
        TalentNode(
            id="alfa_1", name="Líder da Matilha", description="+2 de Velocidade.", cost=1,
            modifiers=[Modifier(stat=Stat.SPEED, kind=ModifierKind.FLAT, value=2, source="alfa_1")],
        ),
        TalentNode(
            id="alfa_keystone", name="Uivo Supremo", cost=2,
            description="Desbloqueia a habilidade Uivo do Alfa.", grants_ability="alpha_howl",
        ),
    ),
    "mestre_arqueiro": (
        "patrulheiro_arqueiro_path", "Caminho do Mestre Arqueiro",
        TalentNode(
            id="mestre_arqueiro_1", name="Olho de Águia", description="+15% de chance de Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.15, source="mestre_arqueiro_1")],
        ),
        TalentNode(
            id="mestre_arqueiro_keystone", name="Mestre do Arco", cost=2,
            description="Desbloqueia a habilidade Salva do Mestre.", grants_ability="master_volley",
        ),
    ),
    "pistoleiro": (
        "patrulheiro_gunner_path", "Caminho do Pistoleiro",
        TalentNode(
            id="pistoleiro_1", name="Mão Firme", description="+40% de dano Crítico.", cost=1,
            modifiers=[Modifier(stat=Stat.CRIT_MULT, kind=ModifierKind.MORE, value=0.4, source="pistoleiro_1")],
        ),
        TalentNode(
            id="pistoleiro_keystone", name="Tiro Final", cost=2,
            description="Desbloqueia a habilidade Bala Certeira.", grants_ability="deadeye_round",
        ),
    ),
    "cacador_de_tesouros": (
        "patrulheiro_atirador_path", "Caminho do Caçador de Tesouros",
        TalentNode(
            id="cacador_de_tesouros_1", name="Faro pra Ouro", description="+20% de dano físico.", cost=1,
            modifiers=[Modifier(stat=Stat.PHYSICAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.2, source="cacador_de_tesouros_1")],
        ),
        TalentNode(
            id="cacador_de_tesouros_keystone", name="Sorte Grande", cost=2,
            description="Desbloqueia a habilidade Tiro da Fortuna.", grants_ability="fortune_shot",
        ),
    ),
    "sombra_da_mata": (
        "patrulheiro_predador_path", "Caminho da Sombra da Mata",
        TalentNode(
            id="sombra_da_mata_1", name="Passo Silencioso", description="+15% de Esquiva.", cost=1,
            modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.15, source="sombra_da_mata_1")],
        ),
        TalentNode(
            id="sombra_da_mata_keystone", name="Predador Invisível", cost=2,
            description="Desbloqueia a habilidade Golpe Invisível.", grants_ability="unseen_strike",
        ),
    ),
    "olho_da_lua": (
        "patrulheiro_arqueiro_elfico_path", "Caminho do Olho da Lua",
        TalentNode(
            id="olho_da_lua_1", name="Luz Élfica", description="+20% de dano elemental.", cost=1,
            modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.2, source="olho_da_lua_1")],
        ),
        TalentNode(
            id="olho_da_lua_keystone", name="Bênção Lunar", cost=2,
            description="Desbloqueia a habilidade Flecha do Luar.", grants_ability="moonlit_arrow",
        ),
    ),
    "arquimago": (
        "mistico_mago_path", "Caminho do Arquimago",
        TalentNode(
            id="arquimago_1", name="Domínio Arcano", description="+8 de Resolução máxima.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_RESOURCE, kind=ModifierKind.FLAT, value=8, source="arquimago_1")],
        ),
        TalentNode(
            id="arquimago_keystone", name="Cataclismo", cost=2,
            description="Desbloqueia a habilidade Cataclismo Arcano.", grants_ability="arcane_cataclysm",
        ),
    ),
    "cantor_do_wyrd": (
        "mistico_encantador_path", "Caminho do Cantor do Wyrd",
        TalentNode(
            id="cantor_do_wyrd_1", name="Voz Clara", description="+25% de cura causada.", cost=1,
            modifiers=[Modifier(stat=Stat.HEALING_DONE_PERCENT, kind=ModifierKind.FLAT, value=0.25, source="cantor_do_wyrd_1")],
        ),
        TalentNode(
            id="cantor_do_wyrd_keystone", name="Canção Final", cost=2,
            description="Desbloqueia a habilidade Canção do Wyrd.", grants_ability="wyrd_song",
        ),
    ),
    "oraculo_do_veu": (
        "mistico_tecelao_path", "Caminho do Oráculo do Véu",
        TalentNode(
            id="oraculo_do_veu_1", name="Olhos do Véu", description="+1 de Resolução por turno.", cost=1,
            modifiers=[Modifier(stat=Stat.RESOURCE_REGEN_PER_TURN, kind=ModifierKind.FLAT, value=1.0, source="oraculo_do_veu_1")],
        ),
        TalentNode(
            id="oraculo_do_veu_keystone", name="Leitura Total", cost=2,
            description="Desbloqueia a habilidade Leitura do Véu.", grants_ability="veil_reading",
        ),
    ),
    "arauto_da_praga": (
        "mistico_senhor_da_peste_path", "Caminho do Arauto da Praga",
        TalentNode(
            id="arauto_da_praga_1", name="Sangue Podre", description="+30% de dano elemental.", cost=1,
            modifiers=[Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=0.3, source="arauto_da_praga_1")],
        ),
        TalentNode(
            id="arauto_da_praga_keystone", name="Peste Final", cost=2,
            description="Desbloqueia a habilidade Arauto da Praga.", grants_ability="plague_herald",
        ),
    ),
    "tita": (
        "guardiao_colosso_path", "Caminho do Titã",
        TalentNode(
            id="tita_1", name="Pele de Pedra", description="+4 de Defesa.", cost=1,
            modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=4, source="tita_1")],
        ),
        TalentNode(
            id="tita_keystone", name="Força Titânica", cost=2,
            description="Desbloqueia a habilidade Golpe Titânico.", grants_ability="titanic_blow",
        ),
    ),
    "muralha_viva": (
        "guardiao_bastiao_path", "Caminho da Muralha Viva",
        TalentNode(
            id="muralha_viva_1", name="Alicerce", description="+15% de chance de Bloqueio.", cost=1,
            modifiers=[Modifier(stat=Stat.BLOCK_CHANCE, kind=ModifierKind.FLAT, value=0.15, source="muralha_viva_1")],
        ),
        TalentNode(
            id="muralha_viva_keystone", name="Fortaleza", cost=2,
            description="Desbloqueia a habilidade Muralha Viva.", grants_ability="living_rampart",
        ),
    ),
    "coracao_da_floresta": (
        "guardiao_guardiao_da_floresta_path", "Caminho do Coração da Floresta",
        TalentNode(
            id="coracao_da_floresta_1", name="Seiva", description="+25% de cura recebida.", cost=1,
            modifiers=[Modifier(stat=Stat.HEALING_RECEIVED_PERCENT, kind=ModifierKind.FLAT, value=0.25, source="coracao_da_floresta_1")],
        ),
        TalentNode(
            id="coracao_da_floresta_keystone", name="Cerne Vivo", cost=2,
            description="Desbloqueia a habilidade Florescer do Cerne.", grants_ability="heartwood_bloom",
        ),
    ),
    "coracao_da_montanha": (
        "guardiao_punho_de_granito_path", "Caminho do Coração da Montanha",
        TalentNode(
            id="coracao_da_montanha_1", name="Raiz de Granito", description="+10 de PV máximo.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=10, source="coracao_da_montanha_1")],
        ),
        TalentNode(
            id="coracao_da_montanha_keystone", name="A Montanha", cost=2,
            description="Desbloqueia a habilidade Coração da Montanha.", grants_ability="mountain_heart",
        ),
    ),
    "arqueiro_berserker_s2": (
        "guerreiro_berserker_path", "Caminho do Arqueiro-Berserker",
        TalentNode(
            id="arqueiro_berserker_s2_1", name="Arco e Lâmina", description="+15% de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.15, source="arqueiro_berserker_s2_1")],
        ),
        TalentNode(
            id="arqueiro_berserker_s2_keystone", name="Fúria de Corda", cost=2,
            description="Desbloqueia a habilidade Fúria de Corda.", grants_ability="berserker_bowstring_fury",
        ),
    ),
}


def _graft_stage2(stage2_id: str, stage1_tree_id: str, name: str, node_1: TalentNode, keystone: TalentNode) -> TalentTree:
    base = SPECIALIZATION_TREES[stage1_tree_id].definition
    archetype_prefix = stage1_tree_id.split("_", 1)[0]
    return _graft(f"{archetype_prefix}_{stage2_id}_path", name, base.nodes, base.edges, node_1, keystone)


for _stage2_id, (_stage1_tree_id, _name, _node_1, _keystone) in _STAGE2_BRANCHES.items():
    _tree = _graft_stage2(_stage2_id, _stage1_tree_id, _name, _node_1, _keystone)
    SPECIALIZATION_TREES[_tree.definition.id] = _tree


# -- Stage 2 ascending from a HYBRID Stage 1 (05b §10's Juggernaut/Colosso
# from Cavaleiro Pesado): one tree per base archetype, grafted onto that
# base's Stage-1 hybrid tree, mirroring _HYBRID_BRANCHES.
_STAGE2_HYBRID_BRANCHES: dict[str, tuple[str, str, TalentNode, TalentNode]] = {
    "sentinela_da_alvorada": (
        "paladino", "Caminho da Sentinela da Alvorada",
        TalentNode(id="sentinela_da_alvorada_1", name="Voto Renovado", description="+10 p.p. de cura causada.",
                   modifiers=[Modifier(stat=Stat.HEALING_DONE_PERCENT, kind=ModifierKind.FLAT,
                                       value=.10, source="sentinela_da_alvorada_1")]),
        TalentNode(id="sentinela_da_alvorada_keystone", name="Alvorada Compartilhada", cost=2,
                   description="Ao aproveitar uma marca aliada, ganha 8 de Escudo.",
                   triggered_effects=[TriggeredEffect(trigger=TriggerEvent.ON_TEAM_COMBO, applies_to="self",
                       effect=Effect(kind=EffectKind.APPLY_SHIELD, amount=8), source="sentinela_da_alvorada_keystone")]),
    ),
    "fio_do_eclipse": (
        "lamina_do_crepusculo", "Caminho do Fio do Eclipse",
        TalentNode(id="fio_do_eclipse_1", name="Ângulo Morto", description="+4 p.p. de Crítico.",
                   modifiers=[Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=.04, source="fio_do_eclipse_1")]),
        TalentNode(id="fio_do_eclipse_keystone", name="Ritmo do Eclipse", cost=2,
                   description="Críticos recuperam 1 ponto do seu recurso.",
                   triggered_effects=[TriggeredEffect(trigger=TriggerEvent.ON_CRIT, applies_to="self",
                       effect=Effect(kind=EffectKind.RESTORE_RESOURCE, amount=1), source="fio_do_eclipse_keystone")]),
    ),
    "convergencia_celestial": (
        "avatar_dividido", "Caminho da Convergência Celestial",
        TalentNode(id="convergencia_celestial_1", name="Entre Dois Mundos", description="+10 p.p. de resistência Sagrada e Sombria.",
                   modifiers=[Modifier(stat=stat, kind=ModifierKind.FLAT, value=.10, source="convergencia_celestial_1")
                              for stat in (Stat.HOLY_RESIST, Stat.SHADOW_RESIST)]),
        TalentNode(id="convergencia_celestial_keystone", name="Manto do Horizonte", cost=2,
                   description="Começa o combate com 10 de Escudo.",
                   triggered_effects=[TriggeredEffect(trigger=TriggerEvent.ON_COMBAT_START, applies_to="self",
                       effect=Effect(kind=EffectKind.APPLY_SHIELD, amount=10), source="convergencia_celestial_keystone")]),
    ),
    "juggernaut_s2": (
        "cavaleiro_pesado", "Caminho do Juggernaut",
        TalentNode(
            id="juggernaut_s2_1", name="Massa em Movimento", description="+20% de Ataque.", cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.2, source="juggernaut_s2_1")],
        ),
        TalentNode(
            id="juggernaut_s2_keystone", name="Imparável", cost=2,
            description="Desbloqueia a habilidade Imparável.", grants_ability="juggernaut_unstoppable",
        ),
    ),
    "colosso_s2": (
        "cavaleiro_pesado", "Caminho do Colosso",
        TalentNode(
            id="colosso_s2_1", name="Pé Firme", description="+10 de PV máximo.", cost=1,
            modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=10, source="colosso_s2_1")],
        ),
        TalentNode(
            id="colosso_s2_keystone", name="Peso do Mundo", cost=2,
            description="Desbloqueia a habilidade Peso do Mundo.", grants_ability="colosso_world_weight",
        ),
    ),
}

for _stage2_id, (_stage1_id, _name, _node_1, _keystone) in _STAGE2_HYBRID_BRANCHES.items():
    for _archetype in _BASE_TREES:
        _base = SPECIALIZATION_TREES[f"{_archetype}_{_stage1_id}_path"].definition
        _tree = _graft(f"{_archetype}_{_stage2_id}_path", _name, _base.nodes, _base.edges, _node_1, _keystone)
        SPECIALIZATION_TREES[_tree.definition.id] = _tree


def _rebase_fixed_trees() -> None:
    """Every fixed `granted_tree_id` tree above was authored on one base
    archetype's nodes -- but Afinidade drifts (05-classes.md §2: an
    off-archetype weapon is *the* way to steer it), so a Patrulheiro can
    legitimately evolve into Berserker. Its allocated Patrulheiro nodes
    must survive that: generate the same branch grafted onto each base,
    under the uniform `<base>_<spec id>_path` name `_talent_tree_id_for`
    resolves. Stage-2 fixed trees carry their Stage-1 branch as extras."""
    from wyrdfall.domain.specializations import SPECIALIZATION_DEFS, STAGE2_DEFS

    for spec in [*SPECIALIZATION_DEFS.values(), *STAGE2_DEFS.values()]:
        source_id = spec.granted_tree_id
        if source_id is None or source_id not in SPECIALIZATION_TREES:
            continue
        prefix = source_id.partition("_")[0]
        if prefix not in _BASE_TREES:
            continue
        source = SPECIALIZATION_TREES[source_id].definition
        base_nodes, base_edges = _BASE_TREES[prefix]
        base_ids = {n.id for n in base_nodes}
        extra_nodes = [n for n in source.nodes if n.id not in base_ids]
        extra_edges = [e for e in source.edges if e not in base_edges]
        for base, (other_nodes, other_edges) in _BASE_TREES.items():
            tree_id = f"{base}_{spec.id}_path"
            if tree_id in SPECIALIZATION_TREES:
                continue
            if base == prefix:
                SPECIALIZATION_TREES[tree_id] = SPECIALIZATION_TREES[source_id]  # alias under the uniform name
                continue
            known = {n.id for n in other_nodes} | {n.id for n in extra_nodes}
            edges = [*other_edges, *[e for e in extra_edges if e[0] in known and e[1] in known]]
            SPECIALIZATION_TREES[tree_id] = TalentTree(
                TalentTreeDef(id=tree_id, name=source.name, nodes=[*other_nodes, *extra_nodes], edges=edges)
            )


_rebase_fixed_trees()
