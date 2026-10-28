#!/bin/bash
# Kullanım: render_chunk.sh <çekim> <ilk kare> <son kare>
# Kareleri final ayarlarla render eder, kayıpsız RGB videoya (libx264rgb -qp 0) paketler, dala gönderir.
set -e
SHOT=$1; F0=$2; F1=$3
R="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(git -C "$R" rev-parse --show-toplevel)"
BR="$(git -C "$REPO" branch --show-current)"
bash "$R/remote/setup.sh"
cd /home/user/promo3d
mkdir -p logs renders
for f in $(seq $F0 $F1); do rm -f out/frames/$SHOT/$(printf %04d $f).png; done
PYTHONUNBUFFERED=1 /home/user/tools/blender-4.5.9-linux-x64/blender -b -P shots.py -- $SHOT $F0 $F1 > logs/${SHOT}_${F0}.log 2>&1 || true
N=$((F1 - F0 + 1))
GOT=$(ls out/frames/$SHOT/ 2>/dev/null | wc -l)
if [ "$GOT" -lt "$N" ]; then echo "EKSIK KARE: $GOT/$N"; tail -30 logs/${SHOT}_${F0}.log; exit 1; fi
OUT=renders/${SHOT}_$(printf %04d $F0)_$(printf %04d $F1).mkv
ffmpeg -v error -y -framerate 24 -start_number $F0 -i out/frames/$SHOT/%04d.png -frames:v $N -c:v libx264rgb -qp 0 -preset veryslow "$OUT"
cd "$REPO"
git add "zenvex_trailer/$OUT" "zenvex_trailer/logs/${SHOT}_${F0}.log"
git commit -q -m "Tanıtım render: $SHOT $F0-$F1"
for i in 1 2 3 4 5 6 7 8; do
  if git push -q origin "$BR"; then echo "GONDERILDI $OUT"; exit 0; fi
  git pull -q --rebase origin "$BR" || true
  sleep $((i * 3))
done
echo "PUSH BASARISIZ"; exit 1
