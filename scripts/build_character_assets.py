import os
import cv2
import numpy as np

def make_blank(size=(1024, 1024)):
    return np.zeros((size[1], size[0], 4), dtype=np.uint8)

def save_scaled(img_1024, path, size=(512, 512)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scaled = cv2.resize(img_1024, size, interpolation=cv2.INTER_AREA)
    cv2.imwrite(path, scaled)

def overlay_rgba(base, top):
    t_a = top[:, :, 3:4] / 255.0
    b_a = base[:, :, 3:4] / 255.0
    out_rgb = top[:, :, :3] * t_a + base[:, :, :3] * b_a * (1.0 - t_a)
    out_a = np.clip(t_a + b_a * (1.0 - t_a), 0.0, 1.0) * 255.0
    mask = (out_a > 0)[:, :, 0]
    res = np.zeros_like(base)
    res[mask, :3] = np.clip(out_rgb[mask] / (out_a[mask] / 255.0), 0, 255).astype(np.uint8)
    res[:, :, 3] = out_a[:, :, 0].astype(np.uint8)
    return res

def build_all():
    brain_dir = r"C:\Users\2doo2\.gemini\antigravity\brain\31d11e8c-04e6-4093-9842-8dd91ea390c1"
    body_idle_1024 = cv2.imread(os.path.join(brain_dir, "test_solid_body.png"), cv2.IMREAD_UNCHANGED)
    body_glitch_1024 = cv2.imread(os.path.join(brain_dir, "test_solid_glitch_body.png"), cv2.IMREAD_UNCHANGED)
    hands_idle_1024 = cv2.imread(os.path.join(brain_dir, "test_hands_canvas.png"), cv2.IMREAD_UNCHANGED)

    # 1. Clean body chassis: remove any stray outer background noise outside [235, 765]
    body_clean_mask = np.zeros(body_idle_1024.shape[:2], dtype=bool)
    body_clean_mask[:, 235:765] = True
    # halo extends slightly wider at top: y < 220, x between 280 and 720
    body_idle_1024[~body_clean_mask] = 0
    body_glitch_1024[~body_clean_mask] = 0

    # 2. Clean hands canvas: precisely keep only the two main hand components (area > 5000)
    alpha_h = (hands_idle_1024[:, :, 3] > 20).astype(np.uint8)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(alpha_h)
    h_clean = np.zeros_like(hands_idle_1024)
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] > 5000:
            h_clean[labels == i] = hands_idle_1024[labels == i]
    hands_idle_1024 = h_clean

    # Hands happy: hands shifted up and slightly rotated
    hands_happy_1024 = np.zeros_like(hands_idle_1024)
    # left hand shifted up 35px
    lh_part = hands_idle_1024[380:560, 130:290]
    hands_happy_1024[345:525, 125:285] = lh_part
    # right hand mirrored wave
    rh_part = hands_idle_1024[550:730, 720:880]
    hands_happy_1024[505:685, 725:885] = rh_part

    # Hands glitch: add subtle red electricity / shift
    hands_glitch_1024 = hands_idle_1024.copy()
    # tint cyan palms to red
    h_mask = hands_glitch_1024[:, :, 3] > 50
    # swap cyan (BGR: 255, 240, 0) to crimson (BGR: 40, 40, 255)
    is_cyan = h_mask & (hands_glitch_1024[:, :, 0] > 180) & (hands_glitch_1024[:, :, 2] < 80)
    hands_glitch_1024[is_cyan, 0] = 30
    hands_glitch_1024[is_cyan, 1] = 30
    hands_glitch_1024[is_cyan, 2] = 255

    # -------------------------------------------------------------
    # 1. EYES
    # -------------------------------------------------------------
    # Left eye: cx=415, cy=445; Right eye: cx=575, cy=445
    CYAN_GLOW = (255, 230, 0, 90)
    CYAN_CORE = (255, 250, 0, 245)
    WHITE_SPEC = (255, 255, 255, 255)

    # 1.1 Eye Idle
    eye_idle = make_blank()
    for cx, cy in [(415, 445), (575, 445)]:
        cv2.ellipse(eye_idle, (cx, cy), (34, 46), 0, 0, 360, CYAN_GLOW, -1, cv2.LINE_AA)
        cv2.ellipse(eye_idle, (cx, cy), (28, 40), 0, 0, 360, CYAN_CORE, -1, cv2.LINE_AA)
        # Scanline dot-matrix pattern inside eye
        for y_scan in range(cy - 36, cy + 38, 6):
            cv2.line(eye_idle, (cx - 24, y_scan), (cx + 24, y_scan), (220, 255, 200, 180), 2, cv2.LINE_AA)
        # White highlight twinkle
        cv2.circle(eye_idle, (cx + 10, cy - 14), 7, WHITE_SPEC, -1, cv2.LINE_AA)
        cv2.circle(eye_idle, (cx - 10, cy + 14), 4, WHITE_SPEC, -1, cv2.LINE_AA)

    # 1.2 Eye Blink
    eye_blink = make_blank()
    for cx, cy in [(415, 452), (575, 452)]:
        cv2.line(eye_blink, (cx - 28, cy), (cx + 28, cy), CYAN_GLOW, 12, cv2.LINE_AA)
        cv2.line(eye_blink, (cx - 26, cy), (cx + 26, cy), CYAN_CORE, 7, cv2.LINE_AA)
        cv2.line(eye_blink, (cx - 24, cy), (cx + 24, cy), WHITE_SPEC, 3, cv2.LINE_AA)

    # 1.3 Eye Happy (^^ crescent)
    eye_happy = make_blank()
    for cx, cy in [(415, 450), (575, 450)]:
        pts = []
        for deg in range(25, 155, 5):
            rad = np.radians(deg)
            x = int(cx - 30 * np.cos(rad))
            y = int(cy - 24 * np.sin(rad))
            pts.append([x, y])
        pts = np.array(pts, np.int32)
        cv2.polylines(eye_happy, [pts], False, CYAN_GLOW, 14, cv2.LINE_AA)
        cv2.polylines(eye_happy, [pts], False, CYAN_CORE, 8, cv2.LINE_AA)
        cv2.polylines(eye_happy, [pts], False, WHITE_SPEC, 4, cv2.LINE_AA)

    # 1.4 Eye Thinking (shifted up-right)
    eye_thinking = make_blank()
    for cx, cy in [(425, 435), (585, 435)]:
        cv2.ellipse(eye_thinking, (cx, cy), (32, 42), 5, 0, 360, CYAN_GLOW, -1, cv2.LINE_AA)
        cv2.ellipse(eye_thinking, (cx, cy), (26, 36), 5, 0, 360, CYAN_CORE, -1, cv2.LINE_AA)
        cv2.circle(eye_thinking, (cx + 8, cy - 12), 7, WHITE_SPEC, -1, cv2.LINE_AA)

    # 1.5 Eye Worried (drooping)
    eye_worried = make_blank()
    for cx, cy, tilt in [(415, 448, 15), (575, 448, -15)]:
        cv2.ellipse(eye_worried, (cx, cy), (30, 42), tilt, 0, 360, CYAN_GLOW, -1, cv2.LINE_AA)
        cv2.ellipse(eye_worried, (cx, cy), (24, 36), tilt, 0, 360, CYAN_CORE, -1, cv2.LINE_AA)
        cv2.circle(eye_worried, (cx + (4 if tilt>0 else -4), cy - 10), 6, WHITE_SPEC, -1, cv2.LINE_AA)

    # 1.6 Eye Glitch (Crimson Red 'X' and slashes)
    RED_GLOW = (30, 20, 255, 120)
    RED_CORE = (50, 40, 255, 250)
    eye_glitch = make_blank()
    for cx, cy in [(415, 445), (575, 445)]:
        cv2.line(eye_glitch, (cx - 24, cy - 24), (cx + 24, cy + 24), RED_GLOW, 14, cv2.LINE_AA)
        cv2.line(eye_glitch, (cx + 24, cy - 24), (cx - 24, cy + 24), RED_GLOW, 14, cv2.LINE_AA)
        cv2.line(eye_glitch, (cx - 24, cy - 24), (cx + 24, cy + 24), RED_CORE, 7, cv2.LINE_AA)
        cv2.line(eye_glitch, (cx + 24, cy - 24), (cx - 24, cy + 24), RED_CORE, 7, cv2.LINE_AA)
        cv2.line(eye_glitch, (cx - 20, cy - 20), (cx + 20, cy + 20), (180, 180, 255, 255), 3, cv2.LINE_AA)
        cv2.line(eye_glitch, (cx + 20, cy - 20), (cx - 20, cy + 20), (180, 180, 255, 255), 3, cv2.LINE_AA)

    # -------------------------------------------------------------
    # 2. MOUTH
    # -------------------------------------------------------------
    # 2.1 Mouth Idle (w curve)
    mouth_idle = make_blank()
    pts1 = np.array([[468, 498], [478, 512], [495, 512], [497, 505]], np.int32)
    pts2 = np.array([[497, 505], [499, 512], [516, 512], [526, 498]], np.int32)
    cv2.polylines(mouth_idle, [pts1, pts2], False, CYAN_GLOW, 10, cv2.LINE_AA)
    cv2.polylines(mouth_idle, [pts1, pts2], False, CYAN_CORE, 5, cv2.LINE_AA)
    cv2.polylines(mouth_idle, [pts1, pts2], False, WHITE_SPEC, 2, cv2.LINE_AA)

    # 2.2 Mouth Open Small (Lip sync frame 1)
    mouth_open_small = make_blank()
    cv2.ellipse(mouth_open_small, (497, 514), (16, 12), 0, 0, 360, (255, 230, 0, 120), -1, cv2.LINE_AA)
    cv2.ellipse(mouth_open_small, (497, 514), (14, 10), 0, 0, 360, CYAN_CORE, 3, cv2.LINE_AA)

    # 2.3 Mouth Open Big (Lip sync frame 2)
    mouth_open_big = make_blank()
    cv2.ellipse(mouth_open_big, (497, 518), (22, 18), 0, 0, 360, (255, 230, 0, 140), -1, cv2.LINE_AA)
    cv2.ellipse(mouth_open_big, (497, 518), (20, 16), 0, 0, 360, CYAN_CORE, 4, cv2.LINE_AA)

    # 2.4 Mouth Glitch (jagged electric red zigzag)
    mouth_glitch = make_blank()
    z_pts = np.array([
        [465, 512], [475, 506], [485, 518], [497, 506], [509, 518], [519, 506], [529, 512]
    ], np.int32)
    cv2.polylines(mouth_glitch, [z_pts], False, RED_GLOW, 10, cv2.LINE_AA)
    cv2.polylines(mouth_glitch, [z_pts], False, RED_CORE, 5, cv2.LINE_AA)

    # -------------------------------------------------------------
    # 3. BROWS (placed neatly inside visor right above eyes at cy=412)
    # -------------------------------------------------------------
    brow_idle = make_blank()
    for cx, cy, tilt in [(415, 412, -4), (575, 412, 4)]:
        cv2.ellipse(brow_idle, (cx, cy), (20, 5), tilt, 0, 360, CYAN_GLOW, -1, cv2.LINE_AA)
        cv2.ellipse(brow_idle, (cx, cy), (16, 3), tilt, 0, 360, CYAN_CORE, -1, cv2.LINE_AA)

    brow_angry = make_blank()
    for cx, cy, tilt in [(415, 410, 20), (575, 410, -20)]:
        cv2.ellipse(brow_angry, (cx, cy), (22, 6), tilt, 0, 360, RED_GLOW, -1, cv2.LINE_AA)
        cv2.ellipse(brow_angry, (cx, cy), (18, 4), tilt, 0, 360, RED_CORE, -1, cv2.LINE_AA)

    brow_worried = make_blank()
    for cx, cy, tilt in [(415, 410, -20), (575, 410, 20)]:
        cv2.ellipse(brow_worried, (cx, cy), (20, 5), tilt, 0, 360, CYAN_GLOW, -1, cv2.LINE_AA)
        cv2.ellipse(brow_worried, (cx, cy), (16, 3), tilt, 0, 360, CYAN_CORE, -1, cv2.LINE_AA)

    # -------------------------------------------------------------
    # 4. VFX
    # -------------------------------------------------------------
    # 4.1 Blush
    vfx_blush = make_blank()
    for cx, cy, tilt in [(375, 488, -6), (615, 488, 6)]:
        cv2.ellipse(vfx_blush, (cx, cy), (22, 11), tilt, 0, 360, (255, 160, 50, 140), -1, cv2.LINE_AA)
        cv2.ellipse(vfx_blush, (cx, cy), (15, 7), tilt, 0, 360, (255, 240, 120, 200), -1, cv2.LINE_AA)

    # 4.2 Sweat
    vfx_sweat = make_blank()
    cv2.ellipse(vfx_sweat, (640, 385), (10, 16), -20, 0, 360, (255, 240, 0, 180), -1, cv2.LINE_AA)
    cv2.circle(vfx_sweat, (637, 380), 4, WHITE_SPEC, -1, cv2.LINE_AA)

    # -------------------------------------------------------------
    # SAVE ALL LAYERS (512x512)
    # -------------------------------------------------------------
    out_dir = r"assets\character\layers"
    save_scaled(body_idle_1024, os.path.join(out_dir, "body", "body_idle.png"))
    save_scaled(body_glitch_1024, os.path.join(out_dir, "body", "body_glitch.png"))

    # Unified hands (legacy backward compatibility)
    save_scaled(hands_idle_1024, os.path.join(out_dir, "hands", "hand_idle.png"))
    save_scaled(hands_happy_1024, os.path.join(out_dir, "hands", "hand_happy.png"))
    save_scaled(hands_glitch_1024, os.path.join(out_dir, "hands", "hand_glitch.png"))

    # Separated Left and Right hands (for independent phase-shifted floating & gestures)
    hands_left_canvas = np.zeros_like(hands_idle_1024)
    hands_left_canvas[380:560, 130:290] = hands_idle_1024[380:560, 130:290]
    save_scaled(hands_left_canvas, os.path.join(out_dir, "hands", "hand_left.png"))

    hands_right_canvas = np.zeros_like(hands_idle_1024)
    hands_right_canvas[550:730, 720:880] = hands_idle_1024[550:730, 720:880]
    save_scaled(hands_right_canvas, os.path.join(out_dir, "hands", "hand_right.png"))

    hands_left_happy = np.zeros_like(hands_happy_1024)
    hands_left_happy[345:525, 125:285] = hands_happy_1024[345:525, 125:285]
    save_scaled(hands_left_happy, os.path.join(out_dir, "hands", "hand_left_happy.png"))

    hands_right_happy = np.zeros_like(hands_happy_1024)
    hands_right_happy[505:685, 725:885] = hands_happy_1024[505:685, 725:885]
    save_scaled(hands_right_happy, os.path.join(out_dir, "hands", "hand_right_happy.png"))

    save_scaled(eye_idle, os.path.join(out_dir, "eyes", "eye_idle.png"))
    save_scaled(eye_blink, os.path.join(out_dir, "eyes", "eye_blink.png"))
    save_scaled(eye_happy, os.path.join(out_dir, "eyes", "eye_happy.png"))
    save_scaled(eye_thinking, os.path.join(out_dir, "eyes", "eye_thinking.png"))
    save_scaled(eye_worried, os.path.join(out_dir, "eyes", "eye_worried.png"))
    save_scaled(eye_glitch, os.path.join(out_dir, "eyes", "eye_glitch.png"))

    save_scaled(mouth_idle, os.path.join(out_dir, "mouth", "mouth_idle.png"))
    save_scaled(mouth_open_small, os.path.join(out_dir, "mouth", "mouth_open_small.png"))
    save_scaled(mouth_open_big, os.path.join(out_dir, "mouth", "mouth_open_big.png"))
    save_scaled(mouth_glitch, os.path.join(out_dir, "mouth", "mouth_glitch.png"))

    save_scaled(brow_idle, os.path.join(out_dir, "brows", "brow_idle.png"))
    save_scaled(brow_angry, os.path.join(out_dir, "brows", "brow_angry.png"))
    save_scaled(brow_angry, os.path.join(out_dir, "brows", "brow_glitch.png"))
    save_scaled(brow_worried, os.path.join(out_dir, "brows", "brow_worried.png"))

    save_scaled(vfx_blush, os.path.join(out_dir, "vfx", "vfx_blush.png"))
    save_scaled(vfx_sweat, os.path.join(out_dir, "vfx", "vfx_sweat.png"))

    # -------------------------------------------------------------
    # BUILD SINGLE FALLBACK IMAGES (assets/character/*.png)
    # -------------------------------------------------------------
    # idle.png
    idle_comp = overlay_rgba(body_idle_1024, hands_idle_1024)
    idle_comp = overlay_rgba(idle_comp, eye_idle)
    idle_comp = overlay_rgba(idle_comp, mouth_idle)
    save_scaled(idle_comp, r"assets\character\idle.png")

    # happy.png
    happy_comp = overlay_rgba(body_idle_1024, hands_happy_1024)
    happy_comp = overlay_rgba(happy_comp, vfx_blush)
    happy_comp = overlay_rgba(happy_comp, eye_happy)
    happy_comp = overlay_rgba(happy_comp, mouth_idle)
    save_scaled(happy_comp, r"assets\character\happy.png")

    # thinking.png
    thinking_comp = overlay_rgba(body_idle_1024, hands_idle_1024)
    thinking_comp = overlay_rgba(thinking_comp, brow_idle)
    thinking_comp = overlay_rgba(thinking_comp, eye_thinking)
    thinking_comp = overlay_rgba(thinking_comp, mouth_open_small)
    save_scaled(thinking_comp, r"assets\character\thinking.png")

    # glitch.png
    glitch_comp = overlay_rgba(body_glitch_1024, hands_glitch_1024)
    glitch_comp = overlay_rgba(glitch_comp, brow_angry)
    glitch_comp = overlay_rgba(glitch_comp, eye_glitch)
    glitch_comp = overlay_rgba(glitch_comp, mouth_glitch)
    save_scaled(glitch_comp, r"assets\character\glitch.png")

    print("[SUCCESS] All character layers and composited fallbacks successfully built!")

if __name__ == "__main__":
    build_all()
