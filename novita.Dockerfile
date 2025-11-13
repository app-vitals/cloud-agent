# You can use most Debian-based base images
FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Update and install base dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    wget \
    ca-certificates \
    gnupg \
    lsb-release \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x (LTS) - required for Claude Code
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install PostgreSQL and Redis servers
RUN apt-get update && apt-get install -y \
    postgresql \
    postgresql-contrib \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN mkdir -p /etc/apt/keyrings \
    && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager) - copy to /usr/local/bin for all users
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv \
    && cp /root/.local/bin/uvx /usr/local/bin/uvx \
    && chmod 755 /usr/local/bin/uv /usr/local/bin/uvx

# Install Claude Code CLI globally
# Note: This installs to /usr/local which should be accessible
RUN npm install -g @anthropic-ai/claude-code

# Verify installations
RUN node --version \
    && npm --version \
    && gh --version \
    && claude --version \
    && uv --version \
    && psql --version \
    && redis-server --version

# Copy startup script for services
COPY start-services.sh /usr/local/bin/start-services
RUN chmod +x /usr/local/bin/start-services

# Set working directory
WORKDIR /workspace

# Keep container running
CMD ["/bin/bash"]
