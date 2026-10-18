# Use a minimal, secure base image for Python
FROM python:3.10-slim-bullseye

# Create a new, non-root user named "coder" to run the code
RUN useradd --create-home --shell /bin/bash coder

# Switch to the non-root user
USER coder

# Set the working directory for that user
WORKDIR /home/coder
