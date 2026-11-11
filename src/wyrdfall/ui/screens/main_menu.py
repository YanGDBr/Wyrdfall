from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from wyrdfall.domain.content import CLASS_DEFS
from wyrdfall.domain.races import RACE_DEFS
from wyrdfall.ui.widgets import Columns, KeyValue, Panel

_LOGO = """[bold $accent]
 __      __                 _  __      _ _
 \\ \\    / /_  _ _ _ __| |/ _|__ _| | |
  \\ \\/\\/ / || | '_/ _` |  _/ _` | | |
   \\_/\\_/ \\_, |_| \\__,_|_| \\__,_|_|_|
          |__/[/bold $accent]"""


class MainMenuScreen(Screen):
    def compose(self) -> ComposeResult:
        with Vertical(classes="frame"):
            with Center():
                yield Static(_LOGO, id="logo")
            yield Static("Um roguelike de construção de builds, feito de runas e ruínas.", classes="subtitle center")
            yield Static("", id="first-time-hint", classes="subtitle center")
            with Columns(id="menu-columns"):
                with Panel("Jogar", variant="accent", id="menu-panel"):
                    yield Button("Retomar run salva", id="resume_run", variant="success")
                    yield Button("Nova Run (Solo)", id="new_run", variant="primary")
                    yield Button("Hospedar Jogo (LAN / Tailscale)", id="host")
                    yield Button("Entrar em Jogo", id="join")
                    yield Button("Guilda", id="meta")
                    yield Button("Tutorial", id="tutorial")
                    yield Button("Sair", id="quit")
                with Vertical(id="menu-side"):
                    with Panel("Perfil da Guilda", id="profile-panel"):
                        yield KeyValue(id="profile")
                    with Panel("Runs recentes", id="recent-panel"):
                        yield Static("", id="recent-body")
        yield Footer()

    CSS = """
    MainMenuScreen .frame { height: auto; max-width: 110; }
    MainMenuScreen #logo { width: auto; height: auto; }
    MainMenuScreen #menu-columns { height: auto; }
    MainMenuScreen #menu-side { width: 1fr; height: auto; }
    MainMenuScreen #menu-panel Button { margin-bottom: 0; }
    """

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh)

    def on_screen_resume(self) -> None:
        self.call_after_refresh(self._refresh)

    def _refresh(self) -> None:
        if not all(self.query(selector) for selector in ("#resume_run", "#profile", "#recent-body")):
            return
        self.query_one("#resume_run", Button).display = self.app.saved_checkpoint() is not None
        meta = getattr(self.app, "meta", None)
        if meta is None:
            return
        seen = meta.tutorial_seen
        self.query_one("#first-time-hint", Static).update("" if seen else "Primeira vez? Comece pelo Tutorial.")
        self.query_one("#tutorial", Button).label = "Tutorial" if seen else "Tutorial (recomendado na primeira vez)"
        race = RACE_DEFS.get(meta.active_race_id)
        self.query_one("#profile", KeyValue).set_rows([
            ("Ecos", f"[bold cyan]{meta.ecos}[/bold cyan]"),
            ("Raça ativa", race.name if race else meta.active_race_id),
            ("Melhor andar", meta.best_floor_reached),
            ("Vitórias", meta.total_victories),
            ("Raças", f"{len(meta.unlocked_races)}/{len(RACE_DEFS)}"),
        ])
        recent = list(reversed(meta.run_history[-4:]))
        lines = [
            f"{'[green]✓[/green]' if r.victory else '[red]✗[/red]'} {CLASS_DEFS[r.class_id].name if r.class_id in CLASS_DEFS else r.class_id}"
            f" -- andar {r.floor_reached}"
            for r in recent
        ]
        self.query_one("#recent-body", Static).update("\n".join(lines) or "[dim]Nenhuma run ainda.[/dim]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "resume_run":
            from wyrdfall.ui.screens.resume_run import ResumeRunScreen
            self.app.push_screen(ResumeRunScreen())
        elif event.button.id == "tutorial":
            from wyrdfall.ui.screens.tutorial import TutorialScreen

            self.app.push_screen(TutorialScreen())
        elif event.button.id == "new_run":
            from wyrdfall.ui.screens.archetype_select import ArchetypeSelectScreen

            self.app.push_screen(ArchetypeSelectScreen())
        elif event.button.id == "host":
            from wyrdfall.ui.screens.host_join import HostSetupScreen

            self.app.push_screen(HostSetupScreen())
        elif event.button.id == "join":
            from wyrdfall.ui.screens.host_join import JoinSetupScreen

            self.app.push_screen(JoinSetupScreen())
        elif event.button.id == "meta":
            from wyrdfall.ui.screens.meta_progression import MetaProgressionScreen

            self.app.push_screen(MetaProgressionScreen())
        elif event.button.id == "quit":
            self.app.exit()
