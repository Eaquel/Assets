import bpy, sys, time
res = int(sys.argv[-2]); nfr = int(sys.argv[-1])
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, nfr
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, location=(0, 0, 0.2)); bpy.context.object.scale = (1.0, 1.0, 0.35)
src = bpy.context.object; src.name = "FireSrc"
bpy.ops.object.quick_smoke(style='FIRE')
dom = [o for o in bpy.data.objects if o is not src][0]; print("DOM", dom.name, [m.type for m in dom.modifiers])
dom.name = "FireDomain"
dom.scale = (1.3, 1.3, 2.4); dom.location = (0, 0, 2.3)
st = [m for m in dom.modifiers if m.type=="FLUID"][0].domain_settings
st.resolution_max = res
st.cache_directory = "/home/user/promo3d/cache/fire"
st.cache_type = "ALL"
st.cache_frame_start, st.cache_frame_end = 1, nfr
st.use_adaptive_domain = True
st.vorticity = 0.25
st.alpha = 1.2; st.beta = 1.4
st.burning_rate = 0.5; st.flame_smoke = 0.8; st.flame_vorticity = 0.9; st.flame_max_temp = 2.5
st.use_noise = False
fs = [m for m in src.modifiers if m.type=="FLUID"][0].flow_settings
fs.fuel_amount = 2.0; fs.surface_distance = 0.25; fs.temperature = 2.0; fs.flow_source = "MESH"
tex = bpy.data.textures.new("n", "CLOUDS"); tex.noise_scale = 0.3
fs.use_texture = True; fs.noise_texture = tex
src.hide_render = True
t = time.time()
bpy.context.view_layer.objects.active = dom
with bpy.context.temp_override(object=dom, active_object=dom):
    bpy.ops.fluid.bake_all()
print("BAKED", time.time() - t)
bpy.ops.wm.save_as_mainfile(filepath="/home/user/promo3d/cache/fire.blend")
