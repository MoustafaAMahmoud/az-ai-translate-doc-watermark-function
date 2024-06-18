import logging
import azure.functions as func
import requests
import io
import json
from docx2pdf import convert
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from azure.storage.blob import BlobServiceClient
import tempfile
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Define variables for Azure storage
azure_storage_account = "translationservices2024"
container_name = "landing-zone"

# Construct the SAS token and Blob service client
sas_token = "sp=racwdli&st=2024-06-11T08:30:05Z&se=2024-07-06T16:30:05Z&spr=https&sv=2022-11-02&sr=c&sig=CnovetFjr%2F%2BwWu80eBO2do0oEaqcm6E1hW7nTiB5TN4%3D"
blob_service_client = BlobServiceClient(account_url=f"https://{azure_storage_account}.blob.core.windows.net", credential=sas_token)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="document_watermark_function")
def document_watermark_function(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function to add a watermark to a PDF document.
    
    Input:
    - HttpRequest: JSON payload containing 'translated_file_name'.
    
    Output:
    - HttpResponse: JSON response with status and watermarked document URL.
    """
    logging.info('Watermark Function: Python HTTP trigger function processed a request.')

    try:
        # Extract translated_file_name from request
        req_body = req.get_json()
        translated_file_name = req_body.get('translated_file_name')
        if not translated_file_name:
            raise ValueError("Translated file name not provided")

        # Download the translated document
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=translated_file_name)
        download_stream = blob_client.download_blob()
        file_content = download_stream.readall()

        if translated_file_name.endswith('.docx'):
            # Convert .docx to .pdf
            pdf_content = convert_docx_to_pdf(file_content)
        elif translated_file_name.endswith('.pdf'):
            pdf_content = file_content
        else:
            raise ValueError("Unsupported file type")

        # Add watermark to the PDF
        watermarked_content = add_pdf_watermark(pdf_content)

        # Upload the watermarked document back to Azure Blob Storage
        watermarked_blob_name = f"watermarked_{translated_file_name.rsplit('.', 1)[0]}.pdf"
        watermarked_blob_client = blob_service_client.get_blob_client(container=container_name, blob=watermarked_blob_name)
        watermarked_blob_client.upload_blob(watermarked_content, overwrite=True)

        logging.info(f"Watermarked document uploaded to: {watermarked_blob_name}")
        return func.HttpResponse(json.dumps({"status": "Success", "watermarked_document_url": f"https://{azure_storage_account}.blob.core.windows.net/{container_name}/{watermarked_blob_name}"}), status_code=200)
    
    except Exception as e:
        logging.error(f"Error in Watermark Function: {str(e)}")
        return func.HttpResponse(json.dumps({"status": "Error", "message": str(e)}), status_code=500)

def add_pdf_watermark(pdf_content, watermark_text="AI Translated"):
    """
    Adds a watermark to a PDF document.

    Input:
    - pdf_content: The content of the PDF to be watermarked.
    - watermark_text: The text to be used as the watermark.

    Output:
    - Watermarked PDF content.
    """
    try:
        with io.BytesIO(pdf_content) as input_pdf_stream, io.BytesIO() as output_pdf_stream:
            input_pdf = PdfReader(input_pdf_stream)
            output_pdf = PdfWriter()

            # Create a watermark
            watermark_stream = io.BytesIO()
            c = canvas.Canvas(watermark_stream, pagesize=letter)
            c.setFont("Helvetica", 100)
            c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.3)

            # Get the dimensions of the page to center the watermark
            page_width, page_height = letter
            x = page_width / 2
            y = page_height / 2

            c.saveState()
            c.translate(x, y)
            c.rotate(45)
            c.drawCentredString(0, 0, watermark_text)
            c.restoreState()
            c.save()
            watermark_stream.seek(0)
            watermark = PdfReader(watermark_stream).pages[0]

            # Add watermark to each page
            for page in input_pdf.pages:
                page.merge_page(watermark)
                output_pdf.add_page(page)

            output_pdf.write(output_pdf_stream)
            return output_pdf_stream.getvalue()

    except Exception as e:
        logging.error(f"Error adding watermark: {str(e)}")
        raise

def convert_docx_to_pdf(docx_content):
    """
    Converts a .docx file content to .pdf.

    Input:
    - docx_content: The content of the .docx file.

    Output:
    - The content of the converted .pdf file.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            docx_path = os.path.join(tmpdirname, "temp.docx")
            pdf_path = os.path.join(tmpdirname, "temp.pdf")

            with open(docx_path, "wb") as f:
                f.write(docx_content)

            # Convert .docx to .pdf
            convert(docx_path, pdf_path)

            # Read the .pdf file content
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()

        return pdf_content
    except Exception as e:
        logging.error(f"Error converting .docx to .pdf: {str(e)}")
        raise