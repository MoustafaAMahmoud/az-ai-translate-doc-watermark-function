import logging
import requests
from azure.storage.blob import BlobServiceClient
from environment_variables import *

# Construct the SAS token and Blob service client
blob_service_client = BlobServiceClient(
    account_url=f"https://{azure_storage_account}.blob.core.windows.net",
    credential=sas_token,
)


def validate_source_url(source_url):
    """
    Validates the existence of the source URL.

    Input:
    - source_url: URL of the source document.

    Output:
    - True if the file exists, False otherwise.
    """
    logging.info(f"Validating source URL: {source_url}")
    response = requests.head(source_url)
    if response.status_code == 200:
        logging.info("Source file exists")
        return True
    else:
        logging.error(
            f"Source file does not exist. Status code: {response.status_code}"
        )
        return False


def upload_to_blob(
    storage_account, sas_token, container_name, blob_directory, file_name, content
):
    blob_service_client = BlobServiceClient(
        account_url=f"https://{storage_account}.blob.core.windows.net",
        credential=sas_token,
    )
    blob_path = f"{blob_directory}/{file_name}"
    blob_client = blob_service_client.get_blob_client(
        container=container_name, blob=blob_path
    )

    logging.info(f"Uploading file to Azure Blob Storage: {blob_path}")
    try:
        blob_client.upload_blob(content, overwrite=True)
    except Exception as e:
        logging.error("Failed to upload blob: %s", e)
        raise
    logging.info("Upload successful.")

    # Construct and return the full URL for the uploaded blob
    file_url = f"https://{storage_account}.blob.core.windows.net/{container_name}/{blob_path}?{sas_token}"
    return file_url
