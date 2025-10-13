import pdfplumber

# Set up coordinates for key areas based on the invoice image structure.
# NOTE: These coordinates are APPROXIMATE and may need slight tuning 
#       based on the raw pdfplumber output for your specific file.

# Coordinates for the 'Invoice Details' table section
INVOICE_DETAILS_CLIP = (50, 200, 610, 280) 

# Coordinates for the 'Patient Details' table section (Header data)
PATIENT_DETAILS_CLIP = (50, 290, 610, 480) 

# Coordinates for the 'Line Items' table section
LINE_ITEMS_CLIP = (50, 470, 610, 750)

# Coordinates for the 'Financial Totals' section
FINANCIAL_TOTALS_CLIP = (500, 750, 610, 900) 

pdf_path = r'minio_buckets/invoices/invoice_T1_gen1.pdf'

try:
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]

        # 1. Targeted Text Extraction for Invoice Details (Handles scattering)
        print("--- 1. INVOICE DETAILS (Targeted Text) ---")
        invoice_details_text = page.crop(INVOICE_DETAILS_CLIP).extract_text()
        print(invoice_details_text)
        print("\n" + "="*40 + "\n")

        # 2. Targeted Extraction for Patient Details (Handles scattering)
        print("--- 2. PATIENT DETAILS (Targeted Text) ---")
        patient_details_text = page.crop(PATIENT_DETAILS_CLIP).extract_text()
        print(patient_details_text)
        print("\n" + "="*40 + "\n")

        # 3. Table Extraction for Line Items (Handles columns/rows)
        print("--- 3. LINE ITEMS (Table Extraction) ---")
        line_items_table = page.crop(LINE_ITEMS_CLIP).extract_table({
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
        })
        
        if line_items_table:
            # Print table row by row for clarity
            for row in line_items_table:
                print(row)
        else:
            print("Could not extract table data.")
        print("\n" + "="*40 + "\n")

        # 4. Targeted Text Extraction for Totals (Handles scattering)
        print("--- 4. FINANCIAL TOTALS (Targeted Text) ---")
        financial_totals_text = page.crop(FINANCIAL_TOTALS_CLIP).extract_text()
        print(financial_totals_text)


except FileNotFoundError:
    print(f"Error: The file at {pdf_path} was not found. Please check the file path.")
except IndexError:
    print(f"Error: The PDF at {pdf_path} appears to be empty or has no pages.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")