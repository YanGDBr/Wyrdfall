"""Tutorial: a paged walkthrough of every system a new player meets, in
the order they meet it. Pure text (no live state), so it opens from the
main menu at any time; MetaProgressionState.tutorial_seen only decides
whether the menu keeps nudging toward it."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.ui.widgets import ButtonRow, Columns, TitleBar, Panel, Rows

PAGES: list[tuple[str, str]] = [
    (
        "Bem-vindo a Wyrdfall",
        "Wyrdfall é um roguelike de construção de builds, por turnos, no terminal.\n\n"
        "• Uma RUN percorre as Áreas do portal escolhido até o chefe final. Morrer encerra a run "
        "(permadeath), mas você volta à GUILDA com Ecos para gastar em progresso permanente.\n"
        "• ABANDONAR também conta como derrota: registra a run e concede Ecos pelo progresso já acumulado.\n"
        "• Tudo é feito de duas peças: modificadores de atributo e efeitos gatilhados "
        "(\"quando X, faça Y\"). Talentos, raças, runas, cartas, itens e bênçãos são a mesma coisa "
        "vista de lugares diferentes -- por isso tudo combina com tudo.\n"
        "• Dá para jogar sozinho ou em co-op por LAN/Tailscale (cada jogador controla o próprio herói).\n\n"
        "Use Próximo/Anterior para navegar. Este tutorial fica sempre disponível no menu principal.",
    ),
    (
        "1. Criar o personagem",
        "Antes da run, na GUILDA: escolha sua RAÇA (Humano no começo; as outras se desbloqueiam jogando) "
        "e o que levar (Pactos, Companheiro, equipamento de partida).\n\n"
        "Em Nova Run:\n"
        "• ARQUÉTIPO BASE -- Guerreiro (Guardião das Runas), Patrulheiro, Místico ou Guardião. "
        "É só o ponto de partida: sua Especialização vem do que você USA na run, não do que escolheu aqui.\n"
        "• SELAMENTOS (opcional) -- sele arquétipos ou elementos que você NUNCA vai usar. Eles somem das "
        "ofertas e tudo o que sobra ganha um bônus de dano. É uma aposta: menos opções, mais força.\n"
        "• PORTAL DE ENTRADA -- decide o caminho inteiro, com Áreas em ordem fixa. Quatro portais "
        "começam abertos.",
    ),
    (
        "2. Combate",
        "Turnos por ordem de Velocidade. No seu turno, a barra de ações mostra o que dá para fazer -- "
        "clique ou aperte 1-9 (remapeável na Guilda).\n\n"
        "• DEFENDER está sempre disponível: dobra a Defesa até o próximo turno.\n"
        "• POSTURA: golpes pesados desgastam a postura do alvo; quando ela quebra, ele fica Atordoado "
        "um turno. Chefes trocam de fase quando a postura quebra ou o PV cai.\n"
        "• APARAR (Parry): ao comprar a passiva na Guilda, ataques corpo a corpo contra você abrem uma "
        "janela -- aperte Espaço no momento certo para negar o golpe. Errar dói mais; recusar é sempre seguro.\n"
        "• MINIGAMES: algumas habilidades fortes pedem um minigame (janela de tempo, sequência de setas, "
        "canalização, precisão). Errar reduz o efeito, nunca zera.\n"
        "• POÇÕES podem ser bebidas em combate -- gastam o turno.\n"
        "• Elementos: cada inimigo resiste ou é fraco a alguns. Fogo↔Água, Terra↔Ar e Raio↔Gelo reagem entre si.",
    ),
    (
        "3. Recursos e habilidades",
        "Cada arquétipo paga suas habilidades de um jeito:\n"
        "• MANA (Místico) -- regenera por turno.\n"
        "• FÚRIA (Guerreiro) -- ganha ao SOFRER dano; decai se você ficar parado.\n"
        "• ADRENALINA (Guardião) -- cresce a cada turno em combate.\n"
        "• PONTOS DE COMBO (Patrulheiro) -- construtores acumulam, finalizadores gastam tudo.\n"
        "Algumas habilidades pagam com PV, têm tempo de recarga ou cargas por descanso.\n\n"
        "SLOTS DE HABILIDADE ATIVA: você conhece mais habilidades do que pode levar para o combate. "
        "Escolha quais equipar na tela de Equipamento; novos slots vêm com nível.\n\n"
        "COMBOS: lançar certas habilidades em sequência dá bônus. Em co-op, um aliado pode MARCAR um "
        "alvo e outro aliado explode a marca.",
    ),
    (
        "4. Progredir dentro da run",
        "Vencer combates dá Vigor (níveis), pontos de TALENTO e de ATRIBUTO, Fragmentos (a moeda da run) "
        "e uma escolha de 1 entre 3 CARTAS.\n\n"
        "• ATRIBUTOS: 6 (Força, Destreza, Constituição, Inteligência, Sabedoria, Sorte), cada um escalando "
        "3 stats. Sorte também melhora procs e drops.\n"
        "• AFINIDADE POR USO: o jogo mede quais arquétipos e elementos você realmente usa. "
        "No nível 5 ele oferece as ESPECIALIZAÇÕES que sua afinidade justifica (47 no total, incluindo "
        "híbridas e as assinaturas de cada raça); no nível 10, o ESTÁGIO 2. Evoluir abre um ramo novo "
        "na sua árvore sem perder nada.\n"
        "• Usar habilidades de outro estilo muda sua tendência: golpes de espada num Místico o aproximam de Guerreiro. É de propósito.\n"
        "• A cura completa só acontece ao trocar de Área (depois do chefe). Entre combates: Sala de "
        "Descanso, poções, subir de nível e Bênçãos.",
    ),
    (
        "5. Equipamento e build",
        "Tela de EQUIPAMENTO (no mapa):\n"
        "• ARMA -- cada jogador começa com peças de treino de todos os tipos. O tipo escala com atributos e libera habilidades; versões encontradas têm bônus próprios.\n"
        "• RUNAS -- caem de inimigos. Runas corporais afetam você inteiro; runas de habilidade só aquela "
        "habilidade. Duas runas iguais viram uma \"II\" na Forja de Campo.\n"
        "• ARMADURA (cabeça/corpo/pernas) e ACESSÓRIOS -- só o que caiu na run. Peças do mesmo conjunto "
        "dão bônus; itens têm slots de ENCANTAMENTO (1/2/3 por raridade). Cada cópia é independente.\n"
        "• ENCANTAMENTOS -- os drops já trazem um. Na Forja, gravar um efeito ou rerolar um slot custa 10 Fragmentos e 1 material da raridade da peça. Selamentos também valem para os efeitos dos itens.\n"
        "• BOLSA E TROCAS -- veja quem possui cada peça. Entregar a um aliado remove a peça de você e preserva seus encantamentos; ele decide quando equipar. Confira a comparação de atributos e conjuntos antes de trocar.\n"
        "• TOMOS -- consumíveis que ensinam uma habilidade de outro arquétipo.\n\n"
        "Nada trava nada: qualquer classe usa qualquer arma, runa ou item. O limite é o orçamento de "
        "slots -- e os Selamentos que você mesmo escolheu.",
    ),
    (
        "6. A estrutura da run",
        "Cada Área tem uma sequência fixa de salas:\n"
        "• COMBATE (solitário ou grupo), ELITE (um inimigo com mecânica própria) e CHEFE (várias fases).\n"
        "• EVENTO -- escolhas com risco/recompensa; nunca mata, nunca força um combate.\n"
        "• SALA ESPECIAL -- vira Descanso (Acampar cura / Meditar dá talento), Vendedor ou Forja de Campo.\n"
        "• O TERRENO da Área afeta todo mundo em combate (ex.: gelo escorregadio).\n\n"
        "Ainda na run:\n"
        "• CONTRATOS -- aceite desafios no início da run por Ecos extras.\n"
        "• BÊNÇÃOS -- recompensas de elite/altar que duram a run.\n"
        "• MEDIDOR DO WYRD -- risco acumulado (Pactos de Risco, Abraçar a Morte): mais perigo, mais Ecos.\n"
        "• EVOLUÇÃO DE RAÇA -- cada raça tem um gatilho na run (primeiro chefe, X críticos, cair abaixo "
        "de 30% PV...) que libera um bônus até o fim dela.",
    ),
    (
        "7. A Guilda (entre runs)",
        "Ecos são a moeda permanente. Na Guilda você:\n"
        "• Aloca ÁRVORES PERMANENTES da sua raça e do seu arquétipo.\n"
        "• Escolhe a RAÇA ativa -- cada uma se desbloqueia de um jeito (vencer um chefe sem cura, sem "
        "sofrer dano elemental, morrer muitas vezes, achar o Portal Feérico, construir no Ferreiro...). "
        "Meio-celestial é a raça de prestígio: exige evoluir duas outras e custa caro.\n"
        "• Equipa PACTOS DO WYRD (Vantagem = ajuda; Risco = mais perigo, mais recompensa).\n"
        "• Compra o PARRY, pontos de talento iniciais, um COMPANHEIRO, e sobe a ASCENSÃO após vencer.\n"
        "• No FERREIRO, gasta materiais de crafting em equipamento/runas de partida.\n"
        "• Cumpre MISSÕES DA GUILDA e CONQUISTAS (Ecos e desbloqueios).\n"
        "• Consulta o BESTIÁRIO e ajusta acessibilidade: velocidade de combate, paleta, TECLAS.",
    ),
    (
        "8. Co-op e últimas dicas",
        "CO-OP: um jogador Hospeda (compartilha IP:porta), o outro Entra. Cada um escolhe o próprio "
        "personagem no lobby; Pactos e Portal são do host. Inimigos escalam com o tamanho do grupo.\n"
        "• O HOST confirma encontros, eventos, descanso, contratos e avanço. Cada jogador gerencia "
        "sua build e pode comprar itens com os Fragmentos compartilhados.\n"
        "• Cair a 0 PV em grupo deixa você INCAPACITADO: sai da ordem de turno, mas se o grupo vencer "
        "você volta com 10% do PV. Se o grupo perder, a run acaba para todos.\n"
        "• Habilidades de reviver existem, mas são raras.\n\n"
        "DICAS:\n"
        "• Chefes são consideravelmente difíceis: chegue com PV, poções e uma build coerente.\n"
        "• Leia a descrição das cartas e talentos -- combinações inesperadas são o jogo.\n"
        "• Não tem resposta certa: sele, arrisque, misture arquétipos. Cada run é um experimento.\n\n"
        "Boa descida.",
    ),
]


class TutorialScreen(Screen):
    CSS = """
    TutorialScreen #toc { width: 34; height: 100%; }
    TutorialScreen #page { width: 1fr; height: 100%; }
    TutorialScreen #tutorial-body { height: 1fr; }
    """

    def __init__(self, page: int = 0) -> None:
        super().__init__()
        self._page = max(0, min(page, len(PAGES) - 1))

    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            yield TitleBar("Tutorial")
            with Columns(classes="body fill"):
                with Panel("Capítulos", id="toc"):
                    with Rows(id="toc-rows"):
                        for index, (title, _body) in enumerate(PAGES):
                            yield Button(title, id=f"page_{index}", classes="compact")
                with Panel("", id="page", variant="accent"):
                    yield Static("", id="tutorial-title", classes="big")
                    yield Static("", id="tutorial-progress", classes="muted")
                    yield VerticalScroll(Static("", id="tutorial-body"), id="tutorial-scroll")
                    with ButtonRow(id="tutorial-nav"):
                        yield Button("Anterior", id="prev")
                        yield Button("Próximo", id="next", variant="primary")
                        yield Button("Fechar", id="close")
        yield Footer()

    def on_mount(self) -> None:
        self._render_page()

    def _render_page(self) -> None:
        title, body = PAGES[self._page]
        self.query_one("#page", Panel).border_title = title
        self.query_one("#tutorial-title", Static).update(title)
        self.query_one("#tutorial-progress", Static).update(f"página {self._page + 1} de {len(PAGES)}")
        self.query_one("#tutorial-body", Static).update(body)
        self.query_one("#tutorial-scroll", VerticalScroll).scroll_home(animate=False)
        self.query_one("#prev", Button).disabled = self._page == 0
        self.query_one("#next", Button).label = "Próximo" if self._page < len(PAGES) - 1 else "Concluir"
        for index in range(len(PAGES)):
            self.query_one(f"#page_{index}", Button).variant = "primary" if index == self._page else "default"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("page_"):
            self._page = int(button_id.removeprefix("page_"))
            self._render_page()
        elif button_id == "prev" and self._page > 0:
            self._page -= 1
            self._render_page()
        elif button_id == "next":
            if self._page < len(PAGES) - 1:
                self._page += 1
                self._render_page()
            else:
                self._finish()
        elif button_id == "close":
            self._finish()

    def _finish(self) -> None:
        meta = getattr(self.app, "meta", None)
        if meta is not None and not meta.tutorial_seen:
            meta.tutorial_seen = True
            self.app.save_progress()
        self.app.pop_screen()
