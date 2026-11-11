from wyrdfall.domain.consumables import ConsumableDef

CONSUMABLE_DEFS: dict[str, ConsumableDef] = {
    "pocao_de_vida": ConsumableDef(
        id="pocao_de_vida",
        name="Poção de Vida",
        description="Cura 40% do PV máximo.",
        heal_fraction=0.40,
    ),
    "pocao_de_resolucao": ConsumableDef(
        id="pocao_de_resolucao",
        name="Poção de Resolução",
        description="Restaura 50% da Resolução máxima.",
        resource_fraction=0.50,
    ),
    "elixir": ConsumableDef(
        id="elixir",
        name="Elixir",
        description="Cura 25% do PV máximo e restaura 25% da Resolução máxima.",
        heal_fraction=0.25,
        resource_fraction=0.25,
    ),
    # Tomos (10-sistemas-de-build.md §3.8) -- one per Arquétipo Base, each
    # teaching that archetype's lesson to whoever reads it.
    "tomo_do_guerreiro": ConsumableDef(
        id="tomo_do_guerreiro",
        name="Tomo do Guerreiro",
        description="Ensina Golpe Marcial (Guerreiro) permanentemente nesta run.",
        teaches_ability="tome_martial_blow",
    ),
    "tomo_do_patrulheiro": ConsumableDef(
        id="tomo_do_patrulheiro",
        name="Tomo do Patrulheiro",
        description="Ensina Tiro de Emboscada (Patrulheiro) permanentemente nesta run.",
        teaches_ability="tome_ambush_shot",
    ),
    "tomo_do_mistico": ConsumableDef(
        id="tomo_do_mistico",
        name="Tomo do Místico",
        description="Ensina Pulso Arcano (Místico) permanentemente nesta run.",
        teaches_ability="tome_arcane_pulse",
    ),
    "tomo_do_guardiao": ConsumableDef(
        id="tomo_do_guardiao",
        name="Tomo do Guardião",
        description="Ensina Muro de Vontade (Guardião) permanentemente nesta run.",
        teaches_ability="tome_will_wall",
    ),
}
