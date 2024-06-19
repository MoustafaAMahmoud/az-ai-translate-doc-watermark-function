import logging
import os
import urllib.parse
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import tempfile
import subprocess
from datetime import datetime
import requests
import io

# Configure logging
logging.basicConfig(level=logging.INFO)

# Read environment variables from Azure Function App settings
azure_storage_account = os.getenv("AZURE_STORAGE_ACCOUNT")
sas_token = os.getenv("SAS_TOKEN")
storage_account_key = os.getenv("STORAGE_ACCOUNT_KEY")

# Log environment variables to check if they exist
logging.info(f"AZURE_STORAGE_ACCOUNT: {azure_storage_account}")
logging.info(f"SAS_TOKEN: {sas_token}")
logging.info(f"STORAGE_ACCOUNT_KEY: {storage_account_key}")

# Define your container and blob prefix
container_name = "translation-service"
upload_prefix = "translated-zone"
watermarked_output_prefix = "translated-zone"

# Construct the Blob service client
blob_service_client = BlobServiceClient(account_url=f"https://{azure_storage_account}.blob.core.windows.net", credential=sas_token)

app = func.FunctionApp()

@app.blob_trigger(arg_name="myblob", path=f"{container_name}/{upload_prefix}/{{name}}.docx", connection="BlobStorageConnectionString")
def document_watermark_function(myblob: func.InputStream):
    logging.info(f"Blob trigger function processing blob: {myblob.name}")
    logging.info(f"Blob size: {myblob.length} bytes")
    logging.info('Watermark Function: Python Blob trigger function processed a request.')

    try:
        file_name = myblob.name.split('/')[-1]
        logging.info(f"Extracted file name: {file_name}")
        logging.info(f"Full path: {myblob.name}")

        # Filter out unwanted file types
        if not (file_name.endswith('.docx') or file_name.endswith('.pdf')):
            logging.info(f"File type not supported for translation: {file_name}")
            return

        encoded_file_name = urllib.parse.quote(file_name)
        source_url = f"https://{azure_storage_account}.blob.core.windows.net/{container_name}/{upload_prefix}/{encoded_file_name}?{sas_token}"
        logging.info(f"Source URL: {source_url}")
        logging.info(f"Encoded file name: {encoded_file_name}")

        # Validate the existence of the source URL
        if not validate_source_url(source_url):
            logging.error("Source file does not exist")
            return

        # Read the file content from the blob
        file_content = myblob.read()
        logging.info(f"Read file content, size: {len(file_content)} bytes")

        if file_name.endswith('.docx'):
            # Convert .docx to .pdf
            pdf_content = convert_docx_to_pdf(file_content)
        elif file_name.endswith('.pdf'):
            pdf_content = file_content

        logging.info(f"PDF content length: {len(pdf_content)} bytes")

        # Add watermark to the PDF
        watermarked_content = add_pdf_watermark(pdf_content)
        logging.info(f"Watermarked PDF content length: {len(watermarked_content)} bytes")

        # Add timestamp to the target file name
        timestamp = int(datetime.now().timestamp())
        watermarked_blob_name = f"{watermarked_output_prefix}/watermarked_{timestamp}_{file_name.rsplit('.', 1)[0]}.pdf"
        watermarked_blob_client = blob_service_client.get_blob_client(container=container_name, blob=watermarked_blob_name)
        watermarked_blob_client.upload_blob(watermarked_content, overwrite=True)
        logging.info(f"Watermarked document uploaded to: {watermarked_blob_name}")

    except Exception as e:
        logging.error(f"Error in Watermark Function: {str(e)}", exc_info=True)

def validate_source_url(url):
    """
    Validates if the source URL exists.

    Input:
    - url: The URL to be validated.

    Output:
    - True if the URL exists, False otherwise.
    """
    try:
        response = requests.head(url)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Error validating source URL: {str(e)}", exc_info=True)
        return False

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
            logging.debug(f"Watermark added to PDF.")
            return output_pdf_stream.getvalue()

    except Exception as e:
        logging.error(f"Error adding watermark: {str(e)}", exc_info=True)
        raise

def convert_docx_to_pdf(docx_content):
    """
    Converts a .docx file content to .pdf using LibreOffice.

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
            logging.debug(f"Wrote .docx content to {docx_path}")

            # Convert .docx to .pdf using LibreOffice
            subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", docx_path, "--outdir", tmpdirname], check=True)
            logging.debug(f"Converted .docx to .pdf using LibreOffice, output path: {pdf_path}")

            # Read the .pdf file content
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()
            logging.debug(f"Read .pdf content from {pdf_path}")

        return pdf_content
    except Exception as e:
        logging.error(f"Error converting .docx to .pdf: {str(e)}", exc_info=True)
        raise