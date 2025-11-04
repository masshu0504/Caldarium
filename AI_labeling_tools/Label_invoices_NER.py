
import os
import json
from openai import OpenAI
import pdfplumber

import auditsAndRecord

with open("apikey.txt", "r", encoding="utf-8") as f:
    API_KEY = f.read().strip()


# store parsed filenames as a JSON array


MODEL_NAME = "openai/gpt-4.1"
TEMPERATURE = 0.4

def is_parsed_file(filename: str) -> bool:
    basename = os.path.splitext(filename)[0]
    expected = os.path.join(OUTPUT_DIR, f"{basename}.json")
    return os.path.isfile(expected)



def liteBot(messages, temperature=TEMPERATURE):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=temperature
    )
    return completion.choices[0].message.content.strip()


# ------------------------
# MAIN EXECUTION
# ------------------------

def parse(system_prompt,_PDF_DIR,_OUTPUT_DIR,_OUTPUT_AUDIT_FILE):
    
    global PDF_DIR, OUTPUT_DIR, OUTPUT_AUDIT_FILE
    PDF_DIR = _PDF_DIR
    OUTPUT_DIR = _OUTPUT_DIR
    OUTPUT_AUDIT_FILE = _OUTPUT_AUDIT_FILE

    for filename in os.listdir(PDF_DIR):
        if not filename.lower().endswith(".pdf") or is_parsed_file(filename):
            continue

        pdf_path = os.path.join(PDF_DIR, filename)
        print(f"Processing {filename}...")
        
        with pdfplumber.open(pdf_path) as pdf:
            # Use layout-aware text extraction for better column handling
            pages_text = [
                page.extract_text(x_tolerance=2, y_tolerance=2) or "" 
                for page in pdf.pages
            ]
        full_text = "\n\n".join(pages_text).strip()



        

        system = [{"role": "system", "content": system_prompt}]
        user = [{"role": "user", "content": full_text}]

        try:
            outputJsonString = liteBot(system + user, TEMPERATURE)
        except Exception as e:
            print(f"Error calling model for {filename}: {e}")
            continue

        cleaned = (
            outputJsonString.strip()
            .removeprefix("```json")
            .removesuffix("```")
            .strip()
        )

        try:
            parsed = json.loads(cleaned)
        
        except json.JSONDecodeError as e:
            print(f"Invalid JSON for {filename}: {e}")
            print("Raw output:\n", outputJsonString[:300], "...\n")
            continue

        if isinstance(parsed, list) and len(parsed) == 1:
            invoice_data = parsed[0]
        else:
            invoice_data = parsed

        # Analyze fields
        fields_filled = [k for k, v in invoice_data.items() if v not in (None, "", [], {})]
        fields_null = [k for k, v in invoice_data.items() if v in (None, "", [], {})]
        

        # Save output
        output_filename = os.path.join(OUTPUT_DIR, f"{os.path.splitext(filename)[0]}.json")
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(invoice_data, f, indent=2, ensure_ascii=False)

        print(f"Saved {output_filename}")

        # Audit entry
        auditsAndRecord.log_audit(filename, fields_filled, fields_null, system_prompt,outputJsonString)

        # Record parsed files as a JSON array (creates file if missing)
    