# Use the official, lightweight bash image
FROM bash:latest

# Install necessary packages for a minimal admin environment
# sudo: provides elevated privileges
# shadow: provides user/group management tools like groupadd, useradd
RUN apk add --no-cache sudo shadow

# Create the 'coder' user
RUN adduser -D -s /bin/bash coder

# Add 'coder' to the sudoers file for passwordless sudo
RUN echo "coder ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Switch to the non-root user
USER coder

# Set the working directory
WORKDIR /home/coder
