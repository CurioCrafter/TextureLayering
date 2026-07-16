from pathlib import Path
import unittest

from surface_layer_studio.core import (
    detect_channel,
    detect_normal_format,
    detect_pbr_set,
    friendly_layer_name,
    safe_filename,
    texture_set_key,
)


class PBRDetectionTests(unittest.TestCase):
    def test_detects_camel_case_and_common_channels(self):
        self.assertEqual(detect_channel("RustySteel_BaseColor_4K.png"), "base_color")
        self.assertEqual(detect_channel("RustySteel_Roughness_4K.png"), "roughness")
        self.assertEqual(detect_channel("RustySteel_Metalness_4K.png"), "metallic")
        self.assertEqual(detect_channel("RustySteel_NormalDX_4K.png"), "normal")
        self.assertEqual(detect_channel("RustySteel_AO_4K.png"), "ambient_occlusion")
        self.assertEqual(detect_channel("RustedMetal_AO_4K.png"), "ambient_occlusion")
        self.assertEqual(detect_channel("RustySteel_Emissive_4K.png"), "emission")

    def test_groups_one_texture_set_and_ignores_neighbors(self):
        selected = Path("C:/textures/RustySteel_BaseColor_4K.png")
        candidates = [
            selected,
            selected.with_name("RustySteel_Roughness_4K.png"),
            selected.with_name("RustySteel_Metallic_4K.png"),
            selected.with_name("RustySteel_NormalGL_4K.png"),
            selected.with_name("CleanSteel_Roughness_4K.png"),
            selected.with_name("notes.txt"),
        ]
        result = detect_pbr_set(selected, candidates)
        self.assertEqual(set(result), {"base_color", "roughness", "metallic", "normal"})
        self.assertTrue(all("RustySteel" in path.name for path in result.values()))

    def test_normal_format_is_explicit(self):
        self.assertEqual(detect_normal_format("panel_NormalDX.png"), "DIRECTX")
        self.assertEqual(detect_normal_format("panel_normal_directx.png"), "DIRECTX")
        self.assertEqual(detect_normal_format("panel_NormalGL.png"), "OPENGL")

    def test_names_are_stable_and_safe(self):
        self.assertEqual(texture_set_key("PaintedHull_BaseColor_2K.png"), "painted_hull")
        self.assertEqual(texture_set_key("RustyMetal_BaseColor_4K.png"), "rusty_metal")
        self.assertEqual(texture_set_key("RustyMetal_Metallic_4K.png"), "rusty_metal")
        self.assertEqual(friendly_layer_name("PaintedHull_BaseColor_2K.png"), "Painted Hull")
        self.assertEqual(safe_filename(" Deck / Rust: A "), "Deck_Rust_A")
        self.assertNotIn("..", safe_filename("../Deck/../../Rust"))


if __name__ == "__main__":
    unittest.main()
