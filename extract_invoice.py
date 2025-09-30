import pdfplumber

# Replace 'path/to/your/sample/invoice.pdf' with the actual path to one of your sample PDFs.
# You can find the sample PDFs in the repository you cloned.
pdf_path = r'minio_buckets/invoices/invoice_T1_gen1.pdf'

try:
    with pdfplumber.open(pdf_path) as pdf:
        # Assuming you want to extract text from the first page.
        page = pdf.pages[0]
        text = page.extract_text()

        # Print the extracted text to the console.
        if text:
            print(text)
        else:
            print(f"Could not extract text from the first page of {pdf_path}.")
except FileNotFoundError:
    print(f"Error: The file at {pdf_path} was not found. Please check the file path.")
except IndexError:
    print(f"Error: The PDF at {pdf_path} appears to be empty or has no pages.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
