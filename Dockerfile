# Use the official Azure Functions Python image as a parent image
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

# Install LibreOffice and unoconv
RUN apt-get update && \
    apt-get install -y libreoffice unoconv && \
    apt-get clean

# Install Python dependencies
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

# Copy the function app code
COPY . /home/site/wwwroot