#!/usr/bin/env python3
"""
server.py - Servidor Autoritativo Card-Jitsu (Proyecto Final de Redes)
======================================================================
Topología : 1 Servidor + 2 Clientes (TCP sobre LAN WiFi)
Protocolo : JSON delimitado por '\n' (line-delimited JSON)
Hilos     : accept_loop, player_listener (x2), game_loop, dashboard_loop
Librerías : socket, threading, json, time (todas nativas)

La terminal del servidor NO muestra el juego: muestra un dashboard de
telemetría con endpoints, estados, payloads crudos y contadores Tx/Rx.
"""

import socket
import threading
import json
import time
import random
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
HOST = '0.0.0.0'          # Bind a todas las interfaces para aceptar conexiones LAN
PORT = 55555              # Puerto TCP del servidor
MAX_PLAYERS = 2
ROUNDS_TO_WIN = 3
HAND_SIZE = 5             # Cartas en mano por jugador (5 como el Card-Jitsu real)
ELEMENTS = ['fire', 'snow', 'water']
ELEMENT_ES = {'fire': 'Fuego', 'snow': 'Nieve', 'water': 'Agua'}
TICK_RATE = 0.25          # Refresh del dashboard (segundos)
DECK_JSON_PATH = 'deck.json'   # Mazo generado por scrape_assets.py

# Colores permitidos para el pingüino (debe matchear lo del cliente GUI)
PENGUIN_COLORS = ['red', 'blue', 'green', 'yellow', 'pink', 'purple', 'black', 'orange']

# ---------------------------------------------------------------------------
# Carga del mazo
# ---------------------------------------------------------------------------
DECK = []                 # Lista de cartas template cargadas del JSON
DECK_LOADED = False

def load_deck():
    """
    Carga deck.json si existe. Si no, queda vacío y caemos al modo random
    (compatibilidad con la versión TUI que no usa imágenes).
    """
    global DECK, DECK_LOADED
    try:
        with open('deck_gui.json', 'r', encoding='utf-8') as f:
            DECK = json.load(f)
        DECK = data.get('cards', [])
        DECK_LOADED = len(DECK) > 0
        return len(DECK)
    except (FileNotFoundError, json.JSONDecodeError):
        DECK = []
        DECK_LOADED = False
        return 0

# ---------------------------------------------------------------------------
# Secuencias ANSI (sin dependencias externas)
# ---------------------------------------------------------------------------
class C:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    CLEAR = '\033[2J\033[H'   # Borrar pantalla y mover cursor a (1,1)
    HOME = '\033[H'
    HIDE_CURSOR = '\033[?25l'
    SHOW_CURSOR = '\033[?25h'

# ---------------------------------------------------------------------------
# Estado global compartido (protegido por state_lock)
# ---------------------------------------------------------------------------
state_lock = threading.Lock()
players = {}              # player_id (1|2) -> dict con la info del jugador
game_status = "WAITING_PLAYERS"
event_log = []            # cola corta de strings para el dashboard
running = True

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def log_event(msg: str):
    """Agrega una línea al log del dashboard (con timestamp)."""
    with state_lock:
        ts = datetime.now().strftime('%H:%M:%S')
        event_log.append(f"[{ts}] {msg}")
        if len(event_log) > 7:
            event_log.pop(0)

def make_card(card_id: int) -> dict:
    """
    Genera una carta con id único.
    Si deck.json fue cargado, toma una carta random del mazo (con su ref_image).
    Si no, genera valores random (modo TUI/legacy).
    """
    if DECK_LOADED and DECK:
        template = random.choice(DECK)
        return {
            'id': card_id,
            'element': template['element'],
            'value': template['value'],
            'ref_image': template.get('ref_image', ''),
            'color': template.get('color', ''),
        }
    # Fallback: modo random sin imágenes (compatible con cliente TUI)
    return {
        'id': card_id,
        'element': random.choice(ELEMENTS),
        'value': random.randint(2, 12),
    }

def resolve_round(c1: dict, c2: dict) -> int:
    """
    Resuelve la ronda según las reglas del Card-Jitsu.
    Retorna 1 si gana P1, 2 si gana P2, 0 si empate total.
    Reglas: Fuego > Nieve > Agua > Fuego.
    En empate de elemento, gana el valor numérico más alto.
    """
    e1, e2 = c1['element'], c2['element']
    if e1 == e2:
        if c1['value'] > c2['value']:
            return 1
        if c2['value'] > c1['value']:
            return 2
        return 0  # empate total (mismo elemento, mismo valor)
    wins_p1 = {('fire', 'snow'), ('snow', 'water'), ('water', 'fire')}
    return 1 if (e1, e2) in wins_p1 else 2

# ---------------------------------------------------------------------------
# I/O JSON sobre el socket (framing por línea)
# ---------------------------------------------------------------------------
def send_json(player: dict, payload: dict) -> bool:
    """Serializa el dict, agrega '\n' y lo envía. Incrementa Tx (paquetes y bytes). Retorna False si falla."""
    try:
        data = (json.dumps(payload) + '\n').encode('utf-8')
        player['conn'].sendall(data)
        with state_lock:
            player['tx_count'] += 1
            player['tx_bytes'] += len(data)
        return True
    except (OSError, BrokenPipeError, ConnectionResetError):
        return False

def recv_json(conn: socket.socket, buffer: bytes):
    """
    Lee del socket hasta tener una línea completa.
    Retorna (mensaje_dict | None, buffer_restante).
    None indica conexión cerrada por el peer.
    """
    while b'\n' not in buffer:
        chunk = conn.recv(4096)
        if not chunk:                      # peer hizo close() (TCP FIN)
            return None, buffer
        buffer += chunk
    line, _, buffer = buffer.partition(b'\n')
    try:
        return json.loads(line.decode('utf-8')), buffer
    except json.JSONDecodeError:
        return {}, buffer                  # mensaje basura, lo ignoramos

# ---------------------------------------------------------------------------
# Hilo: listener por jugador
# ---------------------------------------------------------------------------
def player_listener(player_id: int):
    """
    Un hilo dedicado por cliente. Lee mensajes JSON y reacciona.
    Cuando llega un PLAY, fija current_play y dispara play_event para
    despertar al game_loop (modelo productor-consumidor).
    """
    player = players[player_id]
    conn = player['conn']
    buffer = b''
    try:
        while running:
            msg, buffer = recv_json(conn, buffer)
            if msg is None:
                break                       # cliente cerró el socket

            # Telemetría: guardamos el payload crudo y subimos Rx (paquetes y bytes)
            with state_lock:
                player['rx_count'] += 1
                raw = json.dumps(msg)
                player['rx_bytes'] += len(raw.encode('utf-8')) + 1  # +1 por el '\n'
                player['last_payload'] = raw

            action = msg.get('action')
            if action == 'JOIN':
                player['name'] = msg.get('name', f'Player{player_id}')
                # Validar color del pingüino (default rojo si no llega o es inválido)
                color = msg.get('penguin_color', 'red')
                if color not in PENGUIN_COLORS:
                    color = 'red'
                player['penguin_color'] = color
                log_event(f"Player {player_id} es: {player['name']} ({color})")

            elif action == 'PLAY':
                card_id = msg.get('card_id')
                with state_lock:
                    card = next((c for c in player['hand'] if c['id'] == card_id), None)
                if card:
                    player['current_play'] = card
                    player['status'] = 'PLAYED'
                    player['play_event'].set()     # despierta al game_loop
                    log_event(f"{player['name']} jugó {ELEMENT_ES[card['element']]} {card['value']}")
                else:
                    log_event(f"{player['name']} envió card_id inválido: {card_id}")

            elif action == 'QUIT':
                log_event(f"{player['name']} QUIT voluntario")
                break
    except Exception as e:
        log_event(f"{player['name']} error: {e}")
    finally:
        # Marcar desconexión y despertar al game_loop por si estaba esperando
        with state_lock:
            player['disconnected'] = True
            player['status'] = 'OFFLINE'
        player['play_event'].set()
        try:
            conn.close()
        except OSError:
            pass

# ---------------------------------------------------------------------------
# Hilo: bucle principal del juego
# ---------------------------------------------------------------------------
def game_loop():
    """Espera a 2 jugadores, reparte cartas y orquesta las rondas."""
    global game_status

    # Esperar a que se conecten ambos jugadores
    while running:
        with state_lock:
            if len(players) >= MAX_PLAYERS:
                break
        time.sleep(0.2)

    log_event("Ambos jugadores conectados. Iniciando partida.")
    next_card_id = 0

    # Inicializar estado de cada jugador
    with state_lock:
        for pid in (1, 2):
            players[pid]['hand'] = [make_card(next_card_id + i) for i in range(HAND_SIZE)]
            players[pid]['score'] = 0
            players[pid]['status'] = 'READY'
        next_card_id += HAND_SIZE
        game_status = "GAME_IN_PROGRESS"

    # Enviar bienvenida + mano inicial
    for pid in (1, 2):
        opp = 3 - pid
        send_json(players[pid], {
            'action': 'WELCOME',
            'player_id': pid,
            'rounds_to_win': ROUNDS_TO_WIN,
            'you': {
                'name': players[pid].get('name', f'Player{pid}'),
                'penguin_color': players[pid].get('penguin_color', 'red'),
            },
            'opponent': {
                'name': players[opp].get('name', f'Player{opp}'),
                'penguin_color': players[opp].get('penguin_color', 'red'),
            },
        })
        send_json(players[pid], {'action': 'DEAL', 'hand': players[pid]['hand']})

    round_num = 0
    # Bucle de rondas
    while running:
        round_num += 1
        log_event(f"--- Ronda {round_num} ---")

        # Reset de jugadas y eventos
        with state_lock:
            for pid in (1, 2):
                players[pid]['current_play'] = None
                players[pid]['status'] = 'WAIT_PLAY'
                players[pid]['play_event'].clear()

        # Pedir jugada a ambos jugadores
        for pid in (1, 2):
            send_json(players[pid], {
                'action': 'REQUEST_PLAY',
                'round': round_num,
                'scores': {
                    'you': players[pid]['score'],
                    'opponent': players[3 - pid]['score']
                }
            })

        # Esperar ambas jugadas de forma ASÍNCRONA.
        # Si una llega primero, notificamos WAIT al otro y seguimos esperando.
        p1_done = p2_done = False
        while not (p1_done and p2_done):
            if not p1_done and players[1]['play_event'].wait(timeout=0.1):
                if players[1].get('disconnected'):
                    log_event(f"{players[1]['name']} se desconectó durante la ronda. Cancelando.")
                    return
                p1_done = True
                if not p2_done:
                    send_json(players[2], {'action': 'WAIT',
                                           'message': 'El rival ya jugó. Esperando tu jugada.'})
            if not p2_done and players[2]['play_event'].wait(timeout=0.1):
                if players[2].get('disconnected'):
                    log_event(f"{players[2]['name']} se desconectó durante la ronda. Cancelando.")
                    return
                p2_done = True
                if not p1_done:
                    send_json(players[1], {'action': 'WAIT',
                                           'message': 'El rival ya jugó. Esperando tu jugada.'})

        # Resolver ronda
        with state_lock:
            game_status = "RESOLVING"
            for pid in (1, 2):
                players[pid]['status'] = 'RESOLVING'
        c1 = players[1]['current_play']
        c2 = players[2]['current_play']
        winner = resolve_round(c1, c2)

        with state_lock:
            if winner == 1:
                players[1]['score'] += 1
            elif winner == 2:
                players[2]['score'] += 1
        log_event(f"Resultado ronda {round_num}: " +
                  (f"{players[winner]['name']} gana" if winner else "Empate"))

        # Reponer las cartas jugadas
        with state_lock:
            for pid in (1, 2):
                played = players[pid]['current_play']
                players[pid]['hand'] = [c for c in players[pid]['hand'] if c['id'] != played['id']]
                players[pid]['hand'].append(make_card(next_card_id))
                next_card_id += 1

        # Broadcast del resultado a cada jugador (desde su perspectiva)
        for pid in (1, 2):
            opp = 3 - pid
            if winner == 0:
                result = 'tie'
            elif winner == pid:
                result = 'win'
            else:
                result = 'lose'
            send_json(players[pid], {
                'action': 'ROUND_RESULT',
                'your_card': players[pid]['current_play'],
                'opponent_card': players[opp]['current_play'],
                'result': result,
                'scores': {
                    'you': players[pid]['score'],
                    'opponent': players[opp]['score']
                },
                'new_hand': players[pid]['hand']
            })

        # ¿Alguien llegó a 3?
        if players[1]['score'] >= ROUNDS_TO_WIN or players[2]['score'] >= ROUNDS_TO_WIN:
            winner_pid = 1 if players[1]['score'] >= ROUNDS_TO_WIN else 2
            log_event(f"GAME OVER. {players[winner_pid]['name']} gana la partida.")
            for pid in (1, 2):
                send_json(players[pid], {
                    'action': 'GAME_OVER',
                    'result': 'win' if pid == winner_pid else 'lose',
                    'final_scores': {
                        'you': players[pid]['score'],
                        'opponent': players[3 - pid]['score']
                    }
                })
            with state_lock:
                game_status = "FINISHED"
            return

        with state_lock:
            game_status = "GAME_IN_PROGRESS"
        time.sleep(0.8)   # pequeña pausa para que el cliente lea el resultado

# ---------------------------------------------------------------------------
# Hilo: dashboard de telemetría
# ---------------------------------------------------------------------------
def render_dashboard():
    """Construye el frame del dashboard y lo escribe a stdout."""
    out = [C.CLEAR]
    out.append(C.BOLD + C.CYAN +
               "╔═══════════════════════════════════════════════════════════════════════════════════════╗\n"
               "║  CARD-JITSU SERVER · DASHBOARD DE TELEMETRÍA                                          ║\n"
               "╚═══════════════════════════════════════════════════════════════════════════════════════╝\n"
               + C.RESET)

    with state_lock:
        out.append(f"  {C.BOLD}Estado:{C.RESET} {C.YELLOW}{game_status:<20}{C.RESET}")
        out.append(f"  {C.BOLD}Hora:{C.RESET} {datetime.now().strftime('%H:%M:%S')}")
        out.append(f"  {C.BOLD}Puerto:{C.RESET} {PORT}\n\n")

        out.append("  ┌──────────────────────┬─────────┬──────────────────────┬──────────────┬───────────────┬───────────────┬─────────┐\n")
        out.append(C.BOLD +
                   "  │ Nombre (Player)      │ Color   │ Endpoint (IP:Puerto) │ Estado       │   Tx (pkt/B)  │   Rx (pkt/B)  │ Score   │\n"
                   + C.RESET)
        out.append("  ├──────────────────────┼─────────┼──────────────────────┼──────────────┼───────────────┼───────────────┼─────────┤\n")
        for pid in (1, 2):
            if pid in players:
                p = players[pid]
                name = p.get('name', f'Player{pid}')
                color = p.get('penguin_color', '-')
                ep = f"{p['addr'][0]}:{p['addr'][1]}"
                score_str = f"{p.get('score', 0)}/{ROUNDS_TO_WIN}"
                tx_str = f"{p['tx_count']}/{p['tx_bytes']}B"
                rx_str = f"{p['rx_count']}/{p['rx_bytes']}B"
                out.append(
                    f"  │ {name:<20} │ {color:<7} │ {ep:<20} │ {p['status']:<12} │ {tx_str:<13} │ {rx_str:<13} │ {score_str:<7} │\n"
                )
            else:
                out.append(
                    f"  │ {'(sin conectar)':<20} │ {'-':<7} │ {'(sin conectar)':<20} │ {'OFFLINE':<12} │ {'-':<13} │ {'-':<13} │ {'-':<7} │\n"
                )
        out.append("  └──────────────────────┴─────────┴──────────────────────┴──────────────┴───────────────┴───────────────┴─────────┘\n\n")

        out.append(f"  {C.BOLD}Último payload JSON recibido:{C.RESET}\n")
        for pid in (1, 2):
            if pid in players:
                name = players[pid].get('name', f'Player{pid}')
                last = players[pid].get('last_payload') or '(ninguno)'
                if len(last) > 70:
                    last = last[:67] + '...'
                out.append(f"    {C.MAGENTA}{name}:{C.RESET} {last}\n")
            else:
                out.append(f"    {C.DIM}Player {pid}: -{C.RESET}\n")
        out.append("\n")

        out.append(f"  {C.BOLD}Log de eventos:{C.RESET}\n")
        for entry in event_log[-7:]:
            out.append(f"    {C.DIM}{entry}{C.RESET}\n")

    out.append(f"\n  {C.DIM}Ctrl+C para detener el servidor{C.RESET}\n")
    sys.stdout.write(''.join(out))
    sys.stdout.flush()

def dashboard_loop():
    sys.stdout.write(C.HIDE_CURSOR)
    while running:
        render_dashboard()
        time.sleep(TICK_RATE)

# ---------------------------------------------------------------------------
# Hilo: aceptar conexiones
# ---------------------------------------------------------------------------
def accept_loop(server_sock: socket.socket):
    pid_counter = 1
    while pid_counter <= MAX_PLAYERS and running:
        try:
            conn, addr = server_sock.accept()
        except OSError:
            break
        with state_lock:
            players[pid_counter] = {
                'conn': conn,
                'addr': addr,
                'name': f'Player{pid_counter}',
                'penguin_color': 'red',
                'hand': [],
                'last_payload': '',
                'tx_count': 0,
                'rx_count': 0,
                'tx_bytes': 0,
                'rx_bytes': 0,
                'status': 'CONNECTED',
                'play_event': threading.Event(),
                'current_play': None,
                'score': 0,
                'disconnected': False
            }
        log_event(f"Player {pid_counter} conectado desde {addr[0]}:{addr[1]}")
        threading.Thread(target=player_listener, args=(pid_counter,), daemon=True).start()
        pid_counter += 1

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    global running
    n_cards = load_deck()
    if n_cards > 0:
        log_event(f"Mazo cargado desde {DECK_JSON_PATH}: {n_cards} cartas")
    else:
        log_event(f"Sin {DECK_JSON_PATH}: usando modo random (sin imágenes)")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(MAX_PLAYERS)
    log_event(f"Servidor escuchando en {HOST}:{PORT}")

    threading.Thread(target=accept_loop, args=(server_sock,), daemon=True).start()
    threading.Thread(target=dashboard_loop, daemon=True).start()
    threading.Thread(target=game_loop, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        running = False
        sys.stdout.write(C.SHOW_CURSOR + C.RESET + "\nCerrando servidor...\n")
        try:
            server_sock.close()
        except OSError:
            pass
        for p in players.values():
            try:
                p['conn'].close()
            except OSError:
                pass
        sys.exit(0)

if __name__ == '__main__':
    main()
