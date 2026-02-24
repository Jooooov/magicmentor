#!/bin/bash
# MagicMentor — double-click to launch
# ──────────────────────────────────────

cd "$(dirname "$0")"

# Fix OpenMP duplicate lib conflict (common on macOS with MLX + other libs)
export KMP_DUPLICATE_LIB_OK=TRUE

# ── Check available RAM (macOS-aware) ────────────────────────────────
TOTAL_RAM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
PAGE_SIZE=16384  # Apple Silicon page size (não 4096)

# free + inactive + purgeable + speculative — tudo reclamável pelo macOS
PAGES_FREE=$(vm_stat | awk '/Pages free/{gsub(/\./,"",$3); print $3}')
PAGES_INACTIVE=$(vm_stat | awk '/Pages inactive/{gsub(/\./,"",$3); print $3}')
PAGES_PURGEABLE=$(vm_stat | awk '/Pages purgeable/{gsub(/\./,"",$3); print $3}')
PAGES_SPECULATIVE=$(vm_stat | awk '/Pages speculative/{gsub(/\./,"",$3); print $3}')
USABLE_PAGES=$(( PAGES_FREE + PAGES_INACTIVE + PAGES_PURGEABLE + PAGES_SPECULATIVE ))
FREE_RAM_GB=$(( USABLE_PAGES * PAGE_SIZE / 1024 / 1024 / 1024 ))

echo "💾 RAM total: ${TOTAL_RAM_GB}GB | Usável: ~${FREE_RAM_GB}GB"

# Choose model based on available RAM
if [ "$FREE_RAM_GB" -ge 6 ]; then
    MODEL_PATH="$HOME/Desktop/apps/MLX/Qwen3-8B-4bit"
    MODEL_NAME="Qwen3-8B"
elif [ "$FREE_RAM_GB" -ge 3 ]; then
    MODEL_PATH="$HOME/Desktop/apps/MLX/Qwen3-4B-4bit"
    MODEL_NAME="Qwen3-4B"
else
    echo "⚠️  RAM livre insuficiente (${FREE_RAM_GB}GB). Fecha algumas aplicações e tenta de novo."
    echo "   Mínimo necessário: 3GB livre para Qwen3-4B"
    read -p "Pressiona Enter para sair..."
    exit 1
fi

echo "🧠 Modelo selecionado: $MODEL_NAME (${FREE_RAM_GB}GB livre)"

# ── Start MLX server if not already running ──────────────────────────
if ! curl -s http://localhost:8080/v1/models > /dev/null 2>&1; then
    echo "   A arrancar servidor MLX..."
    KMP_DUPLICATE_LIB_OK=TRUE mlx_lm.server --model "$MODEL_PATH" --port 8080 &
    MLX_PID=$!

    # Wait until server is ready (max 30s) or detect crash
    for i in $(seq 1 30); do
        sleep 1
        # Check if process is still alive
        if ! kill -0 $MLX_PID 2>/dev/null; then
            echo ""
            echo "❌ Servidor MLX falhou a arrancar."
            echo "   Tenta correr manualmente:"
            echo "   KMP_DUPLICATE_LIB_OK=TRUE mlx_lm.server --model $MODEL_PATH --port 8080"
            read -p "Pressiona Enter para sair..."
            exit 1
        fi
        if curl -s http://localhost:8080/v1/models > /dev/null 2>&1; then
            echo "   ✅ $MODEL_NAME pronto!"
            break
        fi
        echo "   A aguardar... ($i/30)"
    done
else
    echo "🧠 Modelo local já está a correr."
fi

# ── Launch Streamlit web app ──────────────────────────────────────────
echo ""
echo "✨ A iniciar MagicMentor Web App..."
echo ""

PYTHON="$(which python3)"

if [ -z "$PYTHON" ]; then
    echo "❌ Python3 não encontrado no sistema."
    read -p "Pressiona Enter para sair..."
    exit 1
fi

# Abrir browser após 3 segundos (streamlit demora um pouco a arrancar)
(sleep 3 && open http://localhost:8501) &

"$PYTHON" -m streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
