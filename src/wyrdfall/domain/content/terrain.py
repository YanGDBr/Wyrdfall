"""One Terreno per Área (docs/design/07-mundo-dificuldade.md: "cada área tem
um elemento dominante que se reflete no terreno"), keyed by the
EncounterDef.area_id used in domain/content/dungeon.py. Modifiers apply
to everyone in the fight -- first-guess magnitudes, like every other
balance number. Área 1 (the tutorial Túmulo) deliberately has none."""

from wyrdfall.domain.models import Modifier, ModifierKind, Stat
from wyrdfall.domain.terrain import TerrainDef


def _mod(stat: Stat, value: float, area: str, kind: ModifierKind = ModifierKind.FLAT) -> Modifier:
    return Modifier(stat=stat, kind=kind, value=value, source=f"terrain_{area}")


AREA_TERRAINS: dict[str, TerrainDef] = {
    "the_living_forges": TerrainDef(
        id="the_living_forges", name="Calor de Forja",
        description="O ar queima: +15% de dano elemental para todos.",
        modifiers=[_mod(Stat.ELEMENTAL_DAMAGE_PERCENT, 0.15, "the_living_forges")],
    ),
    "the_frozen_pinnacle": TerrainDef(
        id="the_frozen_pinnacle", name="Gelo Traiçoeiro",
        description="Chão escorregadio: -1 de Velocidade para todos.",
        modifiers=[_mod(Stat.SPEED, -1.0, "the_frozen_pinnacle")],
    ),
    "the_eternal_storm": TerrainDef(
        id="the_eternal_storm", name="Ar Carregado",
        description="Cada golpe estala: +10% de chance de Crítico para todos.",
        modifiers=[_mod(Stat.CRIT_CHANCE, 0.10, "the_eternal_storm")],
    ),
    "the_drowned_depths": TerrainDef(
        id="the_drowned_depths", name="Água até o Peito",
        description="Difícil desviar: -10% de Esquiva para todos.",
        modifiers=[_mod(Stat.DODGE_CHANCE, -0.10, "the_drowned_depths")],
    ),
    "the_forgotten_mines": TerrainDef(
        id="the_forgotten_mines", name="Túneis Estreitos",
        description="Pedra por todo lado: +2 de Defesa para todos.",
        modifiers=[_mod(Stat.DEFENSE, 2.0, "the_forgotten_mines")],
    ),
    "the_floating_pinnacles": TerrainDef(
        id="the_floating_pinnacles", name="Rajadas Constantes",
        description="O vento empurra todo mundo: +10% de Esquiva para todos.",
        modifiers=[_mod(Stat.DODGE_CHANCE, 0.10, "the_floating_pinnacles")],
    ),
    "the_putrid_bog": TerrainDef(
        id="the_putrid_bog", name="Miasma",
        description="O ar é veneno: -10% de resistência a Veneno para todos.",
        modifiers=[_mod(Stat.POISON_RESIST, -0.10, "the_putrid_bog")],
    ),
    "the_shattered_sanctuary": TerrainDef(
        id="the_shattered_sanctuary", name="Luz Remanescente",
        description="O que resta do sagrado ampara: +10% de cura causada para todos.",
        modifiers=[_mod(Stat.HEALING_DONE_PERCENT, 0.10, "the_shattered_sanctuary")],
    ),
    "the_shadow_beneath_the_veil": TerrainDef(
        id="the_shadow_beneath_the_veil", name="Escuridão Densa",
        description="Ninguém vê o golpe chegar: +10% de dano físico para todos.",
        modifiers=[_mod(Stat.PHYSICAL_DAMAGE_PERCENT, 0.10, "the_shadow_beneath_the_veil")],
    ),
    "the_fractured_library": TerrainDef(
        id="the_fractured_library", name="Palavras no Ar",
        description="Conhecimento solto: +1 de recurso por turno para todos.",
        modifiers=[_mod(Stat.RESOURCE_REGEN_PER_TURN, 1.0, "the_fractured_library")],
    ),
    "the_unraveling_loom": TerrainDef(
        id="the_unraveling_loom", name="Fios Soltos",
        description="A realidade cede: +5% de dano físico e elemental para todos.",
        modifiers=[
            _mod(Stat.PHYSICAL_DAMAGE_PERCENT, 0.05, "the_unraveling_loom"),
            _mod(Stat.ELEMENTAL_DAMAGE_PERCENT, 0.05, "the_unraveling_loom"),
        ],
    ),
}
