#!/usr/bin/env bash
# --- DMARC RUA Dashboard Runner ---
set -euo pipefail

# Show what we're doing
echo "────────────────────────────────────────────"
echo "🚀 DMARC RUA Dashboard Runner"
echo "📂 Current dir: $(pwd)"
echo "🗂  Script dir  : $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "────────────────────────────────────────────"

# Always run from the repo root (where this file lives)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Pick a python
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "❌ No Python found (python3/python). Install Python 3 first." >&2
  exit 1
fi
echo "🐍 Using: $($PY -V)"

# Create or activate venv
if [[ -d "venv" && -f "venv/bin/activate" ]]; then
  echo "🐍 Activating existing virtualenv..."
  source venv/bin/activate
else
  echo "🆕 Creating virtualenv at ./venv ..."
  $PY -m venv venv
  source venv/bin/activate
  echo "📦 Installing requirements..."
  pip install --upgrade pip
  if [[ -f "requirements.txt" ]]; then
    pip install -r requirements.txt
  else
    # minimal deps if requirements.txt is missing
    pip install streamlit pandas altair
  fi
fi

# Verify streamlit import works
python - <<'PYCHECK'
try:
    import streamlit, pandas, altair
    print("✅ Python deps OK (streamlit/pandas/altair).")
except Exception as e:
    print("❌ Dependency check failed:", e)
    raise
PYCHECK

# Resolve dashboard path
APP="dmarc_rua_dashboard.py"
if [[ ! -f "$APP" ]]; then
  echo "❌ Can't find $APP in $PROJECT_DIR"
  exit 1
fi

echo "🌐 Launching Streamlit → $APP"
exec streamlit run "$APP"