import json
import random
import os

# Configuración de Rutas de Assets (asumidas)
# Ajusta estas rutas si tus carpetas reales tienen otros nombres
ASSETS_DIR = "assets"
CARDS_IMG_DIR = os.path.join(ASSETS_DIR, "cards")
NUMBERS_IMG_DIR = os.path.join(ASSETS_DIR, "numbers")
BACKGROUNDS_IMG_DIR = os.path.join(ASSETS_DIR, "backgrounds")
ICONS_IMG_DIR = os.path.join(ASSETS_DIR, "icons")

# Nombre del archivo JSON de salida (que usará el servidor)
DECK_OUTPUT_FILE = "deck_gui.json"

# Rango de valores y elementos del juego
VALUES_RANGE = range(2, 11) # Del 2 al 10
ELEMENTS = ["Fuego", "Agua", "Nieve"]

# --- Lógica de asignación de Assets (Basada en tus respuestas) ---

# Mapeo de elemento a fondo (background)
# Pregunta 2: Agua es azul, Nieve morado.
ELEMENT_TO_BG = {
    "Fuego": "red.png",
    "Agua": "blue.png",
    "Nieve": "purple.png"
}

# Regla especial: "Y las que son muy altas y rojas como el 8, que sean amarillas"
# Asumiremos "altas" como valor >= 8.
HIGH_VALUE_THRESHOLD = 8
HIGH_VALUE_BG = "yellow.png"

# Mapeo de elemento a icono
ELEMENT_TO_ICON = {
    "Fuego": "icon_fire.png",
    "Agua": "icon_water.png",
    "Nieve": "icon_snow.png"
}

def generate_deck():
    # 1. Obtener la "pool" de imágenes de pingüinos genéricos (Pregunta 1)
    # Asumimos que hay 14 archivos en assets/cards/ (1.png...14.png)
    try:
        penguin_pool = [f for f in os.listdir(CARDS_IMG_DIR) if f.endswith('.png')]
        if not penguin_pool:
            raise FileNotFoundError(f"No se encontraron imágenes .png en {CARDS_IMG_DIR}")
        print(f"-> Se encontraron {len(penguin_pool)} imágenes de pingüinos en la pool.")
    except FileNotFoundError as e:
        print(f"Error crítico: {e}")
        return None

    deck = []
    card_id = 0

    # 2. Generar todas las combinaciones Elemento x Valor (3x9 = 27 cartas)
    for element in ELEMENTS:
        for value in VALUES_RANGE:
            # Lógica de asignación de assets para esta carta específica:

            # -- Determinar el Fondo (Background) --
            if value >= HIGH_VALUE_THRESHOLD:
                bg_file = HIGH_VALUE_BG # Amarilla para valores altos
            else:
                bg_file = ELEMENT_TO_BG[element] # Color del elemento

            # -- Determinar el Pingüino (Random de la pool) --
            # Pregunta 1: "los puedes poner en orden aleatorio"
            penguin_file = random.choice(penguin_pool)

            # -- Determinar el Número (Asumimos formato 'N.png') --
            number_file = f"{value}.png"

            # -- Determinar el Icono --
            icon_file = ELEMENT_TO_ICON[element]

            # Crear el metadato de la carta (lo que leerá el cliente GUI)
            card_metadata = {
                "id": card_id,
                "nombre": f"{element} {value}",
                "elemento": element,
                "valor": value,
                "assets": {
                    # Rutas RELATIVAS desde la raíz del proyecto para que el cliente las cargue
                    "background": os.path.join(BACKGROUNDS_IMG_DIR, bg_file),
                    "penguin": os.path.join(CARDS_IMG_DIR, penguin_file),
                    "number": os.path.join(NUMBERS_IMG_DIR, number_file),
                    "icon": os.path.join(ICONS_IMG_DIR, icon_file)
                }
            }

            deck.append(card_metadata)
            card_id += 1

    print(f"-> Mazo generado con {len(deck)} cartas de metadatos.")
    return deck

def save_deck_json(deck):
    if deck:
        with open(DECK_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(deck, f, indent=4, ensure_ascii=False)
        print(f"-> Mazo guardado exitosamente en: {DECK_OUTPUT_FILE}")
    else:
        print("-> Error: No se generó el mazo, no se guardó el archivo.")

if __name__ == "__main__":
    print("=== Iniciando generación de mazo GUI (build_deck_json.py) ===")
    
    # Verificar si la estructura de carpetas existe antes de empezar
    if not os.path.exists(ASSETS_DIR):
        print(f"Error crítico: La carpeta raíz '{ASSETS_DIR}/' no existe.")
        print("Asegúrate de tener tus assets organizados antes de correr este script.")
        exit(1)

    # Generar el mazo (solo metadatos)
    new_deck = generate_deck()

    # Guardar en el nuevo archivo JSON
    save_deck_json(new_deck)
    print("=== Finalizado ===")