#!/usr/bin/env python3
"""
BuildDeckJson.py - Generador del mazo para la versión GUI
==========================================================
Lee las imágenes que YA tenés en assets/ y arma deck_gui.json con los
metadatos de cada carta + las rutas de sus 4 capas de imagen.

Reglas de asignación (según lo acordado):
  - Fuego  -> fondo rojo
  - Agua   -> fondo azul
  - Nieve  -> fondo morado (purple)
  - Valor >= 8 (cartas "altas") -> fondo amarillo
  - Pingüino central: random del pool assets/cards/*.png
  - Número: assets/numbers/<valor>.png
  - Ícono: assets/icons/icon_<elemento>.png

IMPORTANTE: los campos van en INGLÉS (element/value) porque así los
entiende el server.py. El nombre legible queda en 'name'.

Uso:
    python3 BuildDeckJson.py
"""

import json
import random
import os

# Rutas de assets
ASSETS_DIR = "assets"
CARDS_IMG_DIR = os.path.join(ASSETS_DIR, "cards")
NUMBERS_IMG_DIR = os.path.join(ASSETS_DIR, "numbers")
BACKGROUNDS_IMG_DIR = os.path.join(ASSETS_DIR, "backgrounds")
ICONS_IMG_DIR = os.path.join(ASSETS_DIR, "icons")

DECK_OUTPUT_FILE = "deck_gui.json"

# Rango de valores y elementos (en inglés para el server)
VALUES_RANGE = range(2, 11)        # 2..10
ELEMENTS = ["fire", "water", "snow"]
ELEMENT_ES = {"fire": "Fuego", "water": "Agua", "snow": "Nieve"}

# Fondo por elemento
ELEMENT_TO_BG = {
    "fire": "red.png",
    "water": "blue.png",
    "snow": "purple.png",
}

# Cartas altas -> amarillo
HIGH_VALUE_THRESHOLD = 8
HIGH_VALUE_BG = "yellow.png"

# Ícono por elemento
ELEMENT_TO_ICON = {
    "fire": "icon_fire.png",
    "water": "icon_water.png",
    "snow": "icon_snow.png",
}


def generate_deck():
    # Pool de pingüinos
    try:
        penguin_pool = sorted([f for f in os.listdir(CARDS_IMG_DIR) if f.endswith(".png")])
        if not penguin_pool:
            raise FileNotFoundError(f"No hay .png en {CARDS_IMG_DIR}")
        print(f"-> {len(penguin_pool)} pingüinos en el pool: {penguin_pool}")
    except FileNotFoundError as e:
        print(f"Error crítico: {e}")
        return None

    deck = []
    card_id = 0
    for element in ELEMENTS:
        for value in VALUES_RANGE:
            bg_file = HIGH_VALUE_BG if value >= HIGH_VALUE_THRESHOLD else ELEMENT_TO_BG[element]
            penguin_file = random.choice(penguin_pool)
            number_file = f"{value}.png"
            icon_file = ELEMENT_TO_ICON[element]

            deck.append({
                "id": card_id,
                "name": f"{ELEMENT_ES[element]} {value}",   # legible, opcional
                "element": element,                          # INGLÉS para el server
                "value": value,
                "assets": {
                    "background": os.path.join(BACKGROUNDS_IMG_DIR, bg_file).replace("\\", "/"),
                    "penguin": os.path.join(CARDS_IMG_DIR, penguin_file).replace("\\", "/"),
                    "number": os.path.join(NUMBERS_IMG_DIR, number_file).replace("\\", "/"),
                    "icon": os.path.join(ICONS_IMG_DIR, icon_file).replace("\\", "/"),
                },
            })
            card_id += 1

    print(f"-> Mazo generado con {len(deck)} cartas.")
    return deck


def save_deck(deck):
    if not deck:
        print("-> No se generó el mazo.")
        return
    data = {
        "_meta": {
            "total_cards": len(deck),
            "elements": ELEMENTS,
            "values_range": [min(VALUES_RANGE), max(VALUES_RANGE)],
        },
        "cards": deck,
    }
    with open(DECK_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"-> Guardado en {DECK_OUTPUT_FILE}")


if __name__ == "__main__":
    print("=== BuildDeckJson (GUI) ===")
    if not os.path.exists(ASSETS_DIR):
        print(f"Error: no existe '{ASSETS_DIR}/'.")
        raise SystemExit(1)
    save_deck(generate_deck())
    print("=== Finalizado ===")