"""Generic Eventos usable in any Área (docs/design/14-estrutura-da-run.md
§5). Alinhamento numbers follow docs/design/05-classes.md §4's own
example (poupar +15 / executar -15 / ignorar 0); everything else is a
first-guess balance number like the rest of the content layer."""

from wyrdfall.domain.events import EventDef, EventOptionDef

EVENT_DEFS: dict[str, EventDef] = {
    "prisioneiro_rendido": EventDef(
        id="prisioneiro_rendido",
        name="O Prisioneiro Rendido",
        text=(
            "Um saqueador ferido larga a arma e ergue as mãos. Ele jura que só estava "
            "seguindo ordens, e que sabe onde os outros esconderam o que roubaram."
        ),
        options=[
            EventOptionDef(
                id="poupar", label="Poupar e deixá-lo ir",
                outcome_text="Ele some pelo corredor sem olhar pra trás. Alguma coisa em você fica mais leve.",
                alignment_shift=15.0,
            ),
            EventOptionDef(
                id="executar", label="Executá-lo e revistar o corpo",
                outcome_text="Rápido e silencioso. Havia Fragmentos costurados no forro do casaco.",
                alignment_shift=-15.0, currency_delta=8, wyrd_risk=5.0,
            ),
            EventOptionDef(
                id="ignorar", label="Ignorar e seguir em frente",
                outcome_text="Você passa direto. O que ele faz da vida dele não é problema seu.",
            ),
        ],
    ),
    "altar_esquecido": EventDef(
        id="altar_esquecido",
        name="Altar Esquecido",
        text="Um altar rachado, a um deus que ninguém mais nomeia. Ainda há oferendas -- e ainda há calor nele.",
        options=[
            EventOptionDef(
                id="rezar", label="Rezar",
                outcome_text="O calor sobe pelas mãos. Feridas fecham um pouco.",
                alignment_shift=10.0, heal_fraction=0.25,
            ),
            EventOptionDef(
                id="profanar", label="Levar as oferendas",
                outcome_text="Ninguém aparece pra impedir. As oferendas valem Fragmentos.",
                alignment_shift=-10.0, currency_delta=10,
            ),
            EventOptionDef(
                id="seguir", label="Seguir sem tocar em nada",
                outcome_text="Você deixa o altar como o encontrou.",
            ),
        ],
    ),
    "ferido_no_caminho": EventDef(
        id="ferido_no_caminho",
        name="Ferido no Caminho",
        text="Um explorador de outra expedição, caído, com a perna presa sob uma pedra. A bolsa dele está ao alcance.",
        options=[
            EventOptionDef(
                id="ajudar", label="Tirar a pedra e ajudá-lo",
                outcome_text="Custa esforço e um pouco de sangue, mas ele consegue ficar de pé.",
                alignment_shift=15.0, damage_fraction=0.05, wyrd_risk=5.0,
            ),
            EventOptionDef(
                id="roubar", label="Levar a bolsa e deixá-lo ali",
                outcome_text="Ele grita alguma coisa que você escolhe não ouvir.",
                alignment_shift=-15.0, currency_delta=12,
            ),
            EventOptionDef(
                id="ignorar", label="Passar por ele",
                outcome_text="Não é o seu explorador. Não é a sua pedra.",
            ),
        ],
    ),
    "cofre_selado": EventDef(
        id="cofre_selado",
        name="Cofre Selado",
        text="Um cofre de ferro, trancado com uma runa que ainda pulsa. Forçá-lo vai doer.",
        options=[
            EventOptionDef(
                id="forcar", label="Forçar a runa",
                outcome_text="A runa estoura nas suas mãos -- mas o cofre abre, e estava cheio.",
                damage_fraction=0.20, currency_delta=20, wyrd_risk=10.0,
            ),
            EventOptionDef(
                id="deixar", label="Deixar o cofre",
                outcome_text="Algumas coisas não valem a queimadura.",
            ),
        ],
    ),
    "fonte_estranha": EventDef(
        id="fonte_estranha",
        name="Fonte Estranha",
        text="Água brota de uma rachadura, clara demais pra este lugar. Tem um gosto que você não reconhece.",
        options=[
            EventOptionDef(
                id="beber", label="Beber",
                outcome_text="Fria, doce, e as feridas param de latejar.",
                heal_fraction=0.30,
            ),
            EventOptionDef(
                id="seguir", label="Não arriscar",
                outcome_text="Água que brilha assim raramente é só água.",
            ),
        ],
    ),
    "mercador_perdido": EventDef(
        id="mercador_perdido",
        name="Mercador Perdido",
        text="Um mercador que claramente não deveria estar aqui oferece \"um segredo de ofício\" por um punhado de Fragmentos.",
        options=[
            EventOptionDef(
                id="pagar", label="Pagar 10 Fragmentos",
                outcome_text="O segredo é real. Você entende um pouco melhor o próprio caminho.",
                currency_delta=-10, talent_points=1,
            ),
            EventOptionDef(
                id="recusar", label="Recusar",
                outcome_text="Ele dá de ombros e desaparece na próxima curva.",
            ),
        ],
    ),
    "ecos_do_wyrd": EventDef(
        id="ecos_do_wyrd",
        name="Ecos do Wyrd",
        text="Por um instante, o ar vibra com fios que você quase consegue ver. Ficar aqui e escutar cansa o corpo.",
        options=[
            EventOptionDef(
                id="meditar", label="Meditar sobre os fios",
                outcome_text="O corpo paga o preço, mas a mente sai mais afiada.",
                damage_fraction=0.10, talent_points=1, wyrd_risk=10.0,
            ),
            EventOptionDef(
                id="seguir", label="Seguir em frente",
                outcome_text="Os fios se apagam atrás de você.",
            ),
        ],
    ),
    "reliquia_esquecida": EventDef(
        id="reliquia_esquecida",
        name="Relíquia Esquecida",
        text="Um amuleto gasto, deixado num nicho como se alguém fosse voltar pra buscá-lo. Ninguém voltou.",
        options=[
            EventOptionDef(
                id="pegar", label="Pegar o amuleto",
                outcome_text="Pesa pouco no pescoço, e um pouco menos nos ombros.",
                card_id="amuleto_do_viajante",
            ),
            EventOptionDef(
                id="deixar", label="Deixar onde está",
                outcome_text="Talvez alguém ainda volte.",
            ),
        ],
    ),
    "sombra_de_um_aliado": EventDef(
        id="sombra_de_um_aliado",
        name="Sombra de um Aliado",
        text="Uma sombra com a voz de alguém que você perdeu. Ela pede perdão -- ou pede que você termine o que ela começou.",
        options=[
            EventOptionDef(
                id="perdoar", label="Perdoar",
                outcome_text="A sombra se desfaz em silêncio. Você respira fundo.",
                alignment_shift=10.0,
            ),
            EventOptionDef(
                id="vingar", label="Jurar vingança",
                outcome_text="A sombra sorri. Você sente o peso da promessa.",
                alignment_shift=-10.0,
            ),
        ],
    ),
    # -- Bênçãos (06-economia-progressao.md "Passivas de Run"): altars ------------
    "altar_do_wyrd": EventDef(
        id="altar_do_wyrd",
        name="Altar do Wyrd",
        text="Um altar de pedra lisa, morno ao toque, com fios de luz correndo por dentro como veias.",
        options=[
            EventOptionDef(
                id="rezar", label="Rezar",
                outcome_text="O calor sobe pelo braço e fica. Uma bênção do Wyrd acompanha o grupo.",
                blessing=True,
            ),
            EventOptionDef(
                id="oferenda", label="Deixar uma oferenda (10 Fragmentos)",
                outcome_text="O altar aceita. A luz nos fios pulsa mais forte, e o grupo sente o mesmo.",
                currency_delta=-10, blessing=True, heal_fraction=0.10,
            ),
            EventOptionDef(
                id="seguir", label="Seguir sem tocar",
                outcome_text="Melhor não dever nada a ninguém.",
            ),
        ],
    ),
    "fonte_silenciosa": EventDef(
        id="fonte_silenciosa",
        name="Fonte Silenciosa",
        text="Uma fonte que não faz som algum, mesmo com a água caindo. Beber dela é uma questão de confiança.",
        options=[
            EventOptionDef(
                id="beber", label="Beber",
                outcome_text="A água desce fria e o silêncio vem junto -- e com ele, algo a mais.",
                blessing=True, wyrd_risk=5.0,
            ),
            EventOptionDef(
                id="encher", label="Só encher o cantil",
                outcome_text="Cura leve, sem surpresas.",
                heal_fraction=0.15,
            ),
        ],
    ),
    # -- Fada's unlock (04-racas.md): "Evento raro: encontre e interaja com
    # um Portal Feérico numa run" -- one entry in the pool, drawn like any
    # other Evento from the node's seed.
    "portal_feerico": EventDef(
        id="portal_feerico",
        name="Portal Feérico",
        text="Um anel de cogumelos brancos, e dentro dele o ar dobra como vidro quente. Do outro lado, risadas.",
        options=[
            EventOptionDef(
                id="atravessar", label="Atravessar o anel",
                outcome_text="Por um instante você é pequeno, leve e feito de luz. Quando volta, algo ficou -- a Guilda vai se lembrar.",
                unlocks_race="fada", wyrd_risk=10.0,
            ),
            EventOptionDef(
                id="observar", label="Só observar",
                outcome_text="As risadas somem. O anel continua lá, esperando alguém mais ousado.",
            ),
        ],
    ),
}
