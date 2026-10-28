"""Zenvex Online — 15 sn sinematik tanıtım çekimleri (Blender Cycles).

blender -b -P shots.py -- <çekim> [ilk kare] [son kare] [önizleme]
Kareler: out/frames/<çekim>/0001.png ...  (her çekimin kendi kare numarası 1'den başlar)
"""
import math
import os
import random
import sys
import time

sys.path.insert(0, "/home/user/promo3d")
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import scene as S  # noqa: E402
from anim_apply import attach_weapon, key_pose, m4, sample  # noqa: E402
from zxm_import import import_zxm  # noqa: E402
from zmb import NPCS, Zombie  # noqa: E402
import cloth as CL  # noqa: E402

PREROLL = -20

POOL = [n for n in NPCS if n != "npc_sniper"]

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
SHOT = argv[0] if argv else "A"
PREVIEW = "preview" in argv
VOLFOG = "volfog" in argv
SUBDIV_HERO = 2 if SHOT in ("A", "B", "F") else 1
T0 = time.time()
nums = [int(a) for a in argv[1:] if a.isdigit()]
STEP = int([a for a in argv if a.startswith("step")][0][4:]) if any(a.startswith("step") for a in argv) else 1

# çekim: kare sayısı
LEN = {"A": 36, "B": 36, "C": 84, "D1": 36, "D2": 54, "E": 48, "F": 66}
F0 = nums[0] if nums else 1
F1 = nums[1] if len(nums) > 1 else LEN[SHOT]
RES = (960, 540) if PREVIEW else (1280, 720)
SAMPLES = 12 if PREVIEW else 16
OUT = "/home/user/promo3d/out/%s/%s" % ("preview" if PREVIEW else "frames", SHOT)
os.makedirs(OUT, exist_ok=True)

SCYTHE_TIP = None


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerpv(a, b, t):
    return Vector(a).lerp(Vector(b), t)


# --------------------------------------------------------------------------- dünya
FLIP = "/home/user/promo3d/cache/flipL/f_0001.png"
FLIP_N = len(os.listdir("/home/user/promo3d/cache/flipL"))
FIRE_CONSTRAINTS = []


def fires(spots):
    """Ateş: simülasyondan render edilmiş flipbook kartları (kameraya döner), her biri farklı zaman kaymasıyla + titreyen ışık."""
    img = bpy.data.images.load(FLIP)
    img.source = "SEQUENCE"
    out = []
    for i, (loc, s, off) in enumerate(spots):
        m = bpy.data.materials.new("fire%d" % i)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        t.image_user.frame_duration = FLIP_N
        t.image_user.frame_start = 1 - (off % FLIP_N)
        t.image_user.frame_offset = 0
        t.image_user.use_cyclic = True
        t.image_user.use_auto_refresh = True
        t.extension = "CLIP"
        # flipbook siyah zemin üzerinde: renk = alev ışıması → katkısal (Transparent + Emission)
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs[1].default_value = 3.5
        tint = nt.nodes.new("ShaderNodeMix")
        tint.data_type = "RGBA"
        tint.blend_type = "MULTIPLY"
        tint.inputs[0].default_value = 1.0
        nt.links.new(t.outputs["Color"], tint.inputs[6])
        tint.inputs[7].default_value = (1.0, 0.62, 0.36, 1)
        nt.links.new(tint.outputs[2], em.inputs[0])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(tr.outputs[0], add.inputs[0])
        nt.links.new(em.outputs[0], add.inputs[1])
        o_ = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(add.outputs[0], o_.inputs[0])
        bpy.ops.mesh.primitive_plane_add(size=1, location=(loc[0], loc[1], loc[2] + 2.4 * s))
        o = bpy.context.object
        o.name = "FireCard"
        o.data.transform(Matrix.Rotation(math.radians(90), 4, "X"))
        o.scale = (2.5 * s * (1 if i % 2 else -1), 1, 5.0 * s)
        o.data.materials.append(m)
        o.visible_shadow = False
        o.visible_glossy = False
        c = o.constraints.new("LOCKED_TRACK")
        c.lock_axis = "LOCK_Z"
        c.track_axis = "TRACK_NEGATIVE_Y"
        FIRE_CONSTRAINTS.append(c)
        out.append(o)
        pl = S.light("POINT", (loc[0], loc[1], loc[2] + 1.0 * s), 1500 * s * s, (1.0, 0.42, 0.12), size=0.8 * s, name="FireL")
        fc = pl.data.driver_add("energy")
        fc.driver.expression = "%f*(0.8+0.12*sin(frame*0.9+%d)+0.08*sin(frame*0.37+%d))" % (1500 * s * s, i * 7, i * 3)
    return out


def aim_fires():
    for c in FIRE_CONSTRAINTS:
        c.target = bpy.context.scene.camera


def world(fog=0.004, street=True, sun=3.0, sky=0.1, embers_box=None, fire_spots=None):
    sc = S.reset(RES, SAMPLES)
    sc.cycles.volume_step_rate = 2.0
    S.sky(sun_elev=2.5, sun_rot=0, strength=sky, haze="#ff6a2a")
    if street:
        S.street(110, y0=-40)
    S.light("SUN", (0, 60, 7), sun, (1.0, 0.5, 0.25), size=2, target=(0, 0, 0), name="Sun")
    if fire_spots:
        fires(fire_spots)
    if fog and VOLFOG:
        S.fog_box((0, 15, 7), (40, 120, 16), density=fog, color="#d8a070", anisotropy=0.6)
    if embers_box:
        S.embers(*embers_box)
    CL.wind(2.0)
    S.compositor(mist=None if VOLFOG else (8.0, 90.0, min(0.6, fog * 130), (0.36, 0.16, 0.08, 1)))
    return sc


STREET_FIRES = [((-3.6, 14, 0), 1.5, 40), ((4.8, 22, 0), 1.8, 90), ((-5.5, 33, 0), 2.2, 140), ((3.5, -9, 0), 1.5, 60),
                ((-4.2, -18, 0), 1.8, 110), ((5.5, 42, 0.0), 2.6, 20), ((-7.5, 8, 0.1), 1.2, 75), ((7.6, 3, 0.1), 1.0, 5),
                ((-1.5, 52, 0), 3.0, 33)]


def wrecks():
    S.car_wreck((-3.6, 14, 0), math.radians(25))
    S.car_wreck((3.5, -9.0, 0), math.radians(-60))
    S.car_wreck((5.2, 30, 0), math.radians(100))


# --------------------------------------------------------------------------- Kael
class Hero:
    def __init__(self, weapon="blood_scythe"):
        self.ob, self.rig, self.meta = import_zxm("kael", emission=1.5, subdiv=SUBDIV_HERO, bump=0.3, metal=0.55)
        self._hood_void()
        CL.add_cloth(self.ob, self.rig, self.meta, (PREROLL, LEN[SHOT] + 2), quality=6)
        self.w = None
        if weapon:
            self.w, _, wm = import_zxm(weapon, emission=4.0, rig=False, subdiv=1, bump=0.35, metal=0.8, rough=0.35)
            attach_weapon(self.rig, self.w)
            self.tip = wm["tip"]
        self._eyes()

    def _hood_void(self):
        """kapüşonun içi: kenarın gerisindeki yüz bölgesi zifiri karanlık (yüz görünmez, yalnız gözler yanar)"""
        me = self.ob.data
        co = np.array([v.co[:] for v in me.vertices])
        x, y, z = co[:, 0], co[:, 1], co[:, 2]
        # her yükseklikte kapüşon kenarının en öndeki (en küçük y) noktası
        zs = np.arange(1.45, 1.95, 0.01)
        rim = np.array([y[(np.abs(z - zz) < 0.012) & (np.abs(x) < 0.12)].min() if ((np.abs(z - zz) < 0.012) & (np.abs(x) < 0.12)).any() else 0.0 for zz in zs])
        # kenar profili: yukarıdan aşağı en öndeki kenar (kapüşon saçağı) — yüz bunun gerisinde
        rim_env = np.minimum.accumulate(rim[::-1])[::-1]
        yr = np.interp(z, zs, rim_env)
        behind = np.clip((y - yr - 0.006) / 0.018, 0, 1)
        zf = np.clip((z - 1.52) / 0.04, 0, 1) * np.clip((1.80 - z) / 0.03, 0, 1)
        xf = np.clip((0.092 - np.abs(x)) / 0.025, 0, 1)
        front = np.clip((0.02 - y) / 0.04, 0, 1)
        mask = behind * zf * xf * front
        at = me.attributes.new("hood", "FLOAT", "POINT")
        at.data.foreach_set("value", mask.astype(np.float32))
        mat = me.materials[0]
        nt = mat.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        a = nt.nodes.new("ShaderNodeAttribute")
        a.attribute_name = "hood"
        a.attribute_type = "GEOMETRY"
        inp = bsdf.inputs["Base Color"]
        src = inp.links[0].from_socket
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        nt.links.new(a.outputs["Fac"], mx.inputs[0])
        nt.links.new(src, mx.inputs[6])
        mx.inputs[7].default_value = (0.0, 0.0, 0.0, 1)
        nt.links.new(mx.outputs[2], inp)
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        nt.links.new(a.outputs["Fac"], inv.inputs[1])
        nt.links.new(inv.outputs[0], bsdf.inputs["Specular IOR Level"])
        print("HOOD mask", int((mask > 0.5).sum()), "köşe", flush=True)

    def _eyes(self):
        m = S.emit_mat("eyes", (1.0, 0.2, 0.02, 1), 0.0)
        self.eye_mat = m
        hb = self.rig.data.bones["head"]
        to_bone = (hb.matrix_local @ Matrix.Translation((0, hb.length, 0))).inverted()

        def bone_child(o, p):
            o.parent = self.rig
            o.parent_type = "BONE"
            o.parent_bone = "head"
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_basis = to_bone @ Matrix.Translation(p)

        self.eyes = []
        for sx in (-1, 1):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.011, segments=12, ring_count=6)
            e = bpy.context.object
            e.data.transform(Matrix.Diagonal((1.5, 0.6, 0.7, 1)))
            e.data.materials.append(m)
            e.visible_shadow = False
            bone_child(e, (sx * 0.034, -0.128, 1.69))
            self.eyes.append(e)
        # göz parıltısı ışığı (yüzü hafif kızıl boyar)
        l = S.light("POINT", (0, 0, 0), 0.0, (1.0, 0.3, 0.05), size=0.02, name="EyeL")
        bone_child(l, (0, -0.2, 1.69))
        self.eye_light = l

    def eyes_on(self, strength, frame):
        strength *= 0.4
        self.eye_mat.node_tree.nodes["Emission"].inputs[1].default_value = strength
        self.eye_mat.node_tree.nodes["Emission"].inputs[1].keyframe_insert("default_value", frame=frame)
        self.eye_light.data.energy = strength * 0.08
        self.eye_light.data.keyframe_insert("energy", frame=frame)

    def animate(self, spec_fn, frames, sub=1):
        """spec_fn(f) → animdump girdisi; her kare (ve alt kare) anahtar kare olarak yazılır"""
        specs = []
        for f in frames:
            for k in range(sub):
                specs.append(spec_fn(f + k / sub))
        res = sample("kael", specs)
        self.samples = {}
        i = 0
        for f in frames:
            for k in range(sub):
                fr = res[i]
                i += 1
                self.samples[f + k / sub] = fr
                if k == 0:
                    key_pose(self.rig, self.w, fr, f)
        return res

    def tip_world(self, fr, along=1.0):
        """silah ucunun (ya da sapın `along` oranındaki noktasının) dünya konumu"""
        x = m4(fr["weapon"])
        return self.rig.matrix_world @ (x @ Vector((self.tip * along, 0, 0)))


# --------------------------------------------------------------------------- savurma izi
def trail_mat():
    m = bpy.data.materials.new("trail")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "fade"
    attr.attribute_type = "GEOMETRY"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].color = (0.5, 0.0, 0.0, 1)
    cr.elements[1].color = (1.0, 0.75, 0.45, 1)
    e = cr.elements.new(0.6)
    e.color = (1.0, 0.08, 0.02, 1)
    nt.links.new(attr.outputs["Fac"], ramp.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ramp.outputs[0], em.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 35.0
    nt.links.new(attr.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs[1])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(attr.outputs["Fac"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], out.inputs[0])
    m.blend_method = "BLEND"
    return m


class Trail:
    def __init__(self):
        self.me = bpy.data.meshes.new("trail")
        self.ob = bpy.data.objects.new("Trail", self.me)
        bpy.context.scene.collection.objects.link(self.ob)
        self.me.materials.append(trail_mat())
        self.ob.visible_shadow = False

    def set(self, outer, inner, power=1.0):
        """outer/inner: eskiden yeniye uç noktaları"""
        self.me.clear_geometry()
        n = len(outer)
        if n < 2 or power <= 0.01:
            self.me.update()
            return
        verts = [tuple(p) for p in outer] + [tuple(p) for p in inner]
        faces = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
        self.me.from_pydata(verts, [], faces)
        a = self.me.attributes.new("fade", "FLOAT", "POINT")
        f = [((i / (n - 1)) ** 1.6) * power for i in range(n)]
        a.data.foreach_set("value", f + [x * 0.35 for x in f])
        self.me.update()


# --------------------------------------------------------------------------- kıvılcım / kan parçacıkları (python ile)
class Sparks:
    def __init__(self, n=80, color=(1.0, 0.28, 0.04, 1), strength=22.0, seed=4, size=0.009):
        self.rng = random.Random(seed)
        m = S.emit_mat("spark", color, strength)
        self.obs = []
        for i in range(n):
            bpy.ops.mesh.primitive_ico_sphere_add(radius=size, subdivisions=1, location=(0, 0, -100))
            o = bpy.context.object
            o.data.materials.append(m)
            o.visible_shadow = False
            self.obs.append(o)
        self.parts = []

    def burst(self, at, n=40, speed=6.0, up=2.0, life=14, dir=None):
        for _ in range(n):
            v = Vector((self.rng.gauss(0, 1), self.rng.gauss(0, 1), abs(self.rng.gauss(0, 1)) * 0.8 + 0.3)).normalized() * speed * self.rng.uniform(0.3, 1.0)
            if dir is not None:
                v += Vector(dir) * speed * 0.7
            v.z += up
            self.parts.append([Vector(at), v, 0, life * self.rng.uniform(0.6, 1.2)])

    def step(self, dt=1 / 24):
        alive = []
        for p in self.parts:
            p[0] = p[0] + p[1] * dt
            p[1].z -= 9.0 * dt
            p[1] *= 0.94
            p[2] += 1
            if p[2] < p[3]:
                alive.append(p)
        self.parts = alive
        for i, o in enumerate(self.obs):
            if i < len(self.parts):
                p = self.parts[i]
                o.location = p[0]
                vel = p[1]
                o.rotation_euler = vel.to_track_quat("Z", "Y").to_euler() if vel.length > 0.01 else (0, 0, 0)
                o.scale = (1, 1, 1 + min(vel.length * 0.6, 3.5))
            else:
                o.location = (0, 0, -100)


# --------------------------------------------------------------------------- zombiler (oyunun prosedürel zombi üreticisi)
_ZB = {}


def zombie(kind, anim, phase, loc, facing_deg=0.0, scale=None, dark=0.22):
    import hero_b as HB
    from character2 import skeleton, zombie_pose

    import blib as BL

    if not hasattr(HB, "_mf0"):
        HB._mf0 = BL.meta_family
    dist = (Vector(loc) - bpy.context.scene.camera.location).length if bpy.context.scene.camera else 10.0
    res = min(0.012 * max(1.0, dist / 15.0), 0.019) * (scale or 1.0) ** 0.8
    HB.meta_family = lambda name, mat, resolution=None: HB._mf0(name, mat, res)
    Pz = zombie_pose(anim, phase, kind)
    # oyun koordinatı: x, y yukarı, z güney (= blender -Y). yaw=0 → güneye (kameraya, blender -Y) bakar
    Pz["yaw"] = math.radians(facing_deg)
    J = skeleton(Pz, 0.19)
    s = scale if scale else HB.SCALE.get(kind, 1.0)
    before = set(bpy.data.objects)
    HB.build_human(J, HB.LOOKS[kind], s)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.parent is None:
            o.location = Vector(loc) + o.location
        for ms in getattr(o.data, "materials", []) or []:
            key = (ms.name, dark) if ms else None
            if ms and key not in _ZB and ms.use_nodes:
                _ZB[key] = 1
                nt = ms.node_tree
                bsdf = nt.nodes.get("Principled BSDF")
                if bsdf is None:
                    continue
                inp = bsdf.inputs["Base Color"]
                if inp.is_linked:
                    src = inp.links[0].from_socket
                    mx = nt.nodes.new("ShaderNodeMix")
                    mx.data_type = "RGBA"
                    mx.blend_type = "MULTIPLY"
                    mx.inputs[0].default_value = 1.0
                    nt.links.new(src, mx.inputs[6])
                    mx.inputs[7].default_value = (dark, dark, dark, 1)
                    nt.links.new(mx.outputs[2], inp)
                else:
                    c = inp.default_value
                    inp.default_value = (c[0] * dark, c[1] * dark, c[2] * dark, 1)
    return new


def clear(objs):
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)


# --------------------------------------------------------------------------- çekimler
def render_frames(per_frame):
    sc = bpy.context.scene
    print("KURULUM %.1fs" % (time.time() - T0), flush=True)
    aim_fires()
    sc.frame_start, sc.frame_end = PREROLL, max(F1, LEN[SHOT]) + 2
    with bpy.context.temp_override(scene=sc):
        bpy.ops.ptcache.bake_all(bake=True)
    sc.frame_start = 1
    print("PARCACIK %.1fs" % (time.time() - T0), flush=True)
    for f in range(F0, F1 + 1, STEP):
        p = os.path.join(OUT, "%04d.png" % f)
        if os.path.exists(p) and os.path.getsize(p) > 0 and not PREVIEW:
            continue
        t = time.time()
        sc.frame_set(f)
        per_frame(f)
        print("SAHNE %.1fs" % (time.time() - t), flush=True)
        sc.render.filepath = p
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print("KARE %s %d %.1fs" % (SHOT, f, time.time() - t), flush=True)


def shot_A():
    """KANCA 1: karanlıkta kapüşon, kor gözler yanar; korlar ve arka planda bulanık yangınlar."""
    sc = world(fog=0.003, sun=0.3, sky=0.05, embers_box=((0, -1.0, 1.6), (3, 2.5, 2.0), 260, 3), fire_spots=STREET_FIRES[:3])
    h = Hero()
    h.animate(lambda f: dict(anim=0, t=0.3 + f / 24, period=1.6, weapon="blood_scythe"), range(1, LEN["A"] + 2))
    for f, s in [(1, 0.0), (5, 0.0), (9, 60.0), (12, 25.0), (36, 30.0)]:
        h.eyes_on(s, f)
    key = S.light("AREA", (0.9, 1.0, 2.3), 0.0, (1.0, 0.25, 0.08), size=1.0, target=(0, 0, 1.6), name="Rim")
    for f, e in [(1, 0.0), (6, 0.0), (12, 260.0), (36, 220.0)]:
        key.data.energy = e
        key.data.keyframe_insert("energy", frame=f)
    fill = S.light("AREA", (-1.2, -1.6, 1.4), 0.0, (0.35, 0.45, 1.0), size=1.5, target=(0, 0, 1.6), name="Fill")
    for f, e in [(1, 0.0), (10, 0.0), (20, 18.0)]:
        fill.data.energy = e
        fill.data.keyframe_insert("energy", frame=f)
    cam = S.camera((0.22, -1.15, 1.6), (0, -0.1, 1.68), lens=50, fstop=1.6, focus=1.05)
    S.look(cam, (0.22, -1.15, 1.6), (0, -0.1, 1.68), 1, lens=50, focus=1.04)
    S.look(cam, (0.1, -0.62, 1.66), (0, -0.12, 1.685), LEN["A"], lens=62, focus=0.5)
    render_frames(lambda f: None)


def shot_B():
    """KANCA 2: kameraya doğru 360° tırpan savuruşu, kızıl iz, hilal şok dalgası → beyaz flaş."""
    sc = world(fog=0.004, sun=2.4, sky=0.1, embers_box=((0, 1, 1.5), (6, 6, 3), 500, 5), fire_spots=STREET_FIRES)
    wrecks()
    h = Hero()
    n = LEN["B"]

    def gt(f):  # oyun zamanı: yavaş başla, savuruşta hızlan (hız rampası)
        x = (f - 1) / (n - 1)
        return 1.40 + 0.62 * (0.35 * x + 0.65 * ease(x * 1.15))

    sub = 4
    h.animate(lambda f: dict(anim=4, t=gt(f), period=0.7, weapon="blood_scythe"), range(1, n + 2), sub=sub)
    for f in (1, n):
        h.eyes_on(35.0, f)
    S.light("AREA", (2.5, -2.5, 3.0), 120.0, (1.0, 0.6, 0.4), size=2.0, target=(0, 0, 1.3), name="Key")
    S.light("AREA", (-1.5, 2.0, 2.5), 300.0, (1.0, 0.2, 0.06), size=1.5, target=(0, 0, 1.4), name="Rim")
    cam = S.camera((1.5, -3.3, 0.45), (0, 0, 1.15), lens=24, fstop=2.8)
    S.look(cam, (1.7, -3.6, 0.42), (0, 0, 1.15), 1, lens=24, focus=3.9)
    S.look(cam, (1.0, -2.7, 0.55), (0, 0, 1.2), n, lens=22, focus=2.9)
    tr = Trail()
    sp = Sparks(70)
    # hilal şok dalgası: yerde genişleyen yay
    wave = S.emit_mat("wave", (1.0, 0.1, 0.03, 1), 30.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.04, major_segments=64, minor_segments=8, location=(0, 0, 1.1))
    ring = bpy.context.object
    ring.data.materials.append(wave)
    ring.scale = (1, 1, 0.3)
    ring.hide_render = True
    keys = sorted(h.samples)

    def pf(f):
        hist = [k for k in keys if f - 2.5 <= k <= f]
        outer = [h.tip_world(h.samples[k], 1.0) for k in hist]
        inner = [h.tip_world(h.samples[k], 0.55) for k in hist]
        pw = h.samples[f]["trail"] if f in h.samples else 0.0
        tr.set(outer, inner, max(pw, 0.6))
        if f == n - 9:
            sp.burst(h.tip_world(h.samples[f]), 45, 7.0)
        sp.step()
        if f >= n - 8:
            k = (f - (n - 8)) / 8
            ring.hide_render = False
            r = 1.2 + 6.0 * k ** 1.4
            ring.scale = (r, r, 0.3 + 2.0 * k)
            wave.node_tree.nodes["Emission"].inputs[1].default_value = 40.0 * (1 - 0.5 * k)

    render_frames(pf)


def shot_C():
    """Arkadan geniş plan: yanan sokak, sisten gelen zombi sürüsü, uzakta dev Titan silüeti."""
    sc = world(fog=0.0045, sun=3.4, sky=0.12, embers_box=((0, 8, 2), (14, 24, 4), 700, 7), fire_spots=STREET_FIRES)
    wrecks()
    h = Hero()
    h.rig.rotation_euler.z = math.radians(180)
    h.animate(lambda f: dict(anim=0, t=1.0 + f / 24, period=1.6, weapon="blood_scythe"), range(1, LEN["C"] + 2))
    h.eyes_on(30.0, 1)
    S.light("AREA", (0, -3, 3), 60.0, (0.5, 0.6, 1.0), size=3, target=(0, 0, 1.2), name="Fill")
    cam = S.camera((0.9, -3.0, 1.45), (0, 10, 1.7), lens=30, fstop=4.0)
    S.look(cam, (0.95, -2.9, 1.4), (0.2, 10, 1.6), 1, lens=30, focus=3.0)
    S.look(cam, (0.7, -5.2, 3.0), (0, 12, 2.0), LEN["C"], lens=28, focus=5.6)
    rng = random.Random(11)
    fr = list(range(1, LEN["C"] + 2))
    for i in range(13):
        z = Zombie(POOL[i % len(POOL)], seed=i, cloth_frames=(PREROLL, LEN[SHOT] + 2))
        z.walk(fr, (rng.uniform(-5, 5), rng.uniform(9, 30)), speed=rng.uniform(0.7, 1.3), heading_deg=rng.uniform(-12, 12), t0=rng.random() * 2)
    ti = Zombie("vex", seed=99, scale=3.4, dark=0.3, eye_strength=150, eye_size=0.016, cloth_frames=(PREROLL, LEN[SHOT] + 2))
    ti.walk(fr, (4.0, 62), speed=0.8, heading_deg=-10, period=1.6)
    render_frames(lambda f: None)


def shot_D1():
    """Yandan takip: Kael sürüye doğru koşar."""
    sc = world(fog=0.004, sun=3.0, sky=0.1, embers_box=((0, 6, 1.5), (12, 18, 3), 500, 9), fire_spots=STREET_FIRES)
    wrecks()
    h = Hero()
    h.rig.rotation_euler.z = math.radians(180)
    n = LEN["D1"]
    speed = 5.5
    h.animate(lambda f: dict(anim=2, t=f / 24, period=0.7, weapon="blood_scythe"), range(1, n + 2))
    for f in (1, n + 1):
        h.rig.location = (0, speed * (f - 1) / 24, 0)
        h.rig.keyframe_insert("location", frame=f)
    for fc in h.rig.animation_data.action.fcurves:
        if fc.data_path == "location":
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    h.eyes_on(30.0, 1)
    S.light("AREA", (-3, 3, 3), 150.0, (1.0, 0.5, 0.3), size=3, target=(0, 4, 1.2), name="Key")
    cam = S.camera((-4.4, 0.5, 0.9), (0, 0.8, 1.1), lens=30, fstop=2.8)
    for f in (1, n):
        y = speed * (f - 1) / 24
        S.look(cam, (-4.4 + 0.5 * (f > 1), y - 0.6, 0.85), (0, y + 0.35, 1.05), f, lens=30, focus=4.4)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    rng = random.Random(5)
    for i in range(6):
        z = Zombie(POOL[(i + 3) % len(POOL)], seed=20 + i, cloth_frames=(PREROLL, LEN[SHOT] + 2))
        z.walk(list(range(1, n + 2)), (rng.uniform(-2, 3), rng.uniform(9, 17)), speed=rng.uniform(0.8, 1.3), heading_deg=rng.uniform(-10, 10), t0=rng.random())
    render_frames(lambda f: None)


def shot_D2():
    """Kombo: iki savuruş, üç zombi savrulur; vuruşlarda ağır çekim, kıvılcım ve ateş patlaması."""
    sc = world(fog=0.004, sun=3.0, sky=0.1, embers_box=((0, 8, 1.5), (10, 10, 3), 400, 13), fire_spots=STREET_FIRES)
    wrecks()
    h = Hero()
    h.rig.location = (0, 8, 0)
    h.rig.rotation_euler.z = math.radians(180)
    n = LEN["D2"]

    # oyun zamanı: vuruş anlarında yavaşlar (t≈0.28 ve t≈0.98)
    def gt(f):
        tt = 0.0
        for i in range(1, int(f)):
            g = 0.0 + tt
            slow = 0.4 if (0.2 < g % 0.7 < 0.4) else 1.0
            tt += slow * 0.7 / 18
        return tt

    sub = 4
    gts = {}

    def spec(f):
        base = gt(int(f))
        nxt = gt(int(f) + 1)
        t = base + (nxt - base) * (f - int(f))
        gts[f] = t
        return dict(anim=4, t=min(t, 1.39), period=0.7, weapon="blood_scythe")

    h.animate(spec, range(1, n + 2), sub=sub)
    h.eyes_on(35.0, 1)
    S.light("AREA", (3, 6, 3), 160.0, (1.0, 0.55, 0.35), size=3, target=(0, 9, 1.2), name="Key")
    S.light("AREA", (-2, 12, 2.5), 300.0, (1.0, 0.2, 0.05), size=2, target=(0, 9, 1.3), name="Rim")
    cam = S.camera((-3.4, 9.0, 0.9), (0.1, 9.6, 1.25), lens=28, fstop=3.2)
    S.look(cam, (-3.5, 8.8, 0.85), (0.1, 9.5, 1.25), 1, lens=28, focus=3.6)
    S.look(cam, (-3.0, 9.4, 1.0), (0.2, 10.0, 1.2), n, lens=26, focus=3.3)
    tr = Trail()
    sp = Sparks(90)
    HITS = {0: 11, 1: 36}
    targets = [dict(name=POOL[0], x=-0.6, y=10.6, stage=0, hdir=(0.25, 1.0)), dict(name=POOL[4], x=0.7, y=10.5, stage=0, hdir=(0.7, 0.8)),
               dict(name=POOL[6], x=0.0, y=11.2, stage=1, hdir=(0.35, 1.0))]
    from zmb import decapitate

    rng = random.Random(77)
    for i, t in enumerate(targets):
        z = Zombie(t["name"], seed=40 + i, subdiv=1, cloth_frames=(PREROLL, LEN[SHOT] + 2))
        hit = HITS[t["stage"]]
        z.walk(list(range(1, hit + 1)), (t["x"], t["y"]), speed=0.35, t0=i * 0.4)
        y_hit = t["y"] - 0.35 * (hit - 1) / 24
        t["hit"] = hit
        # başsız gövde: ölüm animasyonuyla geriye sendeleyip yığılır
        post = list(range(hit + 1, n + 2))
        z.anim_frames(post, 11, lambda f, hit=hit: min((f - hit) / 24 * 1.1, 0.88), period=0.9, zombie_pose=False)
        for f in post:
            k = min((f - hit) / 24, 0.6)
            dd = 1.6 * k - 1.2 * k * k
            z.rig.location = (t["x"] + t["hdir"][0] * dd * 0.6, y_hit + t["hdir"][1] * dd, 0)
            z.rig.keyframe_insert("location", frame=f)
        head = decapitate(z, hit, n + 1, t["hdir"], rng, bpy.context.scene)
        t["at"] = tuple(head.matrix_world.translation) if head else (t["x"], y_hit, 1.6)
        t["at"] = (t["x"], y_hit - 0.15, 1.55)
    keys = sorted(h.samples)

    def pf(f):
        hist = [k for k in keys if f - 2.5 <= k <= f]
        outer = [h.tip_world(h.samples[k], 1.0) for k in hist]
        inner = [h.tip_world(h.samples[k], 0.55) for k in hist]
        pw = h.samples[f]["trail"] if f in h.samples else 0.0
        tr.set(outer, inner, max(pw, 0.6))
        if f == n - 9:
            sp.burst(h.tip_world(h.samples[f]), 45, 7.0)
        sp.step()
        if f >= n - 8:
            k = (f - (n - 8)) / 8
            ring.hide_render = False
            r = 1.2 + 6.0 * k ** 1.4
            ring.scale = (r, r, 0.3 + 2.0 * k)
            wave.node_tree.nodes["Emission"].inputs[1].default_value = 40.0 * (1 - 0.5 * k)

    render_frames(pf)


def shot_C():
    """Arkadan geniş plan: yanan sokak, sisten gelen zombi sürüsü, uzakta dev Titan silüeti."""
    sc = world(fog=0.0045, sun=3.4, sky=0.12, embers_box=((0, 8, 2), (14, 24, 4), 700, 7), fire_spots=STREET_FIRES)
    wrecks()
    h = Hero()
    h.rig.rotation_euler.z = math.radians(180)
    h.animate(lambda f: dict(anim=0, t=1.0 + f / 24, period=1.6, weapon="blood_scythe"), range(1, LEN["C"] + 2))
    h.eyes_on(30.0, 1)
    S.light("AREA", (0, -3, 3), 60.0, (0.5, 0.6, 1.0), size=3, target=(0, 0, 1.2), name="Fill")
    cam = S.camera((0.9, -3.0, 1.45), (0, 10, 1.7), lens=30, fstop=4.0)
    S.look(cam, (0.95, -2.9, 1.4), (0.2, 10, 1.6), 1, lens=30, focus=3.0)
    S.look(cam, (0.7, -5.2, 3.0), (0, 12, 2.0), LEN["C"], lens=28, focus=5.6)
    rng = random.Random(11)
    fr = list(range(1, LEN["C"] + 2))
    for i in range(13):
        z = Zombie(POOL[i % len(POOL)], seed=i, cloth_frames=(PREROLL, LEN[SHOT] + 2))
        z.walk(fr, (rng.uniform(-5, 5), rng.uniform(9, 30)), speed=rng.uniform(0.7, 1.3), heading_deg=rng.uniform(-12, 12), t0=rng.random() * 2)
    ti = Zombie("vex", seed=99, scale=3.4, dark=0.3, eye_strength=150, eye_size=0.016, cloth_frames=(PREROLL, LEN[SHOT] + 2))
    ti.walk(fr, (4.0, 62), speed=0.8, heading_deg=-10, period=1.6)
    render_frames(lambda f: None)


def shot_D1():
    """Yandan takip: Kael sürüye doğru koşar."""
    sc = world(fog=0.004, sun=3.0, sky=0.1, embers_box=((0, 6, 1.5), (12, 18, 3), 500, 9), fire_spots=STREET_FIRES)
    wrecks()
    h = Hero()
    h.rig.rotation_euler.z = math.radians(180)
    n = LEN["D1"]
    speed = 5.5
    h.animate(lambda f: dict(anim=2, t=f / 24, period=0.7, weapon="blood_scythe"), range(1, n + 2))
    for f in (1, n + 1):
        h.rig.location = (0, speed * (f - 1) / 24, 0)
        h.rig.keyframe_insert("location", frame=f)
    for fc in h.rig.animation_data.action.fcurves:
        if fc.data_path == "location":
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    h.eyes_on(30.0, 1)
    S.light("AREA", (-3, 3, 3), 150.0, (1.0, 0.5, 0.3), size=3, target=(0, 4, 1.2), name="Key")
    cam = S.camera((-4.4, 0.5, 0.9), (0, 0.8, 1.1), lens=30, fstop=2.8)
    for f in (1, n):
        y = speed * (f - 1) / 24
        S.look(cam, (-4.4 + 0.5 * (f > 1), y - 0.6, 0.85), (0, y + 0.35, 1.05), f, lens=30, focus=4.4)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    rng = random.Random(5)
    for i in range(6):
        z = Zombie(POOL[(i + 3) % len(POOL)], seed=20 + i, cloth_frames=(PREROLL, LEN[SHOT] + 2))
        z.walk(list(range(1, n + 2)), (rng.uniform(-2, 3), rng.uniform(9, 17)), speed=rng.uniform(0.8, 1.3), heading_deg=rng.uniform(-10, 10), t0=rng.random())
    render_frames(lambda f: None)


def shot_D2():
    """Kombo: iki savuruş, üç zombi savrulur; vuruşlarda ağır çekim, kıvılcım ve ateş patlaması."""
    sc = world(fog=0.004, sun=3.0, sky=0.1, embers_box=((0, 8, 1.5), (10, 10, 3), 400, 13), fire_spots=STREET_FIRES)
    wrecks()
    h = Hero()
    h.rig.location = (0, 8, 0)
    h.rig.rotation_euler.z = math.radians(180)
    n = LEN["D2"]

    # oyun zamanı: vuruş anlarında yavaşlar (t≈0.28 ve t≈0.98)
    def gt(f):
        tt = 0.0
        for i in range(1, int(f)):
            g = 0.0 + tt
            slow = 0.4 if (0.2 < g % 0.7 < 0.4) else 1.0
            tt += slow * 0.7 / 18
        return tt

    sub = 4
    gts = {}

    def spec(f):
        base = gt(int(f))
        nxt = gt(int(f) + 1)
        t = base + (nxt - base) * (f - int(f))
        gts[f] = t
        return dict(anim=4, t=min(t, 1.39), period=0.7, weapon="blood_scythe")

    h.animate(spec, range(1, n + 2), sub=sub)
    h.eyes_on(35.0, 1)
    S.light("AREA", (3, 6, 3), 160.0, (1.0, 0.55, 0.35), size=3, target=(0, 9, 1.2), name="Key")
    S.light("AREA", (-2, 12, 2.5), 300.0, (1.0, 0.2, 0.05), size=2, target=(0, 9, 1.3), name="Rim")
    cam = S.camera((-3.4, 9.0, 0.9), (0.1, 9.6, 1.25), lens=28, fstop=3.2)
    S.look(cam, (-3.5, 8.8, 0.85), (0.1, 9.5, 1.25), 1, lens=28, focus=3.6)
    S.look(cam, (-3.0, 9.4, 1.0), (0.2, 10.0, 1.2), n, lens=26, focus=3.3)
    tr = Trail()
    sp = Sparks(90)
    HITS = {0: 11, 1: 36}
    targets = [dict(name=POOL[0], x=-0.6, y=10.6, stage=0, hdir=(0.25, 1.0)), dict(name=POOL[4], x=0.7, y=10.5, stage=0, hdir=(0.7, 0.8)),
               dict(name=POOL[6], x=0.0, y=11.2, stage=1, hdir=(0.35, 1.0))]
    for i, t in enumerate(targets):
        z = Zombie(t["name"], seed=40 + i, subdiv=1, cloth_frames=(PREROLL, LEN[SHOT] + 2))
        hit = HITS[t["stage"]]
        z.walk(list(range(1, hit + 1)), (t["x"], t["y"]), speed=0.35, t0=i * 0.4)
        y_hit = t["y"] - 0.35 * (hit - 1) / 24
        t["hit"], t["at"] = hit, (t["x"], y_hit - 0.3, 1.2)
        post = list(range(hit + 1, n + 2))
        z.anim_frames(post, 14, lambda f, hit=hit: (f - hit) / 24 * 1.3, period=0.6, zombie_pose=False)
        for f in post:
            k = (f - hit) / 24
            dd = 7.0 * k - 6.0 * k * k if k < 0.55 else 7.0 * 0.55 - 6.0 * 0.3025
            z.rig.location = (t["x"] + t["hdir"][0] * dd, y_hit + t["hdir"][1] * dd, max(0.0, 3.0 * k - 8.0 * k * k))
            z.rig.keyframe_insert("location", frame=f)
            z.rig.rotation_euler = (0, 0, t["hdir"][0] * 1.2 * min(k * 3, 1.0))
            z.rig.keyframe_insert("rotation_euler", frame=f)
    keys = sorted(h.samples)

    def pf(f):
        hist = [k for k in keys if f - 2.5 <= k <= f]
        outer = [h.tip_world(h.samples[k], 1.0) for k in hist]
        inner = [h.tip_world(h.samples[k], 0.55) for k in hist]
        tr.set(outer, inner, max(h.samples[f]["trail"], 0.15) if f in h.samples else 0.0)
        for t in targets:
            if t["hit"] == f:
                sp.burst(t["at"], 30, 7.5, dir=(t["hdir"][0], t["hdir"][1], 0.3))
        sp.step()

    # kıvılcımlar sıralı simülasyon ister: başlangıç karesinden önceki kareleri de adımla
    for f in range(1, F0):
        bpy.context.scene.frame_set(f)
        pf(f)
    render_frames(pf)


def shot_E():
    """Kan Tırpanı yakın plan: karanlıkta yavaş dönen silah, kızıl ağız ışıması, korlar."""
    sc = S.reset(RES, SAMPLES)
    sc.cycles.volume_step_rate = 2.0
    S.sky(sun_elev=2, strength=0.0)
    w, _, wm = import_zxm("blood_scythe", emission=8.0, rig=False, subdiv=1, bump=0.35, metal=0.8, rough=0.35)
    n = LEN["E"]
    pivot = bpy.data.objects.new("pivot", None)
    sc.collection.objects.link(pivot)
    # silah düzlemi (x boy, z ağız) kameraya dönük; sap sol alttan sağ üste çapraz
    R = Matrix.Rotation(math.radians(-38), 4, "Y")
    c = Vector(((wm["lo"][0] + wm["hi"][0]) / 2, 0, (wm["lo"][2] + wm["hi"][2]) / 2))
    w.parent = pivot
    w.matrix_basis = R @ Matrix.Translation(-c)
    for f, rz in [(1, -28), (n, 22)]:
        pivot.rotation_euler = (0, 0, math.radians(rz))
        pivot.keyframe_insert("rotation_euler", frame=f)
    blade = R @ (Vector((wm["tip"] * 0.85, 0, 0.05)) - c)
    S.light("AREA", (1.4, 0.9, 1.2), 260.0, (1.0, 0.22, 0.06), size=0.8, target=tuple(blade), name="Rim1")
    S.light("AREA", (-1.5, 0.8, 0.6), 160.0, (0.55, 0.65, 1.0), size=0.8, target=(0, 0, 0), name="Rim2")
    S.light("AREA", (0.4, -1.6, -0.3), 25.0, (1.0, 0.8, 0.7), size=2.0, target=(0, 0, 0), name="Fill")
    S.fog_box((0, 2.0, 0), (8, 3, 6), density=0.05, color="#ff7a4a")
    S.embers((0, -0.2, 0.0), (2.4, 1.4, 1.8), 350, 17, strength=90.0)
    cam = S.camera((0.25, -1.9, 0.05), tuple(blade * 0.5), lens=45, fstop=2.2)
    S.look(cam, (0.3, -2.0, 0.0), tuple(blade * 0.45), 1, lens=45, focus=2.0)
    S.look(cam, (0.12, -1.45, 0.12), tuple(blade * 0.6), n, lens=52, focus=1.45)
    S.compositor(glare=0.8)
    render_frames(lambda f: None)


def shot_F():
    """Son: kahraman pozu, arkada yangınlar ve sisten yükselen Titan; logo kartı sonradan eklenir."""
    sc = world(fog=0.0045, sun=3.0, sky=0.15, embers_box=((0, 3, 2), (10, 10, 4), 700, 19), fire_spots=STREET_FIRES)
    wrecks()
    h = Hero()
    h.animate(lambda f: dict(anim=0, t=0.7 + f / 24, period=1.6, weapon="blood_scythe"), range(1, LEN["F"] + 2))
    h.eyes_on(40.0, 1)
    S.light("AREA", (2.2, -2.6, 2.2), 90.0, (1.0, 0.6, 0.45), size=2.0, target=(0, 0, 1.3), name="Key")
    S.light("AREA", (-1.6, 1.8, 2.6), 380.0, (1.0, 0.22, 0.06), size=1.5, target=(0, 0, 1.4), name="Rim")
    S.light("AREA", (1.6, 1.8, 2.4), 220.0, (0.5, 0.6, 1.0), size=1.5, target=(0, 0, 1.4), name="Rim2")
    cam = S.camera((0.9, -4.6, 0.55), (0, 0, 1.35), lens=28, fstop=3.2)
    S.look(cam, (1.0, -4.8, 0.5), (0.1, 0, 1.4), 1, lens=28, focus=4.9)
    S.look(cam, (0.7, -3.7, 0.62), (0.05, 0, 1.45), LEN["F"], lens=28, focus=3.75)
    ti = Zombie("vex", seed=99, scale=3.4, dark=0.3, eye_strength=150, eye_size=0.016, cloth_frames=(PREROLL, LEN[SHOT] + 2))
    ti.walk(list(range(1, LEN["F"] + 2)), (-4.5, 44), speed=0.6, heading_deg=8, period=1.6)
    render_frames(lambda f: None)


SHOTS = {"A": shot_A, "B": shot_B, "C": shot_C, "D1": shot_D1, "D2": shot_D2, "E": shot_E, "F": shot_F}
SHOTS[SHOT]()
