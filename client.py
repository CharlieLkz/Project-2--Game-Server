import pygame
import socket
import json
import threading
import os
import sys

# --- Configuración de Red (Mismo que tu client.py antiguo) ---
# Ejecuta 'ipconfig' en la Nitro V15 y pon la IP aquí.
# Ejemplo: SERVER_IP = '192.168.1.15' 
SERVER_IP = '127.0.0.1' # Pon tu IP real aquí para jugar en LAN
SERVER_PORT = 55555
ADDR = (SERVER_IP, SERVER_PORT)
FORMAT = 'utf-8'

# --- Configuración de Pygame y Assets ---
# Usamos las mismas rutas asumidas en build_deck_json.py
ASSETS_DIR = "assets"
BACKGROUNDS_IMG_DIR = os.path.join(ASSETS_DIR, "backgrounds")
ICONS_IMG_DIR = os.path.join(ASSETS_DIR, "icons")

# Configuración de Ventana
WIDTH, HEIGHT = 1200, 800
FPS = 60
pygame.init()
pygame.display.set_caption("Card-Jitsu Clone (GUI Version)")
screen = pygame.display.set_caption("Card-Jitsu")
# Usar variable WIDTH y HEIGHT definida arriba
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
FONT = pygame.font.SysFont('arial', 24)
LARGE_FONT = pygame.font.SysFont('arial', 40, bold=True)

# Colores
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
DARK_GRAY = (50, 50, 50)
GREEN = (0, 255, 0)
RED = (255, 0, 0)

# --- Clase para dibujar Cartas (Layer Compositor) ---
class CardGUI:
    def __init__(self, card_data, x, y, width=200, height=300):
        self.data = card_data # Los metadatos JSON completos de la carta
        self.id = card_data['id']
        self.rect = pygame.Rect(x, y, width, height)
        self.width = width
        self.height = height
        self.images = {} # Caché de imágenes cargadas y escaladas para esta carta
        self.selected = False
        
        # Cargar imágenes desde las rutas del JSON
        assets = self.data['assets']
        try:
            # Cargar y escalar imágenes
            self.images['background'] = pygame.image.load(assets['background']).convert_alpha()
            self.images['penguin'] = pygame.image.load(assets['penguin']).convert_alpha()
            self.images['number'] = pygame.image.load(assets['number']).convert_alpha()
            self.images['icon'] = pygame.image.load(assets['icon']).convert_alpha()
            
            # Escalar para que se ajusten al marco (width, height)
            self.images['background'] = pygame.transform.scale(self.images['background'], (self.width, self.height))
            # Escalar pingüino al centro (proporcionalmente)
            self.images['penguin'] = pygame.transform.scale(self.images['penguin'], (int(self.width*0.8), int(self.height*0.7)))
            # Escalar número (pequeño arriba-izq)
            self.images['number'] = pygame.transform.scale(self.images['number'], (50, 50))
            # Escalar icono (pequeño arriba-izq)
            self.images['icon'] = pygame.transform.scale(self.images['icon'], (40, 40))

        except pygame.error as e:
            print(f"Error cargando assets para carta {self.data['nombre']}: {e}")
            sys.exit(1)

    def draw(self, surface):
        # Composición en Capas (De abajo hacia arriba):
        # [ Capa 1 — marco/borde de color ]
        surface.blit(self.images['background'], self.rect)
        
        # [ Capa 2 — fondo gris translúcido (solo si está seleccionada) ]
        if self.selected:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100)) # Gris translúcido
            surface.blit(overlay, self.rect)
        
        # [ Capa 3 — imagen del pingüino al centro ]
        penguin_rect = self.images['penguin'].get_rect()
        penguin_rect.center = self.rect.center # Centrado en el marco
        surface.blit(self.images['penguin'], penguin_rect)
        
        # [ Capa 4 — ícono del elemento arriba-izq ]
        surface.blit(self.images['icon'], (self.rect.x + 10, self.rect.y + 10))
        
        # [ Capa 5 — número grande arriba-izq ]
        surface.blit(self.images['number'], (self.rect.x + 15, self.rect.y + 15))

        # Borde visual alrededor de la carta
        borde_color = GREEN if self.selected else DARK_GRAY
        pygame.draw.rect(surface, borde_color, self.rect, 3, border_radius=10)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

# --- Funciones de Red y Lógica del Juego ---
# Estas funciones corren en un hilo secundario para no congelar la GUI.
class GameClient:
    def __init__(self):
        self.client_socket = None
        self.game_state = "CONECTANDO" # Estados: CONECTANDO, ESPERANDO_OPONENTE, JUGANDO, FINALIZADO
        self.hand_data = [] # Datos JSON crudos de la mano
        self.card_guis = [] # Objetos CardGUI para dibujar
        self.selected_card_id = None
        self.oponent_played = False
        self.round_result = ""
        self.score = [0, 0] # [Jugador, Oponente]
        self.current_turn_data = {} # Datos recibidos en el último turno

    def connect_to_server(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect(ADDR)
            # Hilo para escuchar mensajes continuamente
            threading.Thread(target=self.receive_messages, daemon=True).start()
            self.game_state = "ESPERANDO_OPONENTE"
        except ConnectionRefusedError:
            self.game_state = "ERROR_CONEXION"
            print(f"Error: No se pudo conectar al servidor en {SERVER_IP}.")

    def receive_messages(self):
        while True:
            try:
                # Recibir payload JSON
                msg_len_str = self.client_socket.recv(64).decode(FORMAT)
                if not msg_len_str:
                    break
                msg_len = int(msg_len_str)
                payload_str = self.client_socket.recv(msg_len).decode(FORMAT)
                
                # Decodificar Payload (Mismo formato que el antiguo client.py)
                payload = json.loads(payload_str)
                self.current_turn_data = payload
                # print(f"[SERVER] Payload recibido: {payload['accion']}") # Debug

                # Manejar acciones (Lógica replicada del client.py antiguo)
                if payload['accion'] == 'HAND':
                    self.hand_data = payload['cartas']
                    self.game_state = "JUGANDO"
                    self.selected_card_id = None # Reset selección
                    # Crear los objetos CardGUI a partir de los datos recibidos
                    self.create_card_guis()
                
                elif payload['accion'] == 'OPONENT_PLAYED':
                    self.oponent_played = True
                
                elif payload['accion'] == 'ROUND_RESULT':
                    self.round_result = payload['mensaje']
                    self.oponent_played = False # Reset para la siguiente ronda
                
                elif payload['accion'] == 'END_GAME':
                    self.game_state = "FINALIZADO"
                    self.round_result = payload['mensaje']

            except (ConnectionResetError, json.JSONDecodeError, ValueError) as e:
                print(f"Error recibiendo mensajes: {e}")
                self.game_state = "DESCONECTADO"
                break

    def create_card_guis(self):
        # Crear objetos CardGUI y posicionarlos en la pantalla
        self.card_guis = []
        
        # Posiciones y dimensiones de las cartas de la mano (abajo)
        card_width, card_height = 180, 270
        start_x = 100
        start_y = HEIGHT - card_height - 50 # Parte inferior de la pantalla
        spacing = card_width + 30

        # Crear los objetos a partir de la mano recibida (asumimos 3 cartas)
        for i, card_data in enumerate(self.hand_data):
            x = start_x + (i * spacing)
            self.card_guis.append(CardGUI(card_data, x, start_y, card_width, card_height))

    def play_card(self, card_id):
        if self.game_state != "JUGANDO" or self.selected_card_id is not None:
            return

        print(f"-> Jugando carta ID: {card_id}")
        self.selected_card_id = card_id
        
        # Enviar elección al servidor (replicando el formato antiguo)
        # Nota: El servidor antiguo no usa el ID en el payload de 'PLAY', sino que
        # el servidor deduce el índice de la carta en la mano.
        # Esto es un problema. El servidor tiene que actualizarse.
        # Pero para que funcione CON EL SERVIDOR ACTUAL, deduciremos el índice.
        card_index = next((i for i, c in enumerate(self.hand_data) if c['id'] == card_id), None)
        
        if card_index is not None:
            play_payload = {
                "accion": "PLAY",
                "eleccion": card_index # Servidor antiguo espera el índice (0, 1, 2)
            }
            try:
                payload_str = json.dumps(play_payload).encode(FORMAT)
                msg_len = len(play_payload)
                self.client_socket.send(str(msg_len).encode(FORMAT).ljust(64))
                self.client_socket.send(payload_str)
            except (ConnectionResetError, BrokenPipeError):
                print("Error enviando carta al servidor.")
                self.game_state = "DESCONECTADO"

# --- Main Game Loop (Pygame Render) ---
def main():
    game = GameClient()
    game.connect_to_server() # Iniciar conexión de red
    
    running = True
    while running:
        # 1. Gestión de Eventos (Clics y Cerrar)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                if game.client_socket:
                    game.client_socket.close()
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Clic izquierdo en JUGANDO
                if game.game_state == "JUGANDO":
                    # Comprobar si se ha clicado en alguna carta de la mano
                    for card_gui in game.card_guis:
                        if card_gui.is_clicked(event.pos):
                            # Selección visual
                            for other_card in game.card_guis: other_card.selected = False
                            card_gui.selected = True
                            
                            # Jugar la carta (enviar al servidor)
                            game.play_card(card_gui.id)
                            break # Solo una carta por clic

        # 2. Dibujar en Pantalla (Rendering)
        screen.fill(WHITE) # Fondo blanco
        
        # -- Dibujar Dashboard (Telemetry/Log) del Servidor --
        pygame.draw.rect(screen, GRAY, (WIDTH-350, 0, 350, HEIGHT)) # Fondo panel derecho
        
        dash_title = FONT.render("Dashboard Servidor", True, DARK_GRAY)
        screen.blit(dash_title, (WIDTH-330, 20))
        
        y_offset = 60
        server_log = f"Server IP: {SERVER_IP}\nPort: {SERVER_PORT}"
        screen.blit(FONT.render(server_log, True, BLACK), (WIDTH-330, y_offset))
        y_offset += 40
        
        state_log = f"Estado: {game.game_state}"
        screen.blit(FONT.render(state_log, True, BLUE if game.game_state == "CONECTANDO" else GREEN), (WIDTH-330, y_offset))
        
        # Mostrar el último payload JSON crudo recibido
        y_offset += 60
        payload_title = FONT.render("Último Payload (Crudo):", True, DARK_GRAY)
        screen.blit(payload_title, (WIDTH-330, y_offset))
        y_offset += 30
        
        # Texto JSON multi-línea (formateado)
        if game.current_turn_data:
            json_str = json.dumps(game.current_turn_data, indent=2, ensure_ascii=False)
            lines = json_str.split('\n')
            for line in lines:
                if y_offset > HEIGHT - 30: break # No salirse de la pantalla
                # Truncar líneas muy largas para que no se superpongan
                if len(line) > 30: line = line[:27] + "..."
                
                screen.blit(FONT.render(line, True, BLACK), (WIDTH-330, y_offset))
                y_offset += 25

        # -- Dibujar Interfaz del Juego --
        
        if game.game_state == "ESPERANDO_OPONENTE":
            msg = LARGE_FONT.render("Esperando al Jugador 2...", True, DARK_GRAY)
            screen.blit(msg, (100, 200))
        
        elif game.game_state == "JUGANDO":
            # Dibujar Título del turno y resultados
            turn_msg = LARGE_FONT.render(f"Puntuación: J1: {game.score[0]} | Opp: {game.score[1]}", True, BLACK)
            screen.blit(turn_msg, (100, 50))
            
            # Dibujar la mano del jugador
            for card_gui in game.card_guis:
                card_gui.draw(screen)
            
            # Dibujar mensaje de resultado de ronda anterior (si lo hay)
            if game.round_result:
                result_msg = FONT.render(f"Resultado anterior: {game.round_result}", True, RED if "Perdiste" in game.round_result else GREEN)
                screen.blit(result_msg, (100, 400))
            
            # Dibujar estado del oponente
            if game.oponent_played:
                opp_msg = FONT.render("Oponente ya jugó su carta.", True, BLACK)
                screen.blit(opp_msg, (100, 350))
            else:
                opp_msg = FONT.render("Esperando oponente...", True, DARK_GRAY)
                screen.blit(opp_msg, (100, 350))

        # -- Actualizar Pantalla --
        pygame.display.flip()
        clock.tick(FPS)

    # Cerrar Pygame y socket limpiamente
    pygame.quit()
    if game.client_socket:
        game.client_socket.close()

if __name__ == "__main__":
    main()