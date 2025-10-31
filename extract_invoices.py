import pdfplumber
import os
import json

# 📁 Folder containing your hospital invoice PDFs
PDF_DIR = "invoices"
# 📄 Output JSON file to upload into Label Studio
OUTPUT_JSON = "invoices_text.json"

data = []

for filename in os.listdir(PDF_DIR):
    if filename.lower().endswith(".pdf"):
        pdf_path = os.path.join(PDF_DIR, filename)
        print(f"Extracting text from: {filename}")
        text_pages = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                text_pages.append(text.strip())

        # Join all page texts together
        full_text = "\n\n".join(text_pages).strip()

        # Add to Label Studio JSON format
        data.append({
            "data": {
                "text": full_text,
                "filename": filename
            }
        })

# 💾 Save output for Label Studio
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n✅ Done! Created {OUTPUT_JSON} with {len(data)} documents.")
print("→ You can now import this JSON file into Label Studio.")
