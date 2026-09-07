"""Deterministic NumPy mask/image operations; no Blender or network dependency."""
import math
import struct
import zlib
from pathlib import Path

import numpy as np

PATTERNS = ('NOISE', 'STREAKS', 'CELLS', 'CRACKS', 'STRIPES', 'TILES', 'NONE')
OPERATIONS = ('INVERT', 'LEVELS', 'BLUR', 'GROW', 'SHRINK', 'EDGE', 'NORMALIZE',
              'FLIP_X', 'FLIP_Y', 'OFFSET', 'GRAYSCALE', 'THRESHOLD')
MAX_PIXELS = 4096 * 4096


def checked(a):
    a = np.asarray(a, dtype=np.float32)
    if a.ndim not in (2, 3) or min(a.shape[:2]) < 1 or a.shape[0] * a.shape[1] > MAX_PIXELS:
        raise ValueError('Image must be nonempty and no larger than 16 megapixels')
    if not np.isfinite(a).all():
        raise ValueError('Image contains non-finite pixels')
    return a


def levels(a, black=0.0, white=1.0, gamma=1.0):
    if not (math.isfinite(black) and math.isfinite(white) and math.isfinite(gamma)):
        raise ValueError('Levels must be finite')
    if white <= black or gamma <= 0:
        raise ValueError('White must exceed black, and gamma must be positive')
    return np.clip((a - black) / (white - black), 0, 1) ** (1.0 / gamma)


def _noise(width, height, nx, ny, seed):
    rng = np.random.default_rng(int(seed) % (2**32))
    lattice = rng.random((ny, nx), dtype=np.float32)
    x = (np.arange(width, dtype=np.float32) + .5) * (nx / width)
    y = (np.arange(height, dtype=np.float32) + .5) * (ny / height)
    xi, yi = x.astype(int), y.astype(int)
    xf, yf = x - xi, y - yi
    xf, yf = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    a, b = lattice[yi[:, None] % ny, xi % nx], lattice[yi[:, None] % ny, (xi + 1) % nx]
    c, d = lattice[(yi[:, None] + 1) % ny, xi % nx], lattice[(yi[:, None] + 1) % ny, (xi + 1) % nx]
    return ((a * (1 - xf) + b * xf) * (1 - yf[:, None]) +
            (c * (1 - xf) + d * xf) * yf[:, None]).astype(np.float32)


def pattern(width, height, kind='NOISE', seed=1, scale=8, coverage=.5, softness=.15):
    """Periodic 2D art masks. They approximate, but do not bake, shader generators."""
    width, height = int(width), int(height)
    if min(width, height) < 1 or width * height > MAX_PIXELS:
        raise ValueError('Generator is limited to 16 megapixels')
    if kind not in PATTERNS:
        raise ValueError(f'Unknown pattern: {kind}')
    if not all(math.isfinite(v) for v in (scale, coverage, softness)):
        raise ValueError('Generator parameters must be finite')
    n = min(128, max(1, round(scale)))
    x = (np.arange(width, dtype=np.float32) + .5) / width
    y = (np.arange(height, dtype=np.float32) + .5) / height
    if kind == 'NONE':
        field = np.ones((height, width), dtype=np.float32)
    elif kind == 'STRIPES':
        field = .5 + .5 * np.sin(2 * np.pi * n * (x[None, :] + y[:, None]))
    elif kind == 'TILES':
        u, v = (x * n) % 1, (y * n) % 1
        field = np.minimum(np.minimum(u, 1 - u)[None, :], np.minimum(v, 1 - v)[:, None])
        field = np.clip(field * 12, 0, 1)
    elif kind in {'CELLS', 'CRACKS'}:
        # Periodic jittered cellular field; row chunks bound temporary memory.
        rng = np.random.default_rng(int(seed) % (2**32))
        offsets = rng.random((n, n, 2), dtype=np.float32)
        field = np.empty((height, width), dtype=np.float32)
        gx = x * n
        ix = gx.astype(int)
        for start in range(0, height, 128):
            gy = y[start:start+128, None] * n
            iy = gy.astype(int)
            first = np.full((len(gy), width), np.inf, dtype=np.float32)
            second = first.copy()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    jitter = offsets[(iy + dy) % n, (ix[None, :] + dx) % n]
                    d = (ix + dx + jitter[..., 0] - gx) ** 2 + (iy + dy + jitter[..., 1] - gy) ** 2
                    second = np.minimum(second, np.maximum(first, d))
                    first = np.minimum(first, d)
            first, second = np.sqrt(first), np.sqrt(second)
            field[start:start+len(gy)] = np.clip(1 - first if kind == 'CELLS' else 1 - (second-first)*3, 0, 1)
    else:
        field = np.zeros((height, width), dtype=np.float32)
        for octave, amplitude in enumerate((.57, .28, .15)):
            nx = min(256, n * 2**octave)
            ny = max(1, round(nx / 10)) if kind == 'STREAKS' else nx
            field += amplitude * _noise(width, height, nx, ny, seed + octave * 997)
    if kind == 'NONE' or coverage >= 1:
        return np.ones_like(field) if coverage >= 1 else np.full_like(field, np.clip(coverage, 0, 1))
    if coverage <= 0:
        return np.zeros_like(field)
    width_transition = max(.001, softness)
    a = np.clip((field - (1 - coverage - width_transition / 2)) / width_transition, 0, 1)
    return (a * a * (3 - 2 * a)).astype(np.float32)


def _box(a, radius, wrap=False):
    result = a.copy()
    radius = max(1, min(64, int(radius)))
    for axis in (0, 1):
        padding = [(0, 0)] * result.ndim
        padding[axis] = (radius, radius)
        padded = np.pad(result, padding, mode='wrap' if wrap else 'edge')
        cs = np.cumsum(padded, axis=axis, dtype=np.float64)
        pad_zero = [(0, 0)] * result.ndim
        pad_zero[axis] = (1, 0)
        cs = np.pad(cs, pad_zero, mode='constant')
        lo, hi = [slice(None)] * result.ndim, [slice(None)] * result.ndim
        lo[axis], hi[axis] = slice(0, -(radius*2+1)), slice(radius*2+1, None)
        result = ((cs[tuple(hi)] - cs[tuple(lo)]) / (radius*2+1)).astype(np.float32)
    return result


def _morph(a, radius, grow, wrap=False):
    result = a.copy()
    radius = max(1, min(32, int(radius)))
    compare = np.maximum if grow else np.minimum
    for axis in (0, 1):
        pad = [(0, 0)] * a.ndim
        pad[axis] = (radius, radius)
        padded = np.pad(result, pad, mode='wrap' if wrap else 'edge')
        size = result.shape[axis]
        output = None
        for offset in range(radius * 2 + 1):
            sl = [slice(None)] * a.ndim
            sl[axis] = slice(offset, offset + size)
            sample = padded[tuple(sl)]
            output = sample.copy() if output is None else compare(output, sample)
        result = output
    return result


def edit(a, operation, black=0., white=1., gamma=1., radius=2, wrap=False):
    """Transform grayscale or RGBA data without mutating input or RGBA alpha."""
    a = checked(a)
    if operation not in OPERATIONS:
        raise ValueError(f'Unknown operation: {operation}')
    if operation in ('FLIP_X', 'FLIP_Y', 'OFFSET'):
        if operation == 'FLIP_X':
            return a[:, ::-1].copy()
        if operation == 'FLIP_Y':
            return a[::-1].copy()
        return np.roll(a, (a.shape[0]//2, a.shape[1]//2), (0, 1)).copy()
    out = a.copy()
    color = a[..., :3] if a.ndim == 3 else a
    if operation == 'INVERT':
        value = 1 - color
    elif operation == 'LEVELS':
        value = levels(color, black, white, gamma)
    elif operation == 'BLUR':
        value = _box(color, radius, wrap)
    elif operation in ('GROW', 'SHRINK'):
        value = _morph(color, radius, operation == 'GROW', wrap)
    elif operation == 'EDGE':
        value = _morph(color, radius, True, wrap) - _morph(color, radius, False, wrap)
    elif operation == 'NORMALIZE':
        low, high = float(color.min()), float(color.max())
        value = color.copy() if high - low < 1e-8 else (color-low)/(high-low)
    elif operation == 'THRESHOLD':
        value = (color >= black).astype(np.float32)
    else:
        value = color if a.ndim == 2 else np.repeat(np.sum(color * (.2126, .7152, .0722), axis=-1)[..., None], 3, axis=-1)
    if out.ndim == 3:
        out[..., :3] = value
    else:
        out[:] = value
    return np.clip(out, 0, 1)


def height_to_normal(height, strength=2., directx=False, wrap=True):
    height = checked(height)
    if height.ndim != 2 or not math.isfinite(strength) or strength < 0:
        raise ValueError('Expected grayscale height and nonnegative finite strength')
    if wrap:
        dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * .5
        dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * .5
    else:
        pad = np.pad(height, 1, mode='edge')
        dx, dy = (pad[1:-1, 2:] - pad[1:-1, :-2]) * .5, (pad[2:, 1:-1] - pad[:-2, 1:-1]) * .5
    n = np.stack((-dx * strength, dy * strength if directx else -dy * strength, np.ones_like(height)), -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return np.concatenate((n*.5+.5, np.ones((*height.shape, 1), dtype=np.float32)), -1).astype(np.float32)


def pack_orm(ao, roughness, metallic):
    arrays = [checked(a) for a in (ao, roughness, metallic)]
    if any(a.ndim != 2 or a.shape != arrays[0].shape for a in arrays):
        raise ValueError('ORM inputs must be equally sized grayscale arrays')
    return np.stack((*arrays, np.ones_like(arrays[0])), -1).clip(0, 1)


def write_png(path, pixels):
    """Small dependency-free RGBA8 writer for temporary UI swatches."""
    a = np.clip(np.asarray(pixels) * 255, 0, 255).astype(np.uint8)
    if a.ndim != 3 or a.shape[2] != 4:
        raise ValueError('PNG requires RGBA pixels')
    h, w, _ = a.shape
    def chunk(tag, data):
        return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag+data)&0xffffffff)
    raw = b''.join(b'\x00' + row.tobytes() for row in a[::-1])
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', w,h,8,6,0,0,0)) +
                           chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
