#!/bin/bash
cd /home/user/promo3d
for s in A B C D1 D2 E F; do
  echo "=== $s $(date +%T)" >> out/render.log
  PYTHONUNBUFFERED=1 /home/user/tools/blender-4.5.9-linux-x64/blender -b -P shots.py -- $s 2>&1 | grep --line-buffered -E "KARE|Error|Trace|HIT" >> out/render.log
done
echo "=== BITTI $(date +%T)" >> out/render.log
