from __future__ import annotations

import websockets.exceptions

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Static

from wyrdfall.domain.content import CLASS_DEFS, PORTAL_DEFS, build_dungeon_for_portal
from wyrdfall.domain.loadout import PlayerLoadout
from wyrdfall.domain.races import RACE_DEFS
from wyrdfall.net.client import NetworkConnection
from wyrdfall.net.discovery import get_local_ip
from wyrdfall.net.host_client import HostGameClient
from wyrdfall.net.protocol import (
    ClientHello,
    ServerLobbyUpdate,
    ServerStateUpdate,
    ServerWelcome,
    ServerError,
)
from wyrdfall.net.remote_client import RemoteGameClient
from wyrdfall.net.server import HostServer
from wyrdfall.ui.screens.archetype_select import ArchetypeSelectScreen, CharacterPick


def describe_loadout(class_id: str, race_id: str, sealed_count: int = 0) -> str:
    class_name = CLASS_DEFS[class_id].name if class_id in CLASS_DEFS else class_id
    race_name = RACE_DEFS[race_id].name if race_id in RACE_DEFS else race_id
    seals = f", {sealed_count} selamento{'s' if sealed_count != 1 else ''}" if sealed_count else ""
    return f"{class_name} / {race_name}{seals}"


class _CharacterPickMixin:
    """Shared by both lobby screens: a "Personagem" line + button that
    opens ArchetypeSelectScreen in pick mode (docs/design/14-estrutura-
    da-run.md §1 -- each player chooses their own Raça + Arquétipo Base +
    Selamentos; Raça comes from this player's own Guild)."""

    def _init_pick(self) -> None:
        self._pick: CharacterPick = ("runeguard", set(), set())

    def loadout(self) -> PlayerLoadout:
        class_id, sealed, sealed_elements = self._pick
        return self.app.build_loadout(class_id, sealed, sealed_elements)

    def _refresh_pick_status(self) -> None:
        class_id, sealed, sealed_elements = self._pick
        self.query_one("#character-status", Static).update(
            f"Seu personagem: {describe_loadout(class_id, self.app.meta.active_race_id, len(sealed) + len(sealed_elements))}"
        )

    def _open_character_pick(self) -> None:
        def _store(result: CharacterPick | None) -> None:
            if result is not None:
                self._pick = result
                self._refresh_pick_status()

        self.app.push_screen(ArchetypeSelectScreen(pick_only=True), _store)


class HostSetupScreen(_CharacterPickMixin, Screen):
    CSS = "HostSetupScreen #portal-rows { height: auto; }"
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="dungeon-panel"):
            yield Static("Hospedar um Jogo", classes="title")
            yield Static(
                "Inicia um servidor nesta máquina. Compartilhe seu IP de LAN ou Tailscale e "
                "a porta mostrada abaixo com os amigos que devem entrar -- pegue seu IP do "
                "Tailscale com `tailscale ip` se estiver jogando via Tailscale.",
                classes="subtitle",
            )
            yield Input(placeholder="Seu nome", id="name_input", value="Herói")
            # Personagem is per player (docs/design/09-roadmap.md Fase 5a):
            # this is the host's own; each joiner brings theirs in ClientHello.
            yield Static("", id="character-status")
            yield Button("Escolher personagem (arquétipo, selamentos)...", id="pick_character")
            # Portal de Entrada is lobby-wide -- chosen once by the host
            # before the server starts (docs/design/14-estrutura-da-run.md §1).
            yield Static("Portal de Entrada do grupo: Portão do Túmulo", id="portal-status")
            with Vertical(id="portal-rows"):
                for portal in PORTAL_DEFS.values():
                    if portal.id in self.app.meta.unlocked_portals:
                        yield Button(portal.name, id=f"portal_{portal.id}")
                    else:
                        yield Static(f"{portal.name} — bloqueado na Guilda")
            yield Static("", id="host-status")
            yield Button("Iniciar Servidor", id="start_server", variant="primary")
            yield Button("Iniciar Run", id="start_run", disabled=True)
            yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.server: HostServer | None = None
        self.portal_id = "portao_do_tumulo"
        self._init_pick()
        self._refresh_pick_status()

    async def on_unmount(self) -> None:
        if self.server is not None:
            self.server.off_lobby_update(self.refresh_lobby)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            if self.server is not None:
                await self.app.leave_multiplayer()
            self.app.pop_screen()
        elif button_id == "start_server":
            await self.start_server()
        elif button_id == "start_run":
            await self.start_run()
        elif button_id == "pick_character":
            self._open_character_pick()
        elif button_id.startswith("portal_"):
            self.portal_id = button_id.removeprefix("portal_")
            if self.server is not None and self.server.session is None:
                self.server.dungeon = build_dungeon_for_portal(self.portal_id)
            self.query_one("#portal-status", Static).update(
                f"Portal de Entrada do grupo: {PORTAL_DEFS[self.portal_id].name}"
            )

    async def start_server(self) -> None:
        name = self.query_one("#name_input", Input).value.strip() or "Herói"
        self.app.player_name = name
        status = self.query_one("#host-status", Static)

        dungeon = build_dungeon_for_portal(self.portal_id)
        self.server = HostServer(
            self.app.ruleset, host_player_id="host", host_player_name=name, dungeon=dungeon, host_loadout=self.loadout(),
            pacts=list(self.app.meta.equipped_pacts), ascension_level=self.app.meta.ascension_level,
            companion_id=self.app.meta.active_companion_id,
            starting_gear=list(self.app.meta.starting_gear),
            starting_runes=list(self.app.meta.starting_runes),
        )
        self.app.host_server = self.server
        self.server.on_lobby_update(self.refresh_lobby)
        port = await self.server.start(port=0)

        local_ip = get_local_ip()
        status.update(f"Ouvindo em {local_ip}:{port} (LAN) -- compartilhe este endereço e porta.\nJogadores: {name} (você)")

        self.query_one("#start_server", Button).disabled = True
        self.query_one("#name_input", Input).disabled = True
        self.query_one("#start_run", Button).disabled = False
        self.query_one("#pick_character", Button).disabled = True

    def refresh_lobby(self) -> None:
        if self.server is None:
            return
        names = ", ".join(
            f"{p.name}{' (você)' if p.player_id == 'host' else ''} [{describe_loadout(p.class_id, p.race_id)}]"
            for p in self.server.lobby_players()
        )
        status = self.query_one("#host-status", Static)
        local_ip = get_local_ip()
        status.update(f"Ouvindo em {local_ip}:{self.server.port} (LAN) -- compartilhe este endereço e porta.\nJogadores: {names}")

    async def start_run(self) -> None:
        from wyrdfall.ui.screens.dungeon import DungeonScreen

        assert self.server is not None
        self.server.checkpoint_callback = self.app.save_host_checkpoint
        await self.server.start_run()
        self.app.client = HostGameClient(self.server)
        self.app.push_screen(DungeonScreen())


class JoinSetupScreen(_CharacterPickMixin, Screen):
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="dungeon-panel"):
            yield Static("Entrar em um Jogo", classes="title")
            yield Static(
                "Digite o endereço do host (IP de LAN ou Tailscale) e a porta que ele "
                "compartilhou, ex.: 192.168.1.5:8765 ou 100.64.1.2:8765",
                classes="subtitle",
            )
            yield Input(placeholder="Seu nome", id="name_input", value="Herói")
            yield Static("", id="character-status")
            yield Button("Escolher personagem (arquétipo, selamentos)...", id="pick_character")
            yield Input(placeholder="host:porta", id="address_input")
            yield Static("", id="join-status")
            yield Button("Conectar", id="connect", variant="primary")
            yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.connection: NetworkConnection | None = None
        self._welcome: ServerWelcome | None = None
        self._entered = False
        self._connection_error = None
        self._init_pick()
        self._refresh_pick_status()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            if self.connection is not None and not self._entered:
                await self.connection.close()
                self.connection = None
            self.app.pop_screen()
        elif event.button.id == "pick_character":
            self._open_character_pick()
        elif event.button.id == "connect":
            await self.attempt_connect()

    async def attempt_connect(self) -> None:
        name = self.query_one("#name_input", Input).value.strip() or "Herói"
        address = self.query_one("#address_input", Input).value.strip()
        status = self.query_one("#join-status", Static)
        if not address or ":" not in address:
            status.update("Digite o endereço do host incluindo a porta, ex.: 192.168.1.5:8765")
            return

        host, _, port = address.rpartition(":")
        if not port.isdigit() or not 1 <= int(port) <= 65535 or not host:
            status.update("Digite um endereço com porta válida (1 a 65535).")
            return
        uri = f"ws://{host}:{port}"
        status.update(f"Conectando a {uri}...")
        self.query_one("#connect", Button).disabled = True
        self.query_one("#pick_character", Button).disabled = True

        connection = NetworkConnection(uri)
        self._welcome = None
        self._connection_error = None
        connection.on_message(self._handle_message)
        connection.on_disconnect(lambda: self.call_later(self._connection_closed, connection))
        self.connection = connection
        self.app.net_connection = connection
        try:
            await connection.connect()
            await connection.send(ClientHello(player_name=name, loadout=self.loadout()))
        except (OSError, ValueError, websockets.exceptions.WebSocketException) as exc:
            await connection.close()
            self.connection = None
            self.app.net_connection = None
            status.update(f"Não foi possível conectar: {exc}")
            self.query_one("#connect", Button).disabled = False
            self.query_one("#pick_character", Button).disabled = False
            return

        self.connection = connection
        self.app.net_connection = connection
        self.app.player_name = name
        status.update("Conectado. Aguardando o host iniciar a run...")

    def _handle_message(self, message) -> None:
        if self._entered:
            return
        if isinstance(message, ServerWelcome):
            self._welcome = message
        elif isinstance(message, ServerError):
            self._connection_error = message.message
            self.query_one("#join-status", Static).update(message.message)
            self.query_one("#connect", Button).disabled = False
            self.query_one("#pick_character", Button).disabled = False
        elif isinstance(message, ServerLobbyUpdate):
            names = ", ".join(f"{p.name} [{describe_loadout(p.class_id, p.race_id)}]" for p in message.players)
            self.query_one("#join-status", Static).update(f"No lobby com: {names}\nAguardando o host iniciar...")
        elif isinstance(message, ServerStateUpdate) and self._welcome is not None:
            self._enter_run(message)

    def _connection_closed(self, connection) -> None:
        if self._entered or self.connection is not connection or not self.is_mounted:
            return
        self.connection = None
        if self.app.net_connection is connection:
            self.app.net_connection = None
        self.query_one("#join-status", Static).update(self._connection_error or "Conexão encerrada pelo host. Tente novamente.")
        self.query_one("#connect", Button).disabled = False
        self.query_one("#pick_character", Button).disabled = False

    def _enter_run(self, initial_state: ServerStateUpdate) -> None:
        from wyrdfall.ui.screens.dungeon import DungeonScreen

        assert self.connection is not None and self._welcome is not None
        self._entered = True
        self.connection.off_message(self._handle_message)
        client = RemoteGameClient(self.connection, self.app.ruleset, self._welcome.player_id, initial_state)
        client.on_error(self.app.report_run_error)
        self.app.client = client
        self.app.attach_autosave()
        self.app.push_screen(DungeonScreen())
