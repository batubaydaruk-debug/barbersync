#!/usr/bin/env bash
# BarberSync - kurulum scripti (Git Bash icin)
# Calistirma: bash setup.sh

set -e

cd "$(dirname "$0")"
echo "Calisma klasoru: $(pwd)"

# Python komutunu bul
PY=""
for cand in python py python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
      PY="$cand"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo ""
  echo "HATA: Python 3.9+ bulunamadi."
  echo ""
  echo "Once Python kur:"
  echo "  https://www.python.org/downloads/"
  echo "  Yukleme sirasinda 'Add Python to PATH' kutusunu isaretle."
  echo "  Sonra Git Bash'i kapat, yeniden ac ve bu scripti yeniden calistir."
  exit 1
fi

echo "Python bulundu: $PY"
"$PY" --version

# Bagimliliklari yukle
echo ""
echo "Bagimliliklar yukleniyor..."
"$PY" -m pip install --upgrade pip
# --only-binary :all: -> kaynak kodundan derlemeyi tamamen yasakla,
#   pyiceberg gibi yan dependency'lerin Rust build hatalarini onler.
"$PY" -m pip install --only-binary=:all: --prefer-binary -r requirements.txt

# secrets.toml kontrol
if [ ! -f ".streamlit/secrets.toml" ]; then
  echo ""
  echo "UYARI: .streamlit/secrets.toml bulunamadi."
  echo "  Supabase URL ve key'in olmadan uygulama calismaz."
  exit 1
fi

echo ""
echo "Kurulum tamam. Uygulama baslatiliyor..."
echo "Tarayicin acilmazsa: http://localhost:8501"
echo ""
"$PY" -m streamlit run app.py
