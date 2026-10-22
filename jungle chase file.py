import math, os, sys, random

FPS = 24
SECONDS = 28
FRAMES = FPS * SECONDS      # frames 1..672
V = 22.0                    # prey top speed in m/s (the story's "speed")
G0 = 10.0                   # starting gap in metres
CL = 0.09                   # how much faster the jaguar is while closing in
DT = 1.0 / FPS

def ss(a, b, t):
    u = min(1.0, max(0.0, (t - a) / (b - a)))
    return u * u * (3 - 2 * u)
def lerp(a, b, t): return a + (b - a) * t
def lerp3(a, b, t): return tuple(lerp(a[i], b[i], t) for i in range(3))

# ---- Story: speed curves (edit these to retime the whole film) ----------------
def prey_speed(t):
    return V * ss(3, 6.5, t) * (1 - ss(22, 27, t))
def jag_speed(t):
    closing = 1 + CL * ss(5, 9, t) * (1 - ss(11, 19, t))
    return V * ss(3.6, 6.8, t) * closing * (1 - ss(21, 26.5, t))

def simulate():
    pp, pj, sp, sj = [], [], [], []
    p, j = 0.0, -G0
    for i in range(FRAMES + 1):
        t = i * DT
        pp.append(p); pj.append(j)
        sp.append(prey_speed(t)); sj.append(jag_speed(t))
        p += sp[-1] * DT; j += sj[-1] * DT
    return pp, pj, sp, sj

LOG_TIMES = [9.5, 12.5, 15.5, 18.5, 21.0]
def jump(x, logs, h):
    return max([h * max(0.0, 1 - ((x - lx) / 2.6) ** 2) for lx in logs] + [0.0])

def camera_state(t, px, jx, sf):
    mid = (px + jx) / 2
    E = (mid - 4, -15.0, 2.8)
    A = (mid + 0.5, -9.5 + 0.8 * math.sin(t * 0.6), 1.6)
    B = (px + 7.5, -3.8, 1.0)
    C = (mid - 3, -16.0, 5.5)
    w1 = ss(3, 5.5, t)
    wB = ss(12, 13.5, t) * (1 - ss(16.5, 18, t))
    wC = ss(22, 26, t)
    pos = lerp3(lerp3(lerp3(E, A, w1), B, wB), C, wC)
    lens = lerp(26, 28 - 6 * sf, w1)
    lens = lerp(lens, 22, wB)
    lens = lerp(lens, 30, wC)
    target = (mid + 1.2, 0.0, 0.9)
    return pos, target, lens

# ===== BLENDER PART =============================================================
import bpy, bmesh

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.getcwd()
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, FRAMES
random.seed(7)

PP, PJ, SP, SJ = simulate()
LOGS = [PP[int(t * FPS)] for t in LOG_TIMES]
END_X = PP[-1]

# ---- materials ----------------------------------------------------------------
def principled(name, rgb, rough=0.75):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    return m

def emission(name, rgb, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*rgb, 1); e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(e.outputs['Emission'], o.inputs['Surface'])
    return m

def spotted(name, base, spot, scale, thresh):
    m = principled(name, base, 0.6); nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    v = nt.nodes.new('ShaderNodeTexVoronoi'); v.inputs['Scale'].default_value = scale
    r = nt.nodes.new('ShaderNodeValToRGB'); r.color_ramp.interpolation = 'CONSTANT'
    r.color_ramp.elements[0].position = 0.0; r.color_ramp.elements[0].color = (*spot, 1)
    r.color_ramp.elements[1].position = thresh; r.color_ramp.elements[1].color = (*base, 1)
    nt.links.new(tc.outputs['Object'], v.inputs['Vector'])
    nt.links.new(v.outputs['Distance'], r.inputs['Fac'])
    nt.links.new(r.outputs['Color'], b.inputs['Base Color'])
    return m

def ground_mat():
    m = principled('ground', (0.1, 0.3, 0.08), 0.95); nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    g = nt.nodes.new('ShaderNodeNewGeometry')
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 0.4
    r = nt.nodes.new('ShaderNodeValToRGB')
    r.color_ramp.elements[0].color = (0.05, 0.2, 0.05, 1); r.color_ramp.elements[1].color = (0.2, 0.42, 0.1, 1)
    nt.links.new(g.outputs['Position'], n.inputs['Vector'])
    nt.links.new(n.outputs['Fac'], r.inputs['Fac'])
    nt.links.new(r.outputs['Color'], b.inputs['Base Color'])
    return m

M = dict(
    jag=spotted('jaguar', (0.85, 0.5, 0.12), (0.12, 0.05, 0.02), 7.0, 0.22),
    deer=spotted('deer', (0.5, 0.3, 0.14), (0.95, 0.9, 0.8), 9.0, 0.14),
    dark=principled('dark', (0.12, 0.07, 0.04)),
    cream=principled('cream', (0.95, 0.85, 0.65)),
    eye=emission('eye', (1.0, 0.85, 0.2), 4.0),
    horn=principled('horn', (0.8, 0.72, 0.55)),
    wood=principled('wood', (0.3, 0.17, 0.08), 0.9),
    trunk=principled('trunk', (0.22, 0.14, 0.08), 0.9),
    leaf=[principled('leaf%d' % i, c, 0.8) for i, c in enumerate(
        [(0.04, 0.28, 0.1), (0.07, 0.36, 0.12), (0.02, 0.2, 0.09)])],
    tuft=principled('tuft', (0.25, 0.55, 0.12), 0.9),
    trail=principled('trail', (0.32, 0.2, 0.1), 1.0),
    streak=emission('streak', (1.0, 0.95, 0.8), 2.5),
    text=emission('text', (1.0, 0.93, 0.7), 3.0),
)

# ---- helpers ------------------------------------------------------------------
def prim(kind, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), mat=None, parent=None):
    if kind == 'sphere': bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1)
    elif kind == 'cyl': bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=1, depth=2)
    elif kind == 'cone': bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=1, depth=2)
    else: bpy.ops.mesh.primitive_cube_add(size=2)
    o = bpy.context.view_layer.objects.active
    o.scale = scale; o.rotation_euler = rot
    if mat: o.data.materials.append(mat)
    if parent: o.parent = parent
    o.location = loc
    return o

def empty(name, loc=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, None)
    sc.collection.objects.link(o)
    if parent: o.parent = parent
    o.location = loc
    return o

def join(parts, name):
    """Merge objects into one mesh with bmesh (bpy.ops.object.join fails in script context)."""
    bm = bmesh.new(); mats = []
    for p in parts:
        me = p.data
        v0, f0 = len(bm.verts), len(bm.faces)
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
        mw = p.matrix_basis.copy()
        for v in bm.verts[v0:]:
            v.co = mw @ v.co
        pm = list(me.materials)
        for m in pm:
            if m not in mats: mats.append(m)
        for f in bm.faces[f0:]:
            f.material_index = mats.index(pm[f.material_index]) if pm else 0
    me2 = bpy.data.meshes.new(name); bm.to_mesh(me2); bm.free()
    for m in mats: me2.materials.append(m)
    for p in parts:
        me = p.data
        bpy.data.objects.remove(p); bpy.data.meshes.remove(me)
    o = bpy.data.objects.new(name, me2); sc.collection.objects.link(o)
    return o

def drive(obj, path, index, expr, **vars_):
    d = obj.driver_add(path, index).driver
    for name, (idobj, prop) in vars_.items():
        v = d.variables.new(); v.name = name; v.type = 'SINGLE_PROP'
        v.targets[0].id = idobj; v.targets[0].data_path = '["%s"]' % prop
    d.expression = expr

# ---- animals ------------------------------------------------------------------
def build_animal(kind):
    root = empty(kind + '_root')
    root['phase'] = 0.0; root['amp'] = 0.0
    torso = empty('torso', parent=root)
    drive(torso, 'location', 2, 'abs(sin(ph))*0.09*amp', ph=(root, 'phase'), amp=(root, 'amp'))
    cat = kind == 'jaguar'
    body_m = M['jag'] if cat else M['deer']
    hip_z = 0.8 if cat else 1.1
    if cat:
        prim('sphere', (0, 0, 0.85), (0.95, 0.36, 0.4), mat=body_m, parent=torso)
        prim('sphere', (-0.55, 0, 0.9), (0.5, 0.38, 0.42), mat=body_m, parent=torso)
        head = empty('head', (0.95, 0, 1.05), torso)
        prim('sphere', (0.25, 0, 0), (0.32, 0.26, 0.26), mat=body_m, parent=head)
        prim('sphere', (0.52, 0, -0.06), (0.18, 0.15, 0.12), mat=M['cream'], parent=head)
        for s in (-1, 1):
            prim('cone', (0.12, 0.15 * s, 0.26), (0.07, 0.07, 0.1), mat=M['dark'], parent=head)
            prim('sphere', (0.4, 0.14 * s, 0.07), (0.05, 0.04, 0.04), mat=M['eye'], parent=head)
        prim('cyl', (-1.45, 0, 1.05), (0.07, 0.07, 0.55), rot=(0, -1.25, 0), mat=body_m, parent=torso)
        legs = [(0.6, 0.2, 0), (0.6, -0.2, 0.5), (-0.6, 0.2, 2.6), (-0.6, -0.2, 3.1)]
        leg_r, leg_h = 0.1, 0.4
    else:
        prim('sphere', (0, 0, 1.2), (0.85, 0.3, 0.34), mat=body_m, parent=torso)
        prim('sphere', (-0.5, 0, 1.22), (0.4, 0.3, 0.34), mat=body_m, parent=torso)
        prim('sphere', (-0.95, 0, 1.3), (0.1, 0.08, 0.1), mat=M['cream'], parent=torso)
        head = empty('head', (0.7, 0, 1.3), torso)
        prim('cyl', (0.17, 0, 0.35), (0.11, 0.11, 0.45), rot=(0, 0.4, 0), mat=body_m, parent=head)
        prim('sphere', (0.5, 0, 0.78), (0.3, 0.13, 0.13), rot=(0, 0.35, 0), mat=body_m, parent=head)
        prim('sphere', (0.78, 0, 0.7), (0.05, 0.06, 0.05), mat=M['dark'], parent=head)
        for s in (-1, 1):
            prim('sphere', (0.5, 0.11 * s, 0.84), (0.05, 0.05, 0.05), mat=M['dark'], parent=head)
            prim('cone', (0.32, 0.12 * s, 1.0), (0.03, 0.03, 0.4), rot=(0.25 * s, -0.2, 0), mat=M['horn'], parent=head)
            prim('cone', (0.36, 0.2 * s, 1.18), (0.025, 0.025, 0.2), rot=(0.6 * s, 0.4, 0), mat=M['horn'], parent=head)
        legs = [(0.55, 0.15, 0), (0.55, -0.15, 0.5), (-0.55, 0.15, 2.6), (-0.55, -0.15, 3.1)]
        leg_r, leg_h = 0.05, 0.55
    for i, (lx, ly, off) in enumerate(legs):
        piv = empty('leg%d' % i, (lx, ly, hip_z), root)
        drive(piv, 'rotation_euler', 1, 'sin(ph+%.2f)*amp*0.9' % off, ph=(root, 'phase'), amp=(root, 'amp'))
        prim('cyl', (0, 0, -leg_h), (leg_r, leg_r, leg_h), mat=M['dark'], parent=piv)
    return root, head

# ---- scene dressing -----------------------------------------------------------
def build_ground():
    L = END_X + 220
    bpy.ops.mesh.primitive_plane_add(size=2)
    g = bpy.context.view_layer.objects.active; g.name = 'Ground'
    g.scale = (L / 2, 70, 1); g.location = (L / 2 - 90, 0, 0)
    g.data.materials.append(ground_mat())
    bpy.ops.mesh.primitive_plane_add(size=2)
    t = bpy.context.view_layer.objects.active; t.name = 'Trail'
    t.scale = (L / 2, 1.8, 1); t.location = (L / 2 - 90, 0, 0.01)
    t.data.materials.append(M['trail'])

def tree_variant(i):
    h = [7.0, 9.0, 6.0][i]
    parts = [prim('cyl', (0, 0, h / 2), (0.28, 0.28, h / 2), mat=M['trunk'])]
    if i < 2:
        for k, (dx, dy, dz, r) in enumerate([(0, 0, h + 0.5, 2.0), (1.2, 0.6, h - 0.3, 1.5), (-1.1, -0.5, h - 0.5, 1.6)]):
            parts.append(prim('sphere', (dx, dy, dz), (r, r, r * 0.8), mat=M['leaf'][i]))
    else:
        for k in range(6):
            a = k * math.pi / 3
            parts.append(prim('sphere', (math.cos(a) * 1.2, math.sin(a) * 1.2, h), (1.8, 0.3, 0.1),
                              rot=(0, 0.35, a), mat=M['leaf'][1]))
    return join(parts, 'treeT%d' % i)

def scatter():
    trees = [tree_variant(i) for i in range(3)]
    bush = join([prim('sphere', (0, 0, 0.5), (1.1, 1.1, 0.7), mat=M['leaf'][2]),
                 prim('sphere', (0.8, 0.4, 0.4), (0.8, 0.8, 0.55), mat=M['leaf'][0])], 'bushT')
    tuft = join([prim('cone', (0, 0, 0.3), (0.07, 0.07, 0.3), rot=(0.3 * k - 0.3, 0.25 * k - 0.2, 0), mat=M['tuft'])
                 for k in range(3)], 'tuftT')
    def put(src, x, y, s):
        o = bpy.data.objects.new(src.name[:-1], src.data)
        o.location = (x, y, 0); o.rotation_euler[2] = random.uniform(0, 6.28); o.scale = (s, s, s)
        sc.collection.objects.link(o)
    x = -60.0
    while x < END_X + 80:
        put(random.choice(trees), x + random.uniform(-1, 1), -random.uniform(20, 55), random.uniform(0.9, 1.7))
        put(random.choice(trees), x + random.uniform(-1, 1), random.uniform(6, 45), random.uniform(0.9, 1.7))
        x += 3.5
    x = -60.0
    while x < END_X + 80:
        put(bush, x + random.uniform(-2, 2), random.uniform(2.5, 6), random.uniform(0.8, 1.5))
        x += 5.0
    x = -60.0
    while x < END_X + 80:
        put(tuft, x + random.uniform(-1, 1), -random.uniform(2.6, 8), random.uniform(0.8, 1.6))
        put(tuft, x + random.uniform(-1, 1), random.uniform(2.6, 8), random.uniform(0.8, 1.6))
        x += 1.6
    for t in trees + [bush, tuft]:
        bpy.data.objects.remove(t)

def build_logs():
    for lx in LOGS:
        prim('cyl', (lx, 0, 0.38), (0.38, 0.38, 1.0), rot=(math.pi / 2, 0, 0), mat=M['wood'])

def build_lights_world():
    sun = bpy.data.lights.new('Sun', 'SUN'); sun.angle = 0.05
    so = bpy.data.objects.new('Sun', sun); sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(60), 0, math.radians(-65))
    for f, col, en in ((1, (1.0, 0.55, 0.3), 3.0), (8 * FPS, (1.0, 0.92, 0.75), 5.0), (FRAMES, (1.0, 0.7, 0.4), 4.0)):
        sun.color = col; sun.energy = en
        sun.keyframe_insert('color', frame=f); sun.keyframe_insert('energy', frame=f)
    w = bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Strength'].default_value = 1.2
    try:
        for f, c in ((1, (0.9, 0.45, 0.25)), (8 * FPS, (0.55, 0.75, 0.8)), (24 * FPS, (0.55, 0.75, 0.8)), (FRAMES, (0.95, 0.6, 0.35))):
            bg.inputs['Color'].default_value = (*c, 1)
            bg.inputs['Color'].keyframe_insert('default_value', frame=f)
    except Exception as e:
        print('World colour animation skipped:', e)

def make_text(cam, body, size, pos, t0, t1):
    c = bpy.data.curves.new(body, 'FONT'); c.body = body; c.size = size
    c.align_x = 'CENTER'; c.align_y = 'CENTER'; c.extrude = 0.03
    o = bpy.data.objects.new(body, c); sc.collection.objects.link(o)
    o.parent = cam; o.location = pos; o.data.materials.append(M['text'])
    keys = [(1, 0.0001), (int(t0 * FPS), 0.0001), (int(t0 * FPS) + 10, 1.0)]
    if t1 < SECONDS:
        keys += [(int(t1 * FPS) - 6, 1.0), (int(t1 * FPS), 0.0001)]
    for f, s in keys:
        o.scale = (s, s, s); o.keyframe_insert('scale', frame=f)

def build_camera():
    rig = empty('CamRig'); rig['shake'] = 0.0
    cd = bpy.data.cameras.new('Cam'); cd.clip_end = 3000
    cam = bpy.data.objects.new('Cam', cd); sc.collection.objects.link(cam); cam.parent = rig
    tgt = empty('CamTarget')
    con = cam.constraints.new('TRACK_TO'); con.target = tgt
    con.track_axis = 'TRACK_NEGATIVE_Z'; con.up_axis = 'UP_Y'
    sc.camera = cam
    drive(cam, 'location', 1, '(sin(frame*2.3)*0.035+sin(frame*5.1)*0.02)*sh', sh=(rig, 'shake'))
    drive(cam, 'location', 2, '(sin(frame*1.9+1)*0.035+sin(frame*4.3)*0.02)*sh', sh=(rig, 'shake'))
    # speed lines, parented to the camera
    sk = empty('SpeedLines', parent=cam)
    for i in range(30):
        o = prim('cube', (0, random.uniform(-3.2, 3.2), -random.uniform(6, 9)), (1.6, 0.01, 0.01), mat=M['streak'], parent=sk)
        drive(o, 'location', 0, '7-fmod(frame*%.2f+%.1f,14)' % (random.uniform(0.9, 1.5), random.uniform(0, 14)))
    make_text(cam, 'SPEED', 1.9, (0, 0.6, -8), 0.2, 2.8)
    make_text(cam, 'a jungle chase', 0.6, (0, -1.0, -8), 0.9, 2.8)
    make_text(cam, 'SPEED', 1.9, (0, 1.0, -8), 24.6, 99)
    make_text(cam, 'IS SURVIVAL', 1.1, (0, -0.9, -8), 25.4, 99)
    for i in range(FRAMES + 1):
        f, t = i + 1, i / FPS
        sf = SP[i] / V
        pos, target, lens = camera_state(t, PP[i], PJ[i], sf)
        rig.location = pos; rig.keyframe_insert('location', frame=f)
        tgt.location = target; tgt.keyframe_insert('location', frame=f)
        cd.lens = lens; cd.keyframe_insert('lens', frame=f)
        rig['shake'] = sf; rig.keyframe_insert('["shake"]', frame=f)
        s = max(0.0001, min(1.0, sf * sf * 1.5))
        sk.scale = (s, s, s); sk.keyframe_insert('scale', frame=f)

def animate(root, head, xs, speeds, mult, head_fn, crouch_fn, jump_h):
    ph = 0.0
    for i in range(FRAMES + 1):
        f, t = i + 1, i / FPS
        ph += speeds[i] * DT * mult
        z = jump(xs[i], LOGS, jump_h) - 0.3 * crouch_fn(t)
        root.location = (xs[i], 0, z); root.keyframe_insert('location', frame=f)
        root['phase'] = ph; root.keyframe_insert('["phase"]', frame=f)
        root['amp'] = min(1.0, speeds[i] / (V * 0.8)) * 0.85
        root.keyframe_insert('["amp"]', frame=f)
        head.rotation_euler[1] = head_fn(t); head.keyframe_insert('rotation_euler', index=1, frame=f)

def settings():
    r = sc.render
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try: r.engine = eng; break
        except TypeError: pass
    try: sc.eevee.taa_render_samples = 48
    except Exception: pass
    for fn in (lambda: setattr(r, 'use_motion_blur', True), lambda: setattr(sc.eevee, 'use_motion_blur', True)):
        try: fn()
        except Exception: pass
    r.resolution_x, r.resolution_y, r.fps = 1920, 1080, FPS
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'; r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'HIGH'; r.ffmpeg.audio_codec = 'NONE'
    r.filepath = os.path.join(HERE, 'render', 'jungle_chase_')
    if '--farm' in ARGS:   # PNG frames: safest for a render farm, stitch to MP4 afterwards
        r.image_settings.file_format = 'PNG'
        r.filepath = os.path.join(HERE, 'render', 'frame_')

# ---- build --------------------------------------------------------------------
build_ground(); scatter(); build_logs(); build_lights_world()
deer, deer_head = build_animal('deer')
jag, jag_head = build_animal('jaguar')
animate(deer, deer_head, PP, SP, 0.55,
        lambda t: lerp(0.95 + 0.05 * math.sin(t * 4), -0.12, ss(2.9, 3.6, t)), lambda t: 0.0, 1.4)
animate(jag, jag_head, PJ, SJ, 0.6,
        lambda t: lerp(0.35, -0.05, ss(4, 6, t)), lambda t: 1 - ss(4, 6.2, t), 1.5)
build_camera()
settings()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'jungle_chase.blend'))
print('Saved jungle_chase.blend  (%d frames, %.0f s)' % (FRAMES, SECONDS))

if '--stills' in ARGS:
    os.makedirs(os.path.join(HERE, 'wip'), exist_ok=True)
    sc.render.image_settings.file_format = 'PNG'
    for f in (1, 60, 150, 260, 330, 440, 560, 672):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(HERE, 'wip', 'frame_%04d.png' % f)
        bpy.ops.render.render(write_still=True)
    settings()
if '--render' in ARGS:
    bpy.ops.render.render(animation=True)
