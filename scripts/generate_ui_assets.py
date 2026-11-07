"""
Generate high-fidelity Warframe / Cephalon Ordis theme UI assets:
1. assets/icons/ordis_logo.png (Cephalon Ordis Holo-Core Logo)
2. assets/icons/btn_save.png (Holographic Save & Apply Icon)
3. assets/icons/btn_cancel.png (Holographic Cancel Icon)
4. assets/icons/settings.png (2-Tone HUD Settings Cog Icon)
"""
import os
import math
from PIL import Image, ImageDraw, ImageFilter

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ICONS_DIR = os.path.join(ROOT_DIR, "assets", "icons")

def ensure_dirs():
    os.makedirs(ICONS_DIR, exist_ok=True)

def generate_ordis_logo():
    """Cephalon Ordis holo-core logo: 256x256 RGBA.
    Features the iconic floating Orokin Cephalon diamond with dual cyan / glitch-crimson facets,
    concentric holo-rings, and digital scanline particles.
    """
    scale = 4
    w, h = 256 * scale, 256 * scale
    cx, cy = w // 2, h // 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Outer radial halo glow
    for r in range(int(100 * scale), int(30 * scale), -int(4 * scale)):
        alpha = int(45 * (1.0 - (r / (100.0 * scale))))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 210, 255, alpha))

    # Glitch secondary glow on the right
    glitch_cx, glitch_cy = cx + int(24 * scale), cy + int(10 * scale)
    for r in range(int(65 * scale), int(20 * scale), -int(4 * scale)):
        alpha = int(35 * (1.0 - (r / (65.0 * scale))))
        draw.ellipse([glitch_cx - r, glitch_cy - r, glitch_cx + r, glitch_cy + r], fill=(255, 45, 90, alpha))

    # 2. Concentric Orokin tech orbital rings
    for radius, width, stroke_rgba in [
        (92 * scale, 3 * scale, (0, 229, 255, 140)),
        (80 * scale, 1 * scale, (0, 180, 230, 90)),
        (68 * scale, 2 * scale, (0, 240, 255, 120)),
        (56 * scale, 1 * scale, (148, 163, 184, 80)),
    ]:
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=stroke_rgba, width=width)

    # Ring ticks and orbital telemetry nodes
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        r_inner = 90 * scale
        r_outer = 96 * scale
        x1 = cx + int(r_inner * math.cos(rad))
        y1 = cy + int(r_inner * math.sin(rad))
        x2 = cx + int(r_outer * math.cos(rad))
        y2 = cy + int(r_outer * math.sin(rad))
        draw.line([x1, y1, x2, y2], fill=(0, 240, 255, 180), width=2 * scale)

    # 3. Main Cephalon Ordis Diamond Geometry
    # Top vertex, Bottom vertex, Left vertex, Right vertex, Center
    top = (cx, cy - int(62 * scale))
    bottom = (cx, cy + int(62 * scale))
    left = (cx - int(54 * scale), cy)
    center = (cx, cy)
    right = (cx + int(54 * scale), cy)

    # Facet 1: Top-Left (Vibrant Cyan Cephalon Core)
    draw.polygon([top, left, center], fill=(0, 215, 255, 220), outline=(220, 255, 255, 255))
    # Facet 2: Bottom-Left (Deep Space Cyan)
    draw.polygon([left, bottom, center], fill=(0, 140, 200, 210), outline=(100, 230, 255, 240))

    # Facet 3: Top-Right (Glitch Shard - Fiery Crimson/Amber)
    # Give it a slight geometric glitch offset
    g_offset_x = int(5 * scale)
    g_offset_y = -int(3 * scale)
    draw.polygon([
        (top[0] + g_offset_x, top[1] + g_offset_y),
        (right[0] + g_offset_x, right[1] + g_offset_y),
        (center[0] + g_offset_x, center[1] + g_offset_y)
    ], fill=(255, 50, 85, 230), outline=(255, 190, 210, 255))

    # Facet 4: Bottom-Right (Deep Crimson / Dark Orokin Gold)
    draw.polygon([
        (right[0] + g_offset_x, right[1] + g_offset_y),
        (bottom[0] + g_offset_x, bottom[1] + g_offset_y),
        (center[0] + g_offset_x, center[1] + g_offset_y)
    ], fill=(200, 30, 60, 220), outline=(255, 120, 150, 240))

    # Glitch scanlines on the right shard
    for y_scan in range(cy - int(45 * scale), cy + int(45 * scale), int(6 * scale)):
        draw.line([
            cx + g_offset_x + int(4 * scale), y_scan,
            cx + g_offset_x + int(42 * scale), y_scan
        ], fill=(255, 220, 100, 160), width=1 * scale)

    # Central White-Hot Energy Core
    core_r = int(12 * scale)
    draw.ellipse([cx - core_r, cy - core_r, cx + core_r, cy + core_r], fill=(255, 255, 255, 255))
    draw.ellipse([cx - core_r - 4*scale, cy - core_r - 4*scale, cx + core_r + 4*scale, cy + core_r + 4*scale],
                 outline=(0, 240, 255, 200), width=2 * scale)

    # Floating corner telemetry markers (Aiming brackets)
    bracket_len = int(18 * scale)
    bracket_inset = int(82 * scale)
    for bx, by, sx, sy in [
        (cx - bracket_inset, cy - bracket_inset, 1, 1),
        (cx + bracket_inset, cy - bracket_inset, -1, 1),
        (cx - bracket_inset, cy + bracket_inset, 1, -1),
        (cx + bracket_inset, cy + bracket_inset, -1, -1),
    ]:
        draw.line([bx, by, bx + sx * bracket_len, by], fill=(0, 229, 255, 180), width=2 * scale)
        draw.line([bx, by, bx, by + sy * bracket_len], fill=(0, 229, 255, 180), width=2 * scale)

    # Downscale for high quality anti-aliasing
    final_img = img.resize((256, 256), Image.Resampling.LANCZOS)
    out_path = os.path.join(ICONS_DIR, "ordis_logo.png")
    final_img.save(out_path, "PNG")
    print(f"Generated {out_path}")

def generate_btn_save():
    """Holographic Save & Apply icon: 128x128 RGBA.
    Features a sleek glowing cyan data chip with a radiant checkmark.
    """
    scale = 4
    w, h = 128 * scale, 128 * scale
    cx, cy = w // 2, h // 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Subtle cyan radial glow
    for r in range(int(52 * scale), int(20 * scale), -int(3 * scale)):
        alpha = int(35 * (1.0 - (r / (52.0 * scale))))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 215, 255, alpha))

    # Hexagonal / Chamfered Tech Capsule
    box_w = int(42 * scale)
    box_h = int(42 * scale)
    ch = int(10 * scale)
    x1, y1 = cx - box_w, cy - box_h
    x2, y2 = cx + box_w, cy + box_h

    # Chamfered polygon
    poly = [
        (x1 + ch, y1),
        (x2 - ch, y1),
        (x2, y1 + ch),
        (x2, y2 - ch),
        (x2 - ch, y2),
        (x1 + ch, y2),
        (x1, y2 - ch),
        (x1, y1 + ch)
    ]
    # Background fill
    draw.polygon(poly, fill=(12, 22, 36, 220), outline=(0, 210, 255, 240))
    # Inner border
    inner_poly = [(px * 0.9 + cx * 0.1, py * 0.9 + cy * 0.1) for px, py in poly]
    draw.polygon(inner_poly, outline=(0, 180, 230, 90))

    # Radiant checkmark + data arrow
    # Checkmark points: left, bottom, top-right
    p1 = (cx - int(20 * scale), cy - int(2 * scale))
    p2 = (cx - int(6 * scale), cy + int(14 * scale))
    p3 = (cx + int(22 * scale), cy - int(16 * scale))

    # Glow line underneath
    draw.line([p1, p2, p3], fill=(0, 229, 255, 120), width=int(10 * scale), joint="round")
    # Core bright line
    draw.line([p1, p2, p3], fill=(255, 255, 255, 255), width=int(5 * scale), joint="round")

    final_img = img.resize((128, 128), Image.Resampling.LANCZOS)
    out_path = os.path.join(ICONS_DIR, "btn_save.png")
    final_img.save(out_path, "PNG")
    print(f"Generated {out_path}")

def generate_btn_cancel():
    """Holographic Cancel icon: 128x128 RGBA.
    Features a sleek high-tech circular glyph with stylized silver-cyan cross and tech nodes.
    """
    scale = 4
    w, h = 128 * scale, 128 * scale
    cx, cy = w // 2, h // 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Subtle ambient slate-crimson glow
    for r in range(int(50 * scale), int(20 * scale), -int(3 * scale)):
        alpha = int(25 * (1.0 - (r / (50.0 * scale))))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(244, 63, 94, alpha))

    # Outer circle / orbital ring
    r_outer = int(42 * scale)
    draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
                 fill=(18, 24, 38, 220), outline=(71, 85, 105, 240), width=int(2 * scale))

    # Accent arcs on top and bottom
    draw.arc([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
             start=35, end=145, fill=(0, 210, 255, 200), width=int(3 * scale))
    draw.arc([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
             start=215, end=325, fill=(244, 63, 94, 200), width=int(3 * scale))

    # Tech Cross 'X'
    arm = int(18 * scale)
    # Glow underneath
    for dx, dy in [(-1, -1), (1, 1), (-1, 1), (1, -1)]:
        pass
    draw.line([cx - arm, cy - arm, cx + arm, cy + arm], fill=(244, 63, 94, 120), width=int(9 * scale), joint="round")
    draw.line([cx - arm, cy + arm, cx + arm, cy - arm], fill=(244, 63, 94, 120), width=int(9 * scale), joint="round")

    # Core crisp white-slate line
    draw.line([cx - arm, cy - arm, cx + arm, cy + arm], fill=(248, 250, 252, 255), width=int(4 * scale), joint="round")
    draw.line([cx - arm, cy + arm, cx + arm, cy - arm], fill=(248, 250, 252, 255), width=int(4 * scale), joint="round")

    # Center dot
    dot_r = int(3 * scale)
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=(0, 229, 255, 240))

    final_img = img.resize((128, 128), Image.Resampling.LANCZOS)
    out_path = os.path.join(ICONS_DIR, "btn_cancel.png")
    final_img.save(out_path, "PNG")
    print(f"Generated {out_path}")

def generate_settings_icon():
    """2-tone HUD Settings Gear icon: 128x128 RGBA.
    Matches the existing assets/icons style.
    """
    scale = 4
    w, h = 128 * scale, 128 * scale
    cx, cy = w // 2, h // 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 8-tooth gear geometry
    num_teeth = 8
    r_outer = 44 * scale
    r_inner = 35 * scale
    r_hole = 16 * scale

    points = []
    for i in range(num_teeth):
        angle_base = i * (360.0 / num_teeth)
        # Tooth width angle ~ 18 deg
        a1 = math.radians(angle_base - 10)
        a2 = math.radians(angle_base - 6)
        a3 = math.radians(angle_base + 6)
        a4 = math.radians(angle_base + 10)
        a_next = math.radians(angle_base + (360.0 / num_teeth) - 10)

        points.append((cx + int(r_inner * math.cos(a1)), cy + int(r_inner * math.sin(a1))))
        points.append((cx + int(r_outer * math.cos(a2)), cy + int(r_outer * math.sin(a2))))
        points.append((cx + int(r_outer * math.cos(a3)), cy + int(r_outer * math.sin(a3))))
        points.append((cx + int(r_inner * math.cos(a4)), cy + int(r_inner * math.sin(a4))))

    # Draw gear body
    draw.polygon(points, fill=(18, 24, 38, 230), outline=(0, 229, 255, 255))
    # Gear border accent
    draw.ellipse([cx - r_inner + 4*scale, cy - r_inner + 4*scale, cx + r_inner - 4*scale, cy + r_inner - 4*scale],
                 outline=(0, 180, 230, 120), width=int(2 * scale))
    # Inner hole
    draw.ellipse([cx - r_hole, cy - r_hole, cx + r_hole, cy + r_hole], fill=(12, 16, 23, 255), outline=(0, 229, 255, 240), width=int(3 * scale))
    # Core diamond
    cd = int(7 * scale)
    draw.polygon([(cx, cy - cd), (cx + cd, cy), (cx, cy + cd), (cx - cd, cy)], fill=(0, 240, 255, 255))

    final_img = img.resize((128, 128), Image.Resampling.LANCZOS)
    out_path = os.path.join(ICONS_DIR, "settings.png")
    final_img.save(out_path, "PNG")
    print(f"Generated {out_path}")

def build_all():
    ensure_dirs()
    generate_ordis_logo()
    generate_btn_save()
    generate_btn_cancel()
    generate_settings_icon()
    print("All UI assets successfully generated!")

if __name__ == "__main__":
    build_all()
