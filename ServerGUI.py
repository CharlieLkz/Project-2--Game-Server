#!/usr/bin/env python3
"""
server_gui.py - Dashboard de telemetría GRÁFICO (Pygame)
=========================================================
Reutiliza TODA la lógica de red de server.py (no la duplica): importa el
módulo, arranca los hilos de red con start_network(with_terminal_dashboard=False)
y dibuja en una ventana Pygame el MISMO contenido que el dashboard de terminal:
estado, tabla de jugadores (con color del pingüino), último payload JSON y log.

Estética Club Penguin: paleta suave (azules, crema, amarillo), bordes
redondeados, tipografía gruesa.

Uso:
    pip install pygame --break-system-packages
    python3 server_gui.py

Requiere server.py en la misma carpeta.
"""

import sys
import pygame

# Importamos la lógica de red intacta (el archivo se llama Server.py con mayúscula)
import Server as server

# ---------------------------------------------------------------------------
# Paleta Club Penguin (suave, no abrasiva)
# ---------------------------------------------------------------------------
CP_BLUE       = (43, 108, 176)     # azul principal
CP_BLUE_DARK  = (29, 78, 137)      # azul oscuro (banners)
CP_BLUE_LIGHT = (120, 170, 220)    # azul claro
CP_CREAM      = (255, 248, 225)    # crema de fondo
CP_CREAM_DARK = (240, 230, 200)    # crema más oscuro (paneles)
CP_YELLOW     = (255, 199, 44)     # amarillo acento
CP_TEXT       = (45, 55, 72)       # texto principal (gris azulado oscuro)
CP_TEXT_SOFT  = (90, 100, 120)     # texto secundario
CP_WHITE      = (255, 255, 255)
CP_GREEN      = (104, 187, 89)     # estado OK
CP_RED        = (220, 95, 80)      # alertas suaves
CP_PANEL      = (252, 245, 222)    # fondo de cajas

# Colores de los pingüinos (para el chip de color en la tabla)
PENGUIN_RGB = {
    'red': (224, 90, 80), 'blue': (70, 130, 200), 'green': (104, 187, 89),
    'yellow': (245, 200, 70), 'pink': (240, 150, 190), 'purple': (160, 130, 200),
    'black': (70, 70, 80), 'orange': (240, 150, 70),
}

WIDTH, HEIGHT = 1000, 680
FPS = 30


def draw_round_rect(surface, color, rect, radius=12, border=0, border_color=None):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border > 0 and border_color:
        pygame.draw.rect(surface, border_color, rect, width=border, border_radius=radius)


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Card-Jitsu Server · Dashboard")
    clock = pygame.time.Clock()

    # Fuentes (Pygame trae fuentes del sistema; usamos una gruesa para títulos)
    f_title = pygame.font.SysFont('arialrounded,arial', 30, bold=True)
    f_head  = pygame.font.SysFont('arialrounded,arial', 20, bold=True)
    f_body  = pygame.font.SysFont('arial', 18)
    f_mono  = pygame.font.SysFont('couriernew,monospace', 15)
    f_small = pygame.font.SysFont('arial', 15)

    # Arrancar la red SIN el dashboard de terminal (lo reemplaza esta ventana)
    server_sock = server.start_network(with_terminal_dashboard=False)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # ----- Fondo -----
        screen.fill(CP_CREAM)

        # ----- Banner superior -----
        draw_round_rect(screen, CP_BLUE, pygame.Rect(20, 16, WIDTH - 40, 56), radius=16)
        title = f_title.render("CARD-JITSU SERVER · DASHBOARD", True, CP_WHITE)
        screen.blit(title, (40, 28))

        # Leer estado de forma segura (mismo lock que usa el server)
        with server.state_lock:
            game_status = server.game_status
            players_snapshot = {}
            for pid in (1, 2):
                if pid in server.players:
                    p = server.players[pid]
                    players_snapshot[pid] = {
                        'name': p.get('name', f'Player{pid}'),
                        'color': p.get('penguin_color', '-'),
                        'addr': p.get('addr', ('-', '-')),
                        'status': p.get('status', '-'),
                        'tx_count': p.get('tx_count', 0),
                        'tx_bytes': p.get('tx_bytes', 0),
                        'rx_count': p.get('rx_count', 0),
                        'rx_bytes': p.get('rx_bytes', 0),
                        'score': p.get('score', 0),
                        'last_payload': p.get('last_payload', ''),
                    }
            log_snapshot = list(server.event_log)

        # ----- Línea de estado -----
        estado_txt = f_head.render(f"Estado: {game_status}", True, CP_TEXT)
        screen.blit(estado_txt, (40, 86))
        puerto_txt = f_body.render(f"Puerto: {server.PORT}", True, CP_TEXT_SOFT)
        screen.blit(puerto_txt, (WIDTH - 180, 90))

        # ----- Tabla de jugadores -----
        table_y = 124
        draw_round_rect(screen, CP_PANEL, pygame.Rect(20, table_y, WIDTH - 40, 150),
                        radius=14, border=2, border_color=CP_BLUE_LIGHT)
        # Encabezados
        headers = ["Jugador", "Color", "Endpoint (IP:Puerto)", "Estado", "Tx (pkt/B)", "Rx (pkt/B)", "Score"]
        col_x = [40, 200, 290, 520, 640, 770, 900]
        for h, x in zip(headers, col_x):
            screen.blit(f_small.render(h, True, CP_BLUE_DARK), (x, table_y + 12))
        pygame.draw.line(screen, CP_BLUE_LIGHT, (35, table_y + 36), (WIDTH - 35, table_y + 36), 2)

        # Filas
        for i, pid in enumerate((1, 2)):
            row_y = table_y + 48 + i * 48
            if pid in players_snapshot:
                p = players_snapshot[pid]
                screen.blit(f_body.render(p['name'][:16], True, CP_TEXT), (col_x[0], row_y))
                # Chip de color
                chip = PENGUIN_RGB.get(p['color'], (180, 180, 180))
                draw_round_rect(screen, chip, pygame.Rect(col_x[1], row_y, 26, 22), radius=6,
                                border=2, border_color=CP_TEXT_SOFT)
                screen.blit(f_small.render(p['color'], True, CP_TEXT_SOFT), (col_x[1] + 32, row_y + 3))
                ep = f"{p['addr'][0]}:{p['addr'][1]}"
                screen.blit(f_small.render(ep, True, CP_TEXT), (col_x[2], row_y + 3))
                screen.blit(f_small.render(p['status'], True, CP_TEXT), (col_x[3], row_y + 3))
                screen.blit(f_small.render(f"{p['tx_count']}/{p['tx_bytes']}B", True, CP_TEXT), (col_x[4], row_y + 3))
                screen.blit(f_small.render(f"{p['rx_count']}/{p['rx_bytes']}B", True, CP_TEXT), (col_x[5], row_y + 3))
                screen.blit(f_head.render(f"{p['score']}/{server.ROUNDS_TO_WIN}", True, CP_BLUE_DARK), (col_x[6], row_y))
            else:
                screen.blit(f_small.render("(sin conectar)", True, CP_TEXT_SOFT), (col_x[0], row_y + 3))
                screen.blit(f_small.render("OFFLINE", True, CP_TEXT_SOFT), (col_x[3], row_y + 3))

        # ----- Panel último payload JSON -----
        pay_y = 290
        draw_round_rect(screen, CP_PANEL, pygame.Rect(20, pay_y, WIDTH - 40, 130),
                        radius=14, border=2, border_color=CP_BLUE_LIGHT)
        screen.blit(f_head.render("Último payload JSON recibido:", True, CP_BLUE_DARK), (40, pay_y + 10))
        line_y = pay_y + 42
        for pid in (1, 2):
            if pid in players_snapshot:
                name = players_snapshot[pid]['name']
                last = players_snapshot[pid]['last_payload'] or '(ninguno)'
                if len(last) > 78:
                    last = last[:75] + '...'
                screen.blit(f_mono.render(f"{name}: {last}", True, CP_TEXT), (40, line_y))
            else:
                screen.blit(f_mono.render(f"Player {pid}: -", True, CP_TEXT_SOFT), (40, line_y))
            line_y += 30

        # ----- Panel log de eventos -----
        log_y = 436
        draw_round_rect(screen, CP_PANEL, pygame.Rect(20, log_y, WIDTH - 40, HEIGHT - log_y - 20),
                        radius=14, border=2, border_color=CP_BLUE_LIGHT)
        screen.blit(f_head.render("Log de eventos:", True, CP_BLUE_DARK), (40, log_y + 10))
        entry_y = log_y + 42
        for entry in log_snapshot[-6:]:
            screen.blit(f_mono.render(entry[:92], True, CP_TEXT_SOFT), (40, entry_y))
            entry_y += 24

        pygame.display.flip()
        clock.tick(FPS)

    # Cierre limpio
    server.running = False
    try:
        server_sock.close()
    except OSError:
        pass
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()