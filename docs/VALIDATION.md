# Validation record — 1.1.0

## Executed locally

Linux, official Blender 4.5.11 LTS and 5.2.1 LTS. Blender downloads used the official release SHA-256 checksums. No Windows or macOS runtime was used.

- 26 pure-Python unittest methods passed, covering catalog integrity, every image operation and pattern, numerical edge cases, normals, ORM, and package checks.
- `blender_desk_smoke.py` passed **799 assertions in each Blender version**. These are assertions within an integration scenario, not 799 independent unittest cases. Coverage includes all 48 preset graphs, eight recipes, brush settings, placement/coordinate combinations, duplicate-pixel persistence, copy-on-edit behavior, locks, UI RNA references, projection conventions, and save/reopen metadata.
- That integration scenario performs an actual 32px eight-map Cycles bake, reads output pixels, verifies ORM channel ordering, checks that source datablocks/settings are retained, and exercises cleanup after a forced failure. This is a correctness fixture, not a production resolution or performance benchmark.
- Original source, UI, importer, and saved-file reopen scripts passed in both versions. The original scenario retains its 20-layer graph stress test.
- The 1.1 extension was installed in an isolated Blender profile, then exercised from a new Blender process loading only the installed copy. Preset application, mask generation, and a copy-on-edit filter passed in each version.
- Both Blender versions accepted the extension manifest validator.
- Native-window workspace tests ran with Xvfb/OpenGL/Mesa software rendering. They verified the original area's layout was retained and captured actual Blender panels. Vulkan is not validated. First shader compilation can outlast a fixed screenshot delay, so a native-window test is not a rendering-performance certification.

## Important defects found and fixed

Repeated assignment of an image color-space property could discard unsaved pixels. Color-space conversion now avoids redundant assignments and preserves a dirty buffer when changing interpretation. Mask duplication and image export explicitly copy pixels rather than assuming `Image.copy()` retains unsaved paint.

The new workspace now waits for Blender's deferred screen switch before changing editor areas. It performs one area-topology operation per UI loop turn rather than reusing invalid pointers. This prevents modifying the original workspace and avoids the crash found during the first UI test.

Blender 5.x renamed the image-brush and falloff properties. The compatibility path now supports the old and new names; original mask-paint tests verify Soften remains active after changing stroke opacity.

## Reproduce

Build with `python scripts/build_extension.py`, then run `python -m unittest discover -s tests -p 'test_*.py' -v` in an environment with NumPy. The GitHub workflows list the exact commands for source, importer, reopen, desk, manifest, installation, and native-window checks. Use `--python-exit-code 1` so Python failures fail the process.

For a saved-file reopen test, pass the `.blend` to Blender before the Python script. `blender_reopen_smoke.py` accepts `--source-root`; it does not accept an `--artifact` argument. GUI tests must check `gui-report.txt` and the absence of `gui-failure.txt` in addition to the process exit status.

## What these tests do not establish

They do not establish feature parity with Ucupaint, photo-realistic material quality, entire-ship performance, production 4K bake time, Vulkan compatibility, or correct behavior with every third-party shader/geometry modifier. The workflows preserve the original material-copy model rather than translating arbitrary shaders into editable layers. A small tested demo is supplied for inspection; use a versioned copy of your real asset for the first production trial.
