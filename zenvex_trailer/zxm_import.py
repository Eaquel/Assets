"""Zenvex .zxm modellerini Blender'a aktarır (mesh + UV + doku + iskelet + ağırlıklar)."""
import json
import os
import struct

import bpy
import numpy as np
from mathutils import Vector

M3D = "/home/user/eaquel/zenvex_online/android/app/src/main/assets/m3d"


def read_zxm(name):
    b = open(os.path.join(M3D, name + ".zxm"), "rb").read()
    assert b[:4] == b"ZXM1"
    jl = struct.unpack("<I", b[4:8])[0]
    meta = json.loads(b[8 : 8 + jl])
    off = 8 + jl
    nv, st = meta["nverts"], meta["vstride"]
    raw = np.frombuffer(b, np.uint8, nv * st, off).reshape(nv, st)
    lo, hi = np.array(meta["lo"]), np.array(meta["hi"])
    q = raw[:, 0:6].copy().view("<u2").astype(np.float64)
    pos = lo + q / 65535.0 * (hi - lo)
    nrm = raw[:, 6:9].astype(np.int8).astype(np.float64)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    uv = raw[:, 10:14].copy().view("<u2").astype(np.float64) / 65535.0
    bones = raw[:, 14:16].astype(int)
    w = raw[:, 16].astype(np.float64) / 255.0
    off += nv * st
    tris = np.frombuffer(b, "<u2", meta["ntris"] * 3, off).reshape(-1, 3).astype(int)
    return meta, pos, nrm, uv, bones, w, tris


def detail(nt, tex, bsdf, rough=0.55, bump=0.25, metal=0.0, micro=0.08):
    """dokudan yüzey ayrıntısı: kabartma (parlaklıktan + mikro gürültü), pürüzlülük farkı, gri-açık bölgelere metal"""
    lum = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(tex.outputs["Color"], lum.inputs[0])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.004
    nt.links.new(lum.outputs[0], bp.inputs["Height"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 380.0
    nz.inputs["Detail"].default_value = 4
    bp2 = nt.nodes.new("ShaderNodeBump")
    bp2.inputs["Strength"].default_value = micro
    bp2.inputs["Distance"].default_value = 0.001
    nt.links.new(nz.outputs["Fac"], bp2.inputs["Height"])
    nt.links.new(bp.outputs[0], bp2.inputs["Normal"])
    nt.links.new(bp2.outputs[0], bsdf.inputs["Normal"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = min(1.0, rough + 0.18)
    rr.inputs["To Max"].default_value = max(0.05, rough - 0.22)
    nt.links.new(lum.outputs[0], rr.inputs["Value"])
    nt.links.new(rr.outputs[0], bsdf.inputs["Roughness"])
    if metal > 0:
        hsv = nt.nodes.new("ShaderNodeSeparateColor")
        hsv.mode = "HSV"
        nt.links.new(tex.outputs["Color"], hsv.inputs["Color"])
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        nt.links.new(hsv.outputs[1], inv.inputs[1])
        vm = nt.nodes.new("ShaderNodeMapRange")
        vm.inputs["From Min"].default_value = 0.25
        vm.inputs["From Max"].default_value = 0.6
        nt.links.new(hsv.outputs[2], vm.inputs["Value"])
        mm = nt.nodes.new("ShaderNodeMath")
        mm.operation = "MULTIPLY"
        nt.links.new(inv.outputs[0], mm.inputs[0])
        nt.links.new(vm.outputs[0], mm.inputs[1])
        ms = nt.nodes.new("ShaderNodeMath")
        ms.operation = "MULTIPLY"
        ms.inputs[1].default_value = metal
        nt.links.new(mm.outputs[0], ms.inputs[0])
        nt.links.new(ms.outputs[0], bsdf.inputs["Metallic"])


def material_for(name, emission=0.0, rough=0.55, bump=0.25, metal=0.0):
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(M3D, name + ".webp"))
    tex.interpolation = "Cubic"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    detail(nt, tex, bsdf, rough, bump, metal)
    # parlak (doymuş, açık) piksellere hafif ışıma: kor, neon, göz
    if emission > 0:
        hsv = nt.nodes.new("ShaderNodeSeparateColor")
        hsv.mode = "HSV"
        nt.links.new(tex.outputs["Color"], hsv.inputs["Color"])
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        nt.links.new(hsv.outputs[1], mul.inputs[0])
        nt.links.new(hsv.outputs[2], mul.inputs[1])
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.inputs["From Min"].default_value = 0.45
        ramp.inputs["From Max"].default_value = 0.8
        nt.links.new(mul.outputs[0], ramp.inputs["Value"])
        sc = nt.nodes.new("ShaderNodeMath")
        sc.operation = "MULTIPLY"
        sc.inputs[1].default_value = emission
        nt.links.new(ramp.outputs[0], sc.inputs[0])
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        nt.links.new(sc.outputs[0], bsdf.inputs["Emission Strength"])
    return mat


def import_zxm(name, emission=0.0, rough=0.55, subdiv=1, rig=True, bump=0.25, metal=0.0):
    meta, pos, nrm, uv, bones, w, tris = read_zxm(name)
    me = bpy.data.meshes.new(name)
    me.from_pydata(pos.tolist(), [], tris.tolist())
    me.update()
    uvl = me.uv_layers.new(name="UV")
    loops = np.array([l.vertex_index for l in me.loops])
    u = uv[loops]
    uvl.data.foreach_set("uv", np.c_[u[:, 0], 1.0 - u[:, 1]].ravel())
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.normals_split_custom_set_from_vertices(nrm.tolist())
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(material_for(name, emission, rough, bump, metal))
    if subdiv:
        m = ob.modifiers.new("sub", "SUBSURF")
        m.levels = subdiv
        m.render_levels = subdiv
        m.uv_smooth = "PRESERVE_BOUNDARIES"
    if not rig or not meta.get("bones"):
        return ob, None, meta
    # iskelet
    arm = bpy.data.armatures.new(name + "_rig")
    ao = bpy.data.objects.new(name + "_rig", arm)
    bpy.context.scene.collection.objects.link(ao)
    bpy.context.view_layer.objects.active = ao
    bpy.ops.object.mode_set(mode="EDIT")
    B = meta["bones"]
    kids = {i: [j for j, c in enumerate(B) if c["parent"] == i] for i in range(len(B))}
    ebs = []
    for i, bd in enumerate(B):
        eb = arm.edit_bones.new(bd["name"])
        h = Vector(bd["head"])
        if kids[i]:
            t = sum((Vector(B[k]["head"]) for k in kids[i] if not B[k]["name"].startswith(("upper", "thigh"))), Vector())
            n = len([k for k in kids[i] if not B[k]["name"].startswith(("upper", "thigh"))])
            t = t / n if n else h + Vector((0, 0, 0.15))
        elif bd["name"] == "head":
            t = h + Vector((0, 0, 0.22))
        elif bd["name"].startswith("hand"):
            p = Vector(B[bd["parent"]]["head"])
            t = h + (h - p).normalized() * 0.1
        else:  # baldır → ayak
            t = Vector((h.x, h.y, 0.03))
        if (t - h).length < 0.02:
            t = h + Vector((0, 0, 0.1))
        eb.head, eb.tail = h, t
        ebs.append(eb)
    for i, bd in enumerate(B):
        if bd["parent"] >= 0:
            ebs[i].parent = ebs[bd["parent"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    vgs = [ob.vertex_groups.new(name=bd["name"]) for bd in B]
    for vi in range(len(pos)):
        b0, b1, ww = bones[vi, 0], bones[vi, 1], w[vi]
        vgs[b0].add([vi], float(ww), "ADD")
        if ww < 1.0:
            vgs[b1].add([vi], float(1.0 - ww), "ADD")
    mod = ob.modifiers.new("arm", "ARMATURE")
    mod.object = ao
    # armatür değiştiricisi alt bölmeden önce
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    ob.parent = ao
    return ob, ao, meta
