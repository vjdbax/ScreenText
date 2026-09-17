#!/bin/bash
# ScreenText Helper — Google Colab Setup
# Run this cell in Colab to install Ollama and download recommended Vision models.

echo "========================================"
echo " ScreenText Helper — Colab Setup"
echo "========================================"

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama server in background
ollama serve &
sleep 3

# Pull recommended Vision models (3B + 7B)
echo ""
echo ">>> Downloading Qwen 2.5 VL (3B) — fast inference..."
ollama pull qwen2.5vl:3b

echo ""
echo ">>> Downloading Qwen 2.5 VL (7B) — max accuracy..."
ollama pull qwen2.5vl:7b

echo ""
echo "========================================"
echo " [SUCCESS] Models ready!"
echo "  - qwen2.5vl:3b  (3-4 GB VRAM)"
echo "  - qwen2.5vl:7b  (8+ GB VRAM)"
echo "========================================"
