# Wyrdfall

Wyrdfall é um RPG roguelike de fantasia sombria para o terminal, com combate por turnos. Você atravessa portais e explora ruínas cheias de monstros, eventos e chefes. A ideia é montar um personagem diferente a cada expedição, combinando talentos, cartas, runas e equipamentos conforme o que encontrar pelo caminho.

Uma derrota encerra a expedição. O progresso acumulado rende Ecos para desbloquear opções na Guilda e experimentar novas estratégias nas próximas partidas. Dá para jogar solo ou em grupo pela rede.

O jogo ainda está em desenvolvimento.

## Jogar no Windows

1. Baixe o arquivo `wyrdfall.exe` na seção **Assets** da versão mais recente em [Releases](https://github.com/YanGDBr/Wyrdfall/releases).
2. Abra o executável com dois cliques. O jogo roda em uma janela de terminal e dispensa a instalação do Python.
3. No menu inicial, selecione **Tutorial** para conhecer os controles ou **Nova Run (Solo)** para começar.

## Jogar a partir do código

Tenha o Git e o Python 3.11 ou superior instalados. No terminal, clone o repositório e crie um ambiente virtual:

```sh
git clone https://github.com/YanGDBr/Wyrdfall.git
cd Wyrdfall
python -m venv .venv
```

No PowerShell do Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m wyrdfall
```

No Linux ou macOS (use `python3` para criar o ambiente, se esse for o comando da sua instalação):

```sh
.venv/bin/python -m pip install -e .
.venv/bin/python -m wyrdfall
```

Para gerar e abrir o executável localmente no Windows, na raiz do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\build.ps1
.\dist\wyrdfall.exe
```

## Jogar em cooperativo

1. Na mesma rede local ou no mesmo ambiente Tailscale, um jogador seleciona **Hospedar Jogo (LAN / Tailscale)** e compartilha o endereço e a porta da sala.
2. Os demais selecionam **Entrar em Jogo** e informam o endereço no formato `host:porta`. Todos devem usar a mesma versão do jogo.
3. Depois que o anfitrião iniciar a expedição, cada jogador controla seu próprio herói. Quando a partida pedir confirmação para avançar, todos devem marcar **Estou pronto**.
