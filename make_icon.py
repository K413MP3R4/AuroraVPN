"""
============================================================================
 AuroraVPN - Generation de l'icone Windows (.ico)
============================================================================
 Lance par build_windows.bat. Genere assets/aurora.ico a partir de cercles
 concentriques violet -> cyan, sans dependance autre que Pillow.
============================================================================
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("[ERREUR] Pillow manquant. Lancez : pip install pillow")
    raise SystemExit(1)


def build_icon(out_path: Path) -> None:
    """Genere une icone multi-tailles (16/32/48/64/128/256)."""
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        m = max(1, size // 32)  # marge proportionnelle
        # Anneau exterieur violet
        d.ellipse((m, m, size - m, size - m), fill=(139, 92, 246, 255))
        # Anneau intermediaire violet sombre
        inner = size // 5
        d.ellipse((inner, inner, size - inner, size - inner),
                  fill=(109, 40, 217, 255))
        # Coeur cyan
        core = size // 3
        d.ellipse((core, core, size - core, size - core),
                  fill=(34, 211, 238, 255))
        # Centre noir (effet anneau)
        center = int(size // 2.4)
        d.ellipse((center, center, size - center, size - center),
                  fill=(10, 10, 18, 255))
        images.append(img)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(out_path, format="ICO",
                   sizes=[(s, s) for s in sizes],
                   append_images=images[1:])
    print(f"[OK] Icone generee : {out_path} ({len(sizes)} tailles)")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    build_icon(here / "assets" / "aurora.ico")
