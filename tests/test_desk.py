"""Numerical and catalog contracts independent of Blender."""
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
from surface_layer_studio import desk_pixels as px
from surface_layer_studio.desk_catalog import PRESETS, BY_ID, CATEGORIES, RECIPES, BRUSHES, rgb, find_presets


class CatalogTests(unittest.TestCase):
    def test_catalog_ids_and_categories(self):
        self.assertEqual(len(PRESETS),48)
        self.assertEqual(len(BY_ID),48)
        self.assertEqual(len(CATEGORIES),6)
        for category in CATEGORIES:
            self.assertEqual(sum(p.category==category for p in PRESETS),8)

    def test_every_preset_is_valid(self):
        for preset in PRESETS:
            with self.subTest(preset=preset.id):
                self.assertIn(preset.pattern,px.PATTERNS)
                self.assertIn(preset.placement,{'ALL','UP','DOWN','WATERLINE'})
                for scalar in (preset.roughness,preset.metallic,preset.coverage,preset.relief):
                    self.assertTrue(0<=scalar<=1)
                for color in (preset.color,preset.secondary):
                    self.assertTrue(all(0<=v<=1 for v in rgb(color,linear=True)))

    def test_recipes_reference_existing_presets(self):
        self.assertEqual(len(RECIPES),8)
        for name,ids in RECIPES.values():
            self.assertTrue(name)
            self.assertGreaterEqual(len(ids),3)
            self.assertTrue(set(ids)<=BY_ID.keys())
        self.assertEqual(len(BRUSHES),8)

    def test_linear_color_conversion(self):
        self.assertAlmostEqual(rgb('808080',linear=True)[0],.2158605,places=6)
        self.assertEqual(rgb('ffffff',linear=True),(1,1,1,1))
        self.assertEqual(rgb('000000'),(0,0,0,1))

    def test_search_category_favorites(self):
        self.assertEqual(len(find_presets()),48)
        found = find_presets('rust')
        self.assertGreater(len(found),2)
        self.assertTrue(all('rust' in (p.name+' '+p.category+' '+p.note).lower() for p in found))
        self.assertEqual(find_presets('definitely-not-a-material'),[])
        self.assertEqual([p.id for p in find_presets(favorites={'biofilm'})],['biofilm'])
        self.assertEqual(find_presets(favorites=set()),[])
        self.assertEqual(len(find_presets(category=CATEGORIES[0])),8)


class PixelTests(unittest.TestCase):
    def setUp(self):
        self.image=np.random.default_rng(3).random((19,23,4),dtype=np.float32)

    def test_every_pattern_deterministic_bounded_rectangular(self):
        for pattern in px.PATTERNS:
            with self.subTest(pattern=pattern):
                a=px.pattern(31,17,pattern,seed=7)
                np.testing.assert_array_equal(a,px.pattern(31,17,pattern,seed=7))
                self.assertEqual(a.shape,(17,31))
                self.assertTrue(np.isfinite(a).all())
                self.assertTrue(((0<=a)&(a<=1)).all())

    def test_seed_changes_noise_and_cells(self):
        for kind in ('NOISE','STREAKS','CELLS','CRACKS'):
            self.assertFalse(np.array_equal(px.pattern(32,32,kind,seed=1),px.pattern(32,32,kind,seed=2)))

    def test_coverage_endpoints(self):
        for kind in px.PATTERNS:
            np.testing.assert_array_equal(px.pattern(9,7,kind,coverage=0),np.zeros((7,9)))
            np.testing.assert_array_equal(px.pattern(9,7,kind,coverage=1),np.ones((7,9)))

    def test_generator_validation(self):
        for kwargs in ({'width':0,'height':2},{'width':4097,'height':4097},{'width':1,'height':1,'kind':'BAD'},{'width':1,'height':1,'scale':float('nan')}):
            with self.assertRaises(ValueError):px.pattern(**kwargs)

    def test_all_filters_keep_source_unchanged(self):
        before=self.image.copy()
        for operation in px.OPERATIONS:
            with self.subTest(operation=operation):
                out=px.edit(self.image,operation,black=.2,white=.9,gamma=1.2)
                self.assertEqual(out.shape,self.image.shape)
                self.assertTrue(np.isfinite(out).all())
                self.assertFalse(np.shares_memory(out,self.image))
                np.testing.assert_array_equal(self.image,before)
                if operation not in {'FLIP_X','FLIP_Y','OFFSET'}:
                    np.testing.assert_array_equal(out[...,3],self.image[...,3])

    def test_grayscale_and_flips(self):
        a=np.array([[[1,0,0,.7],[0,1,0,.3]]],dtype=np.float32)
        b=px.edit(a,'GRAYSCALE')
        self.assertAlmostEqual(float(b[0,0,0]),.2126,places=5)
        np.testing.assert_array_equal(px.edit(px.edit(a,'FLIP_X'),'FLIP_X'),a)
        np.testing.assert_array_equal(px.edit(px.edit(a,'FLIP_Y'),'FLIP_Y'),a)

    def test_levels_endpoints_gamma(self):
        a=np.array([.2,.5,.8],dtype=np.float32)
        np.testing.assert_allclose(px.levels(a,.2,.8),[0,.5,1],atol=1e-6)
        self.assertGreater(px.levels(a,.2,.8,2)[1],.5)
        for params in ((1,0,1),(0,1,0),(0,1,float('nan'))):
            with self.assertRaises(ValueError):px.levels(a,*params)

    def test_morphology_and_blur(self):
        a=np.zeros((9,9),dtype=np.float32);a[4,4]=1
        grown=px.edit(a,'GROW',radius=1)
        self.assertEqual(float(grown.sum()),9)
        np.testing.assert_array_equal(px.edit(grown,'SHRINK',radius=1),a)
        self.assertAlmostEqual(float(px.edit(a,'BLUR',radius=1).sum()),1,places=5)
        self.assertAlmostEqual(float(px.edit(a,'BLUR',radius=1)[4,4]),1/9,places=5)
        self.assertEqual(float(px.edit(np.ones((2,3)),'EDGE').sum()),0)

    def test_boundary_wrap_and_tiny_images(self):
        a=np.zeros((8,8),dtype=np.float32);a[0,0]=1
        self.assertEqual(px.edit(a,'GROW',radius=1,wrap=True)[-1,-1],1)
        self.assertEqual(px.edit(a,'GROW',radius=1,wrap=False)[-1,-1],0)
        for op in px.OPERATIONS:
            self.assertEqual(px.edit(np.ones((1,1)),op).shape,(1,1))
        for kind in px.PATTERNS:
            self.assertEqual(px.pattern(1,1,kind).shape,(1,1))

    def test_normal_map_flat_unit_vectors_and_directx(self):
        np.testing.assert_allclose(px.height_to_normal(np.zeros((1,1))),[[[.5,.5,1,1]]])
        h=np.arange(64,dtype=np.float32).reshape(8,8)/64
        gl=px.height_to_normal(h,wrap=False);dx=px.height_to_normal(h,directx=True,wrap=False)
        np.testing.assert_allclose(gl[...,0],dx[...,0])
        np.testing.assert_allclose(gl[...,1],1-dx[...,1],atol=1e-6)
        np.testing.assert_allclose(np.linalg.norm(gl[...,:3]*2-1,axis=-1),1,atol=1e-6)
        np.testing.assert_array_equal(gl[...,3],1)

    def test_orm_channel_layout(self):
        a=np.ones((3,5),dtype=np.float32)
        out=px.pack_orm(a,a*.6,a*.2)
        np.testing.assert_allclose(out[...,0],1)
        np.testing.assert_allclose(out[...,1],.6)
        np.testing.assert_allclose(out[...,2],.2)
        np.testing.assert_allclose(out[...,3],1)
        with self.assertRaises(ValueError):px.pack_orm(a,a[:2],a)

    def test_bad_images_and_operations(self):
        for a in (np.zeros((0,2)),np.array([[np.nan]]),np.array([1,2,3])):
            with self.assertRaises(ValueError):px.edit(a,'BLUR')
        with self.assertRaises(ValueError):px.edit(self.image,'UNKNOWN')
        with self.assertRaises(ValueError):px.height_to_normal(np.zeros((2,2)),strength=-1)

    def test_png_header_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'test.png';px.write_png(file,self.image)
            data=file.read_bytes()
            self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertEqual(struct.unpack('!II',data[16:24]),(23,19))


if __name__=='__main__':unittest.main()
