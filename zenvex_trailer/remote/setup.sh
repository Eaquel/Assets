#!/bin/bash
# Render işçisi kurulumu: Blender 4.5.9, oyun reposu (sabit commit), animasyon aracı.
set -e
R="$(cd "$(dirname "$0")/.." && pwd)"
[ -e /home/user/promo3d ] || ln -s "$R" /home/user/promo3d
mkdir -p /home/user/tools /home/user/eaquel
if [ ! -x /home/user/tools/blender-4.5.9-linux-x64/blender ]; then
  (cd /home/user/tools && curl -sSL -O https://download.blender.org/release/Blender4.5/blender-4.5.9-linux-x64.tar.xz \
    && tar xf blender-4.5.9-linux-x64.tar.xz && rm blender-4.5.9-linux-x64.tar.xz)
fi
GAME=/home/user/eaquel/zenvex_online
COMMIT=74f36d80f41b2440a588f046b25bb19c1882733a
if [ ! -d $GAME/.git ]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/Eaquel/zenvex_online $GAME
fi
if [ "$(git -C $GAME rev-parse HEAD)" != "$COMMIT" ]; then
  git -C $GAME fetch --depth 1 origin $COMMIT && git -C $GAME -c advice.detachedHead=false checkout $COMMIT
fi
(cd "$R/animdump" && cargo build --release -q)
echo KURULUM_TAMAM
