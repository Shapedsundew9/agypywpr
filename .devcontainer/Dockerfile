FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ripgrep \
    vim \
    xclip \
    && rm -rf /var/lib/apt/lists/*
