#!/bin/bash
# Script: git_quick_push.sh
# Uso: ./git_quick_push.sh "Mensaje de commit"

# Verifica que se pase un mensaje de commit
if [ -z "$1" ]; then
  echo "Error: Debes escribir un mensaje de commit."
  echo "Uso: $0 \"Mensaje de commit\""
  exit 1
fi

# Mensaje de commit
COMMIT_MSG="$1"

# Añadir todos los cambios
git add .

# Hacer commit (si no hay cambios, no falla)
git commit -m "$COMMIT_MSG" 2>/dev/null || echo "No hay cambios para commitear"

# Traer cambios remotos y hacer rebase
git fetch origin
git rebase origin/main 2>/dev/null || echo "No hay commits remotos, continuando..."

# Subir cambios al remoto
git push origin main
