"""İkincil hareket: karakter mesh'inde etek/palto/pelerin/saç bölgeleri gerçek kumaş simülasyonuyla sallanır.

Bacak ve gövde iskelete sabit (pin ağırlığı 1), etek uçları serbest; bacaklara ve gövdeye görünmez çarpışma kapsülleri
takılır ki kumaş bacakların içinden geçmesin. Hafif, gürültülü rüzgâr alanı.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

PELVIS, SPINE, HEAD, UPPER_R, FORE_R, HAND_R, UPPER_L, FORE_L, HAND_L, THIGH_R, SHIN_R, THIGH_L, SHIN_L = range(13)


def _seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def _ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


CFG = {
    "npc_diana": dict(skirt=False, cape=False), "npc_viktor": dict(skirt=False, cape=False), "npc_jack": dict(skirt=False, cape=False),
    "npc_soldier": dict(skirt=False, cape=False), "npc_sniper": dict(skirt=False, cape=False), "npc_elena": dict(zmin=0.55), "vex": dict(front_only=True, zmin=0.5, cape=False),
}


def free_weights(pos, meta, hair=True, cape=True, skirt=True, zmin=0.32, front_only=False):
    """her köşe için serbestlik 0..1 (1 = tamamen kumaş)"""
    h = meta.get("height", 1.8)
    s = h / 1.86
    B = [np.array(b["head"]) for b in meta["bones"]]
    foot_r = B[SHIN_R].copy()
    foot_r[2] = 0.06
    foot_l = B[SHIN_L].copy()
    foot_l[2] = 0.06
    dleg = np.minimum.reduce([_seg_dist(pos, B[THIGH_R], B[SHIN_R]), _seg_dist(pos, B[SHIN_R], foot_r),
                              _seg_dist(pos, B[THIGH_L], B[SHIN_L]), _seg_dist(pos, B[SHIN_L], foot_l)])
    z = pos[:, 2]
    hip = B[PELVIS][2] + 0.04 * s
    r_leg = 0.095 * s
    free = np.zeros(len(pos))
    if skirt:
        # bacaktan uzak, kalçanın altındaki kumaş; aşağı indikçe serbestleşir
        away = _ss(r_leg + 0.015 * s, r_leg + 0.07 * s, dleg)
        down = _ss(0.0, 0.40 * s, hip - z)
        sk = away * down * _ss(zmin * s - 0.05, zmin * s + 0.05, z)
        if front_only:
            sk = sk * _ss(0.0, 0.08, -pos[:, 1]) * _ss(0.32 * s, 0.22 * s, np.abs(pos[:, 0]))
        free = np.maximum(free, sk)
    if cape:
        # sırttaki pelerin: omurgadan uzak, arkada (y > 0) ve göğüsten aşağıda
        # omurganın yatay uzaklığı (bacaklar sayılmasın diye kalça üstü + belirgin arkada)
        rxy = np.hypot(pos[:, 0] - B[SPINE][0], pos[:, 1] - B[SPINE][1])
        back = _ss(0.10 * s, 0.16 * s, pos[:, 1] - B[SPINE][1])
        far = _ss(0.14 * s, 0.22 * s, rxy)
        low = _ss(0.0, 0.5 * s, B[SPINE][2] + 0.1 * s - z) * _ss(hip - 0.45 * s, hip - 0.25 * s, z)
        free = np.maximum(free, back * far * low * 0.85)
    if hair:
        # başın arkasından/altından sarkan saç (kafa kemiğine yakın, boyun ekseninden uzak, kafa merkezinin altında)
        hb = B[HEAD]
        dh = np.linalg.norm(pos - (hb + np.array([0, 0, 0.12 * s])), axis=1)
        dneck = _seg_dist(pos, B[SPINE], hb + np.array([0, 0, 0.2 * s]))
        hang = (_ss(0.075 * s, 0.11 * s, dneck) * (dh < 0.30 * s) * _ss(-0.02, 0.08, hb[2] + 0.16 * s - z)
                * _ss(hb[2] - 0.10 * s, hb[2] - 0.02 * s, z) * _ss(0.03 * s, 0.08 * s, pos[:, 1] - hb[1]))
        free = np.maximum(free, hang * 0.7)
    return np.clip(free, 0, 1)


def capsule(name, rig, bone, a, b, r):
    """görünmez çarpışma kapsülü, kemiğe bağlı"""
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=r, depth=max(d.length, 0.02), location=(a + b) / 2)
    o = bpy.context.object
    o.name = name
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bn = rig.data.bones[bone]
    to_bone = (bn.matrix_local @ Matrix.Translation((0, bn.length, 0))).inverted()
    o.parent = rig
    o.parent_type = "BONE"
    o.parent_bone = bone
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_basis = to_bone
    c = o.modifiers.new("col", "COLLISION")
    o.collision.thickness_outer = 0.012
    o.collision.cloth_friction = 5.0
    o.hide_render = True
    o.display_type = "WIRE"
    o.visible_camera = False
    return o


def add_cloth(ob, rig, meta, frames, quality=5, hair=True, cape=True, skirt=True, stiff=1.0, colliders=True):
    """ob: karakter mesh'i (Armature değiştiricisi ilk sırada). frames: (başlangıç, bitiş) önbellek aralığı"""
    me = ob.data
    pos = np.array([v.co[:] for v in me.vertices])
    kw = dict(hair=hair, cape=cape, skirt=skirt)
    kw.update(CFG.get(meta.get("name", ""), {}))
    free = free_weights(pos, meta, **kw)
    if (free > 0.3).sum() < 30:
        return None
    vg = ob.vertex_groups.new(name="pin")
    pin = 1.0 - free
    for i, w in enumerate(pin):
        vg.add([i], float(w), "REPLACE")
    cl = ob.modifiers.new("cloth", "CLOTH")
    # sıra: Armature → Cloth → (Subsurf)
    names = [m.name for m in ob.modifiers]
    ob.modifiers.move(names.index("cloth"), names.index("arm") + 1 if "arm" in names else 0)
    st = cl.settings
    st.quality = quality
    st.mass = 0.4
    st.air_damping = 2.0
    st.tension_stiffness = 30 * stiff
    st.compression_stiffness = 30 * stiff
    st.shear_stiffness = 12 * stiff
    st.bending_stiffness = 2.0 * stiff
    st.tension_damping = 5
    st.compression_damping = 5
    st.bending_damping = 0.5
    st.vertex_group_mass = "pin"
    st.pin_stiffness = 1.2
    st.use_internal_springs = False
    cs = cl.collision_settings
    cs.use_collision = True
    cs.distance_min = 0.008
    cs.collision_quality = 3
    cs.use_self_collision = False
    pc = cl.point_cache
    pc.frame_start, pc.frame_end = frames
    if colliders:
        h = meta.get("height", 1.8)
        s = h / 1.86
        Bn = [Vector(b["head"]) for b in meta["bones"]]
        nm = ob.name
        for th, sh, side in ((THIGH_R, SHIN_R, "r"), (THIGH_L, SHIN_L, "l")):
            capsule(nm + "_ct" + side, rig, "thigh_" + side, Bn[th], Bn[sh], 0.085 * s)
            foot = Vector((Bn[sh].x, Bn[sh].y, 0.07))
            capsule(nm + "_cs" + side, rig, "shin_" + side, Bn[sh], foot, 0.065 * s)
        capsule(nm + "_cb", rig, "spine", Bn[PELVIS] + Vector((0, 0, -0.05 * s)), Bn[HEAD] + Vector((0, 0, -0.08 * s)), 0.15 * s)
    return cl


def wind(strength=2.5, direction=(0.3, -1.0, 0.0), noise=1.5):
    bpy.ops.object.effector_add(type="WIND", location=(0, 0, 1))
    w = bpy.context.object
    w.name = "Wind"
    w.rotation_euler = Vector(direction).to_track_quat("Z", "Y").to_euler()
    w.field.strength = strength
    w.field.noise = noise
    w.field.flow = 0.6
    return w
