#!/usr/bin/env python3
"""
generate_deck.py - Generador local de assets de Card-Jitsu
===========================================================
Reemplaza el scraper. Genera localmente:
  - assets/cards/refs/   -> 30 imágenes "ref" de pingüinos por elemento+valor
  - assets/icons/        -> 3 íconos de elementos (llama, copo, gota)
  - deck.json            -> mazo con 30 cartas (10 fuego + 10 nieve + 10 agua)

Sin red, sin scraping, sin dependencias de Fandom. 100% reproducible.

Uso:
    pip install pillow --break-system-packages
    python3 generate_deck.py
"""

import json
import random
import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    print("Falta la librería Pillow. Instalala con:")
    print("    pip install pillow --break-system-packages")
    raise SystemExit(1)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
ASSETS_DIR = Path("assets")
CARDS_REFS_DIR = ASSETS_DIR / "cards" / "refs"
ICONS_DIR = ASSETS_DIR / "icons"
PENGUINS_DIR = ASSETS_DIR / "penguins"
BG_DIR = ASSETS_DIR / "backgrounds"
UI_DIR = ASSETS_DIR / "ui"
FONTS_DIR = ASSETS_DIR / "fonts"
DECK_JSON = Path("deck.json")

# Paleta de colores de Club Penguin
COLORS = {
    "fire":  (228, 76, 60),     # rojo Card-Jitsu
    "snow":  (91, 192, 235),    # celeste Card-Jitsu
    "water": (52, 152, 219),    # azul Card-Jitsu
    "fire_dark":  (180, 40, 30),
    "snow_dark":  (50, 140, 200),
    "water_dark": (30, 100, 180),
    "fire_light":  (255, 180, 50),
    "snow_light":  (220, 240, 255),
    "water_light": (150, 220, 255),
}

# Tamaños
REF_SIZE = (300, 300)     # Tamaño de cada imagen de referencia
ICON_SIZE = (96, 96)      # Tamaño de los íconos de elemento

# Cuántas cartas por elemento y rango de valores (2-10 según pediste)
ELEMENTS = ["fire", "snow", "water"]
VALUES_PER_ELEMENT = list(range(2, 11))   # 9 valores: 2,3,4,5,6,7,8,9,10
# Vamos a generar varias variantes por elemento+valor para tener variedad visual.
# El cliente al pedir una carta del mazo elegirá una variante random.
VARIANTS_PER_COMBO = 2     # 2 dibujos distintos por (elemento, valor)

# ---------------------------------------------------------------------------
# Generación de imágenes
# ---------------------------------------------------------------------------
def ensure_dirs():
    for d in (CARDS_REFS_DIR, ICONS_DIR, PENGUINS_DIR, BG_DIR, UI_DIR, FONTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

def draw_penguin_silhouette(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                             body_color, beak_color=(255, 180, 30),
                             eye_color=(0, 0, 0), pose: str = "stand",
                             scale: float = 1.0):
    """
    Dibuja una silueta de pingüino estilo Club Penguin con formas básicas.
    pose: 'stand' (parado), 'throw' (lanzando), 'duck' (agachado).
    """
    s = scale
    # Cuerpo (óvalo grande)
    body_w = int(110 * s)
    body_h = int(135 * s)
    if pose == "duck":
        body_h = int(95 * s)   # más bajo si agachado
        cy = cy + int(20 * s)

    # Cabeza
    head_r = int(50 * s)
    head_cy = cy - body_h // 2 - head_r // 3
    if pose == "throw":
        head_cy -= int(10 * s)

    # Cuerpo elipse
    draw.ellipse(
        [cx - body_w // 2, cy - body_h // 2,
         cx + body_w // 2, cy + body_h // 2],
        fill=body_color, outline=(0, 0, 0), width=3
    )
    # Panza blanca
    belly_w = int(body_w * 0.65)
    belly_h = int(body_h * 0.75)
    draw.ellipse(
        [cx - belly_w // 2, cy - belly_h // 2 + int(15 * s),
         cx + belly_w // 2, cy + belly_h // 2 + int(15 * s)],
        fill=(255, 255, 255)
    )
    # Cabeza
    draw.ellipse(
        [cx - head_r, head_cy - head_r,
         cx + head_r, head_cy + head_r],
        fill=body_color, outline=(0, 0, 0), width=3
    )
    # Ojos
    eye_off_x = int(15 * s)
    eye_off_y = int(8 * s)
    eye_r = int(8 * s)
    for ex in (-eye_off_x, eye_off_x):
        # Blanco del ojo
        draw.ellipse(
            [cx + ex - eye_r, head_cy - eye_off_y - eye_r,
             cx + ex + eye_r, head_cy - eye_off_y + eye_r],
            fill=(255, 255, 255), outline=(0, 0, 0), width=2
        )
        # Pupila
        pupil_r = int(4 * s)
        draw.ellipse(
            [cx + ex - pupil_r, head_cy - eye_off_y - pupil_r + 2,
             cx + ex + pupil_r, head_cy - eye_off_y + pupil_r + 2],
            fill=eye_color
        )
    # Pico naranja
    beak_w = int(22 * s)
    beak_h = int(14 * s)
    beak_y = head_cy + int(8 * s)
    draw.polygon(
        [(cx - beak_w // 2, beak_y),
         (cx + beak_w // 2, beak_y),
         (cx, beak_y + beak_h)],
        fill=beak_color, outline=(150, 90, 0)
    )
    # Aletas (alas)
    flap_w = int(18 * s)
    flap_h = int(50 * s)
    flap_y = cy - int(15 * s)
    if pose == "throw":
        # Aleta derecha levantada
        draw.ellipse(
            [cx + body_w // 2 - 5, flap_y - int(40 * s),
             cx + body_w // 2 + flap_w + 15, flap_y + int(10 * s)],
            fill=body_color, outline=(0, 0, 0), width=2
        )
        # Aleta izquierda normal
        draw.ellipse(
            [cx - body_w // 2 - flap_w, flap_y,
             cx - body_w // 2 + 5, flap_y + flap_h],
            fill=body_color, outline=(0, 0, 0), width=2
        )
    else:
        # Ambas aletas a los lados
        for sx in (-1, 1):
            draw.ellipse(
                [cx + sx * (body_w // 2) - (flap_w if sx > 0 else 0) +
                 (0 if sx > 0 else -flap_w),
                 flap_y,
                 cx + sx * (body_w // 2) + (flap_w if sx > 0 else 0) +
                 (flap_w if sx > 0 else 0),
                 flap_y + flap_h],
                fill=body_color, outline=(0, 0, 0), width=2
            )
    # Patas
    foot_w = int(20 * s)
    foot_h = int(10 * s)
    foot_y = cy + body_h // 2 - int(5 * s)
    for sx in (-1, 1):
        draw.ellipse(
            [cx + sx * int(20 * s) - foot_w // 2, foot_y,
             cx + sx * int(20 * s) + foot_w // 2, foot_y + foot_h],
            fill=beak_color, outline=(150, 90, 0)
        )

def add_fire_effects(img: Image.Image, draw: ImageDraw.ImageDraw):
    """Añade chispas y aura naranja al fondo."""
    w, h = img.size
    # Llamas en la base
    for _ in range(8):
        x = random.randint(20, w - 20)
        y = random.randint(h - 80, h - 10)
        r = random.randint(8, 18)
        color = random.choice([(255, 100, 0, 180), (255, 200, 0, 200), (255, 50, 0, 160)])
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    # Chispas pequeñas dispersas
    for _ in range(15):
        x = random.randint(5, w - 5)
        y = random.randint(5, h - 5)
        r = random.randint(2, 5)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 230, 80, 200))

def add_snow_effects(img: Image.Image, draw: ImageDraw.ImageDraw):
    """Añade copos de nieve y aura fría."""
    w, h = img.size
    for _ in range(35):
        x = random.randint(5, w - 5)
        y = random.randint(5, h - 5)
        r = random.randint(3, 7)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 220))
        # cruz del copo
        draw.line([x - r, y, x + r, y], fill=(220, 240, 255), width=1)
        draw.line([x, y - r, x, y + r], fill=(220, 240, 255), width=1)

def add_water_effects(img: Image.Image, draw: ImageDraw.ImageDraw):
    """Añade gotas y olas."""
    w, h = img.size
    # Olas en la base
    for i, y in enumerate([h - 60, h - 35, h - 15]):
        points = []
        for x in range(0, w + 20, 20):
            offset = int(8 * math.sin(x * 0.1 + i))
            points.append((x, y + offset))
        if len(points) >= 2:
            for j in range(len(points) - 1):
                draw.line([points[j], points[j + 1]],
                         fill=(100, 180, 255, 180), width=4)
    # Gotitas
    for _ in range(10):
        x = random.randint(10, w - 10)
        y = random.randint(10, h // 2)
        r = random.randint(3, 6)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(150, 220, 255, 200))

def make_ref_image(element: str, value: int, variant: int, seed: int) -> Path:
    """
    Crea una imagen de referencia: silueta de pingüino + efectos del elemento.
    Esta imagen va al CENTRO de la carta. La carta completa (con borde, número,
    ícono) se ensambla en el cliente Pygame al vuelo.
    """
    random.seed(seed)  # Reproducible: misma combo → mismo dibujo

    # Fondo neutro gris para que la imagen quede bien sobre cualquier carta
    img = Image.new("RGBA", REF_SIZE, (180, 180, 180, 255))

    # Capa de efectos detrás del pingüino
    fx_layer = Image.new("RGBA", REF_SIZE, (0, 0, 0, 0))
    fx_draw = ImageDraw.Draw(fx_layer)
    if element == "fire":
        add_fire_effects(fx_layer, fx_draw)
    elif element == "snow":
        add_snow_effects(fx_layer, fx_draw)
    else:
        add_water_effects(fx_layer, fx_draw)
    img = Image.alpha_composite(img, fx_layer)

    # Pingüino central (pose varía con valor + variante)
    draw = ImageDraw.Draw(img)
    poses = ["stand", "throw", "duck"]
    pose = poses[(value + variant) % len(poses)]

    # Color del cuerpo del pingüino: usamos el color del elemento como acento
    body_colors = {
        "fire": [(228, 76, 60), (255, 100, 80), (200, 60, 50)],
        "snow": [(91, 192, 235), (130, 210, 240), (60, 150, 200)],
        "water": [(52, 152, 219), (90, 180, 230), (30, 120, 200)],
    }
    body_color = random.choice(body_colors[element])
    draw_penguin_silhouette(draw, REF_SIZE[0] // 2, REF_SIZE[1] // 2 - 10,
                             body_color, pose=pose, scale=1.0)

    # Guardar
    filename = f"ref_{element}_{value:02d}_v{variant}.png"
    out = CARDS_REFS_DIR / filename
    img.save(out)
    return out

def make_icon(element: str):
    """Crea el ícono del elemento (llama, copo, gota) tipo el de la imagen
    de referencia que mandó el usuario."""
    img = Image.new("RGBA", ICON_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    w, h = ICON_SIZE
    cx, cy = w // 2, h // 2

    if element == "fire":
        # Llama: triángulo + óvalo amarillo dentro
        flame_points = [
            (cx, 10),
            (cx - 32, cy + 5),
            (cx - 25, cy + 25),
            (cx - 30, h - 12),
            (cx, h - 18),
            (cx + 30, h - 12),
            (cx + 25, cy + 25),
            (cx + 32, cy + 5),
        ]
        draw.polygon(flame_points, fill=(228, 60, 50), outline=(120, 0, 0))
        # núcleo amarillo
        draw.ellipse([cx - 18, cy - 5, cx + 18, cy + 30],
                    fill=(255, 200, 50), outline=(255, 140, 0), width=2)
    elif element == "snow":
        # Copo: estrella de 6 puntas
        outer_r, inner_r = 38, 12
        points = []
        for i in range(12):
            angle = i * (math.pi / 6) - math.pi / 2
            r = outer_r if i % 2 == 0 else inner_r
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(points, fill=(220, 240, 255), outline=(100, 150, 220), width=2)
        # centro azul
        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8],
                    fill=(91, 192, 235), outline=(50, 140, 200), width=2)
    else:  # water
        # Gota de agua: círculo + triángulo arriba
        drop_points = [
            (cx, 8),
            (cx - 8, 25),
            (cx - 30, cy + 5),
        ]
        # Cuerpo redondo
        draw.ellipse([cx - 32, cy - 10, cx + 32, h - 8],
                    fill=(52, 152, 219), outline=(20, 90, 160), width=2)
        # Punta superior
        draw.polygon([(cx, 5), (cx - 22, cy + 5), (cx + 22, cy + 5)],
                    fill=(52, 152, 219), outline=(20, 90, 160))
        # brillo blanco
        draw.ellipse([cx - 14, cy - 5, cx - 4, cy + 8],
                    fill=(200, 230, 255, 200))

    out = ICONS_DIR / f"icon_{element}.png"
    img.save(out)
    return out

def make_card_back():
    """Reverso de carta (azul con logo abstracto), para mostrar la mano del rival."""
    img = Image.new("RGBA", REF_SIZE, (27, 79, 156, 255))   # azul Club Penguin
    draw = ImageDraw.Draw(img)
    w, h = REF_SIZE
    # Patrón decorativo: rombos amarillos
    for x in range(20, w, 60):
        for y in range(20, h, 60):
            draw.polygon(
                [(x, y - 12), (x + 12, y), (x, y + 12), (x - 12, y)],
                fill=(255, 199, 44), outline=(200, 140, 0)
            )
    # Logo central: "C-J"
    try:
        # ImageFont default
        from PIL import ImageFont
        font = ImageFont.load_default()
        draw.text((w // 2 - 20, h // 2 - 10), "C-J", fill=(255, 255, 255), font=font)
    except Exception:
        draw.text((w // 2 - 20, h // 2 - 10), "C-J", fill=(255, 255, 255))
    out = ICONS_DIR / "card_back.png"
    img.save(out)
    return out

# ---------------------------------------------------------------------------
# Generación del deck.json
# ---------------------------------------------------------------------------
def generate_deck():
    cards = []
    next_id = 0
    for element in ELEMENTS:
        for value in VALUES_PER_ELEMENT:
            for variant in range(VARIANTS_PER_COMBO):
                seed = hash((element, value, variant)) & 0xFFFFFFFF
                ref_path = make_ref_image(element, value, variant, seed)
                cards.append({
                    "id": next_id,
                    "element": element,
                    "value": value,
                    "color": "blue",     # marco azul como en la imagen de ref
                    "ref_image": ref_path.name,
                })
                next_id += 1

    deck_data = {
        "_meta": {
            "source": "Generated locally with PIL/Pillow",
            "total_cards": len(cards),
            "elements": ELEMENTS,
            "values_range": [min(VALUES_PER_ELEMENT), max(VALUES_PER_ELEMENT)],
        },
        "cards": cards,
    }
    DECK_JSON.write_text(json.dumps(deck_data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return len(cards)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("  Card-Jitsu Asset Generator (local, sin scraping)")
    print("=" * 70)

    ensure_dirs()
    print("\n→ Generando íconos de elementos...")
    for el in ELEMENTS:
        p = make_icon(el)
        print(f"   ✓ {p}")

    print("\n→ Generando reverso de carta...")
    p = make_card_back()
    print(f"   ✓ {p}")

    print(f"\n→ Generando imágenes de referencia "
          f"({len(ELEMENTS)} × {len(VALUES_PER_ELEMENT)} × {VARIANTS_PER_COMBO} variantes)...")
    n_cards = generate_deck()
    print(f"   ✓ {n_cards} cartas generadas en {CARDS_REFS_DIR}/")

    print(f"\n→ Mazo escrito en {DECK_JSON}")

    print("\n" + "=" * 70)
    print(f"  ✓ Listo. {n_cards} cartas, 3 íconos, 1 reverso.")
    print(f"  Carpetas:")
    print(f"    {CARDS_REFS_DIR}/")
    print(f"    {ICONS_DIR}/")
    print(f"  Archivo: {DECK_JSON}")
    print("=" * 70)

if __name__ == "__main__":
    main()