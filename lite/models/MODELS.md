# Models (Member 2)

Rules: .obj + .mtl from Blender, <= 1024 triangles, normals outside, one Base Color
per material, front faces Blender -Y. Check with `python pc/check_models.py`.

| File | Source / license | Triangles | Materials | check_models | Notes |
|---|---|---|---|---|---|
| torus.obj | generated test model (not from Blender) | 576 | 2 | OK | loader test: quads + materials |
| teapot.obj | | | | | |
| bunny.obj | | | | | |
| room.obj | | | | | |
| own.obj | | | | | |
| teapot_lod100.obj | decimated teapot | 100 | | | E8 |
| teapot_lod250.obj | decimated teapot | 250 | | | E8 |
| teapot_lod500.obj | decimated teapot | 500 | | | E8 |
| teapot_lod1000.obj | decimated teapot | 1000 | | | E8 |
