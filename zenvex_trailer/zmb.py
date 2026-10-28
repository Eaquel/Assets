"""Oyunun Meshy NPC modellerinden zombi: solgun/çürük ten, kırmızı gözler, kambur + öne uzanan kollar.
Animasyon oyunun motorundan (animdump) gelir; üzerine zombi duruşu eklenir."""
import math
import random

import bpy
import numpy as np
from mathutils import Matrix, Vector

import scene as S
from anim_apply import m4, sample
from zxm_import import import_zxm, read_zxm

NPCS = ["npc_aldric", "npc_diana", "npc_elena", "npc_jack", "npc_marco", "npc_silas", "npc_soldier", "npc_viktor", "npc_sniper"]
UPPER_R, FORE_R, HAND_R, UPPER_L, FORE_L, HAND_L = 3, 4, 5, 6, 7, 8
SPINE, HEAD = 1, 2


def zombify_material(mat, tint=(0.55, 0.62, 0.5), dark=0.6, seed=0):
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = [n for n in nt.nodes if n.type == "TEX_IMAGE"][0]
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = 0.35
    hs.inputs["Value"].default_value = 0.85
    nt.links.new(tex.outputs["Color"], hs.inputs["Color"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 1.0
    nt.links.new(hs.outputs["Color"], mul.inputs[6])
    mul.inputs[7].default_value = (tint[0] * dark, tint[1] * dark, tint[2] * dark, 1)
    # kir ve kan lekeleri
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 7.0 + seed
    nz.inputs["Detail"].default_value = 8
    rp = nt.nodes.new("ShaderNodeMapRange")
    rp.inputs["From Min"].default_value = 0.55
    rp.inputs["From Max"].default_value = 0.7
    nt.links.new(nz.outputs["Fac"], rp.inputs["Value"])
    blood = nt.nodes.new("ShaderNodeMix")
    blood.data_type = "RGBA"
    blood.blend_type = "MULTIPLY"
    nt.links.new(rp.outputs[0], blood.inputs[0])
    nt.links.new(mul.outputs[2], blood.inputs[6])
    blood.inputs[7].default_value = (0.35, 0.06, 0.04, 1)
    nt.links.new(blood.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.75


def eye_points(name):
    meta, pos, nrm, uv, bones, w, tris = read_zxm(name)
    h = meta.get("height", 1.8)
    z = h * 0.925
    sel = (np.abs(pos[:, 2] - z) < 0.025) & (np.abs(pos[:, 0]) < 0.06)
    y = pos[sel][:, 1].min() if sel.any() else -0.1
    return [Vector((sx * 0.032 * h / 1.8, y + 0.012, z)) for sx in (-1, 1)]


class Zombie:
    def __init__(self, name, seed=0, scale=1.0, eye_strength=40.0, dark=0.6, eye_size=0.012, subdiv=0, cloth_frames=None):
        self.name = name
        self.rng = random.Random(seed)
        heavy = name == "vex"
        self.ob, self.rig, self.meta = import_zxm(name, emission=0.0, rough=0.5 if heavy else 0.72, subdiv=subdiv, bump=0.4, metal=0.65 if heavy else 0.15)
        zombify_material(self.ob.data.materials[0], dark=dark, seed=seed % 5)
        if cloth_frames:
            import cloth as CL

            CL.add_cloth(self.ob, self.rig, self.meta, cloth_frames, quality=4)
        self.rig.scale = (scale, scale, scale)
        self.head_rest = [Vector(b["head"]) for b in self.meta["bones"]]
        em = S.emit_mat("zeye", (1.0, 0.08, 0.02, 1), eye_strength)
        hb = self.rig.data.bones["head"]
        to_bone = (hb.matrix_local @ Matrix.Translation((0, hb.length, 0))).inverted()
        for p in eye_points(name):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=eye_size, segments=10, ring_count=5)
            e = bpy.context.object
            e.data.materials.append(em)
            e.visible_shadow = False
            e.parent = self.rig
            e.parent_type = "BONE"
            e.parent_bone = "head"
            e.matrix_parent_inverse = Matrix.Identity(4)
            e.matrix_basis = to_bone @ Matrix.Translation(p)
        # rastgele zombi duruşu
        r = self.rng
        self.hunch = r.uniform(14, 30)
        self.arm_r = r.uniform(55, 85)
        self.arm_l = r.uniform(40, 85)
        self.tilt = r.uniform(-18, 18)
        self.limp = r.uniform(0.0, 1.0)

    def _rot(self, D, idxs, pivot, axis, deg):
        T = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-pivot)
        for i in idxs:
            D[i] = T @ D[i]

    def zpose(self, fr, ph):
        D = [m4(x) for x in fr["bones"]]
        lat = (D[SPINE].to_3x3() @ Vector((1, 0, 0))).normalized()
        up = (D[SPINE].to_3x3() @ Vector((0, 0, 1))).normalized()
        sway = math.sin(ph * math.tau) * 4
        self._rot(D, [SPINE, HEAD, UPPER_R, FORE_R, HAND_R, UPPER_L, FORE_L, HAND_L], D[SPINE] @ self.head_rest[SPINE], lat, self.hunch)
        fwd = (D[SPINE].to_3x3() @ Vector((0, -1, 0))).normalized()
        self._rot(D, [UPPER_R, FORE_R, HAND_R], D[UPPER_R] @ self.head_rest[UPPER_R], lat, -(self.arm_r + sway))
        self._rot(D, [UPPER_L, FORE_L, HAND_L], D[UPPER_L] @ self.head_rest[UPPER_L], lat, -(self.arm_l - sway))
        self._rot(D, [HEAD], D[HEAD] @ self.head_rest[HEAD], fwd, self.tilt + 5 * math.sin(ph * math.tau * 0.5))
        return D

    def key(self, D, frame):
        ao = self.rig
        idx = {b.name: i for i, b in enumerate(ao.data.bones)}
        for b in ao.data.bones:
            i = idx[b.name]
            M = b.matrix_local
            rel = D[i] if b.parent is None else D[idx[b.parent.name]].inverted() @ D[i]
            pb = ao.pose.bones[b.name]
            pb.rotation_mode = "QUATERNION"
            pb.matrix_basis = M.inverted() @ rel @ M
            pb.keyframe_insert("rotation_quaternion", frame=frame)
            pb.keyframe_insert("location", frame=frame)

    def walk(self, frames, start, speed=0.9, heading_deg=0.0, t0=0.0, period=1.3, anim=1, zombie_pose=True):
        """frames: kare listesi; start: (x, y); heading 0 = -Y yönüne (kameraya) yürür"""
        spec = [dict(anim=anim, t=t0 + (f / 24) * 0.75, period=period, weapon="") for f in frames]
        res = sample(self.name, spec)
        h = math.radians(heading_deg)
        d = Vector((math.sin(h), -math.cos(h), 0))
        self.rig.rotation_euler = (0, 0, h)
        for f, fr in zip(frames, res):
            ph = (t0 + f / 24 * 0.75) / period
            D = self.zpose(fr, ph) if zombie_pose else [m4(x) for x in fr["bones"]]
            self.key(D, f)
            self.rig.location = Vector((start[0], start[1], 0)) + d * speed * (f - frames[0]) / 24
            self.rig.keyframe_insert("location", frame=f)

    def anim_frames(self, frames, anim, tfun, period=1.0, zombie_pose=True):
        """oyun animasyonu (ör. KNOCK/DEATH) belirtilen zaman eğrisiyle"""
        spec = [dict(anim=anim, t=tfun(f), period=period, weapon="") for f in frames]
        res = sample(self.name, spec)
        for f, fr in zip(frames, res):
            D = self.zpose(fr, tfun(f)) if zombie_pose else [m4(x) for x in fr["bones"]]
            self.key(D, f)


# --------------------------------------------------------------------------- kafa kesme
def blood_mat():
    m = bpy.data.materials.get("blood")
    if m:
        return m
    m = bpy.data.materials.new("blood")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.3, 0.004, 0.004, 1)
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Emission Color"].default_value = (1.0, 0.03, 0.01, 1)
    b.inputs["Emission Strength"].default_value = 0.03
    b.inputs["Subsurface Weight"].default_value = 0.3
    b.inputs["Subsurface Radius"].default_value = (0.4, 0.02, 0.01)
    return m


def flesh_mat():
    m = bpy.data.materials.get("flesh")
    if m:
        return m
    m = bpy.data.materials.new("flesh")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 60
    rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = (0.10, 0.005, 0.004, 1)
    rp.color_ramp.elements[1].color = (0.35, 0.05, 0.04, 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs[0])
    nt.links.new(rp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.25
    b.inputs["Coat Weight"].default_value = 0.4
    return m


def _keyvis(o, frames_on, frame_switch, prop="hide_render", before=True):
    """frame_switch öncesi `before`, sonrası `not before` (sabit geçiş)"""
    for f, v in ((frame_switch - 1, before), (frame_switch, not before)):
        setattr(o, prop, v)
        o.keyframe_insert(prop, frame=f)
    if o.animation_data and o.animation_data.action:
        for fc in o.animation_data.action.fcurves:
            if fc.data_path == prop:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"


def decapitate(z, hit, end, hdir, rng, sc):
    """z: Zombie (animasyonu yazılmış). hit: kesik karesi. hdir: (x, y) kafanın uçacağı yatay yön."""
    ob, rig, meta = z.ob, z.rig, z.meta
    s = meta.get("height", 1.8) / 1.86 * rig.scale[0]
    B = [Vector(b["head"]) for b in meta["bones"]]
    me = ob.data
    co = np.array([v.co[:] for v in me.vertices])
    neck_z = B[HEAD].z + 0.015 * meta.get("height", 1.8) / 1.86
    hor = np.hypot(co[:, 0] - B[HEAD].x, co[:, 1] - B[HEAD].y)
    is_head = (co[:, 2] > neck_z) & (hor < 0.22)
    vg = ob.vertex_groups.new(name="body_keep")
    vg.add([int(i) for i in np.where(~is_head)[0]], 1.0, "REPLACE")
    msk = ob.modifiers.new("decap", "MASK")
    msk.vertex_group = "body_keep"
    names = [m.name for m in ob.modifiers]
    ob.modifiers.move(names.index("decap"), names.index("sub") if "sub" in names else len(names) - 1)
    msk.show_render = False
    msk.keyframe_insert("show_render", frame=hit - 1)
    msk.show_render = True
    msk.keyframe_insert("show_render", frame=hit)
    for fc in ob.animation_data.action.fcurves:
        if "decap" in fc.data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    # kesik anındaki (pozlanmış + kumaşlı) kafa şeklini ayrı nesneye al
    sub = ob.modifiers.get("sub")
    if sub:
        sub.show_viewport = False
    msk.show_viewport = False
    sc.frame_set(hit)
    dg = bpy.context.evaluated_depsgraph_get()
    hm = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    mw = ob.matrix_world.copy()
    if sub:
        sub.show_viewport = True
    msk.show_viewport = True
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(hm)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not is_head[v.index]], context="VERTS")
    bm.transform(mw)
    cen = sum((v.co for v in bm.verts), Vector()) / max(len(bm.verts), 1)
    low = min(v.co.z for v in bm.verts)
    bmesh.ops.translate(bm, verts=bm.verts, vec=-cen)
    bm.to_mesh(hm)
    bm.free()
    head = bpy.data.objects.new(ob.name + "_head", hm)
    sc.collection.objects.link(head)
    if sub:
        m = head.modifiers.new("sub", "SUBSURF")
        m.levels = m.render_levels = 1
    _keyvis(head, None, hit, before=True)
    # boyun güdükleri (gövdede ve kafanın altında)
    fm = flesh_mat()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.055 * s, segments=16, ring_count=8)
    st = bpy.context.object
    st.scale = (1.0, 0.9, 0.35)
    st.data.materials.append(fm)
    hb = rig.data.bones["head"]
    st.parent = rig
    st.parent_type = "BONE"
    st.parent_bone = "head"
    st.matrix_parent_inverse = Matrix.Identity(4)
    st.matrix_basis = (hb.matrix_local @ Matrix.Translation((0, hb.length, 0))).inverted() @ Matrix.Translation((B[HEAD].x, B[HEAD].y, neck_z)) @ Matrix.Diagonal((1.0, 0.9, 0.35, 1))
    _keyvis(st, None, hit, before=True)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05 * s, segments=16, ring_count=8)
    hs = bpy.context.object
    hs.data.materials.append(fm)
    hs.parent = head
    hs.location = (0, 0, low - cen.z + 0.01)
    hs.scale = (1.0, 0.9, 0.3)
    # gözler söner (kafa artık ölü)
    for c in rig.children:
        if c.parent_type == "BONE" and c.parent_bone == "head" and c is not st:
            _keyvis(c, None, hit, before=False)
    # kafa fiziği: parabol + dönme + zemin sekmesi
    p = cen.copy()
    v = Vector((hdir[0] * 2.4, hdir[1] * 2.4, 3.4)) + Vector((rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(-0.3, 0.5)))
    axis = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.3))).normalized()
    wv = rng.uniform(11, 16)
    q = Matrix.Identity(3).to_quaternion()
    rad = 0.11 * s
    head.rotation_mode = "QUATERNION"
    path = []
    dt = 1 / 24 / 6
    for f in range(hit, end + 1):
        head.location = p
        head.rotation_quaternion = q
        head.keyframe_insert("location", frame=f)
        head.keyframe_insert("rotation_quaternion", frame=f)
        path.append((f, p.copy()))
        for _ in range(6):
            v.z -= 9.81 * dt
            p = p + v * dt
            q = (Matrix.Rotation(wv * dt, 3, axis).to_quaternion() @ q).normalized()
            if p.z < rad and v.z < 0:
                p.z = rad
                v.z = -v.z * 0.32
                v.x *= 0.62
                v.y *= 0.62
                wv *= 0.55
    # kan fışkırması: boyundan (karede boyun konumunu izleyen yayıcı) + kafanın altından
    neck_pos = {}
    for f in range(hit, min(end, hit + 22) + 1):
        sc.frame_set(f)
        pb = rig.pose.bones["head"]
        neck_pos[f] = (rig.matrix_world @ pb.matrix @ hb.matrix_local.inverted() @ Vector((B[HEAD].x, B[HEAD].y, neck_z))).copy()
    em = _emitter("blood_neck", neck_pos, 0.035 * s, hit, hit + 14, 1000, (0, 0, 2.6), 1.1, rng.randrange(1000))
    em2 = _emitter("blood_head", None, 0.03 * s, hit, hit + 9, 220, (0, 0, -0.6), 0.9, rng.randrange(1000), parent=head, ploc=(0, 0, low - cen.z))
    # yere düşen kan lekeleri
    bm_ = blood_mat()
    base = neck_pos[hit]
    for i in range(16):
        d = rng.uniform(0.2, 1.7)
        off = Vector((hdir[0], hdir[1], 0)) * d + Vector((rng.gauss(0, 0.35), rng.gauss(0, 0.35), 0))
        r = rng.uniform(0.04, 0.17) * s
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=1.0, depth=0.004, location=(base.x + off.x, base.y + off.y, 0.003 + i * 0.0002))
        sp = bpy.context.object
        sp.data.materials.append(bm_)
        sp.scale = (r * rng.uniform(0.7, 1.4), r, 1)
        sp.rotation_euler.z = rng.uniform(0, 6.3)
        fa = hit + int(5 + d * 7 + rng.uniform(0, 4))
        for f, k in ((fa - 1, 0.001), (fa + 3, 1.0)):
            sp.scale = (r * k * 1.2, r * k, 1)
            sp.keyframe_insert("scale", frame=f)
    # kafanın düştüğü yere de leke
    for f, pp in path:
        if pp.z <= rad + 0.002 and f > hit + 3:
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.12 * s, depth=0.004, location=(pp.x, pp.y, 0.004))
            sp = bpy.context.object
            sp.data.materials.append(bm_)
            for ff, k in ((f - 1, 0.001), (f + 4, 1.0)):
                sp.scale = (k, k * 0.8, 1)
                sp.keyframe_insert("scale", frame=ff)
            break
    return head


def _emitter(name, track, radius, f0, f1, count, vel, rand, seed, parent=None, ploc=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=8, ring_count=4)
    em = bpy.context.object
    em.name = name
    if parent is not None:
        em.parent = parent
        em.location = ploc
    elif track:
        for f, p in track.items():
            em.location = p
            em.keyframe_insert("location", frame=f)
    em.show_instancer_for_render = False
    drop = bpy.data.objects.get("blood_drop")
    if drop is None:
        bpy.ops.mesh.primitive_ico_sphere_add(radius=0.016, subdivisions=2, location=(0, 0, -100))
        drop = bpy.context.object
        drop.name = "blood_drop"
        drop.data.materials.append(blood_mat())
        drop.hide_render = True
    ps = em.modifiers.new("ps", "PARTICLE_SYSTEM").particle_system
    st = ps.settings
    st.count = count
    st.frame_start, st.frame_end = f0, f1
    st.lifetime = 34
    st.emit_from = "VOLUME"
    st.normal_factor = 0.0
    st.object_align_factor = vel
    st.factor_random = rand
    st.object_factor = 0.4
    st.render_type = "OBJECT"
    st.instance_object = drop
    st.particle_size = 1.0
    st.size_random = 0.8
    st.use_rotations = True
    st.rotation_mode = "VEL"
    st.effector_weights.gravity = 1.0
    st.effector_weights.wind = 0.0
    st.use_die_on_collision = True
    ps.seed = seed
    return em
