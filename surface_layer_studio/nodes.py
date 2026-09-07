"""Generated shader graph for an unlimited ordered stack of paint masks."""

from __future__ import annotations

from collections.abc import Iterable

import bpy

from .constants import MANAGED_TAG, MASK_NODE_SUFFIX, NODE_PREFIX
from .properties import active_layer
from . import desk_shader


_PENDING: set[bpy.types.Material] = set()
_REBUILDING = False


def _new_node(tree, node_type: str, name: str, label: str, x: float, y: float, parent=None):
    node = tree.nodes.new(node_type)
    node.name = name
    node.label = label
    node.location = (x, y)
    node[MANAGED_TAG] = True
    if parent is not None:
        node.parent = parent
    return node


def _value(tree, name: str, value: float, x: float, y: float, parent=None):
    node = _new_node(tree, "ShaderNodeValue", name, name, x, y, parent)
    node.outputs[0].default_value = value
    return node.outputs[0]


def _rgb(tree, name: str, color, x: float, y: float, parent=None):
    node = _new_node(tree, "ShaderNodeRGB", name, name, x, y, parent)
    node.outputs[0].default_value = color
    return node.outputs[0]


def _math(tree, operation: str, name: str, x: float, y: float, parent=None):
    node = _new_node(tree, "ShaderNodeMath", name, name, x, y, parent)
    node.operation = operation
    node.use_clamp = True
    return node


def _mix_scalar(tree, a, b, factor, name: str, x: float, y: float, parent=None):
    inverse = _math(tree, "SUBTRACT", f"{name}_Inverse", x, y + 80, parent)
    inverse.inputs[0].default_value = 1.0
    tree.links.new(factor, inverse.inputs[1])

    lower = _math(tree, "MULTIPLY", f"{name}_Lower", x + 160, y + 80, parent)
    upper = _math(tree, "MULTIPLY", f"{name}_Upper", x + 160, y - 20, parent)
    tree.links.new(a, lower.inputs[0])
    tree.links.new(inverse.outputs[0], lower.inputs[1])
    tree.links.new(b, upper.inputs[0])
    tree.links.new(factor, upper.inputs[1])

    add = _math(tree, "ADD", name, x + 320, y + 30, parent)
    tree.links.new(lower.outputs[0], add.inputs[0])
    tree.links.new(upper.outputs[0], add.inputs[1])
    return add.outputs[0]


def _texture_node(tree, name: str, label: str, image, vector, x: float, y: float, parent=None):
    node = _new_node(tree, "ShaderNodeTexImage", name, label, x, y, parent)
    node.image = image
    node.interpolation = "Linear"
    node.extension = "REPEAT"
    if vector is not None and vector.node.get("sls_box_projection"):
        node.projection = "BOX"
        node.projection_blend = 0.2
    if vector is not None:
        tree.links.new(vector, node.inputs["Vector"])
    return node


def _directx_to_opengl(tree, color, prefix: str, x: float, y: float, parent=None):
    separate = _new_node(tree, "ShaderNodeSeparateColor", f"{prefix}_Separate", "DirectX Normal", x, y, parent)
    separate.mode = "RGB"
    invert = _math(tree, "SUBTRACT", f"{prefix}_Invert_G", x + 170, y - 40, parent)
    invert.inputs[0].default_value = 1.0
    combine = _new_node(tree, "ShaderNodeCombineColor", f"{prefix}_Combine", "OpenGL Normal", x + 340, y, parent)
    combine.mode = "RGB"
    tree.links.new(color, separate.inputs[0])
    tree.links.new(separate.outputs["Red"], combine.inputs["Red"])
    tree.links.new(separate.outputs["Green"], invert.inputs[1])
    tree.links.new(invert.outputs[0], combine.inputs["Green"])
    tree.links.new(separate.outputs["Blue"], combine.inputs["Blue"])
    return combine.outputs[0]


def _find_socket(node, *names: str):
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            return socket
    return None


def _output_node(tree):
    for node in tree.nodes:
        if node.bl_idname == "ShaderNodeOutputMaterial" and getattr(node, "is_active_output", False):
            return node
    for node in tree.nodes:
        if node.bl_idname == "ShaderNodeOutputMaterial":
            return node
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.name = "SLS Material Output"
    output.label = "Surface Layer Studio Output"
    output.location = (1400, 0)
    return output


def capture_original_surface(material: bpy.types.Material) -> None:
    material.use_nodes = True
    tree = material.node_tree
    output = _output_node(tree)
    surface = output.inputs.get("Surface")
    if surface and surface.is_linked:
        link = surface.links[0]
        if not link.from_node.get(MANAGED_TAG):
            material["sls_original_node"] = link.from_node.name
            material["sls_original_socket"] = link.from_socket.name
            stack_id = getattr(getattr(material, "sls", None), "stack_id", "")
            if stack_id:
                link.from_node["sls_original_stack"] = stack_id
    material["sls_output_node"] = output.name


def restore_original_surface(material: bpy.types.Material) -> bool:
    if not material.use_nodes or material.node_tree is None:
        return False
    tree = material.node_tree
    output = tree.nodes.get(material.get("sls_output_node", "")) or _output_node(tree)
    surface = output.inputs.get("Surface")
    if surface:
        for link in list(surface.links):
            tree.links.remove(link)
    restored = False
    node = tree.nodes.get(material.get("sls_original_node", ""))
    if node is None:
        stack_id = getattr(getattr(material, "sls", None), "stack_id", "")
        node = next((candidate for candidate in tree.nodes if candidate.get("sls_original_stack") == stack_id), None)
    if node is not None and surface is not None:
        socket_name = material.get("sls_original_socket", "")
        socket = node.outputs.get(socket_name)
        if socket is not None:
            tree.links.new(socket, surface)
            restored = True
    _remove_managed_nodes(tree)
    return restored


def _remove_managed_nodes(tree) -> None:
    for node in list(tree.nodes):
        if bool(node.get(MANAGED_TAG)):
            tree.nodes.remove(node)


def _active_layers(settings) -> Iterable:
    soloed = any(layer.solo and layer.enabled for layer in settings.layers)
    for layer in reversed(settings.layers):  # Collection is top-to-bottom in the UI.
        if not layer.enabled:
            continue
        if soloed and not layer.solo:
            continue
        yield layer


def _mapped_vector(tree, layer, prefix: str, frame, x: float, y: float):
    uv = _new_node(tree, "ShaderNodeUVMap", f"{prefix}_UV", layer.uv_map or "Active UV", x, y, frame)
    uv.uv_map = layer.uv_map
    mapping = _new_node(tree, "ShaderNodeMapping", f"{prefix}_Mapping", "UV Transform", x + 180, y, frame)
    mapping.vector_type = "POINT"
    mapping.inputs["Location"].default_value[0] = layer.mapping_offset[0]
    mapping.inputs["Location"].default_value[1] = layer.mapping_offset[1]
    mapping.inputs["Rotation"].default_value[2] = layer.mapping_rotation
    mapping.inputs["Scale"].default_value[0] = layer.mapping_scale[0]
    mapping.inputs["Scale"].default_value[1] = layer.mapping_scale[1]
    tree.links.new(uv.outputs["UV"], mapping.inputs["Vector"])
    if hasattr(layer, "desk") and layer.desk.source_projection == "BOX":
        coordinates = _new_node(tree, "ShaderNodeTexCoord", f"{prefix}_BoxCoords", "Object box", x, y - 250, frame)
        box = _new_node(tree, "ShaderNodeMapping", f"{prefix}_BoxMapping", "Box transform", x + 180, y - 250, frame)
        box["sls_box_projection"] = True
        box.inputs["Location"].default_value = (*layer.mapping_offset, 0.0)
        box.inputs["Scale"].default_value = (*layer.mapping_scale, layer.mapping_scale[0])
        box.inputs["Rotation"].default_value[2] = layer.mapping_rotation
        tree.links.new(coordinates.outputs["Object"], box.inputs["Vector"])
        return uv.outputs["UV"], box.outputs["Vector"]
    return uv.outputs["UV"], mapping.outputs["Vector"]


def _layer_nodes(tree, layer, index: int, current: dict[str, object], composite: bool):
    short = layer.uuid.replace("-", "")[:10]
    prefix = f"{NODE_PREFIX}{short}"
    frame = _new_node(tree, "NodeFrame", f"{prefix}_FRAME", layer.name, -1700 + index * 110, -index * 70)
    frame.label = f"{index + 1}. {layer.name}"
    frame.label_size = 24
    frame.use_custom_color = True
    frame.color = (0.12, 0.20, 0.27) if composite else (0.16, 0.16, 0.16)

    mask_vector, source_vector = _mapped_vector(tree, layer, prefix, frame, -650, 440)
    mask_node = _texture_node(
        tree,
        f"{prefix}{MASK_NODE_SUFFIX}",
        f"MASK - {layer.name}",
        layer.mask_image,
        mask_vector,
        -430,
        580,
        frame,
    )
    mask_node["sls_role"] = "mask"
    mask_node["sls_layer_id"] = layer.uuid
    mask_node.extension = "CLIP"
    raw_mask = mask_node.outputs["Color"] if layer.mask_image else _value(
        tree, f"{prefix}_NoMask", 1.0, -430, 580, frame
    )
    raw_mask = desk_shader.mask(tree, layer, prefix, frame, raw_mask)
    if layer.invert_mask:
        invert = _math(tree, "SUBTRACT", f"{prefix}_InvertMask", -200, 580, frame)
        invert.inputs[0].default_value = 1.0
        tree.links.new(raw_mask, invert.inputs[1])
        raw_mask = invert.outputs[0]
    opacity = _math(tree, "MULTIPLY", f"{prefix}_Opacity", 0, 580, frame)
    opacity.inputs[1].default_value = layer.opacity
    tree.links.new(raw_mask, opacity.inputs[0])
    factor = opacity.outputs[0]

    if not composite:
        return raw_mask

    if layer.base_color_image:
        base_tex = _texture_node(
            tree, f"{prefix}_BaseColor", "Base Color", layer.base_color_image, source_vector, -430, 340, frame
        )
        tint = _new_node(tree, "ShaderNodeMixRGB", f"{prefix}_Tint", "Tint", -190, 340, frame)
        tint.blend_type = "MULTIPLY"
        tint.inputs[0].default_value = 1.0
        tint.inputs[2].default_value = layer.tint
        tree.links.new(base_tex.outputs["Color"], tint.inputs[1])
        layer_color = tint.outputs[0]
        if layer.use_base_alpha:
            alpha_factor = _math(tree, "MULTIPLY", f"{prefix}_TextureAlpha", 190, 580, frame)
            tree.links.new(factor, alpha_factor.inputs[0])
            tree.links.new(base_tex.outputs["Alpha"], alpha_factor.inputs[1])
            factor = alpha_factor.outputs[0]
    else:
        layer_color = _rgb(tree, f"{prefix}_TintColor", layer.tint, -190, 340, frame)

    if layer.ao_image:
        ao_tex = _texture_node(tree, f"{prefix}_AO", "Ambient Occlusion", layer.ao_image, source_vector, -430, 120, frame)
        ao_mix = _new_node(tree, "ShaderNodeMixRGB", f"{prefix}_AOStrength", "AO Strength", -180, 120, frame)
        ao_mix.blend_type = "MIX"
        ao_mix.inputs[0].default_value = layer.ao_strength
        ao_mix.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
        tree.links.new(ao_tex.outputs["Color"], ao_mix.inputs[2])
        ao_multiply = _new_node(tree, "ShaderNodeMixRGB", f"{prefix}_ApplyAO", "Apply AO", 20, 260, frame)
        ao_multiply.blend_type = "MULTIPLY"
        ao_multiply.inputs[0].default_value = 1.0
        tree.links.new(layer_color, ao_multiply.inputs[1])
        tree.links.new(ao_mix.outputs[0], ao_multiply.inputs[2])
        layer_color = ao_multiply.outputs[0]

    roughness = _value(tree, f"{prefix}_RoughnessValue", layer.roughness, -180, -20, frame)
    if layer.roughness_image:
        rough_tex = _texture_node(
            tree, f"{prefix}_Roughness", "Roughness", layer.roughness_image, source_vector, -430, -20, frame
        )
        rough_mul = _math(tree, "MULTIPLY", f"{prefix}_RoughnessScale", -180, -20, frame)
        rough_mul.inputs[1].default_value = layer.roughness_multiplier
        tree.links.new(rough_tex.outputs["Color"], rough_mul.inputs[0])
        roughness = rough_mul.outputs[0]

    metallic = _value(tree, f"{prefix}_MetallicValue", layer.metallic, -180, -150, frame)
    if layer.metallic_image:
        metal_tex = _texture_node(
            tree, f"{prefix}_Metallic", "Metallic", layer.metallic_image, source_vector, -430, -150, frame
        )
        metal_mul = _math(tree, "MULTIPLY", f"{prefix}_MetallicScale", -180, -150, frame)
        metal_mul.inputs[1].default_value = layer.metallic_multiplier
        tree.links.new(metal_tex.outputs["Color"], metal_mul.inputs[0])
        metallic = metal_mul.outputs[0]

    layer_color, roughness, generated_height = desk_shader.surface(tree, layer, prefix, frame, layer_color, roughness)

    normal_color = None
    if layer.normal_image:
        normal_tex = _texture_node(tree, f"{prefix}_Normal", "Normal", layer.normal_image, tree.nodes[f"{prefix}_Mapping"].outputs["Vector"], -430, -300, frame)
        normal_color = normal_tex.outputs["Color"]
        if layer.normal_format == "DIRECTX":
            normal_color = _directx_to_opengl(tree, normal_color, prefix, -190, -300, frame)

    height = generated_height
    if layer.height_image:
        height_tex = _texture_node(tree, f"{prefix}_Height", "Height", layer.height_image, source_vector, -430, -470, frame)
        height = height_tex.outputs["Color"]

    emission = None
    if layer.emission_image:
        emission_tex = _texture_node(
            tree, f"{prefix}_Emission", "Emission", layer.emission_image, source_vector, -430, -620, frame
        )
        emission_tint = _new_node(tree, "ShaderNodeMixRGB", f"{prefix}_EmissionTint", "Emission Tint", -190, -620, frame)
        emission_tint.blend_type = "MULTIPLY"
        emission_tint.inputs[0].default_value = 1.0
        emission_tint.inputs[2].default_value = layer.emission_tint
        tree.links.new(emission_tex.outputs["Color"], emission_tint.inputs[1])
        emission = emission_tint.outputs[0]
    elif layer.emission_strength > 0.0:
        emission = _rgb(tree, f"{prefix}_EmissionTintColor", layer.emission_tint, -190, -620, frame)
    if emission is not None:
        emission_scale = _new_node(
            tree, "ShaderNodeMixRGB", f"{prefix}_EmissionScale", "Emission Strength", 20, -620, frame
        )
        emission_scale.blend_type = "MULTIPLY"
        emission_scale.inputs[0].default_value = 1.0
        emission_scale.inputs[2].default_value = (
            layer.emission_strength,
            layer.emission_strength,
            layer.emission_strength,
            1.0,
        )
        tree.links.new(emission, emission_scale.inputs[1])
        emission = emission_scale.outputs[0]

    color_mix = _new_node(tree, "ShaderNodeMixRGB", f"{prefix}_ColorComposite", layer.blend_mode, 350, 330, frame)
    color_mix.blend_type = layer.blend_mode
    color_mix.use_clamp = True
    tree.links.new(factor, color_mix.inputs[0])
    tree.links.new(current["color"], color_mix.inputs[1])
    tree.links.new(layer_color, color_mix.inputs[2])
    current["color"] = color_mix.outputs[0]
    current["roughness"] = _mix_scalar(
        tree, current["roughness"], roughness, factor, f"{prefix}_RoughnessComposite", 350, 70, frame
    )
    current["metallic"] = _mix_scalar(
        tree, current["metallic"], metallic, factor, f"{prefix}_MetallicComposite", 350, -100, frame
    )

    if normal_color is not None:
        normal_factor = _math(tree, "MULTIPLY", f"{prefix}_NormalInfluence", 180, -300, frame)
        normal_factor.inputs[1].default_value = min(layer.normal_strength, 1.0)
        tree.links.new(factor, normal_factor.inputs[0])
        normal_mix = _new_node(tree, "ShaderNodeMixRGB", f"{prefix}_NormalComposite", "Normal Composite", 400, -300, frame)
        normal_mix.blend_type = "MIX"
        tree.links.new(normal_factor.outputs[0], normal_mix.inputs[0])
        tree.links.new(current["normal"], normal_mix.inputs[1])
        tree.links.new(normal_color, normal_mix.inputs[2])
        current["normal"] = normal_mix.outputs[0]
        current["has_normal"] = True

    if height is not None:
        height_factor = _math(tree, "MULTIPLY", f"{prefix}_HeightInfluence", 180, -470, frame)
        height_factor.inputs[1].default_value = layer.height_strength
        tree.links.new(factor, height_factor.inputs[0])
        current["height"] = _mix_scalar(
            tree, current["height"], height, height_factor.outputs[0], f"{prefix}_HeightComposite", 400, -470, frame
        )
        current["has_height"] = True

    if emission is not None:
        emission_mix = _new_node(
            tree, "ShaderNodeMixRGB", f"{prefix}_EmissionComposite", "Emission Composite", 400, -620, frame
        )
        emission_mix.blend_type = "MIX"
        tree.links.new(factor, emission_mix.inputs[0])
        tree.links.new(current["emission"], emission_mix.inputs[1])
        tree.links.new(emission, emission_mix.inputs[2])
        current["emission"] = emission_mix.outputs[0]
        current["emission_strength"] = 1.0
    return raw_mask


def rebuild_material(material: bpy.types.Material) -> bool:
    global _REBUILDING
    if _REBUILDING or material is None or not hasattr(material, "sls") or not material.sls.enabled:
        return False
    _REBUILDING = True
    try:
        material.use_nodes = True
        tree = material.node_tree
        if tree is None:
            return False
        _remove_managed_nodes(tree)
        settings = material.sls
        output = _output_node(tree)
        material["sls_output_node"] = output.name

        current: dict[str, object] = {
            "color": _rgb(tree, "SLS_Undercoat_Color", settings.base_color, -2400, 650),
            "roughness": _value(tree, "SLS_Undercoat_Roughness", settings.base_roughness, -2400, 500),
            "metallic": _value(tree, "SLS_Undercoat_Metallic", settings.base_metallic, -2400, 350),
            "normal": _rgb(tree, "SLS_Flat_Normal", (0.5, 0.5, 1.0, 1.0), -2400, 200),
            "height": _value(tree, "SLS_Flat_Height", 0.5, -2400, 50),
            "emission": _rgb(tree, "SLS_No_Emission", (0.0, 0.0, 0.0, 1.0), -2400, -100),
            "emission_strength": 0.0,
            "has_normal": False,
            "has_height": False,
        }

        effective_ids = {layer.uuid for layer in _active_layers(settings)}
        raw_masks: dict[str, object] = {}
        # Build bottom-to-top while keeping frame numbering aligned to the visible list.
        for reverse_index, layer in enumerate(reversed(settings.layers)):
            raw_masks[layer.uuid] = _layer_nodes(
                tree, layer, len(settings.layers) - reverse_index - 1, current, layer.uuid in effective_ids
            )

        # Explicit unlit channel sockets for safe, temporary export materials.
        for channel in ("color", "roughness", "metallic", "normal", "height", "emission"):
            channel_node = _new_node(tree, "NodeReroute", f"SLS_Channel_{channel}", channel, 650, 600)
            tree.links.new(current[channel], channel_node.inputs[0])
        layer = active_layer(material)
        if layer and layer.uuid in raw_masks:
            channel_node = _new_node(tree, "NodeReroute", "SLS_Channel_mask", "Active mask", 650, 700)
            tree.links.new(raw_masks[layer.uuid], channel_node.inputs[0])

        shader = _new_node(tree, "ShaderNodeBsdfPrincipled", "SLS_Principled", "Layered Surface", 900, 100)
        shader["sls_role"] = "principled"
        shader.inputs["Base Color"].default_value = settings.base_color
        shader.inputs["Roughness"].default_value = settings.base_roughness
        shader.inputs["Metallic"].default_value = settings.base_metallic

        preview = settings.preview_mode
        preview_source = None
        if preview == "ACTIVE_MASK":
            layer = active_layer(material)
            preview_source = raw_masks.get(layer.uuid) if layer else None
        elif preview == "BASE_COLOR":
            preview_source = current["color"]
        elif preview == "ROUGHNESS":
            preview_source = current["roughness"]
        elif preview == "METALLIC":
            preview_source = current["metallic"]
        elif preview == "NORMAL":
            preview_source = current["normal"]
        elif preview == "HEIGHT":
            preview_source = current["height"]
        elif preview == "EMISSION":
            preview_source = current["emission"]

        if preview != "COMPOSITE" and preview_source is not None:
            tree.links.new(preview_source, shader.inputs["Base Color"])
            shader.inputs["Metallic"].default_value = 0.0
            shader.inputs["Roughness"].default_value = 0.65
        else:
            tree.links.new(current["color"], shader.inputs["Base Color"])
            tree.links.new(current["roughness"], shader.inputs["Roughness"])
            tree.links.new(current["metallic"], shader.inputs["Metallic"])

            emission_color = _find_socket(shader, "Emission Color", "Emission")
            emission_strength = _find_socket(shader, "Emission Strength")
            if emission_color is not None:
                tree.links.new(current["emission"], emission_color)
            if emission_strength is not None:
                emission_strength.default_value = float(current["emission_strength"])

            normal_output = None
            if current["has_normal"]:
                normal_map = _new_node(tree, "ShaderNodeNormalMap", "SLS_Normal_Map", "Layered Normal", 650, -180)
                tree.links.new(current["normal"], normal_map.inputs["Color"])
                normal_output = normal_map.outputs["Normal"]
            if current["has_height"]:
                bump = _new_node(tree, "ShaderNodeBump", "SLS_Bump", "Layered Height", 850, -180)
                bump.inputs["Strength"].default_value = 1.0
                bump.inputs["Distance"].default_value = settings.bump_distance
                tree.links.new(current["height"], bump.inputs["Height"])
                if normal_output is not None:
                    tree.links.new(normal_output, bump.inputs["Normal"])
                normal_output = bump.outputs["Normal"]
            if normal_output is not None:
                tree.links.new(normal_output, shader.inputs["Normal"])

        surface = output.inputs.get("Surface")
        if surface is None:
            raise RuntimeError("Material Output has no Surface input")
        for link in list(surface.links):
            tree.links.remove(link)
        tree.links.new(shader.outputs["BSDF"], surface)

        settings.graph_version += 1
        settings.last_error = ""
        _PENDING.discard(material)
        return True
    except Exception as exc:
        material.sls.last_error = str(exc)
        raise
    finally:
        _REBUILDING = False


def mask_node(material: bpy.types.Material, layer_id: str):
    if not material.use_nodes or material.node_tree is None:
        return None
    tagged = next(
        (
            node
            for node in material.node_tree.nodes
            if node.get(MANAGED_TAG) and node.get("sls_role") == "mask" and node.get("sls_layer_id") == layer_id
        ),
        None,
    )
    if tagged is not None:
        return tagged
    short = layer_id.replace("-", "")[:10]
    return material.node_tree.nodes.get(f"{NODE_PREFIX}{short}{MASK_NODE_SUFFIX}")


def graph_health(material: bpy.types.Material | None) -> tuple[bool, str]:
    if material is None or not hasattr(material, "sls") or not material.sls.enabled:
        return False, "Material is not a Surface Layer Studio stack"
    if not material.use_nodes or material.node_tree is None:
        return False, "Material nodes are disabled"
    shader = next(
        (
            node
            for node in material.node_tree.nodes
            if node.get(MANAGED_TAG) and node.get("sls_role") == "principled"
        ),
        None,
    )
    if shader is None:
        return False, "Generated shader is missing; use Repair Stack"
    output = material.node_tree.nodes.get(material.get("sls_output_node", ""))
    if output is None:
        output = next(
            (
                node
                for node in material.node_tree.nodes
                if node.bl_idname == "ShaderNodeOutputMaterial" and getattr(node, "is_active_output", False)
            ),
            None,
        )
    if output is None:
        return False, "Material Output is missing; use Repair Stack"
    surface = output.inputs.get("Surface")
    if not surface or not surface.is_linked or surface.links[0].from_node != shader:
        return False, "Generated shader is disconnected; use Repair Stack"
    for layer in material.sls.layers:
        if mask_node(material, layer.uuid) is None:
            return False, f"Layer node is missing for {layer.name}; use Repair Stack"
    return True, "Stack is healthy"


def _timer_flush():
    flush_pending_rebuilds()
    return None


def request_rebuild(material: bpy.types.Material) -> None:
    if _REBUILDING or material is None or not material.sls.enabled:
        return
    _PENDING.add(material)
    if not bpy.app.timers.is_registered(_timer_flush):
        bpy.app.timers.register(_timer_flush, first_interval=0.08)


def flush_pending_rebuilds() -> None:
    materials = tuple(_PENDING)
    _PENDING.clear()
    for material in materials:
        try:
            is_valid = material.name in bpy.data.materials
        except ReferenceError:
            is_valid = False
        if is_valid and hasattr(material, "sls") and material.sls.enabled:
            try:
                rebuild_material(material)
            except Exception:
                # The error is retained on the material and shown by the UI.
                pass


def cancel_pending_rebuilds() -> None:
    _PENDING.clear()
    if bpy.app.timers.is_registered(_timer_flush):
        bpy.app.timers.unregister(_timer_flush)
