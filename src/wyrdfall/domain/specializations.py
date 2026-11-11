"""Afinidade de Arquétipo/Elemental/Alinhamento/Raça and Especialização
evolution (docs/design/05-classes.md, 10-sistemas-de-build.md §5).

archetype_affinity/elemental_affinity are read-only views over
Character.archetype_usage/elemental_usage -- percentages of total usage,
not raw totals -- computed fresh at the moment of the evolution check,
never cached or stored. alignment_category is the same idea over
Character.alignment_score.

SPECIALIZATION_DEFS is the catalog of all 46 Especializações this
codebase currently authors (of the 47 in docs/design/05b-classes-
roster.md -- only Avatar Dividido, the Meio-celestial racial signature,
still waits, since Meio-celestial itself is deferred, see domain/
races.py), the same shape
and layering as domain/races.py::RACE_DEFS and domain/conquests.py::
CONQUEST_DEFS -- pure data + pure qualification logic, no dependency on
the content layer (which depends on domain, never the other way around).

The original 9 "puras" (Fase 5) have a real grafted TalentTreeDef
(``granted_tree_id`` set, authored in domain/content/specializations.py,
since building it requires reusing a base archetype's NODES/EDGES --
content data). Every Especialização added in Fase 5b originally left
``granted_tree_id=None`` on purpose: the roadmap was explicit that
that phase delivered "nomeáveis e alcançáveis", not a bespoke kit per
entry -- that polish was Fase 7's job.

Fase 7 has now done that polish for every Fase 5b entry that's
genuinely reachable through real play today (see the reachability
paragraph below) -- Atirador, Encantador, Punho de Granito, Arqueiro
Élfico, Fúria Órquica, Lâmina Espectral and Uivo Selvagem all have a
real grafted tree now too, and so do the 3 Alinhamento signatures that
became reachable once Eventos started writing alignment_score
(Guardião da Floresta, Cavaleiro Negro, Senhor da Peste) -- 19 total
with one. Every entry that's
still ``granted_tree_id=None`` is either one of the remaining 30
correctly-modeled-but-unreachable ones below, or Núcleo de Batalha
(reachable-race gap, see below) -- evolve_specialization (engine/
session.py) falls back to the character's current tree whenever
granted_tree_id is None, so evolving into one of those just sets
Character.specialization_id for identity/naming purposes, same as
before.

Reachability, stated plainly: a character's archetype_usage starts 100%
in their own Arquétipo Base, but it drifts -- Habilidades Exclusivas de
Arma (domain/weapons.py) and Tomos (domain/consumables.py) put other
archetypes' abilities in the pool, and using them is what moves the
meter (10-sistemas-de-build.md §5). alignment_score is written by
Eventos; Fada (Portal Feérico) and Construto (the Ferreiro's recipe) are
unlockable. So every entry in SPECIALIZATION_DEFS is reachable through
real play and every one has a kit: the 9 puras, the 2 attribute-led,
the 3 single-archetype Alinhamento signatures and 6 racial signatures
carry a fixed ``granted_tree_id``; everything that can be reached from
more than one base -- the 17 pairs, 4 triples, Errante and its twins,
Justiceiro, Chama Feérica, Núcleo de Batalha -- carries
``hybrid_branch`` and is grafted onto the character's own base tree.
Only Avatar Dividido (Meio-celestial's signature) is absent, with its
race (04-racas.md defers Meio-celestial).
"""

from __future__ import annotations

from itertools import product

from pydantic import BaseModel, Field

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.character import Character
from wyrdfall.domain.models import Alignment, Archetype, DamageElement, EvolutionVariants, Modifier, ModifierKind, Stat


def archetype_affinity(character: Character) -> dict[Archetype, float]:
    total = sum(character.archetype_usage.values())
    if total <= 0:
        return {archetype: 0.0 for archetype in Archetype}
    return {archetype: character.archetype_usage.get(archetype, 0.0) / total for archetype in Archetype}


def elemental_affinity(character: Character) -> dict[DamageElement, float]:
    total = sum(character.elemental_usage.values())
    if total <= 0:
        return {}
    return {element: amount / total for element, amount in character.elemental_usage.items()}


def alignment_category(score: float) -> Alignment:
    if score >= 30:
        return Alignment.BONDOSO
    if score <= -30:
        return Alignment.MALIGNO
    return Alignment.NEUTRO


class ArchetypeThreshold(BaseModel):
    archetype: Archetype
    minimum: float | None = None
    maximum: float | None = None


class SpecializationDef(BaseModel):
    id: str
    name: str
    description: str
    # Display/grafting hint only for the original 9 (which archetype tree
    # they graft onto) -- never used to gate qualification, since a
    # hybrid spans more than one archetype by definition (see thresholds).
    base_archetype: Archetype | None = None
    thresholds: list[ArchetypeThreshold] = Field(default_factory=list)
    required_top_attribute: Atributo | None = None
    # "X entre os 2 atributos mais investidos" (Atirador) -- a weaker
    # condition than required_top_attribute's "X IS the top one".
    required_attribute_in_top_two: Atributo | None = None
    # Inert this phase -- no weapon-equip system exists yet (see
    # Character.equipped_weapon_type). Gunner is the one entry that sets
    # this, correctly authored but currently unreachable, not skipped.
    requires_weapon_type: str | None = None
    required_alignment: Alignment | None = None
    required_race: str | None = None
    granted_tree_id: str | None = None
    # Hybrids can be reached from either of their archetypes, so their
    # branch is grafted onto the character's OWN base tree at evolution
    # time -- engine/session.py::_talent_tree_id_for resolves
    # f"{character.base_archetype}_{id}_path" (one tree per base archetype,
    # generated in domain/content/specializations.py) instead of a fixed
    # granted_tree_id.
    hybrid_branch: bool = False


_ERRANTE_THRESHOLDS = [
    ArchetypeThreshold(archetype=archetype, minimum=0.10, maximum=0.35) for archetype in Archetype
]

SPECIALIZATION_DEFS: dict[str, SpecializationDef] = {
    # -- Puras moderadas (05b-classes-roster.md §1) -------------------------
    "berserker": SpecializationDef(
        id="berserker", name="Berserker",
        description="Agressão pura, defesa baixa de propósito.",
        base_archetype=Archetype.GUERREIRO,
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.60),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, maximum=0.20),
        ],
        granted_tree_id="guerreiro_berserker_path",
    ),
    "arqueiro": SpecializationDef(
        id="arqueiro", name="Arqueiro",
        description="Especialista à distância com arco.",
        base_archetype=Archetype.PATRULHEIRO,
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.55),
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, maximum=0.25),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, maximum=0.25),
        ],
        granted_tree_id="patrulheiro_arqueiro_path",
    ),
    "gunner": SpecializationDef(
        id="gunner", name="Gunner",
        description="Especialista à distância com armas de fogo -- mesma janela do Arqueiro, "
        "puxado pelo tipo de arma equipada.",
        base_archetype=Archetype.PATRULHEIRO,
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.55),
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, maximum=0.25),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, maximum=0.25),
        ],
        requires_weapon_type="firearm",
        granted_tree_id="patrulheiro_gunner_path",
    ),
    "mago": SpecializationDef(
        id="mago", name="Mago",
        description="Conjurador clássico.",
        base_archetype=Archetype.MISTICO,
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.55),
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, maximum=0.25),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, maximum=0.25),
        ],
        granted_tree_id="mistico_mago_path",
    ),
    "colosso": SpecializationDef(
        id="colosso", name="Colosso",
        description="Muralha viva, quase imóvel.",
        base_archetype=Archetype.GUARDIAO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.60)],
        required_top_attribute=Atributo.CONSTITUTION,
        granted_tree_id="guardiao_colosso_path",
    ),
    # -- Lideradas por atributo (05b-classes-roster.md §2) ------------------
    "atirador": SpecializationDef(
        id="atirador", name="Atirador",
        description="Precisão/crítico à distância.",
        base_archetype=Archetype.PATRULHEIRO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.45)],
        required_attribute_in_top_two=Atributo.LUCK,
        granted_tree_id="patrulheiro_atirador_path",
    ),
    "encantador": SpecializationDef(
        id="encantador", name="Encantador",
        description="Buffs/debuffs, suporte mágico.",
        base_archetype=Archetype.MISTICO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.40)],
        required_top_attribute=Atributo.WISDOM,
        granted_tree_id="mistico_encantador_path",
    ),
    # -- Puras absolutas ≥90% (05b-classes-roster.md §3) --------------------
    "avatar_da_guerra": SpecializationDef(
        id="avatar_da_guerra", name="Avatar da Guerra",
        description="O próprio conceito de \"lutar corpo-a-corpo\" feito pessoa.",
        base_archetype=Archetype.GUERREIRO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.90)],
        granted_tree_id="guerreiro_avatar_path",
    ),
    "predador_absoluto": SpecializationDef(
        id="predador_absoluto", name="Predador Absoluto",
        description="Nunca erra, nunca é visto até ser tarde demais.",
        base_archetype=Archetype.PATRULHEIRO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.90)],
        granted_tree_id="patrulheiro_predador_path",
    ),
    "tecelao_do_veu": SpecializationDef(
        id="tecelao_do_veu", name="Tecelão do Véu",
        description="Magia pura, quase nada mais sobrou da build.",
        base_archetype=Archetype.MISTICO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.90)],
        granted_tree_id="mistico_tecelao_path",
    ),
    "bastiao_eterno": SpecializationDef(
        id="bastiao_eterno", name="Bastião Eterno",
        description="Praticamente impossível de derrubar, ofensivamente quase nulo.",
        base_archetype=Archetype.GUARDIAO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.90)],
        granted_tree_id="guardiao_bastiao_path",
    ),
    # -- Híbridas de 2 arquétipos (05b-classes-roster.md §4) ----------------
    # Guerreiro + Patrulheiro
    "arqueiro_berserker": SpecializationDef(
        id="arqueiro_berserker", hybrid_branch=True, name="Arqueiro-Berserker",
        description="Alterna lâmina e arco, sempre agressivo.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.30),
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.30),
        ],
    ),
    "gunner_berserker": SpecializationDef(
        id="gunner_berserker", hybrid_branch=True, name="Gunner-Berserker",
        description="Mesma ideia do Arqueiro-Berserker, com pólvora em vez de corda de arco.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.30),
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.30),
        ],
        requires_weapon_type="firearm",
    ),
    # Guerreiro + Místico
    "paladino": SpecializationDef(
        id="paladino", hybrid_branch=True, name="Paladino",
        description="Guerreiro sagrado, magia de apoio.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.40),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.20),
        ],
    ),
    "mago_runico": SpecializationDef(
        id="mago_runico", hybrid_branch=True, name="Mago Rúnico",
        description="Magia canalizada pela própria arma.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.35),
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.20),
        ],
    ),
    "cavaleiro_arcano": SpecializationDef(
        id="cavaleiro_arcano", hybrid_branch=True, name="Cavaleiro Arcano",
        description="Espadachim arcano, sem viés.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.30),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.30),
        ],
    ),
    # Guerreiro + Guardião
    "cavaleiro": SpecializationDef(
        id="cavaleiro", hybrid_branch=True, name="Cavaleiro",
        description="Guerreiro com lastro defensivo.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.45),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.15, maximum=0.40),
        ],
    ),
    "cavaleiro_pesado": SpecializationDef(
        id="cavaleiro_pesado", hybrid_branch=True, name="Cavaleiro Pesado",
        description="Tanque que ainda bate forte.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.45),
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.20),
        ],
    ),
    "juggernaut": SpecializationDef(
        id="juggernaut", hybrid_branch=True, name="Juggernaut",
        description="Imparável.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.35),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.35),
        ],
    ),
    # Patrulheiro + Místico
    "domador": SpecializationDef(
        id="domador", hybrid_branch=True, name="Domador",
        description="Luta ao lado de uma fera/invocação.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.35),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.20),
        ],
    ),
    "invocador": SpecializationDef(
        id="invocador", hybrid_branch=True, name="Invocador",
        description="Fica atrás, invocações lutam.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.45),
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.15),
        ],
    ),
    "cacador_arcano": SpecializationDef(
        id="cacador_arcano", hybrid_branch=True, name="Caçador Arcano",
        description="Flechas/tiros que já nascem mágicos.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.30),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.30),
        ],
    ),
    "arqueiro_mago": SpecializationDef(
        id="arqueiro_mago", hybrid_branch=True, name="Arqueiro-Mago",
        description="Alterna entre atirar e conjurar -- kit duplo de verdade, diferente do "
        "Caçador Arcano (que funde os dois num só). Mesma janela de afinidade por enquanto: "
        "distingui-los pela composição exata do kit equipado é trabalho de Fase 5c/7.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.30),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.30),
        ],
    ),
    # Patrulheiro + Guardião
    "sentinela": SpecializationDef(
        id="sentinela", hybrid_branch=True, name="Sentinela",
        description="Controle de área à distância, defesa de posição.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.30),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.30),
        ],
    ),
    "bastiao_movel": SpecializationDef(
        id="bastiao_movel", hybrid_branch=True, name="Bastião Móvel",
        description="Armamento pesado de longo alcance, avança devagar e não recua.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.45),
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.20),
        ],
    ),
    # Místico + Guardião
    "avatar": SpecializationDef(
        id="avatar", hybrid_branch=True, name="Avatar",
        description="Corpo defensivo imbuído de magia elemental.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.40),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.20),
        ],
    ),
    "guardiao_arcano": SpecializationDef(
        id="guardiao_arcano", hybrid_branch=True, name="Guardião Arcano",
        description="Barreiras e proteção mágica.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.30),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.30),
        ],
    ),
    "sacerdote_blindado": SpecializationDef(
        id="sacerdote_blindado", hybrid_branch=True, name="Sacerdote Blindado",
        description="Fé e couraça -- cura o grupo enquanto aguenta a linha de frente.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.45),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.20),
        ],
    ),
    # -- Híbridas de 3 arquétipos (05b-classes-roster.md §5) ----------------
    "lamina_do_crepusculo": SpecializationDef(
        id="lamina_do_crepusculo", hybrid_branch=True, name="Lâmina do Crepúsculo",
        description="Guerreiro-caçador-feiticeiro sem nenhum instinto defensivo.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, maximum=0.20),
        ],
    ),
    "capitao_de_vanguarda": SpecializationDef(
        id="capitao_de_vanguarda", hybrid_branch=True, name="Capitão de Vanguarda",
        description="Soldado completo, zero magia.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.MISTICO, maximum=0.20),
        ],
    ),
    "campeao_runico": SpecializationDef(
        id="campeao_runico", hybrid_branch=True, name="Campeão Rúnico",
        description="Marcial, arcano e resistente -- só não atira.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, maximum=0.20),
        ],
    ),
    "vigia_arcano": SpecializationDef(
        id="vigia_arcano", hybrid_branch=True, name="Vigia Arcano",
        description="À distância, mágico e resiliente -- nunca chega perto.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.20),
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, maximum=0.20),
        ],
    ),
    # -- Generalista (05b-classes-roster.md §6) -----------------------------
    "errante_do_wyrd": SpecializationDef(
        id="errante_do_wyrd", hybrid_branch=True, name="Errante do Wyrd",
        description="Recompensa quem não se especializa.",
        thresholds=list(_ERRANTE_THRESHOLDS),
    ),
    # -- Especializações assinatura de Alinhamento (05b-classes-roster.md §7) -
    "guardiao_da_floresta": SpecializationDef(
        id="guardiao_da_floresta", name="Guardião da Floresta",
        description="Protetor da natureza.",
        base_archetype=Archetype.GUARDIAO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.90)],
        required_alignment=Alignment.BONDOSO,
        granted_tree_id="guardiao_guardiao_da_floresta_path",
    ),
    "justiceiro": SpecializationDef(
        id="justiceiro", hybrid_branch=True, name="Justiceiro",
        description="Versão exclusiva do Paladino pra quem realmente age com bondade, não só reza.",
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.40),
            ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.20),
        ],
        required_alignment=Alignment.BONDOSO,
    ),
    "cavaleiro_negro": SpecializationDef(
        id="cavaleiro_negro", name="Cavaleiro Negro",
        description="Poder movido a malícia, não a treino.",
        base_archetype=Archetype.GUERREIRO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.60)],
        required_alignment=Alignment.MALIGNO,
        granted_tree_id="guerreiro_cavaleiro_negro_path",
    ),
    "senhor_da_peste": SpecializationDef(
        id="senhor_da_peste", name="Senhor da Peste",
        description="Magia sombria/venenosa, foco em atrição.",
        base_archetype=Archetype.MISTICO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.40)],
        required_alignment=Alignment.MALIGNO,
        granted_tree_id="mistico_senhor_da_peste_path",
    ),
    "andarilho_do_caminho_cinza": SpecializationDef(
        id="andarilho_do_caminho_cinza", hybrid_branch=True, name="Andarilho do Caminho Cinza",
        description="Versão exclusiva do Errante do Wyrd pra quem escolhe o equilíbrio de propósito.",
        thresholds=list(_ERRANTE_THRESHOLDS),
        required_alignment=Alignment.NEUTRO,
    ),
    # -- Especializações assinatura Racial (05b-classes-roster.md §8) -------
    "andarilho_versatil": SpecializationDef(
        id="andarilho_versatil", hybrid_branch=True, name="Andarilho Versátil",
        description="A adaptabilidade humana levada ao extremo.",
        thresholds=list(_ERRANTE_THRESHOLDS),
        required_race="human",
    ),
    "punho_de_granito": SpecializationDef(
        id="punho_de_granito", name="Punho de Granito",
        description="Tanque anão, sinergiza com Pele de Granito.",
        base_archetype=Archetype.GUARDIAO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.45)],
        required_race="dwarf",
        granted_tree_id="guardiao_punho_de_granito_path",
    ),
    "arqueiro_elfico": SpecializationDef(
        id="arqueiro_elfico", name="Arqueiro Élfico",
        description="O exemplo original do usuário.",
        base_archetype=Archetype.PATRULHEIRO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.45)],
        required_race="elf",
        granted_tree_id="patrulheiro_arqueiro_elfico_path",
    ),
    "furia_orquica": SpecializationDef(
        id="furia_orquica", name="Fúria Órquica",
        description="Berserker orc, sinergiza com Fúria de Batalha.",
        base_archetype=Archetype.GUERREIRO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.45)],
        required_race="orc",
        granted_tree_id="guerreiro_furia_orquica_path",
    ),
    # Fase 7 -- 4 of the 5 remaining racial signatures (05b-classes-
    # roster.md §8), now that domain/races.py has their races; Avatar
    # Dividido came last with the Meio-celestial ("propositalmente por último").
    "chama_ferica": SpecializationDef(
        id="chama_ferica", hybrid_branch=True, name="Chama Feérica",
        description="Caster feérico, sinergiza com Bênção do Acaso.",
        thresholds=[ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.40)],
        required_race="fada",
    ),
    "lamina_espectral": SpecializationDef(
        id="lamina_espectral", name="Lâmina Espectral",
        description="Guerreiro não-morto, sinergiza com roubo de vida.",
        base_archetype=Archetype.GUERREIRO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.40)],
        required_race="renascido",
        granted_tree_id="guerreiro_lamina_espectral_path",
    ),
    "nucleo_de_batalha": SpecializationDef(
        id="nucleo_de_batalha", hybrid_branch=True, name="Núcleo de Batalha",
        description="Tanque inorgânico, sinergiza com absorção de runas.",
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.45)],
        required_race="construto",
    ),
    "avatar_dividido": SpecializationDef(
        id="avatar_dividido", hybrid_branch=True, name="Avatar Dividido",
        description="Alterna entre forma Sagrada/Sombria em pleno combate, sinergiza com Natureza Dual.",
        thresholds=[ArchetypeThreshold(archetype=Archetype.MISTICO, minimum=0.40)],
        required_race="meio_celestial",
    ),
    "uivo_selvagem": SpecializationDef(
        id="uivo_selvagem", name="Uivo Selvagem",
        description="Fúria crescente em combates longos, sinergiza com Instinto.",
        base_archetype=Archetype.GUERREIRO,
        thresholds=[ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.40)],
        required_race="licantropo",
        granted_tree_id="guerreiro_uivo_selvagem_path",
    ),
}


class Stage2Def(BaseModel):
    """One Estágio 2 evolution (docs/design/05b-classes-roster.md §10):
    reached at level 10 (engine/session.py::EVOLUTION_STAGE2_LEVEL) by a
    character whose Stage-1 pick is in ``from_specializations`` and whose
    *current* 4 axes -- affinity may have drifted since Stage 1 -- still
    pass its thresholds/alignment/race. Same qualification vocabulary as
    SpecializationDef, deliberately, so qualifies() serves both."""

    id: str
    name: str
    description: str
    # Stage-1 ids this ascends from; empty means any Stage-1 pick
    from_specializations: set[str] = Field(default_factory=set)
    thresholds: list[ArchetypeThreshold] = Field(default_factory=list)
    required_top_attribute: Atributo | None = None
    required_attribute_in_top_two: Atributo | None = None
    requires_weapon_type: str | None = None
    required_alignment: Alignment | None = None
    required_race: str | None = None
    granted_tree_id: str | None = None
    # A Stage 2 that ascends from a hybrid Stage 1 is itself per-base:
    # f"{base}_{id}_path" grafted onto f"{base}_{stage1}_path" (see
    # domain/content/specializations.py).
    hybrid_branch: bool = False


def _pure(archetype: Archetype, minimum: float) -> list[ArchetypeThreshold]:
    return [ArchetypeThreshold(archetype=archetype, minimum=minimum)]


# The Estágio 2 table. 05b §10 only gave examples ("tabela completa fica
# pra depois") -- this is that table: one pure ascension per Stage-1
# line that is reachable through real play today (each with a grafted
# tree in domain/content/specializations.py), plus the doc's own hybrid
# examples authored without a tree, unreachable for the same reason the
# 27 Stage-1 hybrids are (single-archetype usage) and disclosed the same
# way. Thresholds re-read the CURRENT affinity: a Mago whose Místico
# slipped under 70% does not see Arquimago.
STAGE2_DEFS: dict[str, Stage2Def] = {
    "sentinela_da_alvorada": Stage2Def(
        id="sentinela_da_alvorada", name="Sentinela da Alvorada", hybrid_branch=True,
        description="O Paladino protege a si mesmo ao aproveitar as marcas do grupo.",
        from_specializations={"paladino"}, thresholds=SPECIALIZATION_DEFS["paladino"].thresholds,
    ),
    "fio_do_eclipse": Stage2Def(
        id="fio_do_eclipse", name="Fio do Eclipse", hybrid_branch=True,
        description="A Lâmina do Crepúsculo recupera fôlego com golpes críticos.",
        from_specializations={"lamina_do_crepusculo"}, thresholds=SPECIALIZATION_DEFS["lamina_do_crepusculo"].thresholds,
    ),
    "convergencia_celestial": Stage2Def(
        id="convergencia_celestial", name="Convergência Celestial", hybrid_branch=True,
        description="O Avatar Dividido se protege com as duas naturezas.",
        from_specializations={"avatar_dividido"}, thresholds=_pure(Archetype.MISTICO, 0.40), required_race="meio_celestial",
    ),
    # -- Guerreiro ---------------------------------------------------------
    "senhor_da_guerra": Stage2Def(
        id="senhor_da_guerra", name="Senhor da Guerra",
        description="O Berserker que aprendeu a dirigir a fúria -- golpes em cadeia.",
        from_specializations={"berserker"}, thresholds=_pure(Archetype.GUERREIRO, 0.60),
        granted_tree_id="guerreiro_senhor_da_guerra_path",
    ),
    "encarnacao_da_batalha": Stage2Def(
        id="encarnacao_da_batalha", name="Encarnação da Batalha",
        description="O Avatar da Guerra levado ao absoluto.",
        from_specializations={"avatar_da_guerra"}, thresholds=_pure(Archetype.GUERREIRO, 0.90),
        granted_tree_id="guerreiro_encarnacao_da_batalha_path",
    ),
    "lorde_da_ruina": Stage2Def(
        id="lorde_da_ruina", name="Lorde da Ruína",
        description="O Cavaleiro Negro que abraçou a corrupção de vez.",
        from_specializations={"cavaleiro_negro"}, thresholds=_pure(Archetype.GUERREIRO, 0.60),
        required_alignment=Alignment.MALIGNO,
        granted_tree_id="guerreiro_lorde_da_ruina_path",
    ),
    "senhor_da_horda": Stage2Def(
        id="senhor_da_horda", name="Senhor da Horda",
        description="A Fúria Órquica vira liderança: cada golpe puxa a horda junto.",
        from_specializations={"furia_orquica"}, thresholds=_pure(Archetype.GUERREIRO, 0.45),
        required_race="orc",
        granted_tree_id="guerreiro_senhor_da_horda_path",
    ),
    "ceifador_espectral": Stage2Def(
        id="ceifador_espectral", name="Ceifador Espectral",
        description="A Lâmina Espectral corta o fio entre os vivos e os mortos.",
        from_specializations={"lamina_espectral"}, thresholds=_pure(Archetype.GUERREIRO, 0.40),
        required_race="renascido",
        granted_tree_id="guerreiro_ceifador_espectral_path",
    ),
    "alfa": Stage2Def(
        id="alfa", name="Alfa",
        description="O Uivo Selvagem que a matilha inteira responde.",
        from_specializations={"uivo_selvagem"}, thresholds=_pure(Archetype.GUERREIRO, 0.40),
        required_race="licantropo",
        granted_tree_id="guerreiro_alfa_path",
    ),
    # -- Patrulheiro -------------------------------------------------------
    "mestre_arqueiro": Stage2Def(
        id="mestre_arqueiro", name="Mestre Arqueiro",
        description="O Arqueiro que não erra mais -- nem de longe, nem de perto.",
        from_specializations={"arqueiro"}, thresholds=_pure(Archetype.PATRULHEIRO, 0.55),
        granted_tree_id="patrulheiro_mestre_arqueiro_path",
    ),
    "pistoleiro": Stage2Def(
        id="pistoleiro", name="Pistoleiro",
        description="O Gunner que transformou a pólvora numa arte.",
        from_specializations={"gunner"}, thresholds=_pure(Archetype.PATRULHEIRO, 0.55),
        granted_tree_id="patrulheiro_pistoleiro_path",
    ),
    "cacador_de_tesouros": Stage2Def(
        id="cacador_de_tesouros", name="Caçador de Tesouros",
        description="A sorte do Atirador vira ofício: um tiro certeiro, um bolso cheio.",
        from_specializations={"atirador"}, thresholds=_pure(Archetype.PATRULHEIRO, 0.45),
        granted_tree_id="patrulheiro_cacador_de_tesouros_path",
    ),
    "sombra_da_mata": Stage2Def(
        id="sombra_da_mata", name="Sombra da Mata",
        description="O Predador Absoluto que a presa nunca vê.",
        from_specializations={"predador_absoluto"}, thresholds=_pure(Archetype.PATRULHEIRO, 0.90),
        granted_tree_id="patrulheiro_sombra_da_mata_path",
    ),
    "olho_da_lua": Stage2Def(
        id="olho_da_lua", name="Olho da Lua",
        description="O Arqueiro Élfico guiado pela luz que só os elfos veem.",
        from_specializations={"arqueiro_elfico"}, thresholds=_pure(Archetype.PATRULHEIRO, 0.45),
        required_race="elf",
        granted_tree_id="patrulheiro_olho_da_lua_path",
    ),
    # -- Místico -----------------------------------------------------------
    "arquimago": Stage2Def(
        id="arquimago", name="Arquimago",
        description="O Mago com Místico ainda dominante -- a ascensão pura.",
        from_specializations={"mago"}, thresholds=_pure(Archetype.MISTICO, 0.70),
        granted_tree_id="mistico_arquimago_path",
    ),
    "cantor_do_wyrd": Stage2Def(
        id="cantor_do_wyrd", name="Cantor do Wyrd",
        description="O Encantador cuja voz o próprio Wyrd escuta.",
        from_specializations={"encantador"}, thresholds=_pure(Archetype.MISTICO, 0.40),
        required_top_attribute=Atributo.WISDOM,
        granted_tree_id="mistico_cantor_do_wyrd_path",
    ),
    "oraculo_do_veu": Stage2Def(
        id="oraculo_do_veu", name="Oráculo do Véu",
        description="O Tecelão do Véu que passou a ler o que tece.",
        from_specializations={"tecelao_do_veu"}, thresholds=_pure(Archetype.MISTICO, 0.90),
        granted_tree_id="mistico_oraculo_do_veu_path",
    ),
    "arauto_da_praga": Stage2Def(
        id="arauto_da_praga", name="Arauto da Praga",
        description="O Senhor da Peste que virou a própria doença.",
        from_specializations={"senhor_da_peste"}, thresholds=_pure(Archetype.MISTICO, 0.40),
        required_alignment=Alignment.MALIGNO,
        granted_tree_id="mistico_arauto_da_praga_path",
    ),
    # -- Guardião ----------------------------------------------------------
    "tita": Stage2Def(
        id="tita", name="Titã",
        description="O Colosso que ninguém mais move -- e que move tudo.",
        from_specializations={"colosso"}, thresholds=_pure(Archetype.GUARDIAO, 0.60),
        granted_tree_id="guardiao_tita_path",
    ),
    "muralha_viva": Stage2Def(
        id="muralha_viva", name="Muralha Viva",
        description="O Bastião Eterno como fortaleza ambulante do grupo.",
        from_specializations={"bastiao_eterno"}, thresholds=_pure(Archetype.GUARDIAO, 0.90),
        granted_tree_id="guardiao_muralha_viva_path",
    ),
    "coracao_da_floresta": Stage2Def(
        id="coracao_da_floresta", name="Coração da Floresta",
        description="O Guardião da Floresta que continuou bondoso -- e a mata retribui.",
        from_specializations={"guardiao_da_floresta"}, thresholds=_pure(Archetype.GUARDIAO, 0.90),
        required_alignment=Alignment.BONDOSO,
        granted_tree_id="guardiao_coracao_da_floresta_path",
    ),
    "coracao_da_montanha": Stage2Def(
        id="coracao_da_montanha", name="Coração da Montanha",
        description="O Punho de Granito que virou a própria montanha.",
        from_specializations={"punho_de_granito"}, thresholds=_pure(Archetype.GUARDIAO, 0.45),
        required_race="dwarf",
        granted_tree_id="guardiao_coracao_da_montanha_path",
    ),
    # -- Híbridos do próprio 05b §10: modelados, sem árvore, inalcançáveis
    # hoje pela mesma razão dos 27 híbridos de Estágio 1 ------------------
    "arqueiro_berserker_s2": Stage2Def(
        id="arqueiro_berserker_s2", name="Arqueiro-Berserker", granted_tree_id="guerreiro_arqueiro_berserker_s2_path",
        description="Um Berserker cuja afinidade derivou pra Patrulheiro -- sem ter passado por Arqueiro.",
        from_specializations={"berserker"},
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.30),
            ArchetypeThreshold(archetype=Archetype.PATRULHEIRO, minimum=0.30),
        ],
    ),
    "juggernaut_s2": Stage2Def(
        id="juggernaut_s2", hybrid_branch=True, name="Juggernaut",
        description="Um Cavaleiro Pesado cujo Guerreiro subiu perto do Guardião.",
        from_specializations={"cavaleiro_pesado"},
        thresholds=[
            ArchetypeThreshold(archetype=Archetype.GUERREIRO, minimum=0.35),
            ArchetypeThreshold(archetype=Archetype.GUARDIAO, minimum=0.35),
        ],
    ),
    "colosso_s2": Stage2Def(
        id="colosso_s2", hybrid_branch=True, name="Colosso",
        description="Um Cavaleiro Pesado cujo Guardião continuou subindo sozinho.",
        from_specializations={"cavaleiro_pesado"}, thresholds=_pure(Archetype.GUARDIAO, 0.60),
    ),
}


def _top_n_attributes(character: Character, n: int) -> list[Atributo]:
    invested = {a: p for a, p in character.attribute_points.items() if p > 0}
    ranked = sorted(invested, key=lambda a: invested[a], reverse=True)
    return ranked[:n]


def qualifies(character: Character, spec: SpecializationDef | Stage2Def) -> bool:
    affinity = archetype_affinity(character)
    for threshold in spec.thresholds:
        value = affinity.get(threshold.archetype, 0.0)
        if threshold.minimum is not None and value < threshold.minimum:
            return False
        if threshold.maximum is not None and value > threshold.maximum:
            return False
    if spec.required_top_attribute is not None:
        top_two = _top_n_attributes(character, 2)
        if not top_two or top_two[0] != spec.required_top_attribute:
            return False
    if spec.required_attribute_in_top_two is not None:
        if spec.required_attribute_in_top_two not in _top_n_attributes(character, 2):
            return False
    if spec.requires_weapon_type is not None and character.equipped_weapon_type != spec.requires_weapon_type:
        return False
    if spec.required_alignment is not None and alignment_category(character.alignment_score) != spec.required_alignment:
        return False
    if spec.required_race is not None and character.race_id != spec.required_race:
        return False
    return True


def is_offerable(spec: SpecializationDef | Stage2Def, character: Character) -> bool:
    """Exclude positive archetype requirements touched by a seal.

    Maximum-only thresholds restrict a build rather than contribute an
    archetype. Eligibility and this offer filter remain independent.
    """
    # An upper bound excludes affinity; it does not give the specialization
    # a positive association with that archetype (e.g. Berserker/Guardião).
    spec_archetypes = {threshold.archetype for threshold in spec.thresholds if threshold.minimum is not None and threshold.minimum > 0}
    return not (spec_archetypes & character.sealed_archetypes)


def qualifying_specializations(character: Character) -> list[SpecializationDef]:
    return [
        spec for spec in SPECIALIZATION_DEFS.values() if qualifies(character, spec) and is_offerable(spec, character)
    ]


def qualifies_stage2(character: Character, stage2: Stage2Def) -> bool:
    if character.specialization_id is None:
        return False
    if stage2.from_specializations and character.specialization_id not in stage2.from_specializations:
        return False
    return qualifies(character, stage2) and is_offerable(stage2, character)


def qualifying_stage2(character: Character) -> list[Stage2Def]:
    return [stage2 for stage2 in STAGE2_DEFS.values() if qualifies_stage2(character, stage2)]


def evolution_offers(character: Character) -> list[SpecializationDef | Stage2Def]:
    """What the evolution screen should list for this character right now,
    ignoring level: Stage-1 picks while unevolved, Stage-2 picks once
    evolved, nothing after Stage 2. Level gating stays with the caller
    (engine/session.py::EVOLUTION_LEVEL / EVOLUTION_STAGE2_LEVEL)."""
    if character.specialization_id is None:
        return list(qualifying_specializations(character))
    if character.stage2_specialization_id is None:
        return list(qualifying_stage2(character))
    return []


DAMAGE_ELEMENT_NAMES: dict[DamageElement, str] = {
    DamageElement.PHYSICAL: "Físico",
    DamageElement.FIRE: "Fogo",
    DamageElement.ICE: "Gelo",
    DamageElement.LIGHTNING: "Raio",
    DamageElement.WATER: "Água",
    DamageElement.EARTH: "Terra",
    DamageElement.AIR: "Ar",
    DamageElement.POISON: "Veneno",
    DamageElement.HOLY: "Sagrado",
    DamageElement.SHADOW: "Sombrio",
    DamageElement.ARCANE: "Arcano",
}

RACE_ADJECTIVES: dict[str, str] = {
    "human": "Humano",
    "dwarf": "Anão",
    "elf": "Élfico",
    "orc": "Órquico",
    "fada": "Feérico",
    "renascido": "Renascido",
    "construto": "Constructo",
    "licantropo": "Licantrópico",
    "meio_celestial": "Meio-celestial",
}

_ELEMENTAL_VARIANT_THRESHOLD = 0.50
ELEMENTAL_VARIANT_DAMAGE = 0.25
ELEMENTAL_VARIANT_WEAKNESS = 0.15

# Descriptions and modifiers share the same templates for every specialization.
_RACIAL_VARIANTS = {
    "human": ("+5 PV máximos", ((Stat.MAX_HP, 5),)),
    "dwarf": ("+5 p.p. de resistência a status", ((Stat.STATUS_RESIST, .05),)),
    "elf": ("+3 p.p. de esquiva", ((Stat.DODGE_CHANCE, .03),)),
    "orc": ("+2 de Ataque", ((Stat.ATTACK, 2),)),
    "fada": ("+10% ao multiplicador de disparo de efeitos", ((Stat.PROC_CHANCE_PERCENT, .10),)),
    "renascido": ("+5 p.p. de roubo de vida", ((Stat.LIFESTEAL_PERCENT, .05),)),
    "construto": ("+2 de Defesa", ((Stat.DEFENSE, 2),)),
    "licantropo": ("+5 p.p. de dano físico", ((Stat.PHYSICAL_DAMAGE_PERCENT, .05),)),
    "meio_celestial": ("+5 p.p. de resistência Sagrada e Sombria", ((Stat.HOLY_RESIST, .05), (Stat.SHADOW_RESIST, .05))),
}
_ALIGNMENT_VARIANTS = {
    Alignment.BONDOSO: (
        "Radiante", "+20 p.p. de cura causada, +10 p.p. de cura recebida e −10 p.p. de dano",
        ((Stat.HEALING_DONE_PERCENT, .20), (Stat.HEALING_RECEIVED_PERCENT, .10),
         (Stat.PHYSICAL_DAMAGE_PERCENT, -.10), (Stat.ELEMENTAL_DAMAGE_PERCENT, -.10)),
    ),
    Alignment.MALIGNO: (
        "Corrompido", "+10 p.p. de dano, +4 p.p. de roubo de vida e −20 p.p. de cura causada",
        ((Stat.PHYSICAL_DAMAGE_PERCENT, .10), (Stat.ELEMENTAL_DAMAGE_PERCENT, .10),
         (Stat.LIFESTEAL_PERCENT, .04), (Stat.HEALING_DONE_PERCENT, -.20)),
    ),
}


def evolution_variant_choices(character: Character) -> list[EvolutionVariants]:
    """Add only axes that are eligible now and weren't fixed by Stage 1."""
    inherited = character.evolution_variants
    races = [None]
    if inherited.race_id is None and character.race_id in _RACIAL_VARIANTS:
        races.append(character.race_id)
    alignments = [None]
    category = alignment_category(character.alignment_score)
    if inherited.alignment is None and category in _ALIGNMENT_VARIANTS:
        alignments.append(category)
    elements = [None]
    if inherited.element is None:
        affinity = elemental_affinity(character)
        elements.extend(e for e in DamageElement if affinity.get(e, 0) >= _ELEMENTAL_VARIANT_THRESHOLD
                        and e not in character.sealed_elements)
    choices = [EvolutionVariants(race_id=race, alignment=alignment, element=element)
               for race, alignment, element in product(races, alignments, elements)]
    return sorted(choices, key=lambda choice: len(choice.model_dump(exclude_none=True)))


def merge_evolution_variants(inherited: EvolutionVariants, additions: EvolutionVariants) -> EvolutionVariants:
    return inherited.model_copy(update=additions.model_dump(exclude_none=True))


def evolution_name(base_name: str, variants: EvolutionVariants) -> str:
    suffixes = []
    if variants.race_id in RACE_ADJECTIVES:
        suffixes.append(RACE_ADJECTIVES[variants.race_id])
    if variants.alignment in _ALIGNMENT_VARIANTS:
        suffixes.append(_ALIGNMENT_VARIANTS[variants.alignment][0])
    if variants.element is not None:
        suffixes.append(f"de {DAMAGE_ELEMENT_NAMES[variants.element]}")
    return " ".join([base_name, *suffixes])


def variant_descriptions(variants: EvolutionVariants) -> list[str]:
    descriptions = []
    if variants.race_id in _RACIAL_VARIANTS:
        descriptions.append(_RACIAL_VARIANTS[variants.race_id][0])
    if variants.alignment in _ALIGNMENT_VARIANTS:
        descriptions.append(_ALIGNMENT_VARIANTS[variants.alignment][1])
    if variants.element is not None:
        element = DAMAGE_ELEMENT_NAMES[variants.element]
        descriptions.append(
            f"+{ELEMENTAL_VARIANT_DAMAGE:.0%} de dano de {element} antes das defesas. "
            f"−{ELEMENTAL_VARIANT_WEAKNESS * 100:.0f} p.p. de resistência aos outros elementos"
            + ("." if variants.element == DamageElement.PHYSICAL else " e +15% de dano físico recebido após a Defesa.")
        )
    return descriptions


def variant_modifiers(variants: EvolutionVariants) -> list[Modifier]:
    entries = []
    if variants.race_id in _RACIAL_VARIANTS:
        entries.extend(_RACIAL_VARIANTS[variants.race_id][1])
    if variants.alignment in _ALIGNMENT_VARIANTS:
        entries.extend(_ALIGNMENT_VARIANTS[variants.alignment][2])
    if variants.element is not None:
        for element in DamageElement:
            if element == variants.element:
                continue
            if element == DamageElement.PHYSICAL:
                entries.append((Stat.PHYSICAL_VULNERABILITY_PERCENT, ELEMENTAL_VARIANT_WEAKNESS))
            else:
                entries.append((Stat(f"{element.value}_resist"), -ELEMENTAL_VARIANT_WEAKNESS))
    return [Modifier(stat=stat, kind=ModifierKind.FLAT, value=value, source="evolution_variant")
            for stat, value in entries]


def variant_display_names(character: Character, spec: SpecializationDef | Stage2Def) -> list[str]:
    return [evolution_name(spec.name, merge_evolution_variants(character.evolution_variants, choice))
            for choice in evolution_variant_choices(character)]
