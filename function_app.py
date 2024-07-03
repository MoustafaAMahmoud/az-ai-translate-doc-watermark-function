"""
Azure Function App to handle file uploads, save to temporary location,
upload to Azure Blob Storage, and log the upload details.
"""

import logging
import os
import tempfile
import subprocess
import urllib.parse
import io
from datetime import datetime
import azure.functions as func
from azure.storage.blob import BlobServiceClient, BlobClient
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from database_helper import update_watermark_file_record
from blob_handler import validate_source_url, upload_to_blob
from environment_variables import azure_storage_account, sas_token, container_name, upload_prefix, watermark_prefix

# Initialize the BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(os.getenv("BlobStorageConnectionString"))

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="add_water_mark", methods=["POST"])
def add_water_mark(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle the file upload request, save the file to a temporary location,
    upload it to Azure Blob Storage, and log the upload details in the database.

    Args:
        req (func.HttpRequest): The HTTP request object.

    Returns:
        func.HttpResponse: The HTTP response object with the status of the upload.
    """
    logging.info("Python HTTP trigger function to upload a file processed a request.")

    try:
        # Get the file name from the request
        file_name = req.params.get("file_name")
        input_file_path = file_name
        if not file_name:
            return func.HttpResponse("File name not provided.", status_code=400)

        logging.info("File: %s", file_name)

        # Define the source URL
        encoded_file_name = urllib.parse.quote(file_name)
        source_url = (
            f"https://{azure_storage_account}.blob.core.windows.net/"
            f"{container_name}/{upload_prefix}/{encoded_file_name}?{sas_token}"
        )
        logging.info("Source URL: %s", source_url)

        # Validate the existence of the source URL
        if not validate_source_url(source_url):
            logging.error("Source file does not exist: %s", source_url)
            return func.HttpResponse("Source file does not exist.", status_code=404)

        # Read the file content from the source URL
        blob_client = BlobClient.from_blob_url(source_url)
        downloader = blob_client.download_blob()
        file_content = downloader.readall()
        logging.info("File content read successfully.")

        if file_name.endswith(".docx"):
            pdf_content = convert_docx_to_pdf(file_content)
            pdf_content = add_pdf_watermark(pdf_content)
            new_file_name = file_name.replace(".docx", ".pdf")
        elif file_name.endswith(".pdf"):
            pdf_content = file_content
            pdf_content = add_pdf_watermark(file_content)
            new_file_name = file_name
        else:
            return func.HttpResponse("Unsupported file type.", status_code=400)

        file_url = upload_to_blob(
            azure_storage_account,
            sas_token,
            container_name,
            watermark_prefix,
            new_file_name,
            pdf_content,
        )
        logging.info("File URL: %s", file_url)
        watermark_date = datetime.now().date()
        watermark_datetime = datetime.now()
        watermark_zone_path = file_url
        watermark_status = "done"

        logging.info("Updating the watermark record in the database.")
        update_watermark_file_record(
            input_file_path,
            watermark_date,
            watermark_datetime,
            watermark_status,
            watermark_zone_path,
        )
        logging.info("Watermark record updated successfully.")

        return func.HttpResponse(
            f"File {new_file_name} uploaded successfully", status_code=200
        )

    except Exception as e:
        logging.error("Error processing the request: %s", str(e), exc_info=True)
        update_watermark_file_record(
            input_file_path,
            datetime.now().date(),
            datetime.now(),
            "failed",
            ""
        )
        return func.HttpResponse("Internal Server Error", status_code=500)


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
            logging.debug("Wrote .docx content to %s", docx_path)

            # Convert .docx to .pdf using LibreOffice
            subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    docx_path,
                    "--outdir",
                    tmpdirname,
                ],
                check=True,
            )
            logging.debug("Converted .docx to .pdf using LibreOffice, output path: %s", pdf_path)

            # Read the .pdf file content
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()
            logging.debug("Read .pdf content from %s", pdf_path)

        return pdf_content
    except Exception as e:
        logging.error("Error converting .docx to .pdf: %s", str(e), exc_info=True)
        raise


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
            logging.debug("Watermark added to PDF.")
            return output_pdf_stream.getvalue()

    except Exception as e:
        logging.error("Error adding watermark: %s", str(e), exc_info=True)
        raise
