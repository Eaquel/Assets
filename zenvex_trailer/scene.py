"""Tanıtım sahnesi: gün batımında yıkık şehir sokağı, sis, yangınlar, korlar, Kael + tırpan, zombi silüetleri."""
import math
import os
import random
import sys

T = "/home/user/eaquel/zenvex_online/tools"
sys.path[:0] = ["/home/user/promo3d", T + "/blender", T + "/assetgen"]

import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

GROUND = "/home/user/eaquel/zenvex_online/android/app/src/main/assets/v2/ground"


def reset(res=(1920, 1080), samples=32, fps=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.cycles.volume_bounces = 0
    sc.cycles.volume_step_rate = 4.0
    sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = False
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.fps = fps
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    sc.view_layers[0].use_pass_mist = True
    return sc


def hexc(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x ** 2.2 for x in c) + (a,)


def emit_mat(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = color
    e.inputs[1].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


def tex_mat(name, img, scale=1.0, rough=0.8, tint=None, bump=0.3):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["Generated" if scale == 0 else "Object"], mp.inputs[0])
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(img)
    nt.links.new(mp.outputs[0], t.inputs[0])
    col = t.outputs["Color"]
    if tint:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        nt.links.new(col, mix.inputs[6])
        mix.inputs[7].default_value = tint
        col = mix.outputs[2]
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    if bump:
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(t.outputs["Color"], bw.inputs[0])
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump
        nt.links.new(bw.outputs[0], bp.inputs["Height"])
        nt.links.new(bp.outputs[0], bsdf.inputs["Normal"])
    return m


def plane(name, size, loc, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = (size[0], size[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    return o


def new_objects(fn):
    before = set(bpy.data.objects)
    fn()
    return [o for o in bpy.data.objects if o not in before]


def place(objs, loc, rot_z=0.0):
    for o in objs:
        if o.parent is None:
            o.location = Vector(loc) + Euler((0, 0, rot_z)).to_matrix() @ o.location
            o.rotation_euler.z += rot_z


def sky(sun_elev=4.0, sun_rot=180.0, strength=0.6, haze="#ff7a3a"):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    s = nt.nodes.new("ShaderNodeTexSky")
    s.sky_type = "NISHITA"
    s.sun_elevation = math.radians(sun_elev)
    s.sun_rotation = math.radians(sun_rot)
    s.air_density = 3.0
    s.dust_density = 6.0
    s.sun_disc = True
    s.sun_size = math.radians(2.5)
    s.sun_intensity = 0.4
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 0.6
    nt.links.new(s.outputs[0], mix.inputs[6])
    mix.inputs[7].default_value = hexc(haze)
    nt.links.new(mix.outputs[2], bg.inputs[0])
    bg.inputs[1].default_value = strength
    return w


def light(kind, loc, energy, color, size=1.0, target=None, name="L"):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, kind))
    l.data.energy = energy
    l.data.color = color[:3]
    if kind == "AREA":
        l.data.size = size
    elif kind in ("POINT", "SPOT"):
        l.data.shadow_soft_size = size
    elif kind == "SUN":
        l.data.angle = math.radians(size)
    l.location = loc
    bpy.context.scene.collection.objects.link(l)
    if target is not None:
        l.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return l


def fog_box(center, size, density=0.02, color="#ffb27a", anisotropy=0.5):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    o = bpy.context.object
    o.name = "Fog"
    o.scale = size
    m = bpy.data.materials.new("fog")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    v = nt.nodes.new("ShaderNodeVolumePrincipled")
    v.inputs["Color"].default_value = hexc(color)
    v.inputs["Density"].default_value = density
    v.inputs["Anisotropy"].default_value = anisotropy
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(v.outputs[0], out.inputs["Volume"])
    o.data.materials.append(m)
    o.visible_shadow = False
    return o


def fire(loc, scale=1.0, seed=0, strength=40.0):
    """Ucuz yangın: gürültüyle maskelenmiş ışıyan volume (ateş dili) + titreyen nokta ışık."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(loc[0], loc[1], loc[2] + 0.8 * scale), segments=16, ring_count=8)
    o = bpy.context.object
    o.name = "Fire"
    o.scale = (0.7 * scale, 0.7 * scale, 1.3 * scale)
    m = bpy.data.materials.new("fire%d" % seed)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    nt.links.new(tc.outputs["Object"], mp.inputs[0])
    # yukarı akan gürültü: W zamanla (sürücü) değişir
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 2.2
    nz.inputs["Detail"].default_value = 6
    nz.inputs["Roughness"].default_value = 0.6
    fc = nz.inputs["W"].driver_add("default_value")
    fc.driver.expression = "frame/9.0+%d" % seed
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    # yükseklik maskesi: altta yoğun, üstte söner
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    grad = nt.nodes.new("ShaderNodeMapRange")
    grad.inputs["From Min"].default_value = -1.0
    grad.inputs["From Max"].default_value = 1.0
    grad.inputs["To Min"].default_value = 1.0
    grad.inputs["To Max"].default_value = 0.0
    nt.links.new(sep.outputs["Z"], grad.inputs["Value"])
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    nt.links.new(tc.outputs["Object"], ln.inputs[0])
    rad = nt.nodes.new("ShaderNodeMapRange")
    rad.inputs["From Min"].default_value = 0.3
    rad.inputs["From Max"].default_value = 1.0
    rad.inputs["To Min"].default_value = 1.0
    rad.inputs["To Max"].default_value = 0.0
    nt.links.new(ln.outputs["Value"], rad.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(grad.outputs[0], mul.inputs[0])
    nt.links.new(rad.outputs[0], mul.inputs[1])
    mul2 = nt.nodes.new("ShaderNodeMath")
    mul2.operation = "MULTIPLY"
    nt.links.new(nz.outputs["Fac"], mul2.inputs[0])
    nt.links.new(mul.outputs[0], mul2.inputs[1])
    th = nt.nodes.new("ShaderNodeMapRange")
    th.inputs["From Min"].default_value = 0.25
    th.inputs["From Max"].default_value = 0.55
    nt.links.new(mul2.outputs[0], th.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].color = (0, 0, 0, 1)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (1.0, 0.85, 0.5, 1)
    e = cr.elements.new(0.35)
    e.color = (0.9, 0.12, 0.01, 1)
    e2 = cr.elements.new(0.7)
    e2.color = (1.0, 0.45, 0.05, 1)
    nt.links.new(th.outputs[0], ramp.inputs[0])
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.0
    nt.links.new(ramp.outputs[0], vol.inputs["Emission Color"])
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "MULTIPLY"
    st.inputs[1].default_value = strength
    nt.links.new(th.outputs[0], st.inputs[0])
    nt.links.new(st.outputs[0], vol.inputs["Emission Strength"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    o.data.materials.append(m)
    o.visible_shadow = False
    pl = light("POINT", (loc[0], loc[1], loc[2] + 0.9 * scale), 900 * scale * scale, (1.0, 0.42, 0.12), size=0.6 * scale, name="FireL")
    fc = pl.data.driver_add("energy")
    fc.driver.expression = "%f*(0.78+0.12*sin(frame*0.9+%d)+0.1*sin(frame*0.37+%d))" % (900 * scale * scale, seed * 7, seed * 3)
    return o, pl


def embers(center, size, count=900, seed=1, frames=(1, 400), strength=60.0, rise=1.0, color=(1.0, 0.35, 0.05, 1)):
    """Uçuşan korlar: küçük ışıyan kürecikler, rüzgârla yükselir (parçacık sistemi)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    em = bpy.context.object
    em.name = "EmberSrc"
    em.scale = size
    em.hide_render = True
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.012, subdivisions=1, location=(0, 0, -50))
    sp = bpy.context.object
    sp.name = "Ember"
    sp.data.materials.append(emit_mat("ember", color, strength))
    sp.hide_render = True
    ps = em.modifiers.new("ps", "PARTICLE_SYSTEM").particle_system
    s = ps.settings
    s.count = count
    s.frame_start = frames[0] - 120
    s.frame_end = frames[1]
    s.lifetime = 160
    s.lifetime_random = 0.6
    s.emit_from = "VOLUME"
    s.normal_factor = 0
    s.object_align_factor = (0.25, 0.0, 0.5 * rise)
    s.factor_random = 0.4
    s.effector_weights.gravity = 0.0
    s.brownian_factor = 0.4
    s.damping = 0.02
    s.render_type = "OBJECT"
    s.instance_object = sp
    s.particle_size = 1.0
    s.size_random = 0.7
    s.use_rotations = False
    ps.seed = seed
    em.show_instancer_for_render = False
    return em


def darken(o, f):
    """nesnenin malzemelerinde temel rengi f ile çarpar (ışıyan malzemelere dokunmaz)"""
    done = set()
    for ms in o.data.materials:
        if not ms or ms.name in done or not ms.use_nodes:
            continue
        done.add(ms.name)
        nt = ms.node_tree
        for b in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
            if b.inputs["Emission Strength"].default_value > 0.5:
                continue
            inp = b.inputs["Base Color"]
            if inp.is_linked:
                src = inp.links[0].from_socket
                mx = nt.nodes.new("ShaderNodeMix")
                mx.data_type = "RGBA"
                mx.blend_type = "MULTIPLY"
                mx.inputs[0].default_value = 1.0
                nt.links.new(src, mx.inputs[6])
                mx.inputs[7].default_value = (f, f * 0.95, f * 0.9, 1)
                nt.links.new(mx.outputs[2], inp)
            else:
                c = inp.default_value
                inp.default_value = (c[0] * f, c[1] * f, c[2] * f, 1)


def weather(o, soot_h=3.2, strength=0.85):
    """yangın isi (alttan yukarı azalan, gürültülü) + dikey akıntı lekeleri"""
    done = set()
    for ms in o.data.materials:
        if not ms or ms.name in done or not ms.use_nodes:
            continue
        done.add(ms.name)
        nt = ms.node_tree
        for b in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
            if b.inputs["Emission Strength"].default_value > 0.5:
                continue
            inp = b.inputs["Base Color"]
            tc = nt.nodes.new("ShaderNodeTexCoord")
            sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(tc.outputs["Object"], sep.inputs[0])
            hg = nt.nodes.new("ShaderNodeMapRange")
            hg.inputs["From Min"].default_value = 0.0
            hg.inputs["From Max"].default_value = soot_h
            hg.inputs["To Min"].default_value = 1.0
            hg.inputs["To Max"].default_value = 0.15
            nt.links.new(sep.outputs["Z"], hg.inputs["Value"])
            nz = nt.nodes.new("ShaderNodeTexNoise")
            nz.inputs["Scale"].default_value = 0.9
            nz.inputs["Detail"].default_value = 10
            nz.inputs["Roughness"].default_value = 0.65
            nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
            nm = nt.nodes.new("ShaderNodeMapRange")
            nm.inputs["From Min"].default_value = 0.42
            nm.inputs["From Max"].default_value = 0.62
            nt.links.new(nz.outputs["Fac"], nm.inputs["Value"])
            # dikey akıntılar: x'te sık, z'de uzun gürültü
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = (7.0, 7.0, 0.35)
            nt.links.new(tc.outputs["Object"], mp.inputs[0])
            st = nt.nodes.new("ShaderNodeTexNoise")
            st.inputs["Scale"].default_value = 1.6
            nt.links.new(mp.outputs[0], st.inputs["Vector"])
            sm = nt.nodes.new("ShaderNodeMapRange")
            sm.inputs["From Min"].default_value = 0.55
            sm.inputs["From Max"].default_value = 0.75
            sm.inputs["To Max"].default_value = 0.45
            nt.links.new(st.outputs["Fac"], sm.inputs["Value"])
            m1 = nt.nodes.new("ShaderNodeMath")
            m1.operation = "MULTIPLY"
            nt.links.new(hg.outputs[0], m1.inputs[0])
            nt.links.new(nm.outputs[0], m1.inputs[1])
            m2 = nt.nodes.new("ShaderNodeMath")
            m2.operation = "MAXIMUM"
            nt.links.new(m1.outputs[0], m2.inputs[0])
            nt.links.new(sm.outputs[0], m2.inputs[1])
            m3 = nt.nodes.new("ShaderNodeMath")
            m3.operation = "MULTIPLY"
            m3.use_clamp = True
            m3.inputs[1].default_value = strength
            nt.links.new(m2.outputs[0], m3.inputs[0])
            mx = nt.nodes.new("ShaderNodeMix")
            mx.data_type = "RGBA"
            nt.links.new(m3.outputs[0], mx.inputs[0])
            if inp.is_linked:
                nt.links.new(inp.links[0].from_socket, mx.inputs[6])
            else:
                mx.inputs[6].default_value = inp.default_value
            mx.inputs[7].default_value = (0.012, 0.010, 0.009, 1)
            nt.links.new(mx.outputs[2], inp)
            # isli yerler mat
            rr = nt.nodes.new("ShaderNodeMath")
            rr.operation = "MAXIMUM"
            if b.inputs["Roughness"].is_linked:
                nt.links.new(b.inputs["Roughness"].links[0].from_socket, rr.inputs[0])
            else:
                rr.inputs[0].default_value = b.inputs["Roughness"].default_value
            nt.links.new(m3.outputs[0], rr.inputs[1])
            nt.links.new(rr.outputs[0], b.inputs["Roughness"])


def rubble(seed=7, y0=-40.0, y1=70.0, n_curb=260, n_road=70):
    """moloz: gürültüyle bozulmuş beton parçaları + paslı demir çubuklar; kaldırım dibinde yoğun, yolda seyrek"""
    rng = random.Random(seed)
    conc = tex_mat("rubble", os.path.join(GROUND, "concrete.webp"), scale=1.5, rough=0.9, tint=hexc("#6a645c"), bump=0.8)
    weather_mat = conc
    bases = []
    for i in range(5):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0, location=(0, 0, -300))
        o = bpy.context.object
        tx = bpy.data.textures.new("rb%d" % i, "CLOUDS")
        tx.noise_scale = 0.55 + 0.1 * i
        d = o.modifiers.new("d", "DISPLACE")
        d.texture = tx
        d.strength = 0.55
        o.modifiers.new("dec", "DECIMATE").ratio = 0.35
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        bpy.data.objects.remove(o, do_unlink=True)
        me.materials.append(weather_mat)
        bases.append(me)
    rust = bpy.data.materials.new("rebar")
    rust.use_nodes = True
    rb = rust.node_tree.nodes["Principled BSDF"]
    rb.inputs["Base Color"].default_value = hexc("#4a2a18")
    rb.inputs["Metallic"].default_value = 0.6
    rb.inputs["Roughness"].default_value = 0.8
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.012, depth=1.0, location=(0, 0, -300))
    bar = bpy.context.object.data
    bar.materials.append(rust)
    bpy.data.objects.remove(bpy.context.object, do_unlink=True)

    def put(me, loc, sc, rot):
        o = bpy.data.objects.new("rub", me)
        bpy.context.scene.collection.objects.link(o)
        o.location = loc
        o.scale = sc
        o.rotation_euler = rot
        return o

    for _ in range(n_curb):
        sx = rng.choice((-1, 1))
        x = sx * rng.uniform(5.3, 6.4) if rng.random() < 0.7 else sx * rng.uniform(6.6, 9.6)
        y = rng.uniform(y0, y1)
        s = rng.uniform(0.05, 0.32) * (1.6 if rng.random() < 0.08 else 1.0)
        z = 0.12 if abs(x) > 6.0 else 0.0
        put(rng.choice(bases), (x, y, z + s * 0.25), (s * rng.uniform(0.8, 1.3), s * rng.uniform(0.8, 1.3), s * rng.uniform(0.45, 0.8)),
            (rng.uniform(0, 0.4), rng.uniform(0, 0.4), rng.uniform(0, 6.3)))
    for _ in range(n_road):
        x = rng.uniform(-5.0, 5.0)
        y = rng.uniform(y0, y1)
        if abs(x) < 1.4 and -8 < y < 14:
            continue  # kahramanın yolu temiz kalsın
        s = rng.uniform(0.03, 0.14)
        put(rng.choice(bases), (x, y, s * 0.2), (s, s * rng.uniform(0.8, 1.2), s * 0.55), (0, 0, rng.uniform(0, 6.3)))
    for _ in range(40):
        sx = rng.choice((-1, 1))
        put(bar, (sx * rng.uniform(5.4, 7.0), rng.uniform(y0, y1), 0.15), (1, 1, rng.uniform(0.5, 1.4)),
            (rng.uniform(1.2, 1.5), 0, rng.uniform(0, 6.3)))


def street(length=80.0, seed=3, y0=-12.0):
    """Sokak: asfalt yol, kaldırımlar, iki yanda binalar (oyunun bina üreticisi), sokak lambaları, enkaz."""
    import blib as B  # noqa: F401
    import build_b as BB

    rng = random.Random(seed)
    asph = tex_mat("asphalt", os.path.join(GROUND, "asphalt.webp"), scale=0.18, rough=0.55, tint=hexc("#55555a"), bump=0.5)
    side = tex_mat("sidewalk", os.path.join(GROUND, "sidewalk.webp"), scale=0.35, rough=0.85, tint=hexc("#9a948c"), bump=0.4)
    road = plane("Road", (12, length), (0, y0 + length / 2, 0), asph)
    road.modifiers.new("col", "COLLISION")
    for sx in (-1, 1):
        o = plane("Side", (4, length), (sx * 8, y0 + length / 2, 0.12), side)
        o.scale.z = 1
        o.modifiers.new("col", "COLLISION")
    # her bina tipi bir kez kurulur, tek nesneye birleştirilir; sokağa veri paylaşan kopyaları dizilir
    protos = {}

    def proto(k):
        if k in protos:
            return protos[k]
        objs = new_objects(BB.BUILDERS[k])
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            if o.type in ("MESH", "CURVE", "FONT", "META"):
                o.select_set(True)
            else:
                bpy.data.objects.remove(o, do_unlink=True)
        sel = [o for o in bpy.context.scene.objects if o.select_get()]
        bpy.context.view_layer.objects.active = sel[0]
        bpy.ops.object.convert(target="MESH")
        bpy.ops.object.join()
        p = bpy.context.view_layer.objects.active
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        xs = [v.co.x for v in p.data.vertices]
        ys = [v.co.y for v in p.data.vertices]
        if k != "lamp":
            darken(p, 0.42)
            weather(p)
        p.hide_render = True
        p.location = (0, 0, -200)
        protos[k] = (p, max(xs) - min(xs), max(ys) - min(ys))
        return protos[k]

    def put(k, loc, rz):
        p, w, d = proto(k)
        o = p.copy()
        o.hide_render = False
        bpy.context.scene.collection.objects.link(o)
        o.location = loc
        o.rotation_mode = "XYZ"
        o.rotation_euler = (0, 0, rz)
        return w, d

    kinds = ["apartment0", "apartment1", "shop0", "shop1", "house0", "police", "apartment0", "house2", "apartment1"]
    for sx in (-1, 1):
        y = y0 + 2.0
        while y < y0 + length - 2:
            k = rng.choice(kinds)
            p, w, d = proto(k)
            # bina önü (-y) yola dönsün
            rz = math.radians(90 if sx < 0 else -90)
            put(k, (sx * (10.2 + d / 2), y + w / 2, 0), rz)
            y += w + rng.uniform(0.3, 1.5)
    for y in range(int(y0) + 6, int(y0 + length) - 2, 12):
        for sx in (-1, 1):
            put("lamp", (sx * 6.6, y, 0.12), math.radians(90 if sx < 0 else -90))
    rubble(seed + 4, y0, y0 + length)
    return asph


def car_wreck(loc, rot_z, name="hellhound"):
    from zxm_import import import_zxm

    ob, _, _ = import_zxm(name, emission=0.0, rough=0.6, subdiv=0, rig=False)
    ob.location = loc
    ob.rotation_euler = (0, math.radians(rng_tilt(loc)), rot_z)
    # yanmış: rengi koyulaştır
    nt = ob.data.materials[0].node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = [n for n in nt.nodes if n.type == "TEX_IMAGE"][0]
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    nt.links.new(tex.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (0.3, 0.25, 0.22, 1)
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    weather(ob, soot_h=1.6, strength=0.95)
    return ob


def rng_tilt(loc):
    return (hash((round(loc[0]), round(loc[1]))) % 7) - 3


def camera(loc, target, lens=35, fstop=None, focus=None, name="Cam"):
    sc = bpy.context.scene
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.sensor_width = 36
    cam.data.clip_end = 400
    if fstop:
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.focus_distance = focus if focus else (Vector(target) - Vector(loc)).length
    return cam


def look(cam, loc, target, frame, lens=None, focus=None):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.keyframe_insert("location", frame=frame)
    cam.keyframe_insert("rotation_euler", frame=frame)
    if lens:
        cam.data.lens = lens
        cam.data.keyframe_insert("lens", frame=frame)
    if focus:
        cam.data.dof.focus_distance = focus
        cam.data.dof.keyframe_insert("focus_distance", frame=frame)


def compositor(glare=0.6, mist=None, vignette=0.35):
    """Derinlik sisi (mist pass, isteğe bağlı) + bloom (Glare/Fog Glow) + hafif renk sapması.
    mist: (başlangıç m, derinlik m, en çok örtme 0..1, renk)"""
    sc = bpy.context.scene
    sc.use_nodes = True
    nt = sc.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    cur = rl.outputs["Image"]
    if mist:
        ms = sc.world.mist_settings
        ms.start, ms.depth, ms.falloff = mist[0], mist[1], "QUADRATIC"
        mul = nt.nodes.new("CompositorNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = mist[2]
        nt.links.new(rl.outputs["Mist"], mul.inputs[0])
        mx = nt.nodes.new("CompositorNodeMixRGB")
        nt.links.new(mul.outputs[0], mx.inputs[0])
        nt.links.new(cur, mx.inputs[1])
        mx.inputs[2].default_value = mist[3]
        cur = mx.outputs[0]
    g = nt.nodes.new("CompositorNodeGlare")
    g.glare_type = "FOG_GLOW"
    g.quality = "HIGH"
    g.size = 8
    g.threshold = 0.8
    g.mix = glare - 1.0
    nt.links.new(cur, g.inputs["Image"])
    cur = g.outputs[0]
    ld = nt.nodes.new("CompositorNodeLensdist")
    ld.use_fit = True
    ld.inputs["Dispersion"].default_value = 0.012
    ld.inputs["Distortion"].default_value = 0.0
    nt.links.new(cur, ld.inputs["Image"])
    cur = ld.outputs[0]
    out = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(cur, out.inputs["Image"])
    return nt
