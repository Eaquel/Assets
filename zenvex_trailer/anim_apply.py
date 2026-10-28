"""Oyunun animasyon motorundan (animdump) kareleri alıp Blender iskeletine ve silaha anahtar kare olarak yazar."""
import json
import subprocess

import bpy
from mathutils import Matrix

from zxm_import import M3D

DUMP = "/home/user/promo3d/animdump/target/release/animdump"


def sample(ch, spec):
    r = subprocess.run([DUMP, M3D, ch], input=json.dumps(spec), capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def m4(x):
    r = x["r"]
    t = x["t"]
    return Matrix(((r[0][0], r[0][1], r[0][2], t[0]), (r[1][0], r[1][1], r[1][2], t[1]), (r[2][0], r[2][1], r[2][2], t[2]), (0, 0, 0, 1)))


def key_pose(ao, weapon, fr, frame):
    """fr: animdump çıktısının bir karesi; ao: iskelet nesnesi; weapon: silah nesnesi (iskelete bağlı) ya da None"""
    for pb in ao.pose.bones:
        pb.rotation_mode = "QUATERNION"
    # P_i = D_i·M_i (armatür uzayı), B_i = M_i⁻¹·D_ebeveyn⁻¹·D_i·M_i → sahne güncellemesi gerekmez
    D = [m4(x) for x in fr["bones"]]
    idx = {b.name: i for i, b in enumerate(ao.data.bones)}
    for b in ao.data.bones:
        i = idx[b.name]
        M = b.matrix_local
        rel = D[i] if b.parent is None else D[idx[b.parent.name]].inverted() @ D[i]
        ao.pose.bones[b.name].matrix_basis = M.inverted() @ rel @ M
    for pb in ao.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=frame)
        pb.keyframe_insert("location", frame=frame)
    if weapon is not None and fr["weapon"] is not None:
        weapon.matrix_basis = m4(fr["weapon"])
        weapon.keyframe_insert("location", frame=frame)
        weapon.keyframe_insert("rotation_euler", frame=frame)
        weapon.hide_render = False
        weapon.keyframe_insert("hide_render", frame=frame)


def attach_weapon(ao, wob):
    wob.parent = ao
    wob.matrix_parent_inverse = Matrix.Identity(4)
    wob.rotation_mode = "XYZ"
