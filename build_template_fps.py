# build_template_fps.py
# ---------------------------------------------------
# Generate known_template_fingerprints.json
# by scanning PDFs inside known_templates/<template_id>/.
# ---------------------------------------------------

import os
import json
from template_detector import detect_template_signature

TEMPLATE_ROOT = "known_templates"
OUTPUT_JSON = "known_template_fingerprints.json"


def average_fingerprints(fps):
    """Average numeric fields across multiple fingerprints."""
    if not fps:
        return {}

    numeric_keys = [
        "page_count",
        "avg_width",
        "avg_height",
        "header_text_density",
        "footer_text_density",
        "body_text_density",
        "avg_font_size",
    ]

    avg_fp = {}

    # Average each numeric key
    for key in numeric_keys:
        vals = [fp.get(key, 0) for fp in fps]
        avg_fp[key] = sum(vals) / len(vals) if vals else 0.0

    # Merge top fonts (most common across samples)
    font_counts = {}
    for fp in fps:
        for font in fp.get("top_fonts", []):
            font_counts[font] = font_counts.get(font, 0) + 1

    sorted_fonts = sorted(font_counts.items(), key=lambda x: -x[1])
    avg_fp["top_fonts"] = [f for f, _ in sorted_fonts[:3]]

    return avg_fp


def main():
    template_fps = {}

    # Each folder inside known_templates represents a template ID
    for template_id in os.listdir(TEMPLATE_ROOT):
        template_path = os.path.join(TEMPLATE_ROOT, template_id)
        if not os.path.isdir(template_path):
            continue

        print(f"Processing template: {template_id}")

        fps = []
        for filename in os.listdir(template_path):
            if not filename.lower().endswith(".pdf"):
                continue

            pdf_path = os.path.join(template_path, filename)
            print(f"  - Extracting fingerprint: {filename}")

            fp = detect_template_signature(pdf_path)
            fps.append(fp)

        if fps:
            template_fps[template_id] = average_fingerprints(fps)

    # Write final JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(template_fps, f, indent=2)

    print("\n✅ Finished! Fingerprints saved to:", OUTPUT_JSON)


if __name__ == "__main__":
    main()
