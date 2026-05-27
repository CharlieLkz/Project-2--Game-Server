#!/usr/bin/env python3
"""
client.py - Cliente Card-Jitsu (Proyecto Final de Redes)
========================================================
Uso:
    python3 client.py              # usa SERVER_IP definida abajo
    python3 client.py <IP>         # override por línea de comandos
    python3 client.py <IP> <PUERTO>

Cliente single-thread: el protocolo es request-response (el servidor
manda REQUEST_PLAY cuando es tu turno), así que no hace falta lanzar
un hilo aparte para recibir. Cada recv() bloquea hasta tener un mensaje
JSON delimitado por '\n'.
"""

import socket
import json
import sys

# ===========================================================================
#  ⚙️  CONFIGURACIÓN — EDITAR AQUÍ ANTES DE EJECUTAR
# ===========================================================================
SERVER_IP   = "10.66.66.36"     # ← Reemplazá con la IP LAN del servidor
SERVER_PORT = 55555              # ← Mismo puerto que el server.py 
# ===========================================================================

ELEMENT_ES = {'fire': 'Fuego', 'snow': 'Nieve', 'water': 'Agua'}

# ---------------------------------------------------------------------------
# Secuencias ANSI
# ---------------------------------------------------------------------------
class C:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'
    BRIGHT_CYAN = '\033[96m'
    WHITE = '\033[97m'
    CLEAR = '\033[2J\033[H'

ELEMENT_COLOR = {'fire': C.RED, 'snow': C.BRIGHT_CYAN, 'water': C.BLUE}

def clear():
    sys.stdout.write(C.CLEAR)
    sys.stdout.flush()

# ---------------------------------------------------------------------------
# I/O JSON (mismo framing que el server: line-delimited JSON)
# ---------------------------------------------------------------------------
def send_json(sock: socket.socket, payload: dict):
    data = (json.dumps(payload) + '\n').encode('utf-8')
    sock.sendall(data)

def recv_json(sock: socket.socket, buffer: bytes):
    while b'\n' not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            return None, buffer
        buffer += chunk
    line, _, buffer = buffer.partition(b'\n')
    try:
        return json.loads(line.decode('utf-8')), buffer
    except json.JSONDecodeError:
        return {}, buffer

# ---------------------------------------------------------------------------
# Renderizado ASCII
# ---------------------------------------------------------------------------
def render_card(card: dict, idx=None) -> list:
    """Devuelve una lista de 5 strings que forman la carta ASCII."""
    el = card['element']
    val = card['value']
    color = ELEMENT_COLOR[el]
    name = ELEMENT_ES[el]
    label = f"[{idx}]" if idx is not None else "   "
    return [
        f"{color}┌─────────┐{C.RESET}",
        f"{color}│ {label:<7} │{C.RESET}",
        f"{color}│   {val:<2}    │{C.RESET}",
        f"{color}│ {name:<7} │{C.RESET}",
        f"{color}└─────────┘{C.RESET}",
    ]

def render_screen(hand: list, last_log: str, scores: dict,
                  player_id, round_num: int, prompt: str = ""):
    clear()
    print(C.BOLD + C.CYAN + "╔════════════════════════════════════════════════════════════╗" + C.RESET)
    print(C.BOLD + C.CYAN + f"║  CARD-JITSU  ·  Eres P{player_id}" + " " * 36 + "║" + C.RESET)
    print(C.BOLD + C.CYAN + "╚════════════════════════════════════════════════════════════╝" + C.RESET)
    print()
    print(f"  {C.BOLD}Ronda:{C.RESET} {round_num}     "
          f"{C.BOLD}Marcador:{C.RESET}  Tú {C.GREEN}{scores['you']}{C.RESET} - "
          f"{C.RED}{scores['opponent']}{C.RESET} Rival")
    print()
    if last_log:
        print(f"  {C.DIM}» {last_log}{C.RESET}")
        print()

    if hand:
        print(f"  {C.BOLD}Tus cartas:{C.RESET}")
        print()
        rendered = [render_card(c, i + 1) for i, c in enumerate(hand)]
        for line_idx in range(5):
            print("    " + "   ".join(card[line_idx] for card in rendered))
        print()

    print(C.BOLD + C.CYAN + "─" * 62 + C.RESET)
    if prompt:
        print(f"  {prompt}")

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    # Permitir override por línea de comandos, pero por default usa las
    # constantes SERVER_IP / SERVER_PORT definidas al inicio del archivo.
    host = sys.argv[1] if len(sys.argv) > 1 else SERVER_IP
    port = int(sys.argv[2]) if len(sys.argv) > 2 else SERVER_PORT

    clear()
    print(C.BOLD + C.CYAN + "  CARD-JITSU - CLIENTE" + C.RESET)
    print(C.DIM + f"  Conectando a {host}:{port} ..." + C.RESET)
    try:
        name = input("  Nombre del jugador: ").strip() or "Jugador"
    except (EOFError, KeyboardInterrupt):
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
    except (ConnectionRefusedError, OSError) as e:
        print(C.RED + f"  Error de conexión: {e}" + C.RESET)
        return

    buffer = b''
    send_json(sock, {'action': 'JOIN', 'name': name})

    hand = []
    last_log = "Conectado. Esperando inicio de la partida..."
    scores = {'you': 0, 'opponent': 0}
    player_id = '?'
    round_num = 0

    clear()
    print(C.YELLOW + "  Conectado al servidor. Esperando al otro jugador...\n" + C.RESET)

    try:
        while True:
            msg, buffer = recv_json(sock, buffer)
            if msg is None:
                print(C.RED + "\n  Conexión cerrada por el servidor." + C.RESET)
                break

            action = msg.get('action')

            if action == 'WELCOME':
                player_id = msg['player_id']
                last_log = f"Bienvenido. Eres el jugador {player_id}."

            elif action == 'DEAL':
                hand = msg['hand']
                last_log = "Recibiste 3 cartas. ¡Comienza la partida!"

            elif action == 'REQUEST_PLAY':
                round_num = msg['round']
                scores = msg['scores']
                render_screen(hand, last_log, scores, player_id, round_num,
                              prompt=f"{C.BOLD}Elige una carta (1-3):{C.RESET} ")
                choice = None
                while choice not in (1, 2, 3):
                    try:
                        raw = input("  > ").strip()
                        choice = int(raw)
                    except (ValueError, EOFError):
                        continue
                played = hand[choice - 1]
                send_json(sock, {'action': 'PLAY', 'card_id': played['id']})
                last_log = (f"Jugaste {ELEMENT_ES[played['element']]} "
                            f"{played['value']}. Esperando al rival...")
                clear()
                print(C.YELLOW + f"\n  {last_log}\n" + C.RESET)

            elif action == 'WAIT':
                # mensaje informativo (ej. "el rival ya jugó")
                print(C.DIM + f"  {msg.get('message', '')}" + C.RESET)

            elif action == 'ROUND_RESULT':
                yc = msg['your_card']
                oc = msg['opponent_card']
                result = msg['result']
                scores = msg['scores']
                hand = msg['new_hand']
                tag = {
                    'win':  C.GREEN  + "¡GANASTE la ronda!" + C.RESET,
                    'lose': C.RED    + "Perdiste la ronda."  + C.RESET,
                    'tie':  C.YELLOW + "Empate."             + C.RESET,
                }[result]
                last_log = (f"Jugaste {ELEMENT_ES[yc['element']]} {yc['value']}, "
                            f"rival jugó {ELEMENT_ES[oc['element']]} {oc['value']}. {tag}")
                render_screen(hand, last_log, scores, player_id, round_num)

            elif action == 'GAME_OVER':
                fs = msg['final_scores']
                clear()
                print(C.BOLD + C.CYAN + "╔════════════════════════════════════════════════════════════╗" + C.RESET)
                if msg['result'] == 'win':
                    print(C.GREEN + C.BOLD +
                          "║                  ¡VICTORIA! GANASTE LA PARTIDA              ║" + C.RESET)
                else:
                    print(C.RED + C.BOLD +
                          "║                  DERROTA. El rival ganó.                    ║" + C.RESET)
                print(C.BOLD + C.CYAN + "╚════════════════════════════════════════════════════════════╝" + C.RESET)
                print()
                print(f"  {C.BOLD}Marcador final:{C.RESET}  "
                      f"Tú {C.GREEN}{fs['you']}{C.RESET} - "
                      f"{C.RED}{fs['opponent']}{C.RESET} Rival")
                print()
                break

    except KeyboardInterrupt:
        print("\n  Saliendo...")
        try:
            send_json(sock, {'action': 'QUIT'})
        except OSError:
            pass
    finally:
        try:
            sock.close()
        except OSError:
            pass

if __name__ == '__main__':
    main()
