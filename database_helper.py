import logging
import os
import psycopg2
from psycopg2 import sql, DatabaseError, IntegrityError
from datetime import datetime
import json

# PostgreSQL connection details
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", 5432)
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")

# Log environment variables to check if they exist
logging.debug(f"DB_HOST: {DB_HOST}")
logging.debug(f"DB_PORT: {DB_PORT}")
logging.debug(f"DB_NAME: {DB_NAME}")
logging.debug(f"DB_USER: {DB_USER}")
logging.debug(f"DB_PASSWORD: {'****' if DB_PASSWORD else None}")
logging.debug(f"DB_SSLMODE: {DB_SSLMODE}")


def get_connection():
    """
    Establish a connection to the PostgreSQL database using the provided connection details.
    Returns:
        psycopg2.connection: A connection object to interact with the PostgreSQL database.
    Raises:
        psycopg2.OperationalError: If there is an error connecting to the database.
    """
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode=DB_SSLMODE,
        )
    except psycopg2.OperationalError as e:
        logging.error(f"Error connecting to the database: {str(e)}")
        raise


def update_watermark_file_record(
    file_name, watermark_date, watermark_datetime, watermark_status, watermark_zone_path
):
    """
    Update the record of the file in the PostgreSQL database.
    Args:
        file_name (str): The name of the file.
        watermark_date (datetime.date): The date of the watermark.
        watermark_datetime (datetime.datetime): The date and time of the watermark.
        watermark_status (str): The status of the watermark ('failed', 'in progress', 'done').
        watermark_zone_path (str): The path to the translated file in the translated zone.
    Raises:
        IntegrityError: If there is an integrity constraint violation.
        DatabaseError: If there is a general database error.
        Exception: If there is an unexpected error.
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            update_query = sql.SQL(
                """
                UPDATE file_translation_logs
                SET watermark_date = %s,
                    watermark_datetime = %s,
                    watermark_status = %s,
                    watermark_zone_path = %s               
                WHERE file_name = %s
                """
            )
            cursor.execute(
                update_query,
                (
                    watermark_date,
                    watermark_datetime,
                    watermark_status,
                    watermark_zone_path,
                    file_name,
                ),
            )
            conn.commit()
    except IntegrityError as e:
        logging.error(f"Integrity error: {str(e)}")
        if conn:
            conn.rollback()
    except DatabaseError as e:
        logging.error(f"Database error: {str(e)}")
        if conn:
            conn.rollback()
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
