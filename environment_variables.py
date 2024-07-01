import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    encoding="utf-8",
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Read environment variables from Azure Function App settings
azure_storage_account = os.getenv("AZURE_STORAGE_ACCOUNT")
sas_token = os.getenv("SAS_TOKEN")
storage_account_key = os.getenv("STORAGE_ACCOUNT_KEY")
watermark_prefix = os.getenv("WATERMARK_PREFIX")
container_name = "translation-service"
upload_prefix = "translated-zone"
# Log environment variables to check if they exist
logging.info(f"AZURE_STORAGE_ACCOUNT: {azure_storage_account}")
logging.info(f"SAS_TOKEN: {sas_token}")
logging.info(f"STORAGE_ACCOUNT_KEY: {storage_account_key}")
logging.info(f"WATERMARK_PREFIX: {watermark_prefix}")
