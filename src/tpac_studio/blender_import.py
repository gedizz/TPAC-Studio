"""Executed only inside Blender; exports static geometry and constant base colours."""

import json
import sys
from pathlib import Path


def main() -> None:
    import bpy

    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf8"))
    source = Path(job["source"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = source.suffix.lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(source))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source))
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(source))
    else:
        raise ValueError("Unsupported static model format")
    groups = []
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        if obj.vertex_groups or any(modifier.type == "ARMATURE" for modifier in obj.modifiers):
            raise ValueError("Skinned geometry is not supported by the static importer")
        bpy.context.view_layer.objects.active = obj
        mesh = obj.data
        mesh.calc_loop_triangles()
        uv = mesh.uv_layers.active
        if uv:
            mesh.calc_tangents()
        normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
        by_material = {}
        for triangle in mesh.loop_triangles:
            material = (
                mesh.materials[triangle.material_index]
                if len(mesh.materials) > triangle.material_index
                else None
            )
            group = by_material.setdefault(
                triangle.material_index,
                {
                    "vertices": [],
                    "indices": [],
                    "color": list(material.diffuse_color) if material else [0.6, 0.7, 0.8, 1],
                },
            )
            for loop_index in triangle.loops:
                loop = mesh.loops[loop_index]
                position = obj.matrix_world @ mesh.vertices[loop.vertex_index].co
                normal = (normal_matrix @ loop.normal).normalized()
                tangent = (
                    (obj.matrix_world.to_3x3() @ loop.tangent).normalized()
                    if uv
                    else normal.orthogonal().normalized()
                )
                coords = uv.data[loop_index].uv if uv else (0, 0)
                group["indices"].append(len(group["vertices"]))
                group["vertices"].append(
                    list(position)
                    + list(normal)
                    + list(tangent)
                    + [-loop.bitangent_sign if uv else 1, coords[0], 1 - coords[1]]
                )
        groups.extend(by_material.values())
    Path(job["output"]).write_text(json.dumps({"groups": groups}), encoding="utf8")


if __name__ == "__main__":
    main()
