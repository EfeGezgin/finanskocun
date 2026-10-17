import os
import sys
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------
# 1. GENERATE ULTRA-VIBRANT SCALABLE VECTOR SVG
# -------------------------------------------------------------
svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <!-- Background Gradient: Deep Obsidian & Royal Sapphire -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a" />
      <stop offset="45%" stop-color="#090d19" />
      <stop offset="100%" stop-color="#020617" />
    </linearGradient>

    <!-- Outer Rim Glow: Neon Emerald -> Electric Cyan -> Royal Indigo -->
    <linearGradient id="rimGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00f59b" />
      <stop offset="35%" stop-color="#00e5ff" />
      <stop offset="70%" stop-color="#6366f1" />
      <stop offset="100%" stop-color="#a855f7" />
    </linearGradient>

    <!-- Growth Bars Gradients -->
    <linearGradient id="bar1Grad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#1e293b" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
    <linearGradient id="bar2Grad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#4338ca" />
      <stop offset="100%" stop-color="#818cf8" />
    </linearGradient>
    <linearGradient id="bar3Grad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
    <linearGradient id="bar4Grad" x1="0%" y1="100%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#059669" />
      <stop offset="50%" stop-color="#10b981" />
      <stop offset="100%" stop-color="#34d399" />
    </linearGradient>

    <!-- Golden Rocket/Arrow Gradient -->
    <linearGradient id="goldGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#d97706" />
      <stop offset="40%" stop-color="#fbbf24" />
      <stop offset="80%" stop-color="#fef08a" />
      <stop offset="100%" stop-color="#ffffff" />
    </linearGradient>

    <!-- Glass Reflection Gradient -->
    <linearGradient id="glassGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.22" />
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0.04" />
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
    </linearGradient>

    <!-- Soft Glow Filter -->
    <filter id="neonGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="16" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>

    <filter id="starGlow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="8" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>

  <!-- Drop Shadow of entire badge -->
  <rect x="24" y="32" width="464" height="464" rx="124" fill="#000000" opacity="0.65" filter="blur(20px)" />

  <!-- Outer Neon Border Frame -->
  <rect x="20" y="20" width="472" height="472" rx="126" fill="url(#bgGrad)" stroke="url(#rimGrad)" stroke-width="12" />

  <!-- Inner Ambient Radial Glow -->
  <circle cx="256" cy="240" r="160" fill="#00e5ff" opacity="0.14" filter="blur(40px)" />
  <circle cx="340" cy="180" r="110" fill="#10b981" opacity="0.18" filter="blur(35px)" />

  <!-- 3D Glass Shine (Top Half) -->
  <path d="M 28 136 C 28 72, 72 28, 136 28 L 376 28 C 440 28, 484 72, 484 136 L 484 210 C 370 230, 140 210, 28 210 Z" fill="url(#glassGrad)" />

  <!-- Ascending Growth Columns (3D Beveled Pill Bars) -->
  <!-- Bar 1 -->
  <rect x="115" y="300" width="48" height="95" rx="16" fill="url(#bar1Grad)" opacity="0.85" />
  <rect x="117" y="302" width="44" height="8" rx="4" fill="#ffffff" opacity="0.35" />

  <!-- Bar 2 -->
  <rect x="180" y="235" width="48" height="160" rx="16" fill="url(#bar2Grad)" filter="url(#neonGlow)" />
  <rect x="182" y="237" width="44" height="8" rx="4" fill="#ffffff" opacity="0.4" />

  <!-- Bar 3 -->
  <rect x="245" y="175" width="48" height="220" rx="16" fill="url(#bar3Grad)" filter="url(#neonGlow)" />
  <rect x="247" y="177" width="44" height="8" rx="4" fill="#ffffff" opacity="0.5" />

  <!-- Bar 4 (Peak Sovereign Growth) -->
  <rect x="310" y="115" width="52" height="280" rx="18" fill="url(#bar4Grad)" filter="url(#neonGlow)" stroke="#6ee7b7" stroke-width="2" />
  <rect x="313" y="118" width="46" height="10" rx="5" fill="#ffffff" opacity="0.65" />

  <!-- Ascending Dynamic Golden Growth Curve & Arrow -->
  <path d="M 100 290 Q 230 220 390 95" fill="none" stroke="url(#goldGrad)" stroke-width="15" stroke-linecap="round" filter="url(#starGlow)" />
  
  <!-- Arrow Head -->
  <polygon points="405,75 410,125 365,110" fill="url(#goldGrad)" filter="url(#starGlow)" />

  <!-- Radiant Diamond / AI Star Apex (Top-Right) -->
  <g transform="translate(415, 75)" filter="url(#starGlow)">
    <!-- Light Cross Flares -->
    <ellipse cx="0" cy="0" rx="42" ry="4" fill="#ffffff" opacity="0.85" />
    <ellipse cx="0" cy="0" rx="4" ry="42" fill="#ffffff" opacity="0.85" />
    <!-- Center Diamond Core -->
    <path d="M 0 -28 Q 0 0 28 0 Q 0 0 0 28 Q 0 0 -28 0 Q 0 0 0 -28 Z" fill="url(#goldGrad)" />
    <circle cx="0" cy="0" r="7" fill="#ffffff" />
  </g>

  <!-- Secondary Sapphire AI Sparkle (Left) -->
  <g transform="translate(90, 140) scale(0.65)" filter="url(#starGlow)">
    <ellipse cx="0" cy="0" rx="30" ry="3" fill="#38bdf8" opacity="0.75" />
    <ellipse cx="0" cy="0" rx="3" ry="30" fill="#38bdf8" opacity="0.75" />
    <path d="M 0 -22 Q 0 0 22 0 Q 0 0 0 22 Q 0 0 -22 0 Q 0 0 0 -22 Z" fill="#38bdf8" />
    <circle cx="0" cy="0" r="5" fill="#ffffff" />
  </g>
</svg>
"""

# Save SVGs
(FRONTEND_DIR / "logo.svg").write_text(svg_content, encoding="utf-8")
(FRONTEND_DIR / "favicon.svg").write_text(svg_content, encoding="utf-8")
print("✅ Saved vibrant logo.svg and favicon.svg")


# -------------------------------------------------------------
# 2. GENERATE ULTRA CRISP MULTI-LAYERED RASTER ICONS (PIL)
# -------------------------------------------------------------
def render_vibrant_icon(size: int) -> Image.Image:
    # 4x Supersampling for ultra-crisp edges
    supersample = 4
    canvas_w = size * supersample
    canvas_h = size * supersample
    
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = int(canvas_w * 0.04)
    radius = int(canvas_w * 0.24)
    rect = [margin, margin, canvas_w - margin, canvas_h - margin]

    # 1. Outer Neon Rim (Gradient simulated with layered rounded rects)
    rim_w = max(2, int(canvas_w * 0.024))
    for i in range(rim_w):
        t = i / rim_w
        r_c = int(0 * (1 - t) + 16 * t)
        g_c = int(245 * (1 - t) + 185 * t)
        b_c = int(155 * (1 - t) + 255 * t)
        inset = margin + i
        draw.rounded_rectangle([inset, inset, canvas_w - inset, canvas_h - inset], radius=max(2, radius - i), outline=(r_c, g_c, b_c, 240))

    # 2. Dark Obsidian / Sapphire Base Fill
    inner_inset = margin + rim_w
    inner_rad = radius - rim_w
    draw.rounded_rectangle([inner_inset, inner_inset, canvas_w - inner_inset, canvas_h - inner_inset], radius=inner_rad, fill=(9, 13, 25, 255))

    # 3. Soft Radial Glow in Center
    glow_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    cx, cy = int(canvas_w * 0.52), int(canvas_h * 0.50)
    glow_r = int(canvas_w * 0.35)
    glow_draw.ellipse([cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r], fill=(0, 229, 255, 45))
    glow_r2 = int(canvas_w * 0.25)
    glow_draw.ellipse([cx - glow_r2, cy - glow_r2, cx + glow_r2, cy + glow_r2], fill=(16, 185, 129, 60))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(int(canvas_w * 0.06)))
    img.alpha_composite(glow_img)

    # Re-acquire draw
    draw = ImageDraw.Draw(img)

    # 4. Growth Columns (Financial Ascendance)
    bar_w = int(canvas_w * 0.098)
    base_y = int(canvas_h * 0.78)
    bar_r = int(bar_w * 0.32)

    bars = [
        # (center_x_ratio, top_y_ratio, (R,G,B), highlight)
        (0.26, 0.58, (56, 189, 248), (200, 235, 255)),
        (0.40, 0.44, (99, 102, 241), (220, 225, 255)),
        (0.55, 0.33, (6, 182, 212), (210, 250, 255)),
        (0.70, 0.22, (0, 245, 155), (230, 255, 240))
    ]

    for x_rat, y_rat, col, hi_col in bars:
        bx = int(canvas_w * x_rat - bar_w / 2)
        by = int(canvas_h * y_rat)
        # Bar body
        draw.rounded_rectangle([bx, by, bx + bar_w, base_y], radius=bar_r, fill=(col[0], col[1], col[2], 255))
        # Top highlight pill
        hi_h = max(2, int(bar_w * 0.22))
        draw.rounded_rectangle([bx + 2, by + 2, bx + bar_w - 2, by + hi_h], radius=int(hi_h/2), fill=(hi_col[0], hi_col[1], hi_col[2], 180))

    # 5. Golden Rocket Growth Trend Line
    pts = [
        (int(canvas_w * 0.20), int(canvas_h * 0.60)),
        (int(canvas_w * 0.38), int(canvas_h * 0.46)),
        (int(canvas_w * 0.62), int(canvas_h * 0.27)),
        (int(canvas_w * 0.79), int(canvas_h * 0.15))
    ]
    line_thickness = max(2, int(canvas_w * 0.028))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i+1]], fill=(251, 191, 36, 255), width=line_thickness)

    # 6. Golden Arrow Head at Apex
    tip = pts[-1]
    ah_len = int(canvas_w * 0.08)
    ah_w = int(canvas_w * 0.045)
    draw.polygon([
        (tip[0] + int(ah_len * 0.4), tip[1] - int(ah_len * 0.4)),
        (tip[0] - ah_w, tip[1] + int(ah_len * 0.7)),
        (tip[0] + int(ah_len * 0.7), tip[1] + ah_w)
    ], fill=(255, 215, 0, 255))

    # 7. Sparkling Diamond Stars
    def draw_star(star_x, star_y, rad, fill_col):
        # 4 pointed diamond star
        star_pts = [
            (star_x, star_y - rad),
            (star_x + int(rad * 0.32), star_y - int(rad * 0.32)),
            (star_x + rad, star_y),
            (star_x + int(rad * 0.32), star_y + int(rad * 0.32)),
            (star_x, star_y + rad),
            (star_x - int(rad * 0.32), star_y + int(rad * 0.32)),
            (star_x - rad, star_y),
            (star_x - int(rad * 0.32), star_y - int(rad * 0.32))
        ]
        draw.polygon(star_pts, fill=fill_col)
        # Center glow dot
        cr = max(2, int(rad * 0.25))
        draw.ellipse([star_x - cr, star_y - cr, star_x + cr, star_y + cr], fill=(255, 255, 255, 255))

    # Main Golden Diamond
    draw_star(int(canvas_w * 0.82), int(canvas_h * 0.14), int(canvas_w * 0.075), (255, 220, 50, 255))
    # Secondary Cyan Diamond
    draw_star(int(canvas_w * 0.18), int(canvas_h * 0.26), int(canvas_w * 0.045), (56, 189, 248, 255))

    # 8. Glass Sheen on Top Half
    sheen_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    sheen_draw = ImageDraw.Draw(sheen_img)
    sheen_draw.rounded_rectangle([inner_inset + 2, inner_inset + 2, canvas_w - inner_inset - 2, int(canvas_h * 0.44)], radius=inner_rad, fill=(255, 255, 255, 24))
    img.alpha_composite(sheen_img)

    # High quality LANCZOS downsample
    final_icon = img.resize((size, size), Image.Resampling.LANCZOS)
    return final_icon

# Render All PNG Resolutions
sizes = [
    (512, "icon-512.png"),
    (256, "icon-256.png"),
    (192, "icon-192.png"),
    (180, "apple-touch-icon.png"),
    (128, "icon-128.png"),
    (64, "favicon-64.png"),
    (48, "icon-48.png"),
    (32, "favicon-32.png"),
    (16, "favicon-16.png")
]

generated_images = {}
for sz, fname in sizes:
    ico_img = render_vibrant_icon(sz)
    generated_images[sz] = ico_img
    ico_img.save(FRONTEND_DIR / fname, "PNG")
    print(f"Generated {fname} ({sz}x{sz})")

# -------------------------------------------------------------
# 3. GENERATE FULL MULTI-RESOLUTION WINDOWS .ICO
# -------------------------------------------------------------
# Windows requires 256, 128, 64, 48, 32, 16 all in one file!
ico_sizes = [256, 128, 64, 48, 32, 16]
ico_images = [generated_images[s] for s in ico_sizes]

# Save to frontend/favicon.ico
ico_primary = ico_images[0]
ico_primary.save(
    FRONTEND_DIR / "favicon.ico",
    format="ICO",
    sizes=[(s, s) for s in ico_sizes],
    append_images=ico_images[1:]
)
print("✅ Generated frontend/favicon.ico with 256x256, 128x128, 64x64, 48x48, 32x32, 16x16 mipmaps!")

# Also save directly in smartfinance-ai root as app_icon.ico
root_ico = Path(__file__).resolve().parent.parent / "app_icon.ico"
ico_primary.save(
    root_ico,
    format="ICO",
    sizes=[(s, s) for s in ico_sizes],
    append_images=ico_images[1:]
)
print(f"✅ Generated root icon: {root_ico}")
