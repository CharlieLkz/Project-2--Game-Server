#!/usr/bin/env python3
"""
client.py - Cliente GRAFICO Card-Jitsu (Pygame)
================================================
Pantallas:
  1) LOBBY     -> nombre + elegir color del pinguino (6 colores) + Continuar
  2) ESPERA    -> "Esperando rival..." + boton Salir
  3) COMBATE   -> dojo, ambos pinguinos, tu mano de cartas, marcador
  4) FIN       -> ganador + marcador + Jugar de nuevo / Salir

Protocolo (alineado con server.py, framing por '\n', campos en INGLES):
  Cliente -> Server:  {"action":"JOIN","name":...,"penguin_color":...}
                      {"action":"PLAY","card_id":N}
                      {"action":"QUIT"}
  Server  -> Cliente: WELCOME / DEAL / REQUEST_PLAY / WAIT / ROUND_RESULT / GAME_OVER

Uso:
    pip install pygame --break-system-packages
    python3 client.py            # usa SERVER_IP de abajo
    python3 client.py <IP>       # override
"""

import pygame
import socket
import json
import threading
import os
import sys

# ===========================================================================
#  CONFIGURACION - EDITAR LA IP ANTES DE JUGAR
# ===========================================================================
SERVER_IP   = "192.168.10.34"     # IP LAN del servidor (Nitro V5)
SERVER_PORT = 55555
# ===========================================================================

if len(sys.argv) > 1:
    SERVER_IP = sys.argv[1]
if len(sys.argv) > 2:
    SERVER_PORT = int(sys.argv[2])

ASSETS_DIR = "assets"
MUSIC_DIR = os.path.join("assets", "music")
PENGUIN_PATHS = [
    os.path.join(ASSETS_DIR, "penguins", "PinguinGeneric.png"),
    os.path.join(ASSETS_DIR, "penguins", "PinguinGeneric.PNG"),
    os.path.join(ASSETS_DIR, "penguins", "pinguin_generic.png"),
]

WIDTH, HEIGHT = 1280, 760
FPS = 60

CP_BLUE       = (43, 108, 176)
CP_BLUE_DARK  = (29, 78, 137)
CP_BLUE_LIGHT = (120, 170, 220)
CP_CREAM      = (255, 248, 225)
CP_YELLOW     = (255, 199, 44)
CP_YELLOW_DK  = (220, 165, 20)
CP_TEXT       = (45, 55, 72)
CP_TEXT_SOFT  = (90, 100, 120)
CP_WHITE      = (255, 255, 255)
CP_GREEN      = (104, 187, 89)
CP_RED        = (220, 95, 80)
CP_PANEL      = (252, 245, 222)

PENGUIN_COLORS = [
    ("red",    (224, 90, 80)),
    ("blue",   (70, 130, 200)),
    ("green",  (104, 187, 89)),
    ("yellow", (245, 200, 70)),
    ("pink",   (240, 150, 190)),
    ("purple", (160, 130, 200)),
]
PENGUIN_RGB = dict(PENGUIN_COLORS)

ELEMENT_ES = {'fire': 'Fuego', 'snow': 'Nieve', 'water': 'Agua'}


# ---------------------------------------------------------------------------
# Audio manager: música de fondo (lobby/combate) + efectos por elemento
# Si una pista falta, no crashea: solo lo loguea y sigue.
# ---------------------------------------------------------------------------
class AudioManager:
    def __init__(self):
        self.ok = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.ok = True
        except pygame.error as e:
            print(f"[audio] no se pudo inicializar mixer: {e}")
            return

        # Cargar efectos cortos en memoria (más responsivos que music)
        self.sfx = {}
        for el in ("fire", "snow", "water"):
            path = os.path.join(MUSIC_DIR, f"{el}.mp3")
            if os.path.exists(path):
                try:
                    self.sfx[el] = pygame.mixer.Sound(path)
                    self.sfx[el].set_volume(0.8)
                except pygame.error as e:
                    print(f"[audio] no pude cargar {path}: {e}")
            else:
                print(f"[audio] no existe {path}")

        self.current_music = None   # 'lobby' | 'background' | None

    def play_music(self, kind, volume=0.5):
        """kind: 'lobby' o 'background'. Loop infinito hasta stop_music()."""
        if not self.ok:
            return
        if self.current_music == kind:
            return
        path = os.path.join(MUSIC_DIR, f"{kind}.mp3")
        if not os.path.exists(path):
            print(f"[audio] no existe {path}")
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops=-1)
            self.current_music = kind
        except pygame.error as e:
            print(f"[audio] error reproduciendo {path}: {e}")

    def stop_music(self):
        if not self.ok:
            return
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        self.current_music = None

    def play_sfx(self, element):
        """Reproduce el efecto del elemento jugado (fire/snow/water)."""
        if not self.ok:
            return
        s = self.sfx.get(element)
        if s:
            try:
                s.play()
            except pygame.error:
                pass


class NetClient:
    def __init__(self):
        self.sock = None
        self.buffer = b''
        self.connected = False
        self.inbox = []
        self.inbox_lock = threading.Lock()
        self.error = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((SERVER_IP, SERVER_PORT))
            self.connected = True
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return True
        except (ConnectionRefusedError, OSError) as e:
            self.error = str(e)
            return False

    def _recv_loop(self):
        while self.connected:
            try:
                while b'\n' not in self.buffer:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        self.connected = False
                        return
                    self.buffer += chunk
                line, _, self.buffer = self.buffer.partition(b'\n')
                msg = json.loads(line.decode('utf-8'))
                with self.inbox_lock:
                    self.inbox.append(msg)
            except (ConnectionResetError, OSError, json.JSONDecodeError):
                self.connected = False
                return

    def send(self, payload):
        if not self.connected:
            return
        try:
            self.sock.sendall((json.dumps(payload) + '\n').encode('utf-8'))
        except OSError:
            self.connected = False

    def poll(self):
        with self.inbox_lock:
            msgs = self.inbox[:]
            self.inbox.clear()
        return msgs

    def close(self):
        self.connected = False
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass


def draw_round_rect(surface, color, rect, radius=12, border=0, border_color=None):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border > 0 and border_color:
        pygame.draw.rect(surface, border_color, rect, width=border, border_radius=radius)


def tint_surface(base, rgb):
    tinted = base.copy()
    overlay = pygame.Surface(base.get_size(), pygame.SRCALPHA)
    overlay.fill((rgb[0], rgb[1], rgb[2], 255))
    tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return tinted


class Button:
    def __init__(self, rect, text, font, bg=CP_YELLOW, fg=CP_TEXT, border=CP_YELLOW_DK):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.bg, self.fg, self.border = bg, fg, border

    def draw(self, surface, hover=False):
        color = self.border if hover else self.bg
        draw_round_rect(surface, color, self.rect, radius=14, border=3, border_color=self.border)
        label = self.font.render(self.text, True, self.fg)
        surface.blit(label, label.get_rect(center=self.rect.center))

    def hit(self, pos):
        return self.rect.collidepoint(pos)


class CardSprite:
    _cache = {}

    def __init__(self, card_data, x, y, w=170, h=250):
        self.data = card_data
        self.id = card_data['id']
        self.rect = pygame.Rect(x, y, w, h)
        self.w, self.h = w, h
        self.selected = False
        self.layers = {}
        self._load()

    @classmethod
    def _img(cls, path):
        if path not in cls._cache:
            cls._cache[path] = pygame.image.load(path).convert_alpha()
        return cls._cache[path]

    def _load(self):
        a = self.data.get('assets', {})
        try:
            if a.get('background'):
                bg = self._img(a['background'])
                self.layers['bg'] = pygame.transform.smoothscale(bg, (self.w, self.h))
            if a.get('penguin'):
                pg = self._img(a['penguin'])
                self.layers['penguin'] = pygame.transform.smoothscale(
                    pg, (int(self.w * 0.78), int(self.h * 0.62)))
            if a.get('number'):
                nm = self._img(a['number'])
                self.layers['number'] = pygame.transform.smoothscale(nm, (52, 52))
            if a.get('icon'):
                ic = self._img(a['icon'])
                self.layers['icon'] = pygame.transform.smoothscale(ic, (44, 44))
        except (pygame.error, FileNotFoundError) as e:
            print(f"[carta {self.id}] no se pudo cargar un asset: {e}")

    def draw(self, surface, lift=0):
        r = self.rect.copy()
        r.y -= lift
        if 'bg' in self.layers:
            surface.blit(self.layers['bg'], r)
        else:
            draw_round_rect(surface, CP_BLUE_LIGHT, r, radius=10)
        if 'penguin' in self.layers:
            pr = self.layers['penguin'].get_rect(center=(r.centerx, r.centery + 10))
            surface.blit(self.layers['penguin'], pr)
        if 'icon' in self.layers:
            surface.blit(self.layers['icon'], (r.x + 12, r.y + 10))
        if 'number' in self.layers:
            surface.blit(self.layers['number'], (r.x + 8, r.y + 54))
        if self.selected:
            pygame.draw.rect(surface, CP_GREEN, r, width=5, border_radius=10)

    def hit(self, pos):
        return self.rect.collidepoint(pos)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Card-Jitsu")
        self.clock = pygame.time.Clock()

        self.f_title = pygame.font.SysFont('arial', 46, bold=True)
        self.f_head  = pygame.font.SysFont('arial', 30, bold=True)
        self.f_body  = pygame.font.SysFont('arial', 22)
        self.f_small = pygame.font.SysFont('arial', 18)

        # Audio (música + efectos)
        self.audio = AudioManager()

        self.net = NetClient()
        self.state = "LOBBY"
        self.name = ""
        self.color = PENGUIN_COLORS[0][0]
        self.typing = True

        self.hand = []
        self.cards = []
        self.my_score = 0
        self.opp_score = 0
        self.round_num = 0
        self.last_log = ""
        self.waiting_play = False
        self.player_id = '?'
        self.me = {"name": "", "penguin_color": "red"}
        self.opponent = {"name": "Rival", "penguin_color": "blue"}
        self.my_won_elements = []
        self.opp_won_elements = []
        self.final_result = None

        self.penguin_base = None
        for p in PENGUIN_PATHS:
            if os.path.exists(p):
                self.penguin_base = pygame.image.load(p).convert_alpha()
                break
        self.penguin_tint_cache = {}
        self.icon_cache = {}
        self.color_rects = []

        self.btn_continue = Button((WIDTH - 320, HEIGHT - 140, 240, 64), "CONTINUAR", self.f_head)
        self.btn_quit_wait = Button((WIDTH // 2 - 110, HEIGHT - 130, 220, 60), "SALIR", self.f_head,
                                    bg=CP_RED, fg=CP_WHITE, border=(170, 60, 50))
        self.btn_again = Button((WIDTH // 2 - 250, HEIGHT - 120, 220, 64), "JUGAR DE NUEVO", self.f_body,
                               bg=CP_GREEN, fg=CP_WHITE, border=(70, 140, 60))
        self.btn_exit  = Button((WIDTH // 2 + 30, HEIGHT - 120, 220, 64), "SALIR", self.f_head,
                               bg=CP_RED, fg=CP_WHITE, border=(170, 60, 50))

    def get_tinted_penguin(self, color, size):
        key = (color, size)
        if key in self.penguin_tint_cache:
            return self.penguin_tint_cache[key]
        if self.penguin_base is None:
            surf = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.ellipse(surf, PENGUIN_RGB.get(color, (100, 100, 100)), surf.get_rect())
            self.penguin_tint_cache[key] = surf
            return surf
        scaled = pygame.transform.smoothscale(self.penguin_base, size)
        tinted = tint_surface(scaled, PENGUIN_RGB.get(color, (255, 255, 255)))
        self.penguin_tint_cache[key] = tinted
        return tinted

    def get_element_icon(self, element, size=40):
        key = (element, size)
        if key in self.icon_cache:
            return self.icon_cache[key]
        path = os.path.join(ASSETS_DIR, "icons", f"icon_{element}.png")
        try:
            img = pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), (size, size))
        except (pygame.error, FileNotFoundError):
            img = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(img, CP_YELLOW, (size // 2, size // 2), size // 2)
        self.icon_cache[key] = img
        return img

    def handle_messages(self):
        for msg in self.net.poll():
            action = msg.get('action')
            if action == 'WELCOME':
                self.player_id = msg.get('player_id', '?')
                self.me = msg.get('you', self.me)
                self.opponent = msg.get('opponent', self.opponent)
            elif action == 'DEAL':
                self.hand = msg['hand']
                # Cambiar de lobby.mp3 a background.mp3 al arrancar el combate
                self.audio.play_music('background', volume=0.35)
                self.state = "COMBATE"
                self._rebuild_cards()
            elif action == 'REQUEST_PLAY':
                self.round_num = msg.get('round', self.round_num)
                sc = msg.get('scores', {})
                self.my_score = sc.get('you', self.my_score)
                self.opp_score = sc.get('opponent', self.opp_score)
                self.waiting_play = False
                for c in self.cards:
                    c.selected = False
            elif action == 'WAIT':
                self.last_log = msg.get('message', '')
            elif action == 'ROUND_RESULT':
                yc = msg['your_card']; oc = msg['opponent_card']
                result = msg['result']
                sc = msg.get('scores', {})
                self.my_score = sc.get('you', self.my_score)
                self.opp_score = sc.get('opponent', self.opp_score)
                self.hand = msg['new_hand']
                tag = {'win': "Ganaste la ronda!", 'lose': "Perdiste la ronda.",
                       'tie': "Empate."}[result]
                self.last_log = (f"Jugaste {ELEMENT_ES[yc['element']]} {yc['value']}, "
                                 f"rival {ELEMENT_ES[oc['element']]} {oc['value']}. {tag}")
                if result == 'win':
                    self.my_won_elements.append(yc['element'])
                elif result == 'lose':
                    self.opp_won_elements.append(oc['element'])
                self.waiting_play = False
                self._rebuild_cards()
            elif action == 'GAME_OVER':
                self.final_result = msg.get('result')
                fs = msg.get('final_scores', {})
                self.my_score = fs.get('you', self.my_score)
                self.opp_score = fs.get('opponent', self.opp_score)
                self.audio.stop_music()
                self.state = "FIN"

    def _rebuild_cards(self):
        self.cards = []
        n = len(self.hand)
        card_w, card_h = 150, 220
        gap = 22
        total = n * card_w + (n - 1) * gap
        start_x = (WIDTH - total) // 2
        y = HEIGHT - card_h - 40
        for i, cd in enumerate(self.hand):
            self.cards.append(CardSprite(cd, start_x + i * (card_w + gap), y, card_w, card_h))

    def play_card(self, card_id):
        if self.waiting_play:
            return
        # Reproducir el efecto del elemento de la carta jugada
        played = next((c for c in self.hand if c.get('id') == card_id), None)
        if played:
            self.audio.play_sfx(played.get('element', ''))
        self.waiting_play = True
        self.net.send({'action': 'PLAY', 'card_id': card_id})
        self.last_log = "Esperando al rival..."

    def draw_lobby(self, mouse):
        self.screen.fill(CP_CREAM)
        draw_round_rect(self.screen, CP_BLUE, pygame.Rect(40, 30, WIDTH - 80, 70), radius=18)
        t = self.f_title.render("CARD-JITSU", True, CP_YELLOW)
        self.screen.blit(t, t.get_rect(center=(WIDTH // 2, 65)))
        self.screen.blit(self.f_head.render("Personaliza tu pinguino", True, CP_TEXT), (80, 130))
        self.screen.blit(self.f_body.render("Tu nombre:", True, CP_TEXT), (80, 195))
        name_box = pygame.Rect(80, 225, 360, 50)
        draw_round_rect(self.screen, CP_WHITE, name_box, radius=10, border=3,
                        border_color=CP_BLUE if self.typing else CP_BLUE_LIGHT)
        shown = self.name + ("|" if self.typing and pygame.time.get_ticks() % 1000 < 500 else "")
        self.screen.blit(self.f_body.render(shown, True, CP_TEXT), (name_box.x + 12, name_box.y + 12))
        self.screen.blit(self.f_body.render("Color:", True, CP_TEXT), (80, 300))
        self.color_rects = []
        for i, (cname, rgb) in enumerate(PENGUIN_COLORS):
            cx = 80 + (i % 3) * 70
            cy = 335 + (i // 3) * 70
            rect = pygame.Rect(cx, cy, 54, 54)
            self.color_rects.append((rect, cname))
            draw_round_rect(self.screen, rgb, rect, radius=10,
                            border=5 if self.color == cname else 2,
                            border_color=CP_GREEN if self.color == cname else CP_TEXT_SOFT)
        prev = self.get_tinted_penguin(self.color, (340, 340))
        self.screen.blit(prev, prev.get_rect(center=(WIDTH - 360, HEIGHT // 2 - 10)))
        self.screen.blit(self.f_small.render("Vista previa", True, CP_TEXT_SOFT),
                         (WIDTH - 430, HEIGHT // 2 + 165))
        self.btn_continue.draw(self.screen, self.btn_continue.hit(mouse))

    def draw_espera(self, mouse):
        self.screen.fill(CP_CREAM)
        draw_round_rect(self.screen, CP_BLUE, pygame.Rect(40, 30, WIDTH - 80, 70), radius=18)
        t = self.f_title.render("CARD-JITSU", True, CP_YELLOW)
        self.screen.blit(t, t.get_rect(center=(WIDTH // 2, 65)))
        msg = self.f_head.render("Esperando al otro Ninja...", True, CP_TEXT)
        self.screen.blit(msg, msg.get_rect(center=(WIDTH // 2, 250)))
        bob = int(8 * (pygame.time.get_ticks() / 400 % 2))
        prev = self.get_tinted_penguin(self.color, (260, 260))
        self.screen.blit(prev, prev.get_rect(center=(WIDTH // 2, 430 + bob)))
        self.btn_quit_wait.draw(self.screen, self.btn_quit_wait.hit(mouse))

    def draw_combate(self, mouse):
        self.screen.fill(CP_CREAM)
        draw_round_rect(self.screen, CP_BLUE, pygame.Rect(0, 0, WIDTH, 70), radius=0)
        sc = self.f_head.render(
            f"{self.me.get('name','Tu')}  {self.my_score}   -   {self.opp_score}  {self.opponent.get('name','Rival')}",
            True, CP_WHITE)
        self.screen.blit(sc, sc.get_rect(center=(WIDTH // 2, 35)))
        self.screen.blit(self.f_small.render(f"Ronda {self.round_num}", True, CP_YELLOW), (20, 25))
        my_peng = self.get_tinted_penguin(self.me.get('penguin_color', self.color), (220, 220))
        op_peng = self.get_tinted_penguin(self.opponent.get('penguin_color', 'blue'), (220, 220))
        self.screen.blit(my_peng, my_peng.get_rect(center=(230, 320)))
        op_flipped = pygame.transform.flip(op_peng, True, False)
        self.screen.blit(op_flipped, op_flipped.get_rect(center=(WIDTH - 230, 320)))
        self.screen.blit(self.f_body.render(self.me.get('name', 'Tu'), True, CP_TEXT), (170, 440))
        self.screen.blit(self.f_body.render(self.opponent.get('name', 'Rival'), True, CP_TEXT), (WIDTH - 290, 440))
        for i, el in enumerate(self.my_won_elements):
            self.screen.blit(self.get_element_icon(el, 38), (150 + i * 44, 150))
        for i, el in enumerate(self.opp_won_elements):
            self.screen.blit(self.get_element_icon(el, 38), (WIDTH - 190 - i * 44, 150))
        if self.last_log:
            lg = self.f_body.render(self.last_log, True, CP_TEXT)
            self.screen.blit(lg, lg.get_rect(center=(WIDTH // 2, 200)))
        if self.waiting_play:
            wt = self.f_body.render("Esperando al rival...", True, CP_TEXT_SOFT)
            self.screen.blit(wt, wt.get_rect(center=(WIDTH // 2, HEIGHT - 290)))
        else:
            hint = self.f_body.render("Elige una carta", True, CP_BLUE_DARK)
            self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 290)))
        for c in self.cards:
            hover = c.hit(mouse) and not self.waiting_play
            c.draw(self.screen, lift=16 if hover else 0)

    def draw_fin(self, mouse):
        self.screen.fill(CP_CREAM)
        dip_path = os.path.join(ASSETS_DIR, "backgrounds", "victory_diploma.png")
        if os.path.exists(dip_path):
            try:
                dip = pygame.transform.smoothscale(
                    pygame.image.load(dip_path).convert_alpha(), (WIDTH - 200, HEIGHT - 260))
                self.screen.blit(dip, (100, 110))
            except pygame.error:
                pass
        win = (self.final_result == 'win')
        banner_color = CP_GREEN if win else CP_RED
        draw_round_rect(self.screen, banner_color, pygame.Rect(40, 30, WIDTH - 80, 64), radius=16)
        txt = (f"{self.me.get('name','Tu')} ES EL GANADOR!" if win
               else f"{self.opponent.get('name','Rival')} gano la partida")
        t = self.f_head.render(txt, True, CP_WHITE)
        self.screen.blit(t, t.get_rect(center=(WIDTH // 2, 62)))
        sc = self.f_head.render(f"Marcador final:  {self.my_score} - {self.opp_score}", True, CP_TEXT)
        self.screen.blit(sc, sc.get_rect(center=(WIDTH // 2, HEIGHT - 175)))
        self.btn_again.draw(self.screen, self.btn_again.hit(mouse))
        self.btn_exit.draw(self.screen, self.btn_exit.hit(mouse))

    def handle_click(self, pos):
        if self.state == "LOBBY":
            for rect, cname in self.color_rects:
                if rect.collidepoint(pos):
                    self.color = cname
                    return
            if self.btn_continue.hit(pos):
                if not self.name.strip():
                    self.name = "Ninja"
                self.connect_and_join()
        elif self.state == "ESPERA":
            if self.btn_quit_wait.hit(pos):
                self.quit_game()
        elif self.state == "COMBATE":
            if not self.waiting_play:
                for c in self.cards:
                    if c.hit(pos):
                        for o in self.cards:
                            o.selected = False
                        c.selected = True
                        self.play_card(c.id)
                        break
        elif self.state == "FIN":
            if self.btn_again.hit(pos):
                self.restart()
            elif self.btn_exit.hit(pos):
                self.quit_game()

    def connect_and_join(self):
        if not self.net.connect():
            self.last_log = f"No se pudo conectar: {self.net.error}"
            return
        self.net.send({'action': 'JOIN', 'name': self.name.strip(),
                       'penguin_color': self.color})
        self.me = {"name": self.name.strip(), "penguin_color": self.color}
        self.typing = False
        # Música del lobby mientras espera al otro jugador
        self.audio.play_music('lobby', volume=0.4)
        self.state = "ESPERA"

    def restart(self):
        self.net.close()
        self.net = NetClient()
        self.state = "LOBBY"
        self.hand = []; self.cards = []
        self.my_score = self.opp_score = 0
        self.round_num = 0; self.last_log = ""
        self.waiting_play = False
        self.my_won_elements = []; self.opp_won_elements = []
        self.final_result = None
        self.typing = True
        self.audio.stop_music()

    def quit_game(self):
        self.net.send({'action': 'QUIT'})
        self.net.close()
        self.audio.stop_music()
        pygame.quit()
        sys.exit(0)

    def run(self):
        running = True
        while running:
            mouse = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit_game()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                elif event.type == pygame.KEYDOWN and self.state == "LOBBY" and self.typing:
                    if event.key == pygame.K_RETURN:
                        if not self.name.strip():
                            self.name = "Ninja"
                        self.connect_and_join()
                    elif event.key == pygame.K_BACKSPACE:
                        self.name = self.name[:-1]
                    elif len(self.name) < 14 and event.unicode.isprintable():
                        self.name += event.unicode

            self.handle_messages()

            if self.state == "LOBBY":
                self.draw_lobby(mouse)
            elif self.state == "ESPERA":
                self.draw_espera(mouse)
            elif self.state == "COMBATE":
                self.draw_combate(mouse)
            elif self.state == "FIN":
                self.draw_fin(mouse)

            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()