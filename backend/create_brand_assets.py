import os
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

# 1. Generate Clean Scalable SVG Logo
svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <!-- Background Gradient -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a" />
      <stop offset="50%" stop-color="#0b0f19" />
      <stop offset="100%" stop-color="#030712" />
    </linearGradient>

    <!-- Shield Border Gradient -->
    <linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#10b981" />
      <stop offset="50%" stop-color="#6366f1" />
      <stop offset="100%" stop-color="#06b6d4" />
    </linearGradient>

    <!-- Growth Chevron Gradient -->
    <linearGradient id="chevronGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#10b981" />
      <stop offset="50%" stop-color="#34d399" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>

    <!-- Gold Accent Gradient -->
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fbbf24" />
      <stop offset="100%" stop-color="#f59e0b" />
    </linearGradient>

    <!-- Glow Filter -->
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="12" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <!-- Background Shield Rounded Rect -->
  <rect x="32" y="32" width="448" height="448" rx="112" fill="url(#bgGrad)" stroke="url(#borderGrad)" stroke-width="8" />

  <!-- Inner Soft Radial Glow -->
  <circle cx="256" cy="240" r="140" fill="#10b981" opacity="0.12" filter="blur(30px)" />

  <!-- Growth Bars (Financial Ascendance) -->
  <g transform="translate(0, 10)">
    <!-- Bar 1 -->
    <rect x="130" y="300" width="46" height="80" rx="14" fill="#334155" opacity="0.8" />
    <!-- Bar 2 -->
    <rect x="194" y="240" width="46" height="140" rx="14" fill="url(#borderGrad)" opacity="0.7" />
    <!-- Bar 3 -->
    <rect x="258" y="180" width="46" height="200" rx="14" fill="url(#chevronGrad)" filter="url(#glow)" />
    <!-- Bar 4 (Peak) -->
    <rect x="322" y="130" width="46" height="250" rx="14" fill="url(#chevronGrad)" filter="url(#glow)" />
    
    <!-- Dynamic Growth Arrow Path -->
    <path d="M 120 280 Q 240 210 380 110" fill="none" stroke="url(#goldGrad)" stroke-width="12" stroke-linecap="round" filter="url(#glow)" />
    <polygon points="380,85 395,125 355,120" fill="url(#goldGrad)" filter="url(#glow)" />
  </g>

  <!-- AI Sparkle / Star at top right -->
  <g transform="translate(390, 85) scale(0.9)" filter="url(#glow)">
    <path d="M 0 -24 Q 0 0 24 0 Q 0 0 0 24 Q 0 0 -24 0 Q 0 0 0 -24 Z" fill="url(#goldGrad)" />
  </g>
  <!-- Smaller Sparkle -->
  <g transform="translate(100, 130) scale(0.55)" filter="url(#glow)">
    <path d="M 0 -24 Q 0 0 24 0 Q 0 0 0 24 Q 0 0 -24 0 Q 0 0 0 -24 Z" fill="#38bdf8" />
  </g>
</svg>
"""

# Save SVG logo & favicon
svg_path = FRONTEND_DIR / "logo.svg"
with open(svg_path, "w", encoding="utf-8") as f:
    f.write(svg_content)

favicon_svg = FRONTEND_DIR / "favicon.svg"
with open(favicon_svg, "w", encoding="utf-8") as f:
    f.write(svg_content)

print("Saved logo.svg and favicon.svg successfully.")

# 2. Render Pixel-Perfect Raster PNGs using PIL
def draw_finans_kocun_icon(size: int) -> Image.Image:
    # High-resolution super-sampled canvas for anti-aliasing
    scale = 2
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = int(canvas_size * 0.06)
    radius = int(canvas_size * 0.22)

    # 1. Rounded background
    rect_box = [pad, pad, canvas_size - pad, canvas_size - pad]
    # Draw dark background
    draw.rounded_rectangle(rect_box, radius=radius, fill=(11, 15, 25, 255), outline=(16, 185, 129, 230), width=int(scale * 4))

    # Glow effect
    glow_box = [int(canvas_size * 0.25), int(canvas_size * 0.25), int(canvas_size * 0.75), int(canvas_size * 0.75)]

    # Draw growth bars
    # Bar coordinates normalized to canvas_size
    bar_width = int(canvas_size * 0.09)
    bar_gap = int(canvas_size * 0.04)
    base_y = int(canvas_size * 0.75)
    bar_radius = int(bar_width * 0.35)

    bars = [
        # (x_center_ratio, height_ratio, color)
        (0.28, 0.20, (51, 65, 85, 230)),
        (0.42, 0.35, (99, 102, 241, 240)),
        (0.56, 0.48, (16, 185, 129, 255)),
        (0.70, 0.60, (52, 211, 153, 255))
    ]

    for x_ratio, h_ratio, col in bars:
        bx = int(canvas_size * x_ratio - bar_width / 2)
        by = int(base_y - canvas_size * h_ratio)
        draw.rounded_rectangle([bx, by, bx + bar_width, base_y], radius=bar_radius, fill=col)

    # Draw growth trend arrow
    arrow_pts = [
        (int(canvas_size * 0.22), int(canvas_size * 0.60)),
        (int(canvas_size * 0.45), int(canvas_size * 0.45)),
        (int(canvas_size * 0.72), int(canvas_size * 0.24)),
        (int(canvas_size * 0.82), int(canvas_size * 0.18))
    ]
    # Trend line
    line_w = max(2, int(scale * 6))
    for i in range(len(arrow_pts) - 1):
        draw.line([arrow_pts[i], arrow_pts[i+1]], fill=(245, 158, 11, 255), width=line_w)

    # Arrow head
    tip = arrow_pts[-1]
    head_size = int(scale * 16)
    draw.polygon([
        tip,
        (tip[0] - head_size, tip[1] + int(head_size * 0.7)),
        (tip[0] - int(head_size * 0.3), tip[1] + int(head_size * 1.1))
    ], fill=(245, 158, 11, 255))

    # Diamond / AI Sparkle at top right
    def draw_sparkle(cx, cy, s_size, color):
        pts = [
            (cx, cy - s_size),
            (cx + int(s_size * 0.35), cy - int(s_size * 0.35)),
            (cx + s_size, cy),
            (cx + int(s_size * 0.35), cy + int(s_size * 0.35)),
            (cx, cy + s_size),
            (cx - int(s_size * 0.35), cy + int(s_size * 0.35)),
            (cx - s_size, cy),
            (cx - int(s_size * 0.35), cy - int(s_size * 0.35))
        ]
        draw.polygon(pts, fill=color)

    draw_sparkle(int(canvas_size * 0.80), int(canvas_size * 0.16), int(scale * 20), (251, 191, 36, 255))
    draw_sparkle(int(canvas_size * 0.20), int(canvas_size * 0.28), int(scale * 12), (56, 189, 248, 255))

    # Downsample with LANCZOS for buttery smooth anti-aliased icon
    final_img = img.resize((size, size), Image.Resampling.LANCZOS)
    return final_img

# Generate icons
for sz, name in [
    (512, "icon-512.png"),
    (192, "icon-192.png"),
    (180, "apple-touch-icon.png"),
    (64, "favicon-64.png"),
    (32, "favicon-32.png")
]:
    icon = draw_finans_kocun_icon(sz)
    out_path = FRONTEND_DIR / name
    icon.save(out_path, "PNG")
    print(f"Generated {name} ({sz}x{sz})")

# Generate multi-res favicon.ico
ico_32 = draw_finans_kocun_icon(32)
ico_16 = draw_finans_kocun_icon(16)
ico_path = FRONTEND_DIR / "favicon.ico"
ico_32.save(ico_path, format="ICO", sizes=[(32, 32), (16, 16)])
print("Generated favicon.ico successfully.")
