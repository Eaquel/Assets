"""Bake edilmiş ateşi kameraya dönük şeffaf görüntü dizisine (flipbook) çevirir: RGB = alev ışıması, A = örtme."""
import bpy, math, os
bpy.ops.wm.open_mainfile(filepath="/home/user/promo3d/cache/fire.blend")
sc = bpy.context.scene
dom = bpy.data.objects["FireDomain"]; src = bpy.data.objects["FireSrc"]; src.hide_render = True
nt = dom.data.materials[0].node_tree
pv = [n for n in nt.nodes if n.type == "PRINCIPLED_VOLUME"][0]
pv.inputs["Density Attribute"].default_value = ""
da = nt.nodes.new("ShaderNodeAttribute"); da.attribute_name = "density"
dm = nt.nodes.new("ShaderNodeMath"); dm.operation = "MULTIPLY"; dm.inputs[1].default_value = 1.2
nt.links.new(da.outputs["Fac"], dm.inputs[0]); nt.links.new(dm.outputs[0], pv.inputs["Density"])
pv.inputs["Color"].default_value = (0.04, 0.035, 0.035, 1)
fa = nt.nodes.new("ShaderNodeAttribute"); fa.attribute_name = "flame"
ramp = nt.nodes.new("ShaderNodeValToRGB"); cr = ramp.color_ramp
cr.elements[0].color = (0, 0, 0, 1); cr.elements[1].color = (1.0, 0.92, 0.7, 1)
for pos, c in [(0.05, (0.5, 0.02, 0.0, 1)), (0.3, (1.0, 0.22, 0.02, 1)), (0.65, (1.0, 0.58, 0.14, 1))]:
    e = cr.elements.new(pos); e.color = c
nt.links.new(fa.outputs["Fac"], ramp.inputs[0]); nt.links.new(ramp.outputs[0], pv.inputs["Emission Color"])
em = nt.nodes.new("ShaderNodeMath"); em.operation = "MULTIPLY"; em.inputs[1].default_value = 12.0
nt.links.new(fa.outputs["Fac"], em.inputs[0]); nt.links.new(em.outputs[0], pv.inputs["Emission Strength"])
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 5.0
cam.location = (0, -10, 2.4); cam.rotation_euler = (math.radians(90), 0, 0)
sc.render.engine = "CYCLES"; sc.cycles.samples = 16; sc.cycles.use_denoising = True; sc.cycles.volume_step_rate = 0.5
sc.render.film_transparent = False
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = True; sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.0
sc.render.resolution_x, sc.render.resolution_y = 400, 800
sc.view_settings.view_transform = "AgX"
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"
sc.frame_start, sc.frame_end = 31, 330
sc.render.filepath = "/home/user/promo3d/cache/flip/f_"
bpy.ops.render.render(animation=True)
