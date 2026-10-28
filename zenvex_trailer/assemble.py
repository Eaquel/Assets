"""Paralel işçilerin gönderdiği kayıpsız parçaları (renders/<çekim>_<ilk>_<son>.mkv) kare dizilerine açar."""
import glob
import os
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
for mkv in sorted(glob.glob(os.path.join(ROOT, "renders", "*.mkv"))):
    shot, f0, f1 = os.path.basename(mkv)[:-4].rsplit("_", 2)
    out = os.path.join(ROOT, "out", "frames", shot)
    os.makedirs(out, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mkv, "-start_number", str(int(f0)), "-pix_fmt", "rgb24", os.path.join(out, "%04d.png")], check=True)
    print(shot, f0, f1, "açıldı")
