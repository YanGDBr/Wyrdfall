from wyrdfall.domain.dungeon import DungeonDef, EncounterDef, PortalDef

AREA_NAMES: dict[str, str] = {
    "the_hollow_barrow": "O Túmulo Oco",
    "the_living_forges": "As Fornalhas Vivas",
    "the_frozen_pinnacle": "O Pico Silente",
    "the_eternal_storm": "A Tempestade Eterna",
    "the_drowned_depths": "As Profundezas Afogadas",
    "the_forgotten_mines": "As Minas Esquecidas",
    "the_floating_pinnacles": "Os Pináculos Flutuantes",
    "the_putrid_bog": "O Pântano Pútrido",
    "the_shattered_sanctuary": "O Santuário Desmoronado",
    "the_shadow_beneath_the_veil": "A Sombra Sob o Véu",
    "the_fractured_library": "A Biblioteca Fraturada",
    "the_unraveling_loom": "O Tear Desfeito",
}

# docs/design/14-estrutura-da-run.md §4 -- every regular Área has the same
# fixed 6-node shape: Combate / Combate (pode incluir Sinergia) / Evento /
# Sala Especial (Forja de Campo / Descanso / Vendedor, sorteada por run --
# see domain/special_rooms.py) / Elite / Chefe. Each Área below is
# authored as its 4 combats in order (comum, Sinergia, Elite, Chefe);
# _apply_template splices the Evento and Sala Especial nodes in between.
# Área 12 keeps its own shorter corridor (no Evento, no Sala Especial)
# by design.
_EVENT_FLAVOR: dict[str, str] = {
    "the_hollow_barrow": "Algo se mexe numa cripta lateral, e não são goblins.",
    "the_living_forges": "Entre uma forja e outra, um corredor que os autômatos não patrulham.",
    "the_frozen_pinnacle": "A trilha se abre numa clareira de gelo, silenciosa demais.",
    "the_eternal_storm": "Um intervalo entre dois raios, longo o bastante pra alguém chamar por você.",
    "the_drowned_depths": "A água recua e deixa à mostra o que estava escondido sob ela.",
    "the_forgotten_mines": "Uma galeria antiga, marcada por quem passou por aqui antes.",
    "the_floating_pinnacles": "Uma ponte que leva a lugar nenhum -- e alguém parado no meio dela.",
    "the_putrid_bog": "O charco cala de repente, como se esperasse a sua decisão.",
    "the_shattered_sanctuary": "Um confessionário sem padre, com a porta entreaberta.",
    "the_shadow_beneath_the_veil": "A escuridão aqui tem a forma de uma escolha.",
    "the_fractured_library": "Uma página solta flutua até você, e espera ser lida.",
}
_SPECIAL_FLAVOR: dict[str, str] = {
    "the_hollow_barrow": "Um nicho seco entre as criptas, longe o bastante dos goblins pra parar um pouco.",
    "the_living_forges": "Uma forja apagada, ainda morna -- o único lugar aqui onde o calor não é hostil.",
    "the_frozen_pinnacle": "Uma caverna abrigada do vento, com restos de um acampamento de outra expedição.",
    "the_eternal_storm": "Um oco na rocha onde os raios não alcançam, e o trovão vira só um zumbido distante.",
    "the_drowned_depths": "Uma plataforma seca acima da linha d'água, iluminada por musgo fosforescente.",
    "the_forgotten_mines": "Um túnel lateral desabado nas duas pontas -- fechado, silencioso, seguro por ora.",
    "the_floating_pinnacles": "Uma reentrância sob um pináculo, onde o vento passa por cima sem entrar.",
    "the_putrid_bog": "Uma ilha de raízes firmes no meio do charco, alta o bastante pra ficar seca.",
    "the_shattered_sanctuary": "Uma capela lateral intacta, a única luz do santuário que ainda aquece.",
    "the_shadow_beneath_the_veil": "Um círculo de velas que a escuridão, por algum motivo, não atravessa.",
    "the_fractured_library": "Uma sala de leitura fechada, onde os livros ainda ficam no lugar.",
}


def _apply_template(encounters: list[EncounterDef]) -> list[EncounterDef]:
    grouped: dict[str, list[EncounterDef]] = {}
    for encounter in encounters:
        grouped.setdefault(encounter.area_id, []).append(encounter)
    result: list[EncounterDef] = []
    for area_id, group in grouped.items():
        if area_id not in _EVENT_FLAVOR:
            result.extend(group)
            continue
        assert len(group) == 4 and group[-1].is_boss, area_id
        event = EncounterDef(
            id=f"event_{area_id}", name="Evento", room_type="event", area_id=area_id,
            flavor_text=_EVENT_FLAVOR[area_id],
        )
        special = EncounterDef(
            id=f"special_{area_id}", name="Sala Especial", room_type="special", area_id=area_id,
            flavor_text=_SPECIAL_FLAVOR[area_id],
        )
        elite = group[2].model_copy(update={"is_elite": True})
        result.extend([group[0], group[1], event, special, elite, group[3]])
    return result


MVP_DUNGEON = DungeonDef(
    id="the_hollow_barrow",
    name="O Túmulo Oco",
    encounters=_apply_template([
        EncounterDef(
            id="e1", name="Entrada do Túmulo", enemy_ids=["goblin", "goblin"], area_id="the_hollow_barrow",
            flavor_text="Dois goblins brigam por restos no saguão de entrada.",
        ),
        EncounterDef(
            id="e3", name="Passagem Coberta de Teias", enemy_ids=["skitterling", "skitterling"],
            area_id="the_hollow_barrow",
            flavor_text="Um ninho de Rastejantes bloqueia o caminho adiante.",
        ),
        EncounterDef(
            id="e4", name="Cripta de Ossos", enemy_ids=["bonewarden"], area_id="the_hollow_barrow",
            flavor_text="Um Guardião Ósseo solitário vigia uma cripta repleta de ossos.",
        ),
        EncounterDef(
            id="e6", name="O Trono Oco", enemy_ids=["hollow_knight"], is_boss=True, area_id="the_hollow_barrow",
            flavor_text="O Cavaleiro Oco se ergue de seu trono de ossos.",
        ),
        # -- Área 2: As Fornalhas Vivas (Fogo) -- só alcançável depois do
        # Cavaleiro Oco cair, já que os encontros são estritamente
        # sequenciais (ver docs/design/07-mundo-dificuldade.md).
        EncounterDef(
            id="e7", name="Portal das Fornalhas", enemy_ids=["cinderling"], area_id="the_living_forges",
            flavor_text="O ar fica quente. Um Cinderling solitário guarda a entrada.",
        ),
        EncounterDef(
            id="e9", name="Câmara dos Foles", enemy_ids=["living_bellows", "forge_automaton", "cinderling"],
            area_id="the_living_forges",
            flavor_text="Um Fole Vivo infla os outros com fôlego quente demais.",
        ),
        EncounterDef(
            id="e10", name="Fenda de Magma", enemy_ids=["magma_golem"], area_id="the_living_forges",
            flavor_text="Um Golem de Magma Rachado se ergue da fenda incandescente.",
        ),
        EncounterDef(
            id="e11", name="O Coração da Forja", enemy_ids=["ashkarion"], is_boss=True,
            area_id="the_living_forges",
            flavor_text="Ashkarion se solta de sua armadura de forjador, colossal e ardente.",
        ),
        # -- Área 3: O Pico Silente (Gelo) -- só alcançável depois de
        # Ashkarion cair, mesma regra sequencial das áreas anteriores.
        EncounterDef(
            id="e12", name="Trilha Congelada", enemy_ids=["lobo_de_gelo", "lobo_de_gelo"],
            area_id="the_frozen_pinnacle",
            flavor_text="Uma matilha de Lobos de Gelo ronda a trilha estreita.",
        ),
        EncounterDef(
            id="e14", name="Acampamento da Nevasca", enemy_ids=["xama_da_nevasca", "espectro_gelado", "lobo_de_gelo"],
            area_id="the_frozen_pinnacle",
            flavor_text="Um Xamã da Nevasca ergue barreiras de gelo para proteger seus companheiros.",
        ),
        EncounterDef(
            id="e15", name="Fenda de Carâmbanos", enemy_ids=["ceifador_de_carambano"],
            area_id="the_frozen_pinnacle",
            flavor_text="Um Ceifador de Carâmbano espera entre as estalactites afiadas.",
        ),
        EncounterDef(
            id="e17", name="O Trono Silente", enemy_ids=["viuva_de_gelo"], is_boss=True,
            area_id="the_frozen_pinnacle",
            flavor_text="A Viúva de Gelo se ergue, ainda esperando por algo que ninguém mais lembra.",
        ),
        # -- Área 4: A Tempestade Eterna (Raio) -- só alcançável depois da
        # Viúva de Gelo cair, mesma regra sequencial das áreas anteriores.
        EncounterDef(
            id="e18", name="Bordas da Tempestade", enemy_ids=["ave_trovao", "ave_trovao"],
            area_id="the_eternal_storm",
            flavor_text="Um bando de Aves-Trovão corta o céu carregado antes mesmo do primeiro trovão.",
        ),
        EncounterDef(
            id="e20", name="Círculo da Tempestade", enemy_ids=["arauto_da_tempestade", "sentinela_eletrizada", "ave_trovao"],
            area_id="the_eternal_storm",
            flavor_text="Um Arauto da Tempestade acelera seus companheiros com descargas de Raio.",
        ),
        EncounterDef(
            id="e21", name="Núcleo Carregado", enemy_ids=["colosso_carregado"],
            area_id="the_eternal_storm",
            flavor_text="Um Colosso Carregado pulsa com energia acumulada, prestes a liberar tudo de uma vez.",
        ),
        EncounterDef(
            id="e23", name="O Olho da Tempestade", enemy_ids=["voltharion"], is_boss=True,
            area_id="the_eternal_storm",
            flavor_text="Voltharion paira no olho da tempestade eterna, armadura e relâmpago como uma coisa só.",
        ),
        # -- Área 5: As Profundezas Afogadas (Água) -- só alcançável
        # depois de Voltharion cair, mesma regra sequencial de sempre.
        EncounterDef(
            id="e24", name="Entrada Submersa", enemy_ids=["afogado", "afogado"],
            area_id="the_drowned_depths",
            flavor_text="A água sobe até os joelhos, e algo se arrasta logo abaixo da superfície.",
        ),
        EncounterDef(
            id="e26", name="Santuário Inundado", enemy_ids=["sacerdotisa_afogada", "afogado", "enguia_espectral"],
            area_id="the_drowned_depths",
            flavor_text="Uma Sacerdotisa Afogada canta uma bênção antiga, curando os que ainda a servem.",
        ),
        EncounterDef(
            id="e27", name="Fenda do Kraken", enemy_ids=["kraken_jovem"],
            area_id="the_drowned_depths",
            flavor_text="Um Kraken Jovem se agita na fenda submersa, tentáculos por todos os lados.",
        ),
        EncounterDef(
            id="e29", name="O Templo Afogado", enemy_ids=["maremoto"], is_boss=True,
            area_id="the_drowned_depths",
            flavor_text="Maremoto se ergue das ruínas de um templo que já esteve seco.",
        ),
        # -- Área 6: As Minas Esquecidas (Terra) -- só alcançável depois
        # de Maremoto cair, mesma regra sequencial de sempre.
        EncounterDef(
            id="e30", name="Túnel Desmoronado", enemy_ids=["golem_de_cascalho", "golem_de_cascalho"],
            area_id="the_forgotten_mines",
            flavor_text="Um punhado de Golems de Cascalho bloqueia a passagem estreita.",
        ),
        EncounterDef(
            id="e32", name="Câmara do Xamã", enemy_ids=["xama_de_pedra", "verme_de_pedra", "golem_de_cascalho"],
            area_id="the_forgotten_mines",
            flavor_text="Um Xamã de Pedra canta uma maldição que racha a pedra ao redor.",
        ),
        EncounterDef(
            id="e33", name="Vault Cristalizado", enemy_ids=["guardiao_cristalino"],
            area_id="the_forgotten_mines",
            flavor_text="Um Guardião Cristalino brilha, cristais afiados cobrindo cada centímetro dele.",
        ),
        EncounterDef(
            id="e35", name="O Coração da Montanha", enemy_ids=["terrakon"], is_boss=True,
            area_id="the_forgotten_mines",
            flavor_text="Terrakon se ergue -- não uma criatura na montanha, mas a própria montanha.",
        ),
        # -- Área 7: Os Pináculos Flutuantes (Ar) -- só alcançável depois
        # de Terrakon cair, mesma regra sequencial de sempre.
        EncounterDef(
            id="e36", name="Ponte de Vento", enemy_ids=["harpia", "harpia"],
            area_id="the_floating_pinnacles",
            flavor_text="Um bando de Harpias circula a ponte estreita entre dois pináculos.",
        ),
        EncounterDef(
            id="e38", name="Pico do Vendaval", enemy_ids=["arauto_do_vendaval", "harpia", "elemental_de_vento"],
            area_id="the_floating_pinnacles",
            flavor_text="Um Arauto do Vendaval convoca ventos que tentam te atrasar antes do golpe.",
        ),
        EncounterDef(
            id="e39", name="Ninho do Roc", enemy_ids=["roc_menor"],
            area_id="the_floating_pinnacles",
            flavor_text="Um Roc Menor observa do alto do ninho, esperando o primeiro erro.",
        ),
        EncounterDef(
            id="e41", name="O Último Pináculo", enemy_ids=["zephyra"], is_boss=True,
            area_id="the_floating_pinnacles",
            flavor_text="Zephyra paira sobre o pináculo mais alto -- o vento já levou tudo, menos ela.",
        ),
        # -- Área 8: O Pântano Pútrido (Veneno) -- só alcançável depois
        # de Zephyra cair, mesma regra sequencial de sempre.
        EncounterDef(
            id="e42", name="Margem Podre", enemy_ids=["sanguessuga_gigante", "sanguessuga_gigante"],
            area_id="the_putrid_bog",
            flavor_text="Sanguessugas Gigantes se arrastam pela lama à beira do pântano.",
        ),
        EncounterDef(
            id="e44", name="Círculo do Lodo", enemy_ids=["xama_do_lodo", "esporo_ambulante", "sanguessuga_gigante"],
            area_id="the_putrid_bog",
            flavor_text="Um Xamã do Lodo canta sobre o charco, fazendo o Veneno grudar mais fundo.",
        ),
        EncounterDef(
            id="e45", name="Covil do Horror", enemy_ids=["horror_do_charco"],
            area_id="the_putrid_bog",
            flavor_text="Um Horror do Charco emerge da lama, se curando do próprio veneno.",
        ),
        EncounterDef(
            id="e47", name="O Ninho Pútrido", enemy_ids=["mae_putrida"], is_boss=True,
            area_id="the_putrid_bog",
            flavor_text="A Mãe Pútrida não tem rosto. Só tem fome, e uma quantidade obscena de filhotes.",
        ),
        # -- Área 9: O Santuário Desmoronado (Sagrado) -- só alcançável
        # depois da Mãe Pútrida cair, mesma regra sequencial de sempre.
        EncounterDef(
            id="e48", name="Nave Desmoronada", enemy_ids=["serafim_partido", "zelote_cego"],
            area_id="the_shattered_sanctuary",
            flavor_text="Luz poeirenta cai por vitrais quebrados sobre um Serafim Partido e seu guarda.",
        ),
        EncounterDef(
            id="e50", name="Coro Silencioso", enemy_ids=["cantor_de_hinos", "serafim_partido", "zelote_cego"],
            area_id="the_shattered_sanctuary",
            flavor_text="Um Cantor de Hinos entoa uma melodia que pesa mais do que cura.",
        ),
        EncounterDef(
            id="e51", name="Guarda do Altar", enemy_ids=["guardiao_de_luz"],
            area_id="the_shattered_sanctuary",
            flavor_text="Um Guardião de Luz vigia o altar em ruínas, luz cortante nas mãos.",
        ),
        EncounterDef(
            id="e53", name="O Trono Desmoronado", enemy_ids=["solyth"], is_boss=True,
            area_id="the_shattered_sanctuary",
            flavor_text="Solyth guardou este lugar tempo demais sozinho. O que sobrou de piedade virou outra coisa.",
        ),
        # -- Área 10: A Sombra Sob o Véu (Sombrio) -- só alcançável
        # depois de Solyth cair, mesma regra sequencial de sempre.
        EncounterDef(
            id="e54", name="Além do Véu", enemy_ids=["sussurro", "sussurro"],
            area_id="the_shadow_beneath_the_veil",
            flavor_text="Sussurros pairam na escuridão, sussurrando medos que não são bem seus.",
        ),
        EncounterDef(
            id="e56", name="Círculo do Véu", enemy_ids=["arauto_do_veu", "carne_amaldicoada", "sussurro"],
            area_id="the_shadow_beneath_the_veil",
            flavor_text="Um Arauto do Véu protege os seus, tornando-os difíceis de acertar.",
        ),
        EncounterDef(
            id="e57", name="Fome na Escuridão", enemy_ids=["devorador_de_luz"],
            area_id="the_shadow_beneath_the_veil",
            flavor_text="Um Devorador de Luz suga o ambiente ao redor, e a própria vontade de quem se aproxima.",
        ),
        EncounterDef(
            id="e59", name="O Que Não Tem Nome", enemy_ids=["o_inominavel"], is_boss=True,
            area_id="the_shadow_beneath_the_veil",
            flavor_text="Não tem uma forma. Tem uma coleção de máscaras, e nenhuma memória de qual delas veio primeiro.",
        ),
        # -- Área 11: A Biblioteca Fraturada (Arcano) -- só alcançável
        # depois de O Inominável cair, mesma regra sequencial de sempre.
        EncounterDef(
            id="e60", name="Corredores Infinitos", enemy_ids=["livro_errante", "eco_arcano"],
            area_id="the_fractured_library",
            flavor_text="Livros errantes flutuam entre as estantes, e um Eco Arcano imita o que encontra pela frente.",
        ),
        EncounterDef(
            id="e62", name="Ala das Contradições", enemy_ids=["eco_arcano", "eco_arcano", "copista_louco"],
            area_id="the_fractured_library",
            flavor_text="Ecos Arcanos se contradizem a cada passo, e nenhum deles luta da mesma forma duas vezes.",
        ),
        EncounterDef(
            id="e63", name="O Paradoxo", enemy_ids=["paradoxo_ambulante"],
            area_id="the_fractured_library",
            flavor_text="Um Paradoxo Ambulante avança sem elemento fixo -- nenhuma resistência é a certa contra ele.",
        ),
        EncounterDef(
            id="e65", name="A Bibliotecária Fraturada", is_boss=True,
            enemy_ids=["nyxelle", "eco_de_nyxelle_fogo", "eco_de_nyxelle_gelo"],
            area_id="the_fractured_library",
            flavor_text="Nyxelle tentou catalogar todo o conhecimento arcano existente. Ele não coube nela.",
        ),
        # -- Área 12: O Tear Desfeito (final, todos os elementos) -- só
        # alcançável depois de Nyxelle cair. Deliberadamente mais curta
        # que as demais (docs/design/12-monstros.md §3.12: "poucos
        # monstros regulares -- a Área é majoritariamente o corredor
        # final antes do chefe").
        EncounterDef(
            id="e66", name="O Corredor Final", enemy_ids=["sombra_de_arquetipo"],
            area_id="the_unraveling_loom",
            flavor_text="Uma Sombra de Arquétipo se ergue -- o próprio destino de um herói virado contra ele.",
        ),
        EncounterDef(
            id="e67", name="As Fiandeiras", enemy_ids=["fiandeira_menor", "fiandeira_menor"],
            area_id="the_unraveling_loom",
            flavor_text="Fiandeiras Menores tecem o ritmo da luta que se aproxima.",
        ),
        EncounterDef(
            id="e68", name="Aproximação do Tear", enemy_ids=["sombra_de_arquetipo", "fiandeira_menor"],
            area_id="the_unraveling_loom",
            flavor_text="O tear se aproxima, e as últimas sombras tentam atrasar quem chega.",
        ),
        EncounterDef(
            id="e69", name="A Tecelã Desfeita", is_boss=True, enemy_ids=["tecela_desfeita"],
            area_id="the_unraveling_loom",
            flavor_text="O próprio Wyrd, desfiando-se. É de onde o nome do lugar -- e do jogo -- vem.",
        ),
    ]),
)

# Fase 7 -- docs/design/14-estrutura-da-run.md §3 (Os Portais de
# Entrada). Derived from MVP_DUNGEON.encounters, not hand-duplicated --
# MVP_DUNGEON itself stays exactly as it is (still every Área back to
# back, used as-is by every existing test/caller that predates Portais).
AREA_ENCOUNTERS: dict[str, list[EncounterDef]] = {
    area_id: [e for e in MVP_DUNGEON.encounters if e.area_id == area_id] for area_id in AREA_NAMES
}

PORTAL_DEFS: dict[str, PortalDef] = {
    "portao_do_tumulo": PortalDef(
        id="portao_do_tumulo",
        name="Portão do Túmulo",
        path=[
            "the_hollow_barrow", "the_frozen_pinnacle", "the_forgotten_mines",
            "the_shadow_beneath_the_veil", "the_unraveling_loom",
        ],
    ),
    "portao_da_fornalha": PortalDef(
        id="portao_da_fornalha",
        name="Portão da Fornalha",
        path=[
            "the_living_forges", "the_eternal_storm", "the_putrid_bog",
            "the_shattered_sanctuary", "the_unraveling_loom",
        ],
    ),
    "portao_do_gelo": PortalDef(
        id="portao_do_gelo",
        name="Portão do Gelo",
        path=["the_frozen_pinnacle", "the_floating_pinnacles", "the_fractured_library", "the_unraveling_loom"],
    ),
    "portao_da_tempestade": PortalDef(
        id="portao_da_tempestade",
        name="Portão da Tempestade",
        path=["the_eternal_storm", "the_drowned_depths", "the_shadow_beneath_the_veil", "the_unraveling_loom"],
    ),
    # Portal de veterano (desbloqueável) -- "Ecos + ter vencido a run ao
    # menos uma vez" (see persistence/store.py's buy_portal_unlock).
    "portao_submerso": PortalDef(
        id="portao_submerso",
        name="Portão Submerso",
        path=["the_drowned_depths", "the_shattered_sanctuary", "the_unraveling_loom"],
        unlock_condition="ecos_e_vitoria",
    ),
}


def build_dungeon_for_portal(portal_id: str) -> DungeonDef:
    """Assembles one Portal's fixed path into a playable DungeonDef --
    each Área contributes its own already-authored encounter sequence
    unchanged, just concatenated in the Portal's order (docs/design/
    14-estrutura-da-run.md §2: the path is entirely decided up front,
    no in-run branching)."""
    portal = PORTAL_DEFS[portal_id]
    encounters = [e for area_id in portal.path for e in AREA_ENCOUNTERS[area_id]]
    return DungeonDef(id=portal.id, name=portal.name, encounters=encounters)
