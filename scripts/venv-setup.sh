#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip

# editable installs (ajustar si hace falta)
python -m pip install -e /mnt/d/Diplomatura-IA/TpFinal2/Yolo_TACO/dpetrocelli-cloudgpu-automation
python -m pip install -e /mnt/d/Diplomatura-IA/TpFinal2/DiplomaturaIA-Computer-Vision/libs/contracts
python -m pip install -e /mnt/d/Diplomatura-IA/TpFinal2/DiplomaturaIA-Computer-Vision/libs/common

# service deps (ejemplo)
python -m pip install -e /mnt/d/Diplomatura-IA/TpFinal2/DiplomaturaIA-Computer-Vision/services/training-service
python -m pip install -e /mnt/d/Diplomatura-IA/TpFinal2/DiplomaturaIA-Computer-Vision/services/evaluation-service\n