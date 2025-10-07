import uvicorn
from fastapi import FastAPI

# This is the main FastAPI application instance
app = FastAPI(title="Intake Parser API")

# Define a simple root endpoint to confirm the service is running
@app.get("/")
def read_root():
    return {"status": "Parser API is running", "message": "Ready to process invoices."}

# You will eventually add endpoints here like:
# @app.post("/process_invoice")
# def process_invoice(invoice_file: UploadFile = File(...)):
#     # This is where you will integrate your parser_prototype.py logic
#     pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
