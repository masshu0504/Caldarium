from fastapi import FastAPI, File, UploadFile, HTTPException
from starlette.responses import JSONResponse
from parser_prototype import parse_pdf_bytes
import uvicorn # Not strictly required, but good for context

# Initialize the FastAPI application
app = FastAPI(
    title="Medical Document Parser API",
    description="An API to extract key data from medical invoices."
)

@app.get("/", include_in_schema=False)
def read_root():
    """Simple health check endpoint."""
    return {"status": "Parser API is running"}


@app.post("/parse/invoice")
async def parse_uploaded_invoice(file: UploadFile = File(...)):
    """
    Accepts a PDF file upload, processes it using the parser_prototype, 
    and returns the extracted data.
    """
    
    # 1. Basic Validation
    if file.content_type != 'application/pdf':
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only PDF files are accepted."
        )

    try:
        # 2. Read the file content as bytes
        # Since this is an async function, use await for file reading
        pdf_bytes = await file.read()
        
        # 3. Call the refactored parser function
        extracted_data = parse_pdf_bytes(pdf_bytes)

        # 4. Return the result
        if "error" in extracted_data:
            # If the parser returned an internal error
            return JSONResponse(status_code=500, content=extracted_data)
        
        return extracted_data

    except Exception as e:
        print(f"Server error during processing: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An unexpected server error occurred during file processing."
        )

# If you were to run this locally without Docker/Uvicorn:
# if __name__ == "__main__":
#     uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)