from wyrdfall.domain.character import EnemyPhase
from wyrdfall.domain.models import Modifier, ModifierKind, Stat
from wyrdfall.domain.enemies import EnemyDef
from wyrdfall.domain.models import DamageElement, Effect, EffectKind, StatBlock, TriggerEvent, TriggeredEffect

ENEMY_DEFS: dict[str, EnemyDef] = {
    "goblin": EnemyDef(
        id="goblin",
        name="Goblin",
        base_stats=StatBlock(max_hp=10, attack=3, defense=0, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0),
        abilities=["goblin_bite"],
        currency_reward=1,
        vigor_reward=8,
    ),
    "skitterling": EnemyDef(
        id="skitterling",
        name="Rastejante",
        base_stats=StatBlock(max_hp=7, attack=2, defense=0, speed=12, crit_chance=0.05, crit_mult=1.5, max_resource=0),
        abilities=["skitter_bite"],
        currency_reward=1,
        vigor_reward=6,
    ),
    "bonewarden": EnemyDef(
        id="bonewarden",
        name="Guardião Ósseo",
        # Ossos secos e antigos: resistem ao fogo, racham fácil no frio.
        base_stats=StatBlock(
            max_hp=22, attack=5, defense=3, speed=3, crit_chance=0.03, crit_mult=1.5, max_resource=0,
            fire_resist=0.3, ice_resist=-0.3,
        ),
        abilities=["bonewarden_slam"],
        currency_reward=2,
        vigor_reward=20,
    ),
    "hollow_knight": EnemyDef(
        id="hollow_knight",
        name="Cavaleiro Oco",
        # Uma armadura oca e fria: o gelo escorrega, o fogo encontra o vazio por dentro.
        base_stats=StatBlock(
            max_hp=45, attack=6, defense=4, speed=7, crit_chance=0.08, crit_mult=1.6, max_resource=0,
            fire_resist=-0.3, ice_resist=0.3, max_poise=15.0,
        ),
        # docs/design/13-chefes.md §1: 100-50% "O Trono" (kit padrão),
        # <50% "A Fúria do Guardião" (cleave passa a aplicar Sangrando).
        phases=[
            EnemyPhase(hp_ceiling=1.0, abilities=["hollow_smite", "hollow_cleave"]),
            EnemyPhase(hp_ceiling=0.5, abilities=["hollow_smite", "hollow_cleave_bleed"]),
        ],
        currency_reward=6,
        vigor_reward=60,
    ),
    # -- Área 2: As Fornalhas Vivas (Fogo) -------------------------------------
    "cinderling": EnemyDef(
        id="cinderling",
        name="Cinderling",
        base_stats=StatBlock(
            max_hp=9, attack=4, defense=0, speed=8, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            fire_resist=0.4, ice_resist=-0.3,
        ),
        abilities=["ember_bolt"],
        # docs/design/12-monstros.md §3.2: "ao morrer, explode (dano de Fogo
        # em área pequena) -- pune matar de perto sem cuidado".
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_DEATH,
                effect=Effect(kind=EffectKind.DAMAGE, amount=3.0, damage_element=DamageElement.FIRE),
                applies_to="all_enemies",
                source="cinderling_death_explosion",
            )
        ],
        currency_reward=1,
        vigor_reward=9,
    ),
    "forge_automaton": EnemyDef(
        id="forge_automaton",
        name="Autômato de Forja",
        base_stats=StatBlock(
            max_hp=16, attack=6, defense=2, speed=3, crit_chance=0.03, crit_mult=1.5, max_resource=0,
            fire_resist=0.3, ice_resist=-0.3,
        ),
        abilities=["forge_slam"],
        currency_reward=2,
        vigor_reward=14,
    ),
    "living_bellows": EnemyDef(
        id="living_bellows",
        name="Fole Vivo",
        base_stats=StatBlock(
            max_hp=8, attack=1, defense=0, speed=6, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            fire_resist=0.2,
        ),
        abilities=["bellows_empower"],
        currency_reward=1,
        vigor_reward=10,
    ),
    "magma_golem": EnemyDef(
        id="magma_golem",
        name="Golem de Magma Rachado",
        base_stats=StatBlock(
            max_hp=30, attack=7, defense=3, speed=4, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            fire_resist=0.5, ice_resist=-0.4, max_poise=12.0,
        ),
        abilities=["magma_golem_charge", "magma_golem_eruption"],
        currency_reward=4,
        vigor_reward=35,
    ),
    "ashkarion": EnemyDef(
        id="ashkarion",
        name="Ashkarion, o Coração da Forja",
        base_stats=StatBlock(
            max_hp=60, attack=8, defense=5, speed=5, crit_chance=0.08, crit_mult=1.6, max_resource=0,
            fire_resist=0.5, ice_resist=-0.4, max_poise=20.0,
        ),
        # docs/design/13-chefes.md §2: 100-70% "Forja Fechada" (só físico),
        # 70-40% "Forja Aberta" (ganha dano de Fogo em área), <40% "Fúria do
        # Magma" (ataques mais rápidos/mais fortes).
        phases=[
            EnemyPhase(hp_ceiling=1.0, abilities=["ashkarion_smash"]),
            EnemyPhase(hp_ceiling=0.7, abilities=["ashkarion_smash", "ashkarion_eruption"]),
            EnemyPhase(hp_ceiling=0.4, abilities=["ashkarion_eruption", "ashkarion_frenzy"]),
        ],
        currency_reward=9,
        vigor_reward=95,
    ),
    # -- Área 3: O Pico Silente (Gelo) ------------------------------------------
    "lobo_de_gelo": EnemyDef(
        id="lobo_de_gelo",
        name="Lobo de Gelo",
        base_stats=StatBlock(
            max_hp=11, attack=4, defense=1, speed=9, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            ice_resist=0.3, fire_resist=-0.3,
        ),
        abilities=["wolf_bite"],
        # a pack animal: the survivors get Fortalecido when one of them falls
        # (11-habilidades.md §14 ON_ALLY_DOWNED, enemy side)
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_ALLY_DOWNED,
                effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="empowered", duration=2),
                applies_to="self",
                source="lobo_de_gelo_alcateia",
            )
        ],
        currency_reward=1,
        vigor_reward=10,
    ),
    "espectro_gelado": EnemyDef(
        id="espectro_gelado",
        name="Espectro Gelado",
        base_stats=StatBlock(
            max_hp=9, attack=3, defense=0, speed=7, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            ice_resist=0.3, fire_resist=-0.3,
        ),
        abilities=["frost_touch"],
        currency_reward=1,
        vigor_reward=11,
    ),
    "xama_da_nevasca": EnemyDef(
        id="xama_da_nevasca",
        name="Xamã da Nevasca",
        base_stats=StatBlock(
            max_hp=10, attack=2, defense=0, speed=5, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            ice_resist=0.2,
        ),
        abilities=["ice_ward"],
        currency_reward=2,
        vigor_reward=13,
    ),
    "ceifador_de_carambano": EnemyDef(
        id="ceifador_de_carambano",
        name="Ceifador de Carâmbano",
        base_stats=StatBlock(
            max_hp=32, attack=7, defense=3, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            ice_resist=0.5, fire_resist=-0.4, max_poise=13.0,
        ),
        abilities=["icicle_volley"],
        currency_reward=4,
        vigor_reward=38,
    ),
    "viuva_de_gelo": EnemyDef(
        id="viuva_de_gelo",
        name="A Viúva de Gelo",
        base_stats=StatBlock(
            max_hp=70, attack=9, defense=4, speed=8, crit_chance=0.08, crit_mult=1.6, max_resource=0,
            ice_resist=0.5, fire_resist=-0.4, max_poise=22.0,
        ),
        status_immunities={"fear"},
        # docs/design/13-chefes.md §3: 100-60% "Véu de Neblina" (kit à
        # distância), 60-30% "Coração Congelado" (kit mais agressivo),
        # <30% "Ventania Final" (golpe mais forte). The evasion-window,
        # poise-gated conditional immunity, self-inflicted-stack-on-miss
        # and extended post-poise-break-stun mechanics the doc also
        # describes are disclosed cuts (see the Fase 7 increment 2 plan)
        # -- none of them have engine support today.
        phases=[
            EnemyPhase(hp_ceiling=1.0, abilities=["viuva_frost_bolt"]),
            EnemyPhase(hp_ceiling=0.6, abilities=["viuva_frost_bolt", "viuva_ice_lance"]),
            EnemyPhase(hp_ceiling=0.3, abilities=["viuva_ice_lance", "viuva_glacial_shatter"]),
        ],
        # "Ventania Final" (dano crescente a cada turno) approximated as
        # a real self-stacking buff every one of her own turns -- same
        # working ON_TURN_START pattern as Licantropo's instinto_
        # selvagem (races.py) -- rather than a literal per-turn timer,
        # which has no engine concept to hook into. Not phase-gated
        # (EnemyDef.triggered_effects apply for the whole fight, unlike
        # abilities which ARE phase-swapped above) -- still captures
        # "gets more dangerous as the fight drags on" faithfully.
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TURN_START,
                effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="ventania_final", duration=2, stacks=1),
                applies_to="self",
                source="viuva_de_gelo_enrage",
            ),
        ],
        currency_reward=10,
        vigor_reward=105,
    ),
    # -- Área 4: A Tempestade Eterna (Raio) --------------------------------------
    "ave_trovao": EnemyDef(
        id="ave_trovao",
        name="Ave-Trovão",
        # "Iniciativa altíssima, sempre age cedo" (docs/design/
        # 12-monstros.md §3.4) -- Speed is the only knob turn order reads.
        base_stats=StatBlock(
            max_hp=10, attack=4, defense=1, speed=14, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            lightning_resist=0.3, earth_resist=-0.3,
        ),
        abilities=["thunderbird_strike"],
        currency_reward=1,
        vigor_reward=12,
    ),
    "sentinela_eletrizada": EnemyDef(
        id="sentinela_eletrizada",
        name="Sentinela Eletrizada",
        base_stats=StatBlock(
            max_hp=13, attack=4, defense=2, speed=6, crit_chance=0.03, crit_mult=1.5, max_resource=0,
            block_chance=0.3, lightning_resist=0.3, earth_resist=-0.3,
        ),
        abilities=["sentinela_shock"],
        # "Contra-ataca com Raio quem a acerta enquanto ela está
        # bloqueando" -- ON_BLOCK already fires with the attacker as
        # context (see combat.py::_apply_damage), so this is a plain
        # applies_to="context" TriggeredEffect, no new engine work.
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_BLOCK,
                effect=Effect(kind=EffectKind.DAMAGE, amount=3.0, damage_element=DamageElement.LIGHTNING),
                applies_to="context",
                source="sentinela_counter",
            )
        ],
        currency_reward=2,
        vigor_reward=14,
    ),
    "arauto_da_tempestade": EnemyDef(
        id="arauto_da_tempestade",
        name="Arauto da Tempestade",
        base_stats=StatBlock(
            max_hp=10, attack=2, defense=0, speed=7, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            lightning_resist=0.2,
        ),
        abilities=["storm_bolt", "storm_haste"],
        currency_reward=2,
        vigor_reward=15,
    ),
    "colosso_carregado": EnemyDef(
        id="colosso_carregado",
        name="Colosso Carregado",
        base_stats=StatBlock(
            max_hp=34, attack=7, defense=3, speed=5, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            lightning_resist=0.5, earth_resist=-0.4, max_poise=14.0,
        ),
        # "Acumula Carga a cada turno; ao encher, libera um ataque em
        # área" -- simplified to a normal 2-ability kit (a bolt + the
        # area "release") rather than a true charge-then-auto-release
        # telegraph, since no stack-threshold-triggers-effect mechanism
        # exists yet (same disclosed gap as Área 3's Fragilidade ao
        # Gelo burst).
        abilities=["charged_bolt", "charged_burst"],
        currency_reward=4,
        vigor_reward=40,
    ),
    "voltharion": EnemyDef(
        id="voltharion",
        name="Voltharion, Arauto da Tempestade",
        base_stats=StatBlock(
            max_hp=75, attack=9, defense=4, speed=7, crit_chance=0.08, crit_mult=1.6, max_resource=0,
            lightning_resist=0.5, earth_resist=-0.4, max_poise=24.0,
        ),
        # docs/design/13-chefes.md §4: phases keyed off Postura breaks, not
        # PV -- each break "recarrega" him and changes the pattern; the 3rd
        # opens the final, most aggressive phase. Phase 0 carries the
        # "Esquiva altíssima até a primeira quebra" as its own modifier.
        # Her signature "Tempestade Final" (voltharion_tempest, ALL_ENEMIES)
        # is the literal "encadeia entre todos os jogadores vivos"; only
        # the "pune grupos com resistência parecida" nuance stays cut
        # (Effect has no resistance-comparison logic).
        phases=[
            EnemyPhase(
                trigger="poise_break", abilities=["voltharion_bolt"],
                modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.5, source="voltharion_storm_veil")],
            ),
            EnemyPhase(trigger="poise_break", abilities=["voltharion_bolt", "voltharion_strike"]),
            EnemyPhase(trigger="poise_break", abilities=["voltharion_strike", "voltharion_tempest"]),
            EnemyPhase(trigger="poise_break", abilities=["voltharion_strike", "voltharion_tempest", "voltharion_bolt"]),
        ],
        currency_reward=11,
        vigor_reward=115,
    ),
    # -- Área 5: As Profundezas Afogadas (Água) ----------------------------------
    "afogado": EnemyDef(
        id="afogado",
        name="Afogado",
        base_stats=StatBlock(
            max_hp=12, attack=5, defense=1, speed=7, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            water_resist=0.3, earth_resist=-0.3,
        ),
        abilities=["drowned_grasp"],
        currency_reward=1,
        vigor_reward=13,
    ),
    "enguia_espectral": EnemyDef(
        id="enguia_espectral",
        name="Enguia-Espectral",
        base_stats=StatBlock(
            max_hp=10, attack=4, defense=0, speed=8, crit_chance=0.05, crit_mult=1.5, max_resource=6,
            water_resist=0.3, earth_resist=-0.3,
        ),
        abilities=["resource_drain"],
        currency_reward=1,
        vigor_reward=14,
    ),
    "sacerdotisa_afogada": EnemyDef(
        id="sacerdotisa_afogada",
        name="Sacerdotisa Afogada",
        base_stats=StatBlock(
            max_hp=12, attack=2, defense=0, speed=5, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            earth_resist=-0.2,
        ),
        abilities=["drowned_blessing"],
        currency_reward=2,
        vigor_reward=16,
    ),
    "kraken_jovem": EnemyDef(
        id="kraken_jovem",
        name="Kraken Jovem",
        base_stats=StatBlock(
            max_hp=36, attack=8, defense=3, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            water_resist=0.5, earth_resist=-0.4, max_poise=15.0,
        ),
        # "Várias habilidades diferentes por turno" (flavor de múltiplos
        # tentáculos) read as kit breadth (3 abilities to choose from),
        # not multiple actions per turn -- no such mechanism exists.
        abilities=["kraken_tentacle_strike", "kraken_crush", "kraken_soak"],
        currency_reward=4,
        vigor_reward=42,
    ),
    "maremoto": EnemyDef(
        id="maremoto",
        name="Maremoto, o Que Devora Correntes",
        base_stats=StatBlock(
            max_hp=85, attack=10, defense=5, speed=6, crit_chance=0.08, crit_mult=1.6, max_resource=0,
            # docs/design/13-chefes.md §5: "muito fraco a Terra... o
            # primeiro chefe com uma fraqueza tão extrema" -- set more
            # negative than any prior boss's elemental weakness on purpose.
            water_resist=0.5, earth_resist=-0.6, max_poise=25.0,
        ),
        # "Imune a Afogar" -- no Afogar StatusEffectDef exists anywhere
        # (only Encharcado is real, applied content in this area) --
        # correctly modeled, not yet reachable, same disclosed pattern
        # as "fear" elsewhere.
        status_immunities={"afogar"},
        # docs/design/13-chefes.md §5: 100-50% "Correntes Profundas"
        # (aplica Encharcado em área), <50% "Fúria da Maré" (adiciona um
        # golpe de Correnteza/Lentidão pesada). HP-threshold phases fit
        # this boss's own documented breakpoints directly, unlike
        # Voltharion's Postura-gating.
        phases=[
            EnemyPhase(hp_ceiling=1.0, abilities=["maremoto_bite", "maremoto_soak"]),
            EnemyPhase(hp_ceiling=0.5, abilities=["maremoto_bite", "maremoto_soak", "maremoto_undertow"]),
        ],
        currency_reward=12,
        vigor_reward=125,
    ),
    # -- Área 6: As Minas Esquecidas (Terra) -------------------------------------
    "verme_de_pedra": EnemyDef(
        id="verme_de_pedra",
        name="Verme de Pedra",
        # "Sempre age primeiro no 1o turno" (docs/design/12-monstros.md
        # §3.6) simplified to a permanently very high Speed, same
        # simplification already used for Área 4's Ave-Trovão.
        base_stats=StatBlock(
            max_hp=13, attack=5, defense=1, speed=15, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            earth_resist=0.3, air_resist=-0.3,
        ),
        abilities=["stoneworm_ambush"],
        currency_reward=1,
        vigor_reward=14,
    ),
    "golem_de_cascalho": EnemyDef(
        id="golem_de_cascalho",
        name="Golem de Cascalho",
        # "Individualmente frágil, sempre em quantidade" -- low HP,
        # fielded in numbers via EncounterDef.enemy_ids repeats.
        base_stats=StatBlock(
            max_hp=8, attack=4, defense=1, speed=5, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            earth_resist=0.3, air_resist=-0.3,
        ),
        abilities=["gravel_slam"],
        currency_reward=1,
        vigor_reward=11,
    ),
    "xama_de_pedra": EnemyDef(
        id="xama_de_pedra",
        name="Xamã de Pedra",
        # "Aplica Fragmentado em quem os aliados dele acertarem"
        # (reactive to ALLIES' hits) simplified to her own direct
        # castable debuff -- no trigger broadcasts one character's
        # ON_HIT to their allies today, same cut already used for Área
        # 4's Arauto da Tempestade.
        base_stats=StatBlock(
            max_hp=11, attack=2, defense=0, speed=5, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            air_resist=-0.2,
        ),
        abilities=["shatter_curse"],
        currency_reward=2,
        vigor_reward=16,
    ),
    "guardiao_cristalino": EnemyDef(
        id="guardiao_cristalino",
        name="Guardião Cristalino",
        base_stats=StatBlock(
            max_hp=40, attack=7, defense=6, speed=5, crit_chance=0.03, crit_mult=1.5, max_resource=0,
            earth_resist=0.5, air_resist=-0.4, max_poise=16.0,
        ),
        abilities=["crystal_guard_strike"],
        # "Alterna uma stance Cristalizada que reflete parte do dano
        # recebido" simplified to a permanent flat-amount reflection
        # (no toggleable-stance mechanism exists, and Effect can't
        # reference the damage amount just dealt for a true %-based
        # reflection) -- same disclosed-cut category as Meio-celestial's
        # form-switch.
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TAKE_DAMAGE,
                effect=Effect(kind=EffectKind.DAMAGE, amount=3.0, damage_element=DamageElement.EARTH),
                applies_to="context",
                source="guardiao_cristalino_reflect",
            )
        ],
        currency_reward=4,
        vigor_reward=44,
    ),
    "terrakon": EnemyDef(
        id="terrakon",
        name="Terrakon, o Que Não Desaba",
        # docs/design/13-chefes.md §6: no HP-phases at all in the doc --
        # a 3-layer "armadura de pedra" gated by Postura-breaks blocks
        # all HP damage until broken, a mechanic combat.py has no
        # support for (HP damage always applies once computed; poise-
        # break only stuns/resets poise, never gates whether damage
        # lands). Disclosed cut (Fase 7 increment 5 plan): reuses the
        # proven HP-phase mechanism instead, and leans on the highest
        # Defense/max_poise/max_hp of any boss so far to capture the
        # "war of attrition tank" fantasy without the literal armor
        # layers. Immunity to Fragmentado is simplified from "outside
        # brief post-break windows" to permanent, since those windows
        # are exactly the cut part.
        base_stats=StatBlock(
            max_hp=95, attack=9, defense=8, speed=4, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            earth_resist=0.6, air_resist=-0.5, max_poise=28.0,
        ),
        status_immunities={"fragmentado"},
        phases=[
            EnemyPhase(hp_ceiling=1.0, abilities=["terrakon_crush"]),
            EnemyPhase(hp_ceiling=0.5, abilities=["terrakon_crush", "terrakon_quake"]),
        ],
        currency_reward=13,
        vigor_reward=135,
    ),
    # -- Área 7: Os Pináculos Flutuantes (Ar) ------------------------------------
    "harpia": EnemyDef(
        id="harpia",
        name="Harpia",
        base_stats=StatBlock(
            max_hp=11, attack=4, defense=1, speed=9, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            air_resist=0.3, earth_resist=-0.3, lightning_resist=-0.2,
        ),
        abilities=["harpy_gust"],
        currency_reward=1,
        vigor_reward=13,
    ),
    "elemental_de_vento": EnemyDef(
        id="elemental_de_vento",
        name="Elemental de Vento",
        # "Foge/prioriza fugir quando baixo de PV" -- no flee/disengage
        # AI behavior exists (every enemy always acts via
        # resolve_ai_turn's normal ability selection) -- a plain attack
        # instead, disclosed cut.
        base_stats=StatBlock(
            max_hp=9, attack=3, defense=0, speed=10, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            air_resist=0.3, earth_resist=-0.3, lightning_resist=-0.2,
        ),
        abilities=["wind_gale"],
        currency_reward=1,
        vigor_reward=12,
    ),
    "arauto_do_vendaval": EnemyDef(
        id="arauto_do_vendaval",
        name="Arauto do Vendaval",
        base_stats=StatBlock(
            max_hp=10, attack=2, defense=0, speed=6, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            earth_resist=-0.2, lightning_resist=-0.2,
        ),
        abilities=["gale_call"],
        currency_reward=2,
        vigor_reward=16,
    ),
    "roc_menor": EnemyDef(
        id="roc_menor",
        name="Roc Menor",
        base_stats=StatBlock(
            max_hp=38, attack=8, defense=3, speed=8, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            dodge_chance=0.25, air_resist=0.5, earth_resist=-0.4, lightning_resist=-0.3, max_poise=16.0,
        ),
        abilities=["roc_strike"],
        # "Aplica Desequilibrado em quem erra um ataque contra ele" --
        # ON_DODGE already fires on the dodger with the attacker as
        # context (combat.py::_apply_damage), so this is a plain
        # applies_to="context" TriggeredEffect, same shape as Sentinela
        # Eletrizada's block-counter (Área 4).
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_DODGE,
                effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="desequilibrado", duration=3, stacks=1),
                applies_to="context",
                source="roc_menor_punish",
            )
        ],
        currency_reward=4,
        vigor_reward=46,
    ),
    "zephyra": EnemyDef(
        id="zephyra",
        name="Zephyra, a Última Rajada",
        # docs/design/13-chefes.md §7: "esquiva altíssima o tempo todo;
        # só fica atingível de verdade durante uma janela curta logo
        # depois que ela mesma ataca" -- the identical shape to Viúva de
        # Gelo's already-cut evasion-window mechanic (no timing-window
        # concept exists in combat.py). Disclosed cut: a permanently
        # high dodge_chance instead. Postura Precisa (the player-facing
        # stance system she's designed to reward) doesn't exist anywhere
        # in this codebase and is a separate, much larger system -- the
        # doc itself says the fight is completable without it.
        base_stats=StatBlock(
            max_hp=90, attack=9, defense=4, speed=9, crit_chance=0.08, crit_mult=1.6, max_resource=0,
            dodge_chance=0.35, air_resist=0.5, earth_resist=-0.5, lightning_resist=-0.4, max_poise=24.0,
        ),
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_DODGE,
                effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="desequilibrado", duration=3, stacks=1),
                applies_to="context",
                source="zephyra_punish",
            )
        ],
        # "A 50% ganha um segundo ataque por turno -- fica mais rápida,
        # não mecanicamente diferente" -- approximated as a single
        # ability with two DAMAGE effects (Ability.effects already
        # applies every effect to the resolved targets in one action),
        # not a new multi-action-per-turn mechanism.
        phases=[
            EnemyPhase(hp_ceiling=1.0, abilities=["zephyra_gust"]),
            EnemyPhase(hp_ceiling=0.5, abilities=["zephyra_double_gale"]),
        ],
        currency_reward=14,
        vigor_reward=145,
    ),
    # -- Área 8: O Pântano Pútrido (Veneno) --------------------------------------
    "sanguessuga_gigante": EnemyDef(
        id="sanguessuga_gigante",
        name="Sanguessuga Gigante",
        # "Lifesteal básico" -- the existing lifesteal_percent StatBlock
        # field, already consumed for any character in
        # combat.py::_apply_damage. No ability needed to carry it.
        base_stats=StatBlock(
            max_hp=13, attack=5, defense=1, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            poison_resist=0.3, holy_resist=-0.3, lifesteal_percent=0.25,
        ),
        abilities=["leech_bite"],
        currency_reward=1,
        vigor_reward=14,
    ),
    "esporo_ambulante": EnemyDef(
        id="esporo_ambulante",
        name="Esporo Ambulante",
        base_stats=StatBlock(
            max_hp=9, attack=3, defense=0, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            poison_resist=0.3, holy_resist=-0.3,
        ),
        abilities=["spore_bolt"],
        # "Ao morrer, libera uma nuvem que aplica Veneno em quem estiver
        # perto" -- same ON_DEATH/all_enemies shape as Cinderling's
        # death explosion (Área 2).
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_DEATH,
                effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=3, stacks=1),
                applies_to="all_enemies",
                source="esporo_ambulante_death_cloud",
            )
        ],
        currency_reward=1,
        vigor_reward=12,
    ),
    "xama_do_lodo": EnemyDef(
        id="xama_do_lodo",
        name="Xamã do Lodo",
        # "Empilha Veneno mais rápido em alvos já envenenados" --
        # simplified to a flat stacks=2 per cast (see mud_curse) rather
        # than a new "check the target's current status" hook.
        base_stats=StatBlock(
            max_hp=10, attack=2, defense=0, speed=5, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            holy_resist=-0.2,
        ),
        abilities=["mud_curse"],
        currency_reward=2,
        vigor_reward=16,
    ),
    "horror_do_charco": EnemyDef(
        id="horror_do_charco",
        name="Horror do Charco",
        # "Regenera PV proporcionalmente aos próprios stacks de Veneno"
        # -- no Effect/Modifier scales off "stacks of a specific status
        # this character carries" (only off a Stat), and nothing puts
        # Veneno stacks on an enemy today anyway (no player ability
        # deals Veneno yet) -- lifesteal_percent instead, same general
        # "self-sustaining Veneno enemy" identity.
        base_stats=StatBlock(
            max_hp=36, attack=7, defense=3, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            poison_resist=0.5, holy_resist=-0.4, max_poise=15.0, lifesteal_percent=0.3,
        ),
        abilities=["bog_horror_strike"],
        currency_reward=4,
        vigor_reward=42,
    ),
    "mae_putrida": EnemyDef(
        id="mae_putrida",
        name="A Mãe Pútrida",
        # docs/design/13-chefes.md §8: no HP-phases -- every Postura break
        # splits off a Broto (a real SUMMON on her side, capped at 3 alive);
        # the encounter only ends when she AND the living Brotos are down,
        # which is what _check_victory already demands of enemy summons.
        # The 3 break-phases below are the "how many Brotos are out" beats.
        base_stats=StatBlock(
            max_hp=98, attack=10, defense=5, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            poison_resist=0.6, holy_resist=-0.5, max_poise=26.0,
        ),
        status_immunities={"poisoned"},
        phases=[
            EnemyPhase(trigger="poise_break", abilities=["putrid_mother_bite", "putrid_cloud"]),
            EnemyPhase(trigger="poise_break", abilities=["putrid_mother_bite", "putrid_cloud"], summon_id="broto_putrido"),
            EnemyPhase(trigger="poise_break", abilities=["putrid_mother_bite", "putrid_swarm"], summon_id="broto_putrido"),
            EnemyPhase(trigger="poise_break", abilities=["putrid_mother_bite", "putrid_swarm"], summon_id="broto_putrido"),
        ],
        currency_reward=15,
        vigor_reward=150,
    ),
    # -- Área 9: O Santuário Desmoronado (Sagrado) -------------------------------
    "serafim_partido": EnemyDef(
        id="serafim_partido",
        name="Serafim Partido",
        base_stats=StatBlock(
            max_hp=12, attack=3, defense=1, speed=6, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            holy_resist=0.3, shadow_resist=-0.3,
        ),
        # "Cura a si mesmo" -- forces the player to interrupt or accept
        # a longer fight; a simple TargetMode.SELF heal already covers
        # this, no new mechanism needed.
        abilities=["seraph_strike", "seraph_mend"],
        currency_reward=1,
        vigor_reward=13,
    ),
    "zelote_cego": EnemyDef(
        id="zelote_cego",
        name="Zelote Cego",
        base_stats=StatBlock(
            max_hp=13, attack=4, defense=1, speed=7, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            holy_resist=0.3, shadow_resist=-0.3,
        ),
        # "Ganha ATQ quanto mais baixo o próprio PV" (continuous
        # scaling) approximated as a discrete stronger attack below 50%
        # HP -- the proven EnemyPhase mechanism, not a new HP-dependent
        # formula (Modifier/StatusEffectDef only carry static values).
        phases=[
            EnemyPhase(hp_ceiling=1.0, abilities=["zealot_strike"]),
            EnemyPhase(hp_ceiling=0.5, abilities=["zealot_fury_strike"]),
        ],
        currency_reward=1,
        vigor_reward=14,
    ),
    "cantor_de_hinos": EnemyDef(
        id="cantor_de_hinos",
        name="Cantor de Hinos",
        base_stats=StatBlock(
            max_hp=10, attack=2, defense=0, speed=5, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            shadow_resist=-0.2,
        ),
        abilities=["hymn_curse"],
        currency_reward=2,
        vigor_reward=16,
    ),
    "guardiao_de_luz": EnemyDef(
        id="guardiao_de_luz",
        name="Guardião de Luz",
        base_stats=StatBlock(
            max_hp=38, attack=8, defense=4, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            holy_resist=0.5, shadow_resist=-0.4, max_poise=16.0,
        ),
        # "Imune a Medo" -- inert, disclosed (no "fear" StatusEffectDef
        # exists anywhere yet, same pattern as Renascido/Construto).
        status_immunities={"fear"},
        abilities=["light_guardian_strike"],
        currency_reward=4,
        vigor_reward=48,
    ),
    "solyth": EnemyDef(
        id="solyth",
        name="Solyth, o Arcanjo Renegado",
        base_stats=StatBlock(
            max_hp=105, attack=10, defense=5, speed=7, crit_chance=0.08, crit_mult=1.6, max_resource=0,
            holy_resist=0.5, shadow_resist=-0.5, max_poise=27.0,
        ),
        # docs/design/13-chefes.md §9: 100-66% "Piedade" (heals the
        # PLAYER party -- see solyth_mercy: an ALL_ENEMIES-targeted HEAL
        # cast by a non-player actor resolves via combat.py::
        # legal_target_ids's own other_side=party_ids() for non-players,
        # so this lands on the party with zero new engine work), 66-33%
        # "Julgamento" (a damage-reflection window -- cut: EnemyDef.
        # triggered_effects can't be scoped to one phase, and applying
        # it for the whole fight would contradict phase 1's explicit
        # "not a trap" framing; a plain attack instead), <33% "Queda"
        # (self-inflicted Sagrado vulnerability -- cut: holy_resist has
        # no per-phase override; her strongest, bonus_vs_tags-carrying
        # attack unlocks here instead, "desperate power" rather than
        # literal self-vulnerability).
        phases=[
            EnemyPhase(hp_ceiling=1.0, abilities=["solyth_mercy"]),
            EnemyPhase(hp_ceiling=0.66, abilities=["solyth_smite"]),
            EnemyPhase(hp_ceiling=0.33, abilities=["solyth_smite", "solyth_fallen_wrath"]),
        ],
        currency_reward=16,
        vigor_reward=160,
    ),
    # -- Área 10: A Sombra Sob o Véu (Sombrio) -----------------------------------
    "sussurro": EnemyDef(
        id="sussurro",
        name="Sussurro",
        base_stats=StatBlock(
            max_hp=10, attack=3, defense=0, speed=7, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            shadow_resist=0.3, holy_resist=-0.3,
        ),
        abilities=["whisper_fear"],
        currency_reward=1,
        vigor_reward=13,
    ),
    "carne_amaldicoada": EnemyDef(
        id="carne_amaldicoada",
        name="Carne Amaldiçoada",
        base_stats=StatBlock(
            max_hp=11, attack=4, defense=1, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            shadow_resist=0.3, holy_resist=-0.3,
        ),
        abilities=["cursed_flesh_strike"],
        # "Ao chegar a 0 PV, fica Latente 1 turno (ainda pode agir uma
        # última vez) antes de morrer de vez" -- reuses the existing
        # can_cheat_death/cheated_death_used mechanism (Humano's own
        # "Nunca Desista" trait), now wired for enemies too.
        grants_cheat_death=True,
        currency_reward=1,
        vigor_reward=15,
    ),
    "arauto_do_veu": EnemyDef(
        id="arauto_do_veu",
        name="Arauto do Véu",
        base_stats=StatBlock(
            max_hp=10, attack=2, defense=0, speed=5, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            holy_resist=-0.2,
        ),
        abilities=["veil_herald_ward"],
        currency_reward=2,
        vigor_reward=16,
    ),
    "devorador_de_luz": EnemyDef(
        id="devorador_de_luz",
        name="Devorador de Luz",
        base_stats=StatBlock(
            max_hp=40, attack=8, defense=3, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            shadow_resist=0.5, holy_resist=-0.4, max_poise=17.0,
        ),
        abilities=["light_devourer_drain"],
        currency_reward=4,
        vigor_reward=50,
    ),
    "o_inominavel": EnemyDef(
        id="o_inominavel",
        name="O Inominável",
        # docs/design/13-chefes.md §10: on every Postura break, draws one
        # of 3 Máscaras (Garras/Olhos/Bocas) at random, never the same one
        # twice in a row (random_phase_on_break excludes the current one).
        base_stats=StatBlock(
            max_hp=110, attack=10, defense=5, speed=7, crit_chance=0.08, crit_mult=1.6, max_resource=0,
            # "Imune a dano Sombrio" -- combat.py caps total elemental
            # resistance at 0.9 and floors damage at 1.0 regardless
            # (an existing engine ceiling, not a new gap) -- 0.9 is the
            # closest reachable approximation to true immunity.
            shadow_resist=0.9, holy_resist=-0.5, max_poise=28.0,
        ),
        random_phase_on_break=True,
        phases=[
            EnemyPhase(trigger="poise_break", abilities=["nameless_claws"]),
            EnemyPhase(trigger="poise_break", abilities=["nameless_eyes"]),
            EnemyPhase(trigger="poise_break", abilities=["nameless_mouths"]),
        ],
        currency_reward=17,
        vigor_reward=165,
    ),
    # -- Área 11: A Biblioteca Fraturada (Arcano) -----------------------------------
    "livro_errante": EnemyDef(
        id="livro_errante",
        name="Livro Errante",
        base_stats=StatBlock(
            max_hp=11, attack=4, defense=1, speed=6, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            arcane_resist=0.3,
        ),
        abilities=["wandering_book_read"],
        currency_reward=1,
        vigor_reward=14,
    ),
    "eco_arcano": EnemyDef(
        id="eco_arcano",
        name="Eco Arcano",
        base_stats=StatBlock(
            max_hp=12, attack=4, defense=1, speed=7, crit_chance=0.05, crit_mult=1.5, max_resource=10,
            arcane_resist=0.2,
        ),
        # "Usa uma habilidade genérica de arquétipo aleatório a cada
        # turno" -- needs no new mechanic: resolve_ai_turn already picks
        # uniformly at random among an enemy's usable abilities every
        # turn (combat.py:249), so 3 abilities styled as 3 archetypes
        # (melee/magic/support) already deliver the doc line as-is.
        abilities=["arcane_echo_strike", "arcane_echo_bolt", "arcane_echo_focus"],
        currency_reward=1,
        vigor_reward=15,
    ),
    "copista_louco": EnemyDef(
        id="copista_louco",
        name="Copista Louco",
        base_stats=StatBlock(
            max_hp=9, attack=2, defense=0, speed=5, crit_chance=0.0, crit_mult=1.5, max_resource=0,
            arcane_resist=0.2,
        ),
        # "Replica o último efeito que o grupo de jogadores usou,
        # devolvendo contra eles" -- no last-player-action tracking
        # exists on CombatState. Disclosed simplification (Fase 7
        # increment 10 plan): applies the existing "weakened" debuff to
        # the whole party instead of a dynamic mirror.
        abilities=["mad_copyist_mirror", "mad_copyist_silence", "mad_copyist_draft"],
        currency_reward=2,
        vigor_reward=17,
    ),
    "paradoxo_ambulante": EnemyDef(
        id="paradoxo_ambulante",
        name="Paradoxo Ambulante",
        base_stats=StatBlock(
            max_hp=42, attack=8, defense=3, speed=7, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            arcane_resist=0.4, max_poise=18.0,
        ),
        # "Elemento de dano aleatório a cada turno -- não dá pra ter uma
        # resistência 'certa' contra ele de propósito" -- built for real
        # via Effect.random_damage_element, its doc-defined identity.
        abilities=["paradox_unstable_strike", "paradox_arcane_rift"],
        currency_reward=4,
        vigor_reward=52,
    ),
    "eco_de_nyxelle_fogo": EnemyDef(
        id="eco_de_nyxelle_fogo",
        name="Eco de Nyxelle (Fogo)",
        base_stats=StatBlock(
            max_hp=35, attack=7, defense=2, speed=8, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            fire_resist=0.4, ice_resist=-0.3, arcane_resist=0.3,
        ),
        abilities=["echo_of_fire"],
        currency_reward=3,
        vigor_reward=30,
    ),
    "eco_de_nyxelle_gelo": EnemyDef(
        id="eco_de_nyxelle_gelo",
        name="Eco de Nyxelle (Gelo)",
        base_stats=StatBlock(
            max_hp=35, attack=7, defense=2, speed=8, crit_chance=0.05, crit_mult=1.5, max_resource=0,
            ice_resist=0.4, fire_resist=-0.3, arcane_resist=0.3,
        ),
        abilities=["echo_of_ice"],
        currency_reward=3,
        vigor_reward=30,
    ),
    "nyxelle": EnemyDef(
        id="nyxelle",
        name="Nyxelle, a Bibliotecária Fraturada",
        # docs/design/13-chefes.md §11: "fica imune enquanto qualquer Eco
        # estiver vivo" + "dano Arcano nela cura em vez de ferir" -- both
        # built for real (Character.immune_while_allies_alive/
        # absorbs_damage_element, Fase 7 increment 10 plan), not
        # approximated. Session instance ids are f"{enemy_id}_{i}" with i
        # = position in EncounterDef.enemy_ids (session.py:87) -- this
        # only resolves correctly because e60's enemy_ids is fixed to
        # ["nyxelle", "eco_de_nyxelle_fogo", "eco_de_nyxelle_gelo"].
        #
        # Cut (same category as Terrakon/Voltharion/O Inominável): Phase
        # 2's "herda um resquício do elemento do Eco que sobreviveu mais
        # tempo" needs death-order/duration tracking that doesn't exist
        # anywhere. No EnemyPhase is used here at all -- her real
        # defining mechanic is fully carried by immune_while_allies_alive,
        # and she keeps one flat (disclosed-fixed, not dynamic) resist
        # profile for the whole fight instead.
        # arcane_resist is irrelevant on her -- absorbs_damage_element
        # short-circuits Arcane hits into a heal before resist is ever
        # read, so no arcane_resist value is set here.
        base_stats=StatBlock(
            max_hp=120, attack=11, defense=4, speed=8, crit_chance=0.08, crit_mult=1.6, max_resource=0,
            holy_resist=-0.2, max_poise=26.0,
        ),
        abilities=["nyxelle_shredded_page", "nyxelle_unbound_knowledge"],
        immune_while_allies_alive={"eco_de_nyxelle_fogo_1", "eco_de_nyxelle_gelo_2"},
        absorbs_damage_element=DamageElement.ARCANE,
        currency_reward=18,
        vigor_reward=175,
    ),
    # -- Área 12: O Tear Desfeito (final, todos os elementos) -----------------------
    "sombra_de_arquetipo": EnemyDef(
        id="sombra_de_arquetipo",
        name="Sombra de Arquétipo",
        # "Copia o Arquétipo Base de um jogador específico" -- no
        # mechanism exists to read a specific player's build and mirror
        # it. Disclosed simplification (Fase 7 increment 11 plan): a
        # static melee+magic hybrid instead.
        base_stats=StatBlock(
            max_hp=30, attack=7, defense=3, speed=8, crit_chance=0.08, crit_mult=1.6, max_resource=0,
        ),
        abilities=["archetype_shadow_slash", "archetype_shadow_bolt"],
        currency_reward=3,
        vigor_reward=28,
    ),
    "fiandeira_menor": EnemyDef(
        id="fiandeira_menor",
        name="Fiandeira Menor",
        # "Acelera o Medidor do Wyrd de todos os presentes" -- the Wyrd
        # Meter is explicitly Fase 8 scope (09-roadmap.md), not built
        # yet. Disclosed simplification: a generic ally-attack buff.
        base_stats=StatBlock(
            max_hp=16, attack=3, defense=1, speed=9, crit_chance=0.0, crit_mult=1.5, max_resource=0,
        ),
        abilities=["spinner_hasten"],
        currency_reward=2,
        vigor_reward=20,
    ),
    "tecela_desfeita": EnemyDef(
        id="tecela_desfeita",
        name="A Tecelã Desfeita",
        # docs/design/13-chefes.md §12: "muda a cada quebra de Postura,
        # não por PV" -- same structural gap as every boss this arc
        # (EnemyPhase is HP-ceiling-only, no poise-break phase-trigger
        # exists). Disclosed cut: 4 HP-threshold phases instead.
        # "Nenhuma resistência elemental fixa (muda por fase)" -- no
        # per-phase resistance override exists either, so she keeps one
        # flat, neutral resist profile for the whole fight (no
        # elemental resist stats set at all) instead of one that
        # changes per phase.
        base_stats=StatBlock(
            max_hp=160, attack=13, defense=6, speed=9, crit_chance=0.1, crit_mult=1.7, max_resource=0,
            max_poise=32.0,
        ),
        phases=[
            EnemyPhase(hp_ceiling=1.0, abilities=["loom_thread_of_fire", "loom_thread_of_ice"]),
            EnemyPhase(hp_ceiling=0.66, abilities=["loom_thread_of_lightning", "loom_thread_of_earth"]),
            EnemyPhase(hp_ceiling=0.33, abilities=["loom_thread_of_shadow", "loom_thread_of_light"]),
            EnemyPhase(hp_ceiling=0.15, abilities=["loom_broken_thread"]),
        ],
        # "Fio Partido" real enrage timer -- approximated exactly like
        # Viúva de Gelo's ventania_final: a real self-stacking buff
        # every one of her own turns, not a literal per-turn timer.
        # Re-applying every turn regardless of phase is harmless: the
        # status is only ever visible once she's already in Fio Partido
        # (her last phase), since nothing removes prior stacks on a
        # phase change either way.
        triggered_effects=[
            TriggeredEffect(
                trigger=TriggerEvent.ON_TURN_START,
                effect=Effect(kind=EffectKind.APPLY_STATUS, status_id="fio_partido", duration=2, stacks=1),
                applies_to="self",
                source="tecela_desfeita_enrage",
            ),
        ],
        currency_reward=25,
        vigor_reward=220,
    ),
}
