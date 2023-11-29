import os.path

import bpy
from typing import List, Tuple
import mathutils

# mesh_paths_csv = os.path.join(os.path.dirname(__file__), 'mesh_paths.csv')
# frames_csv = os.path.join(os.path.dirname(__file__), 'frames.csv')
# forces_csv = os.path.join(os.path.dirname(__file__), 'forces.csv')
mesh_paths_csv = '/Users/keenonwerling/Desktop/dev/AddBiomechanics/blender/mesh_paths.csv'
frames_csv = '/Users/keenonwerling/Desktop/dev/AddBiomechanics/blender/frames.csv'
forces_csv = '/Users/keenonwerling/Desktop/dev/AddBiomechanics/blender/forces.csv'
predicted_forces_csv = '/Users/keenonwerling/Desktop/dev/AddBiomechanics/blender/predicted_forces.csv'


############################################################################
# Read in the files
############################################################################
with open(mesh_paths_csv, 'r') as f:
    paths: List[Tuple[str, List[float]]] = []
    for line in f.readlines()[1:]:
        parts = line.split(',')
        path = parts[1]
        scale = [float(x) for x in parts[2:]]
        paths.append((path.strip(), scale))

with open(frames_csv, 'r') as f:
    frames = []
    for line in f.readlines()[1:]:
        parts = line.split(',')
        time = int(parts[0])
        frame = [float(x) for x in parts[1:]]
        body_positions: List[Tuple[List[float], List[float]]] = []
        for i in range(0, len(frame), 6):
            body_positions.append((frame[i:i+3], frame[i+3:i+6]))
        frames.append(body_positions)

with open(forces_csv, 'r') as f:
    force_frames = []
    for line in f.readlines()[1:]:
        parts = line.split(',')
        time = int(parts[0])
        frame = [float(x) for x in parts[1:]]
        force_arrows: List[Tuple[List[float], List[float]]] = []
        for i in range(0, len(frame), 6):
            force_arrows.append((frame[i:i+3], frame[i+3:i+6]))
        force_frames.append(force_arrows)

if os.path.exists(predicted_forces_csv):
    with open(predicted_forces_csv, 'r') as f:
        predicted_force_frames = []
        for line in f.readlines()[1:]:
            parts = line.split(',')
            time = int(parts[0])
            frame = [float(x) for x in parts[1:]]
            force_arrows: List[Tuple[List[float], List[float]]] = []
            for i in range(0, len(frame), 6):
                force_arrows.append((frame[i:i+3], frame[i+3:i+6]))
            predicted_force_frames.append((time, force_arrows))

# Set the end frame of the animation
bpy.context.scene.frame_end = len(frames)

############################################################################
# Create the materials
############################################################################

bone_material_name = "Bone"
if bone_material_name not in bpy.data.materials:
    bone_mat = bpy.data.materials.new(name=bone_material_name)

    # Setting up the bone material
    bone_mat.use_nodes = True
    nodes = bone_mat.node_tree.nodes
    nodes.clear()

    # Create a Principled BSDF node
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)

    # Set base color to a light, slightly yellowish tone
    bsdf.inputs['Base Color'].default_value = (0.27, 0.27, 0.25, 1)  # RGBA
    # Increase Subsurface Scattering for organic feel
    bsdf.inputs['Subsurface'].default_value = 0.1
    bsdf.inputs['Subsurface Color'].default_value = (0.57, 0.57, 0.27, 1)  # Slightly yellow
    # Subsurface radius can be tweaked as needed; these are starter values
    bsdf.inputs['Subsurface Radius'].default_value = (1.0, 0.2, 0.1)
    # Decrease the Specular and increase Roughness for a more matte finish
    bsdf.inputs['Specular'].default_value = 0.1
    bsdf.inputs['Roughness'].default_value = 0.5

    # Add output node
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (200, 0)

    # Link BSDF to output
    links = bone_mat.node_tree.links
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
else:
    bone_mat = bpy.data.materials[bone_material_name]

arrow_material_name = "Arrow"
if arrow_material_name not in bpy.data.materials:
    arrow_mat = bpy.data.materials.new(name=arrow_material_name)

    # Basic arrow material setup
    arrow_mat.use_nodes = True
    nodes = arrow_mat.node_tree.nodes
    nodes.clear()

    # Create a Principled BSDF node
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)

    # Set base color for the arrow material
    bsdf.inputs['Base Color'].default_value = (0.01, 0.06, 0.40) # (0.406, 0.03, 0.02, 1)  # Red
    bsdf.inputs['Emission'].default_value = (0, 0.07, 0.17) # (0.176, 0.0, 0.0, 1)  # Red

    # Add output node
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (200, 0)

    # Link BSDF to output
    links = arrow_mat.node_tree.links
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
else:
    arrow_mat = bpy.data.materials[arrow_material_name]

predicted_arrow_material_name = "Predicted Arrow"
if predicted_arrow_material_name not in bpy.data.materials:
    predicted_arrow_mat = bpy.data.materials.new(name=predicted_arrow_material_name)

    # Basic arrow material setup
    predicted_arrow_mat.use_nodes = True
    nodes = predicted_arrow_mat.node_tree.nodes
    nodes.clear()

    # Create a Principled BSDF node
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)

    # Set base color for the arrow material
    bsdf.inputs['Base Color'].default_value = (0.406, 0.03, 0.02, 1)  # Red
    bsdf.inputs['Emission'].default_value = (0.176, 0.0, 0.0, 1)  # Red

    # Add output node
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (200, 0)

    # Link BSDF to output
    links = predicted_arrow_mat.node_tree.links
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
else:
    predicted_arrow_mat = bpy.data.materials[arrow_material_name]

############################################################################
# Create the bones, and animate them
############################################################################

for i, (mesh_path, mesh_scale) in enumerate(paths):
    bpy.ops.import_mesh.ply(filepath=mesh_path)
    mesh_object = bpy.context.active_object
    mesh_object.rotation_mode = 'ZYX'
    mesh_object.scale = mesh_scale
    mesh_object.data.materials.clear()
    mesh_object.data.materials.append(bone_mat)

    # Add keyframes
    for t, frame in enumerate(frames):
        bpy.context.scene.frame_set(t)
        mesh_object.location = frame[i][0]
        mesh_object.rotation_euler = frame[i][1]
        mesh_object.keyframe_insert(data_path="location", frame=t)
        mesh_object.keyframe_insert(data_path="rotation_euler", frame=t)

############################################################################
# Create the force arrows, and animate them
############################################################################


def create_cone(name, location, scale=(1, 1, 1), material=arrow_mat):
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.1, radius2=0, depth=1, location=location)
    cone = bpy.context.object
    cone.name = name
    cone.scale = scale
    cone.data.materials.clear()
    cone.data.materials.append(material)
    return cone


def create_cylinder(name, location, scale=(1, 1, 1), material=arrow_mat):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=1, location=location)
    cylinder = bpy.context.object
    cylinder.name = name
    cylinder.scale = scale
    cylinder.data.materials.clear()
    cylinder.data.materials.append(material)
    return cylinder


def create_arrow(name, start, material=arrow_mat):
    start = mathutils.Vector(start)
    direction = mathutils.Vector([0, 0, 1])

    # Create cylinder
    cyl_length = 0.5
    cyl_scale = (1, 1, cyl_length)
    cylinder = create_cylinder(name + "_Cylinder", start, scale=cyl_scale, material=material)

    # Create cone
    cone_scale = (1, 1, 0.5)
    cone_location = start + direction.normalized() * 0.75
    cone = create_cone(name + "_Cone", cone_location, scale=cone_scale, material=material)

    # Parent the cone to the cylinder
    cone.parent = cylinder

    # Set cone to inherit visibility from parent
    cone.hide_render = cylinder.hide_render
    cone.hide_viewport = cylinder.hide_viewport

    # Apply transformations
    cylinder.select_set(True)
    bpy.context.view_layer.objects.active = cylinder
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    cylinder.rotation_mode = 'QUATERNION'

    return cylinder, cone


def orient_arrow(cylinder, cone, start, end):
    direction = mathutils.Vector(end) - mathutils.Vector(start)
    if direction.length == 0:
        cylinder.hide_viewport = True
        cylinder.hide_render = True
        cone.hide_viewport = True
        cone.hide_render = True
    else:
        cylinder.hide_viewport = False
        cylinder.hide_render = False
        cone.hide_viewport = False
        cone.hide_render = False
        cylinder.location = mathutils.Vector(start) + direction / 4
        cylinder.scale.z = direction.length
        cylinder.scale.x = direction.length / 2
        cylinder.scale.y = direction.length / 2
        cylinder.rotation_quaternion = direction.to_track_quat('Z', 'Y')


for i in range(len(force_frames[0])):
    cylinder, cone = create_arrow("Force_"+str(i), [0,0,0], material=arrow_mat)

    # Add keyframes
    for t, forces in enumerate(force_frames):
        start, end = forces[i]
        bpy.context.scene.frame_set(t)
        orient_arrow(cylinder, cone, start, end)
        cone.keyframe_insert(data_path="hide_viewport", frame=t)
        cone.keyframe_insert(data_path="hide_render", frame=t)
        cylinder.keyframe_insert(data_path="hide_viewport", frame=t)
        cylinder.keyframe_insert(data_path="hide_render", frame=t)
        cylinder.keyframe_insert(data_path="location", frame=t)
        cylinder.keyframe_insert(data_path="rotation_quaternion", frame=t)
        cylinder.keyframe_insert(data_path="scale", frame=t)

if len(predicted_force_frames) > 0:
    start_time = predicted_force_frames[0][0]

    for i in range(len(predicted_force_frames[0][1])):
        cylinder, cone = create_arrow("Predicted_Force_"+str(i), [0,0,0], material=predicted_arrow_mat)

        if start_time > 0:
            cone.hide_viewport = True
            cone.hide_render = True
            cylinder.hide_viewport = True
            cylinder.hide_render = True
            cone.keyframe_insert(data_path="hide_viewport", frame=start_time-1)
            cone.keyframe_insert(data_path="hide_render", frame=start_time-1)
            cylinder.keyframe_insert(data_path="hide_viewport", frame=start_time-1)
            cylinder.keyframe_insert(data_path="hide_render", frame=start_time-1)

        # Add keyframes
        for t, forces in predicted_force_frames:
            start, end = forces[i]
            bpy.context.scene.frame_set(t)
            orient_arrow(cylinder, cone, start, end)
            cone.keyframe_insert(data_path="hide_viewport", frame=t)
            cone.keyframe_insert(data_path="hide_render", frame=t)
            cylinder.keyframe_insert(data_path="hide_viewport", frame=t)
            cylinder.keyframe_insert(data_path="hide_render", frame=t)
            cylinder.keyframe_insert(data_path="location", frame=t)
            cylinder.keyframe_insert(data_path="rotation_quaternion", frame=t)
            cylinder.keyframe_insert(data_path="scale", frame=t)
