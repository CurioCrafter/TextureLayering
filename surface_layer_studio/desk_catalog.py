"""Original, asset-free art-direction recipes for Shipwreck Discovery.

Colors are display sRGB swatches, converted to scene linear on application.
These are starting materials, not scanned PBR assets or biological simulations.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    category: str
    color: str
    secondary: str
    roughness: float
    metallic: float
    pattern: str
    coverage: float
    scale: float
    relief: float
    placement: str = 'ALL'
    emission: float = 0.0
    note: str = ''


# id, name, category, colors, roughness, metallic, pattern, coverage, scale, relief
PRESETS = (
    Preset('hull_oxide', 'Hull oxide', 'Corrosion', '#854225', '#cb8a46', .9, 0, 'NOISE', .55, 6, .3),
    Preset('deep_rust', 'Deep iron rust', 'Corrosion', '#38201a', '#a95528', .98, 0, 'CELLS', .72, 14, .65),
    Preset('flaking_rust', 'Flaking red oxide', 'Corrosion', '#682a1f', '#db7641', .92, 0, 'CRACKS', .65, 16, .55),
    Preset('rust_drips', 'Rust runoff', 'Corrosion', '#4c261a', '#a75c31', .82, 0, 'STREAKS', .33, 8, .15),
    Preset('pitted_iron', 'Pitted iron', 'Corrosion', '#272f30', '#737779', .7, .7, 'CELLS', .95, 26, .35),
    Preset('zinc', 'Weathered zinc', 'Corrosion', '#687777', '#b8c5c2', .6, .55, 'CELLS', .9, 18, .1),
    Preset('verdigris', 'Copper verdigris', 'Corrosion', '#23594e', '#8aa984', .88, 0, 'NOISE', .6, 9, .2),
    Preset('brass', 'Tarnished brass', 'Corrosion', '#6b5425', '#b29a4b', .48, .85, 'NOISE', .95, 7, .08),
    Preset('biofilm', 'Green biofilm', 'Marine growth', '#233a20', '#73814a', .5, 0, 'NOISE', .38, 5, .12),
    Preset('olive_turf', 'Olive algal turf', 'Marine growth', '#333b18', '#9a9951', .9, 0, 'STREAKS', .55, 14, .3),
    Preset('brown_algae', 'Brown algae stain', 'Marine growth', '#382b17', '#797140', .79, 0, 'NOISE', .42, 8, .2),
    Preset('dark_slime', 'Dark slime', 'Marine growth', '#101d15', '#354731', .23, 0, 'NOISE', .32, 4, .08),
    Preset('barnacles', 'Barnacle crust', 'Marine growth', '#786f58', '#ddd6bb', .94, 0, 'CELLS', .28, 32, .8, note='Shading relief only; no silhouette geometry.'),
    Preset('coralline', 'Pink coralline crust', 'Marine growth', '#724659', '#c59a9b', .87, 0, 'NOISE', .32, 11, .25),
    Preset('sponge', 'Orange sponge patches', 'Marine growth', '#8f3b17', '#d38c38', .92, 0, 'CELLS', .2, 9, .35),
    Preset('calcareous', 'Calcareous deposits', 'Marine growth', '#92977e', '#dedccb', .97, 0, 'CRACKS', .42, 20, .3),
    Preset('silt', 'Settled fine silt', 'Sediment', '#746952', '#b9ac8b', .96, 0, 'NOISE', .65, 4, .12, 'UP'),
    Preset('bilge', 'Muddy bilge', 'Sediment', '#252921', '#645b3c', .62, 0, 'NOISE', .7, 5, .22, 'UP'),
    Preset('sand', 'Pale sand dust', 'Sediment', '#a69878', '#d7c8a4', .99, 0, 'NOISE', .5, 25, .1, 'UP'),
    Preset('grime', 'Dark accumulated grime', 'Sediment', '#19201d', '#4a4b37', .84, 0, 'NOISE', .4, 7, .1),
    Preset('salt', 'Salt residue', 'Sediment', '#bac1ac', '#ece9d5', .98, 0, 'CRACKS', .28, 15, .12),
    Preset('waterline', 'Algae waterline', 'Sediment', '#273e20', '#7c8650', .7, 0, 'NOISE', .9, 8, .2, 'WATERLINE'),
    Preset('oil', 'Black oil seep', 'Sediment', '#101715', '#36372b', .16, 0, 'STREAKS', .22, 5, .05),
    Preset('mineral', 'Mineral runoff', 'Sediment', '#a59b7d', '#d6d3b5', .9, 0, 'STREAKS', .25, 9, .12),
    Preset('teal_paint', 'Faded naval teal', 'Hull coatings', '#31585b', '#73918b', .67, 0, 'NOISE', .98, 5, .08),
    Preset('white_enamel', 'Chalked white enamel', 'Hull coatings', '#acb3a8', '#e0dfc9', .72, 0, 'NOISE', .98, 7, .06),
    Preset('blue_hull', 'Faded blue hull', 'Hull coatings', '#294b65', '#81969d', .74, 0, 'NOISE', .98, 5, .08),
    Preset('antifouling', 'Antifouling red', 'Hull coatings', '#552d29', '#ad6150', .81, 0, 'NOISE', .98, 6, .1),
    Preset('ochre', 'Chipped ochre paint', 'Hull coatings', '#796027', '#c1a25a', .78, 0, 'CRACKS', .8, 10, .14),
    Preset('safety_yellow', 'Weathered safety yellow', 'Hull coatings', '#ac851a', '#e0bf50', .69, 0, 'NOISE', .95, 8, .08),
    Preset('rubber', 'Aged black rubber', 'Hull coatings', '#131a1b', '#414b49', .8, 0, 'CRACKS', .96, 20, .14),
    Preset('aluminum', 'Oxidized aluminum', 'Hull coatings', '#676f6e', '#b5bdb9', .52, .65, 'NOISE', .98, 16, .08),
    Preset('wood', 'Waterlogged wood', 'Interiors', '#342d20', '#7a6d45', .91, 0, 'STREAKS', .98, 12, .3),
    Preset('teak', 'Worn teak deck', 'Interiors', '#5f452b', '#ad8f56', .79, 0, 'STREAKS', .98, 9, .2),
    Preset('carpet', 'Mildewed casino carpet', 'Interiors', '#2b3038', '#647061', .99, 0, 'NOISE', .98, 28, .16),
    Preset('vinyl', 'Stained cream vinyl', 'Interiors', '#79765e', '#c6c3a0', .58, 0, 'NOISE', .98, 5, .07),
    Preset('velvet', 'Faded red upholstery', 'Interiors', '#401e2a', '#884d57', .96, 0, 'NOISE', .98, 16, .1),
    Preset('chrome', 'Casino machine chrome', 'Interiors', '#5f7278', '#bec8c6', .32, .95, 'NOISE', .98, 18, .04),
    Preset('ceramic', 'Old galley tiles', 'Interiors', '#677a75', '#c4c7b1', .62, 0, 'TILES', .98, 8, .2),
    Preset('glass_film', 'Glass mineral frosting', 'Interiors', '#889d98', '#cfdbcd', .9, 0, 'NOISE', .25, 12, .04, note='Opaque surface deposit; not a glass transmission shader.'),
    Preset('hazard', 'Diagonal hazard stripes', 'Markings', '#191e1c', '#dbc044', .64, 0, 'STRIPES', 1, 5, .03),
    Preset('rescue', 'Faded rescue red', 'Markings', '#7d2823', '#ce6b51', .75, 0, 'NOISE', .94, 8, .06),
    Preset('stencil', 'Worn stencil paint', 'Markings', '#b0b7aa', '#ece8d1', .82, 0, 'NOISE', .8, 20, .04, note='Paint through your own stencil or mask; does not generate lettering.'),
    Preset('amber', 'Amber instrument light', 'Markings', '#d48920', '#ffcf5e', .4, 0, 'NONE', 1, 1, 0, emission=2),
    Preset('cyan', 'Cyan instrument light', 'Markings', '#25899c', '#9addd8', .4, 0, 'NONE', 1, 1, 0, emission=2),
    Preset('phosphor', 'Green phosphor light', 'Markings', '#508d37', '#b3e56d', .4, 0, 'NONE', 1, 1, 0, emission=1.5),
    Preset('scraped_metal', 'Brushed exposed metal', 'Markings', '#616b6c', '#bbc1bc', .44, .9, 'STREAKS', .65, 24, .08),
    Preset('soot', 'Engine soot', 'Markings', '#101412', '#3b4039', .98, 0, 'NOISE', .42, 8, .05),
)
BY_ID = {p.id: p for p in PRESETS}
CATEGORIES = tuple(dict.fromkeys(p.category for p in PRESETS))
RECIPES = {
    'WRECK_HULL': ('Wreck hull', ('teal_paint', 'hull_oxide', 'rust_drips', 'biofilm', 'barnacles')),
    'ENGINE_ROOM': ('Flooded engine room', ('pitted_iron', 'hull_oxide', 'soot', 'oil', 'silt')),
    'CASINO': ('Submerged casino interior', ('velvet', 'brown_algae', 'mineral', 'silt')),
    'SLOT_MACHINE': ('Casino slot machine casing', ('chrome', 'rust_drips', 'verdigris', 'biofilm')),
    'GALLEY': ('Galley metal shelving', ('aluminum', 'hull_oxide', 'grime', 'biofilm', 'silt')),
    'DIVE_SIGN': ('Weathered dive signage', ('hazard', 'hull_oxide', 'salt', 'biofilm')),
    'DECK': ('Waterlogged timber deck', ('teak', 'wood', 'olive_turf', 'sand')),
    'PIPEWORK': ('Corroded pipework', ('white_enamel', 'flaking_rust', 'rust_drips', 'calcareous')),
}
BRUSHES = {
    'SOFT_GROWTH': ('Soft growth', 'REVEAL', .22, 110, 'SMOOTH', 8),
    'RUST_DAB': ('Rust dab', 'REVEAL', .65, 40, 'SHARP', 35),
    'SILT_WASH': ('Silt wash', 'REVEAL', .12, 180, 'SMOOTH', 6),
    'HARD_MARK': ('Hard marking', 'REVEAL', 1.0, 25, 'CONSTANT', 5),
    'FINE_WEAR': ('Fine wear', 'REVEAL', .55, 12, 'SHARP', 8),
    'CLEAN_BACK': ('Clean back', 'HIDE', .45, 65, 'SMOOTH', 10),
    'FEATHER': ('Feather edges', 'SOFTEN', .3, 90, 'SMOOTH', 8),
    'BROAD_COAT': ('Broad coat', 'REVEAL', .8, 220, 'SMOOTH', 10),
}


def rgb(hex_color, linear=False):
    value = hex_color.removeprefix('#')
    if len(value) != 6:
        raise ValueError('Expected a six-digit hexadecimal color')
    c = tuple(int(value[i:i+2], 16) / 255 for i in (0, 2, 4))
    if linear:
        c = tuple(v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in c)
    return (*c, 1.0)


def find_presets(query='', category='ALL', favorites=None):
    words = query.casefold().split()
    return [p for p in PRESETS if (category == 'ALL' or p.category == category)
            and (favorites is None or p.id in favorites)
            and all(word in f'{p.name} {p.category} {p.note}'.casefold() for word in words)]
