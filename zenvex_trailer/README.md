# Zenvex Online — 15 sn sinematik tanıtım (Kael)

Blender 4.5 (Cycles) ile, oyunun kendi 3B modelleri (`android/app/src/main/assets/m3d`) ve kendi animasyon motoru
(`rust/zenvex_r3d`, `animdump` aracıyla) kullanılarak üretilir.

| Dosya | Görev |
|---|---|
| `zxm_import.py` | `.zxm` modellerini iskelet, ağırlık ve dokuyla Blender'a aktarır; yüzey ayrıntısı (kabartma, pürüzlülük, metal) |
| `anim_apply.py`, `animdump/` | Oyunun animasyon motorundan kemik dönüşümlerini alıp iskelete yazar |
| `zmb.py` | NPC modellerinden zombi (duruş, ten, gözler) ve kafa kesme (fizik, kan, lekeler) |
| `cloth.py` | Palto/pelerin/saç için kumaş simülasyonu, çarpışma kapsülleri, rüzgâr |
| `scene.py` | Sokak, binalar (oyunun bina üreticisi), is/kir, moloz, ateş, korlar, sis, kompozit |
| `shots.py` | 7 çekim (A, B, C, D1, D2, E, F) |
| `post.py` | Kurgu: renk, flaş, sarsıntı, yazılar, logo kartı, ses tasarımı → mp4 |
| `bake_fire.py`, `flipbook.py` | Mantaflow ateş simülasyonu → dikişsiz döngü flipbook (`cache/flipL`) |
| `remote/` | Paralel render işçileri: `render_chunk.sh <çekim> <ilk> <son>` |

Tek makinede: `blender -b -P shots.py -- <çekim>` ile kareler `out/frames/<çekim>/`, ardından `python3 post.py`.
