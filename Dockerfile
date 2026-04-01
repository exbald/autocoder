FROM python:3.12-slim

# Install dependencies
RUN apt-get update && apt-get install -y     curl     git     npm     nodejs     && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI to /usr/local/bin
RUN curl -fsSL https://claude.ai/install.sh | bash &&     mv /root/.local/bin/claude /usr/local/bin/claude 2>/dev/null ||     (mkdir -p /usr/local/bin &&     curl -fsSL https://claude.ai/install.sh | bash &&     cp /root/.local/bin/claude /usr/local/bin/claude) ||     echo "CLI install attempted"

# Verify CLI installation
RUN which claude || echo "Claude not in default path"

# Set working directory
WORKDIR /app

# Copy autocoder files
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install UI dependencies
WORKDIR /app/ui
RUN npm install && npm run build
WORKDIR /app

# Create non-root user
RUN useradd -m -s /bin/bash autoforge &&     mkdir -p generations /home/autoforge/.claude &&     chown -R autoforge:autoforge /app generations /home/autoforge


EXPOSE 5173 8000 8888

USER autoforge

CMD ["python", "start_ui.py"]
