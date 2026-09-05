"""Non-destructive green relief and tactile paper art direction."""
import bpy

def apply(scene, rgba, solid, aim):
    terrain=bpy.data.objects['LAOS | continuous real elevation surface']
    terrain.data.materials[0].name='Elevation | meadow green, golden slopes, warm summits'
    terrain.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.88

    # Neutral tabletop behind a real, separately modelled sheet of art paper.
    desk=bpy.data.objects['Matte studio ground']
    desk.name='Warm neutral tabletop beneath paper'
    desk.location.z=-.09
    desk.data.materials.clear()
    tablemat=solid('Matte warm tabletop','d2cbb9',.95)
    desk.data.materials.append(tablemat)
    nt=tablemat.node_tree
    coord=nt.nodes.new('ShaderNodeTexCoord')
    noise=nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value=2.8
    noise.inputs['Detail'].default_value=2
    nt.links.new(coord.outputs['Object'],noise.inputs['Vector'])
    cr=nt.nodes.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color=rgba('cbc3b1')
    cr.color_ramp.elements[1].color=rgba('e0d9c8')
    nt.links.new(noise.outputs['Fac'],cr.inputs[0])
    nt.links.new(cr.outputs[0],nt.nodes['Principled BSDF'].inputs['Base Color'])

    paper=solid('Natural warm-white cotton paper | fine grain','f5f1e4',.95)
    nt=paper.node_tree
    coord=nt.nodes.new('ShaderNodeTexCoord')
    grain=nt.nodes.new('ShaderNodeTexNoise')
    grain.name='Fine paper tooth'
    grain.inputs['Scale'].default_value=155
    grain.inputs['Detail'].default_value=2.5
    grain.inputs['Roughness'].default_value=.72
    nt.links.new(coord.outputs['Object'],grain.inputs['Vector'])
    papercolor=nt.nodes.new('ShaderNodeValToRGB')
    papercolor.color_ramp.elements[0].color=rgba('efece1')
    papercolor.color_ramp.elements[1].color=rgba('fffdf5')
    nt.links.new(grain.outputs['Fac'],papercolor.inputs[0])
    nt.links.new(papercolor.outputs[0],nt.nodes['Principled BSDF'].inputs['Base Color'])
    bump=nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value=.22
    bump.inputs['Distance'].default_value=.0012
    nt.links.new(grain.outputs['Fac'],bump.inputs['Height'])
    nt.links.new(bump.outputs[0],nt.nodes['Principled BSDF'].inputs['Normal'])
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,-.27,-.018))
    sheet=bpy.context.object
    sheet.name='Cotton art-paper sheet | visible edge and cast shadow'
    sheet.dimensions=(9.0,11.25,.036)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    sheet.data.materials.append(paper)
    bevel=sheet.modifiers.new('Soft paper edge','BEVEL')
    bevel.width=.01
    bevel.segments=3
    sheet['design']='Warm cotton-paper sheet, fine procedural tooth; tabletop visible at edges.'

    # Printed-looking forest ink: no floating letters or letter cast shadows.
    ink=bpy.data.materials['Typography | blue charcoal']
    ink.name='Printed forest-grey ink'
    ink.node_tree.nodes.get('Emission').inputs['Color'].default_value=rgba('3e4b33')
    for obj in list(scene.objects):
        if obj.type == 'FONT':
            obj.location.z=.0012
            obj.visible_shadow=False
    legend=bpy.data.objects['Continuous elevation scale 0 to 3000 metres']
    legend.location.z=.0015
    legend.dimensions.z=.001
    legend.visible_shadow=False

    # Longer, soft-edged relief shadows without crushing the green lowlands.
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(1,.97,.9,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.23
    soft=bpy.data.objects['Large northwest softbox']
    soft.name='Broad skylight fill'
    soft.location=(2,-2,11)
    soft.data.energy=650
    soft.data.size=7
    soft.data.color=(1,.98,.92)
    aim(soft,(0,0,0))
    sun=bpy.data.objects['Northwest raking relief light']
    sun.location=(-7,5,6.2)
    sun.data.energy=2.8
    sun.data.color=(1,.97,.9)
    sun.data.angle=.075
    aim(sun,(0,0,0))
    scene.camera.data.ortho_scale=12.05
    scene.view_settings.exposure=.3
    scene['Design']='Fresh green elevation relief with warm summits, on textured cotton paper; stronger soft shadows. True projected XY; 14x vertical exaggeration.'
