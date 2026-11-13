"""HOLOGRID - procedural sci-fi HUD generator, 11 themes, 60 fps.

Keys: T / Shift+T next/prev theme | 1-9,0,- jump to theme | F11 fullscreen/window
      M next monitor | F2 setup | SPACE pause | S screenshot | ESC quit
"""
import json
import math
import os
import random
import sys
import time
from collections import deque

os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")
os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "linear")
import pygame  # noqa: E402

W, H = 1600, 1000
TAU = math.tau
PI = math.pi
C = (800, 440)
BOX = pygame.Rect(470, 100, 660, 670)
CS = [(math.cos(i / 360 * TAU - PI / 2), math.sin(i / 360 * TAU - PI / 2)) for i in range(360)]
BOTTOM = [(20 + i * 314, 792, 302, 196) for i in range(5)]
SCOPES = [(20, 240, 170, 110), (20, 360, 170, 110)]
CALLS = [((215, 100, 250, 74), -2.3), ((1135, 100, 250, 74), -0.75),
         ((190, 520, 250, 74), 2.9), ((1160, 520, 250, 74), 0.35)]

BARS = ("uplink", "mesh", "lattice", "vault", "relay", "decoy")
DEF_TELE = ["cam   xz {d:+.1f}° el {a:.1f}°", "ring  r {a:.2f}  n {b}", "cells {b} / 1089",
            "hops  {c} threads", "head  0x{b:04X}", "phase verify", "frame {f}", "heap  0x{h:08X}"]
DEF_LOGS = ["handshake ok", "route recalc", "checksum pass", "heartbeat", "sync nominal", "latency ok"]


# ---- resolution-independent drawing: all coordinates are logical (1600x1000 design space) ----
S = 1.0       # logical -> pixel scale
OX = 0.0      # logical offset (centres the design space on the canvas)
OY = 0.0
_pd = pygame.draw


class _Draw:
    @staticmethod
    def line(surf, col, a, b, w=1):
        _pd.line(surf, col, ((a[0] + OX) * S, (a[1] + OY) * S), ((b[0] + OX) * S, (b[1] + OY) * S), max(1, int(w * S + 0.5)))

    @staticmethod
    def lines(surf, col, closed, pts, w=1):
        _pd.lines(surf, col, closed, [((x + OX) * S, (y + OY) * S) for x, y in pts], max(1, int(w * S + 0.5)))

    @staticmethod
    def circle(surf, col, c, r, w=0):
        _pd.circle(surf, col, ((c[0] + OX) * S, (c[1] + OY) * S), max(1, int(r * S + 0.5)), max(1, int(w * S + 0.5)) if w else 0)

    @staticmethod
    def rect(surf, col, rect, w=0, border_radius=0):
        x, y, ww, hh = rect
        _pd.rect(surf, col, (int((x + OX) * S + 0.5), int((y + OY) * S + 0.5), max(1, int(ww * S + 0.5)), max(1, int(hh * S + 0.5))),
                 max(1, int(w * S + 0.5)) if w else 0, border_radius=int(border_radius * S))

    @staticmethod
    def ellipse(surf, col, rect, w=0):
        x, y, ww, hh = rect
        _pd.ellipse(surf, col, (int((x + OX) * S + 0.5), int((y + OY) * S + 0.5), max(2, int(ww * S + 0.5)), max(2, int(hh * S + 0.5))),
                    max(1, int(w * S + 0.5)) if w else 0)

    @staticmethod
    def polygon(surf, col, pts, w=0):
        _pd.polygon(surf, col, [((x + OX) * S, (y + OY) * S) for x, y in pts], max(1, int(w * S + 0.5)) if w else 0)


D = _Draw


def L(a, b, t):
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def pol(c, r, a):
    return (c[0] + math.cos(a) * r, c[1] + math.sin(a) * r)


def pal(bg, fg, acc, acc2, acc3, dim, panel, core=(0, 0, 0)):
    return dict(bg=bg, fg=fg, acc=acc, acc2=acc2, acc3=acc3, dim=dim, panel=panel, core=core)


THEMES = [
    dict(name="NEON", title="HOLOGRID / AETHER-7", sub="quantum lattice · adaptive mode · procedural telemetry",
         pal=pal((4, 8, 15), (200, 238, 255), (0, 229, 255), (255, 176, 32), (255, 64, 96), (34, 62, 82), (7, 15, 25)),
         center="radar", ring="full", glow=True,
         nodes=[("p1", "FAILOVER"), ("p2", "IDEMPOTENCY"), ("p3", "RETRY BUDGET"), ("p4", "CIRCUIT BREAKER"),
                ("p5", "WEBHOOK REPLAY"), ("p6", "OUTAGE BANNER")], pill="VERIFYING {id}",
         stats=[("THROUGHPUT", "{:.2f} TB/s", 1.0, 1.8, 0.0), ("MODE", "ADAPTIVE", None, 0, 0),
                ("NODES", "{:.0f}/6", 4.6, 6.4, 1.0), ("UPTIME", "clock", None, 0, 0)],
         tele=DEF_TELE,
         callouts=[("01 SCAN", "lattice cells {b}", "depth 4 · roots {c}"), ("02 PLAN", "tasks 6 · parallel-safe", "overlap 0 · eta {c}s"),
                   ("03 BUILD", "diff +{b} / -{c}", "edits {c}"), ("04 VERIFY", "checks {c}/64", "self-verified · pass")],
         panels=[("bars", "SIGNAL INTEGRITY", BARS), ("thr", "THROUGHPUT", None), ("mesh", "NODE MESH", None),
                 ("spec", "SPECTRUM", None), ("log", "EVENT LOG", None)],
         logs=DEF_LOGS, ticker=["LATTICE SYNC OK", "HANDSHAKE 0x3F", "BUFFER 98%", "QUANTUM LINK STABLE", "NODE MESH 6/6",
                                "PACKET LOSS 0.00%", "ENTROPY NOMINAL", "ROUTE OPTIMIZED"],
         rose="HOP ROSE · 24", gauge="CORE LOAD", scopes=("SIGNAL A", "SIGNAL B"), hexmode="hex"),
    dict(name="PAPER", title="HOLOGRID / PAPER-LAB", sub="field notes · print edition · procedural telemetry", light=True,
         pal=pal((236, 236, 230), (22, 24, 30), (30, 70, 230), (230, 90, 20), (200, 30, 50), (170, 170, 168), (246, 246, 242), (12, 12, 14)),
         center="radar", ring="full", glow=False,
         nodes=[("p1", "FAILOVER"), ("p2", "IDEMPOTENCY"), ("p3", "RETRY BUDGET"), ("p4", "CIRCUIT BREAKER"),
                ("p5", "WEBHOOK REPLAY"), ("p6", "OUTAGE BANNER")], pill="VERIFYING {id}",
         stats=[("THROUGHPUT", "{:.2f} TB/s", 1.0, 1.8, 0.4), ("MODE", "ARCHIVE", None, 0, 0),
                ("NODES", "{:.0f}/6", 4.6, 6.4, 2.0), ("UPTIME", "clock", None, 0, 0)],
         tele=DEF_TELE,
         callouts=[("01 SCAN", "lattice cells {b}", "depth 4 · roots {c}"), ("02 PLAN", "tasks 6 · parallel-safe", "overlap 0 · eta {c}s"),
                   ("03 BUILD", "diff +{b} / -{c}", "edits {c}"), ("04 VERIFY", "checks {c}/64", "self-verified · pass")],
         panels=[("bars", "SIGNAL INTEGRITY", BARS), ("thr", "THROUGHPUT", None), ("mesh", "NODE MESH", None),
                 ("spec", "SPECTRUM", None), ("log", "EVENT LOG", None)],
         logs=DEF_LOGS, ticker=["LATTICE SYNC OK", "HANDSHAKE 0x3F", "BUFFER 98%", "ENTROPY NOMINAL", "ROUTE OPTIMIZED"],
         rose="HOP ROSE · 24", gauge="CORE LOAD", scopes=("SIGNAL A", "SIGNAL B"), hexmode="hex"),
    dict(name="CRIMSON", title="RED PROTOCOL / VANTA-9", sub="tactical overlay · weapons free · live tracking",
         pal=pal((12, 3, 4), (255, 226, 216), (255, 42, 52), (255, 170, 60), (255, 90, 90), (86, 26, 30), (22, 6, 8)),
         center="reticle", ring="full", glow=True,
         nodes=[("t1", "BOGEY ALPHA"), ("t2", "BOGEY BRAVO"), ("t3", "DRONE SWARM"), ("t4", "SAM SITE"),
                ("t5", "CONVOY"), ("t6", "UNKNOWN")], pill="TRACKING {id}",
         stats=[("RANGE", "{:.1f} KM", 12, 48, 0.0), ("MODE", "ARMED", None, 0, 0),
                ("TARGETS", "{:.0f}/6", 3.6, 6.4, 1.0), ("MISSION", "clock", None, 0, 0)],
         tele=["lat   {a:.4f}°N", "lon   {d:+.4f}°E", "alt   {b} m", "hdg   {c:03d}° spd {b}", "radar ACTIVE",
               "fuel  {a:.0f}%", "frame {f}", "seed  0x{h:08X}"],
         callouts=[("01 ACQUIRE", "contacts {c} · hostile {e}", "bearing {b}°"), ("02 TRACK", "vectors {b} · lock {c}", "solution {a:.1f}%"),
                   ("03 LOCK", "weapon ready · rng {c}km", "confidence {a:.0f}%"), ("04 ENGAGE", "salvo {c} · pk {a:.0f}%", "bda pending")],
         panels=[("bars", "THREAT MATRIX", ("air", "sea", "land", "cyber", "space", "decoy")), ("thr", "SIGNAL TRAFFIC", None),
                 ("mesh", "SENSOR GRID", None), ("spec", "RF SPECTRUM", None), ("log", "COMMS LOG", None)],
         logs=["target acquired", "iff negative", "range update", "lock maintained", "jamming detected", "countermeasure"],
         ticker=["WEAPONS FREE", "IFF NEGATIVE", "TRACK FILE UPDATED", "SAM RADAR ACTIVE", "LOCK MAINTAINED", "ROE: ENGAGE"],
         rose="THREAT ROSE · 24", gauge="THREAT LEVEL", scopes=("RADAR RET", "ECM"), hexmode="hex"),
    dict(name="MATRIX", title="NEO // TERMINAL", sub="wake up · follow the white rabbit · root access granted",
         pal=pal((0, 6, 2), (205, 255, 215), (0, 255, 90), (190, 255, 0), (0, 200, 140), (10, 74, 34), (2, 14, 7)),
         center="rain", ring="edge", glow=True,
         nodes=[("n1", "ORACLE"), ("n2", "TRINITY"), ("n3", "MORPHEUS"), ("n4", "ZION"), ("n5", "NEBUCHADNEZZAR"), ("n6", "SENTINEL")],
         pill="TRACING {id}",
         stats=[("BANDWIDTH", "{:.1f} GB/s", 2, 9, 0.0), ("MODE", "ROOT", None, 0, 0),
                ("AGENTS", "{:.0f}", 2.6, 6.4, 1.0), ("UPTIME", "clock", None, 0, 0)],
         tele=["root@neo:~# {c}", "kernel 6.{c}.0-sim", "uptime {f}", "pid   {b}", "mem   0x{b:04X}",
               "tty   /dev/pts/{c}", "rain  {a:.1f}%", "hash  0x{h:08X}"],
         callouts=[("01 INJECT", "payload {b} bytes", "vector {c}"), ("02 TRACE", "hops {c} · route {b}", "agent smith {a:.0f}%"),
                   ("03 DECODE", "glyphs {b} · cipher {c}", "entropy {a:.1f}"), ("04 EXIT", "phone line {c}", "ttl {c}s")],
         panels=[("log", "SHELL", None), ("thr", "BANDWIDTH", None), ("mesh", "CELL GRID", None),
                 ("bars", "PROCESSES", ("init", "sshd", "agent", "oracle", "zion", "cron")), ("spec", "SIGNAL", None)],
         logs=["ssh handshake", "agent detected", "exploit loaded", "root shell", "packet trace", "wake up neo"],
         ticker=["WAKE UP NEO", "THE MATRIX HAS YOU", "FOLLOW THE WHITE RABBIT", "KNOCK KNOCK", "ROOT ACCESS GRANTED"],
         rose="PACKET ROSE", gauge="SYNC", scopes=("CARRIER", "NOISE"), hexmode="bin"),
    dict(name="AURORA", title="AURORA / BOREALIS-12", sub="magnetosphere monitor · geomagnetic storm watch",
         pal=pal((6, 5, 20), (228, 240, 255), (90, 255, 200), (200, 120, 255), (255, 110, 200), (46, 40, 92), (10, 9, 30)),
         center="ribbons", ring="box", glow=True,
         nodes=[("s1", "MAGNETOSPHERE"), ("s2", "SOLAR WIND"), ("s3", "KP INDEX"), ("s4", "IONOSPHERE"), ("s5", "CURTAIN"), ("s6", "SUBSTORM")],
         pill="OBSERVING {id}",
         stats=[("KP INDEX", "{:.1f}", 2, 8, 0.0), ("MODE", "STORM", None, 0, 0),
                ("FLUX", "{:.0f} nT", 20, 90, 1.0), ("UPTIME", "clock", None, 0, 0)],
         tele=["kp    {a:.1f}", "bz    {d:+.1f} nT", "wind  {b} km/s", "flux  {a:.2f}", "mlat  {c}°",
               "phase substorm", "frame {f}", "seed  0x{h:08X}"],
         callouts=[("01 SOLAR WIND", "speed {b} km/s", "density {a:.1f} p/cc"), ("02 BZ SHIFT", "bz {d:+.1f} nT", "coupling {a:.0f}%"),
                   ("03 CURTAIN", "intensity {a:.0f}%", "span {c}°"), ("04 FORECAST", "storm g{c}", "visibility {a:.0f}%")],
         panels=[("spec", "ION SPECTRUM", None), ("thr", "SOLAR FLUX", None), ("dials", "FIELD DIALS", ("bx", "by", "bz")),
                 ("bars", "LAYERS", ("E-reg", "F-reg", "D-reg", "belt", "cusp", "tail")), ("log", "OBSERVATORY", None)],
         logs=["magnetometer sync", "kp rising", "substorm onset", "curtain forming", "ion cascade", "bz south"],
         ticker=["KP 7 STORM WATCH", "BZ SOUTHWARD", "CURTAIN FORMING", "ION CASCADE", "MAGNETOMETER SYNC"],
         rose="FIELD ROSE · 24", gauge="STORM", scopes=("BX", "BZ"), hexmode="hex"),
    dict(name="SOLAR", title="HELIOS / ORRERY-1", sub="planetary tracker · ephemeris engine · real-time transit",
         pal=pal((10, 6, 2), (255, 242, 214), (255, 190, 40), (255, 100, 40), (120, 200, 255), (84, 58, 22), (20, 12, 4)),
         center="orrery", ring="ticks", glow=True,
         nodes=[("p1", "MERCURY"), ("p2", "VENUS"), ("p3", "TERRA"), ("p4", "MARS"), ("p5", "JOVE"), ("p6", "SATURN")],
         pill="SCANNING {id}",
         stats=[("DISTANCE", "{:.2f} AU", 0.4, 9.5, 0.0), ("MODE", "TRANSIT", None, 0, 0),
                ("BODIES", "{:.0f}/6", 4.6, 6.4, 1.0), ("EPOCH", "clock", None, 0, 0)],
         tele=["epoch {f}", "ecl   {d:+.2f}°", "au    {a:.2f}", "vel   {b} km/s", "mass  {a:.1f}e24", "phase transit",
               "frame {f}", "jd    {h}"],
         callouts=[("01 EPHEMERIS", "bodies 6 · moons {c}", "epoch {b}"), ("02 TRANSIT", "venus {a:.1f}° · mars {c}°", "window {c}d"),
                   ("03 BURN", "dv {b} m/s", "isp {c}s"), ("04 ARRIVAL", "eta {c}d", "orbit insertion {a:.0f}%")],
         panels=[("dials", "ORBITAL DIALS", ("a", "e", "i")), ("thr", "SOLAR ACTIVITY", None), ("bars", "BODY MASS", ("hg", "ve", "te", "ma", "ju", "sa")),
                 ("lissa", "RESONANCE", None), ("log", "MISSION LOG", None)],
         logs=["perihelion pass", "gravity assist", "trajectory burn", "flare detected", "comm window open", "fuel nominal"],
         ticker=["PERIHELION PASS", "GRAVITY ASSIST", "FLARE DETECTED", "COMM WINDOW OPEN", "ORBIT STABLE"],
         rose="ECLIPTIC ROSE", gauge="SOLAR FLUX", scopes=("LIGHT CURVE", "WIND"), hexmode="hex"),
    dict(name="ABYSS", title="ABYSSAL / TRENCH-11", sub="deep sonar survey · hadal zone · pressure hull nominal",
         pal=pal((1, 8, 14), (204, 246, 240), (30, 222, 192), (255, 200, 80), (80, 170, 255), (10, 64, 74), (2, 17, 26)),
         center="contour", ring="edge", glow=True,
         nodes=[("d1", "SUB ALPHA"), ("d2", "WHALE POD"), ("d3", "VENT FIELD"), ("d4", "WRECK"), ("d5", "THERMOCLINE"), ("d6", "UNKNOWN")],
         pill="PINGING {id}",
         stats=[("DEPTH", "{:.0f} M", 4000, 10900, 0.0), ("MODE", "SONAR", None, 0, 0),
                ("CONTACTS", "{:.0f}/6", 3.6, 6.4, 1.0), ("DIVE", "clock", None, 0, 0)],
         tele=["depth {b} m", "press {a:.1f} bar", "temp  {d:+.1f} °C", "sal   {a:.1f} ppt", "hdg   {c}°",
               "ping  active", "frame {f}", "seed  0x{h:08X}"],
         callouts=[("01 SOUNDING", "bottom {b} m", "slope {a:.1f}°"), ("02 CONTACT", "bearing {b}° · rng {c}m", "class biologic"),
                   ("03 THERMOCLINE", "layer {b} m", "delta {d:+.1f} °C"), ("04 HULL", "stress {a:.0f}%", "margin {c} bar")],
         panels=[("spec", "SONAR RETURN", None), ("bars", "HULL STRESS", ("bow", "mid", "aft", "dome", "ring", "keel")),
                 ("thr", "PRESSURE", None), ("mesh", "SEABED GRID", None), ("log", "DIVE LOG", None)],
         logs=["ping returned", "thermocline crossed", "biologic contact", "ballast trim", "hull stress ok", "bottom sounding"],
         ticker=["SONAR ACTIVE", "HULL NOMINAL", "BIOLOGIC CONTACT", "THERMOCLINE CROSSED", "BALLAST TRIM"],
         rose="CURRENT ROSE", gauge="PRESSURE", scopes=("ECHO", "HYDRO"), hexmode="hex"),
    dict(name="CYBER", title="NEON CITY / SYNTH-84", sub="night drive · retro grid · outrun protocol",
         pal=pal((10, 2, 20), (255, 232, 250), (255, 50, 200), (50, 230, 255), (255, 230, 60), (76, 26, 96), (19, 5, 36)),
         center="synth", ring="box", glow=True,
         nodes=[("c1", "DISTRICT 9"), ("c2", "MEGACORP"), ("c3", "DATA HAVEN"), ("c4", "NIGHT MARKET"), ("c5", "SKYBRIDGE"), ("c6", "BLACK ICE")],
         pill="CRUISING {id}",
         stats=[("SPEED", "{:.0f} KPH", 120, 290, 0.0), ("MODE", "OUTRUN", None, 0, 0),
                ("BPM", "{:.0f}", 100, 140, 1.0), ("TRIP", "clock", None, 0, 0)],
         tele=["neon  {a:.0f}%", "bpm   {c}", "grid  {b}", "sync  0x{b:04X}", "mood  synthwave", "vol   {a:.0f}",
               "frame {f}", "tape  0x{h:08X}"],
         callouts=[("01 CRUISE", "speed {b} kph", "gear {c}"), ("02 SYNC", "bpm {c} · beat {b}", "phase {a:.0f}%"),
                   ("03 DRIFT", "angle {a:.0f}° · boost {c}", "heat {b}"), ("04 ARRIVE", "eta {c}min", "district 9 · clear")],
         panels=[("lissa", "WAVEFORM", None), ("spec", "EQUALIZER", None), ("bars", "ENGINE", ("rpm", "turbo", "temp", "fuel", "grip", "neon")),
                 ("thr", "SPEED TRACE", None), ("log", "RADIO", None)],
         logs=["track change", "beat drop", "turbo engaged", "checkpoint", "district entered", "ice detected"],
         ticker=["NIGHT DRIVE", "OUTRUN PROTOCOL", "BEAT DROP", "TURBO ENGAGED", "NEON CITY 1984"],
         rose="SYNC ROSE", gauge="TURBO", scopes=("LEFT", "RIGHT"), hexmode="hex"),
    dict(name="ICE", title="CRYO / TESSERACT-4D", sub="hyperspace lattice · four-dimensional rotation · cold start",
         pal=pal((5, 12, 20), (236, 248, 255), (150, 220, 255), (255, 255, 255), (120, 150, 255), (40, 72, 98), (9, 21, 34)),
         center="tesseract", ring="ticks", glow=True,
         nodes=[("k1", "VERTEX LOCK"), ("k2", "W-AXIS"), ("k3", "FOLD 4D"), ("k4", "CRYO CORE"), ("k5", "SHEAR"), ("k6", "PHASE")],
         pill="ROTATING {id}",
         stats=[("TEMP", "{:.1f} K", 2, 40, 0.0), ("MODE", "CRYO", None, 0, 0),
                ("VERTS", "16", None, 0, 0), ("CYCLE", "clock", None, 0, 0)],
         tele=["w-axis {d:+.2f}", "rot   {a:.1f}°", "verts 16 · edges 32", "cells 8", "temp  {d:+.1f} K",
               "phase fold", "frame {f}", "seed  0x{h:08X}"],
         callouts=[("01 PROJECT", "4d to 3d · f {a:.2f}", "vertices 16"), ("02 ROTATE", "xw {a:.1f}° · zw {c}°", "rate {b}"),
                   ("03 FOLD", "cells 8 · faces 24", "shear {a:.1f}%"), ("04 COOL", "temp {d:+.1f} K", "stability {a:.0f}%")],
         panels=[("mesh", "CELL LATTICE", None), ("thr", "ENTROPY", None), ("dials", "AXES", ("xw", "yz", "zw")),
                 ("spec", "FREQUENCY", None), ("log", "CRYO LOG", None)],
         logs=["vertex locked", "w-axis rotation", "cell fold", "cooling cycle", "lattice stable", "shear detected"],
         ticker=["TESSERACT STABLE", "W-AXIS ROTATION", "CELL FOLD", "COOLING CYCLE", "LATTICE LOCKED"],
         rose="AXIS ROSE", gauge="COOLANT", scopes=("XW", "ZW"), hexmode="hex"),
    dict(name="QUANTUM", title="QUANTUM / ELECTRON-7", sub="wave function viewer · probability cloud · superposition",
         pal=pal((8, 4, 20), (242, 232, 255), (170, 100, 255), (255, 255, 120), (80, 200, 255), (56, 36, 102), (14, 8, 33)),
         center="atom", ring="ticks", glow=True,
         nodes=[("e1", "SPIN UP"), ("e2", "SPIN DOWN"), ("e3", "ENTANGLE"), ("e4", "TUNNEL"), ("e5", "COLLAPSE"), ("e6", "SUPERPOSE")],
         pill="OBSERVING {id}",
         stats=[("COHERENCE", "{:.1f}%", 60, 99, 0.0), ("MODE", "SUPERPOSED", None, 0, 0),
                ("QUBITS", "{:.0f}", 6, 9.4, 1.0), ("T2", "clock", None, 0, 0)],
         tele=["spin  {d:+.2f} h", "psi   {a:.3f}", "state |{c}>", "orbit 3", "coher {a:.1f}%", "phase superpos",
               "frame {f}", "seed  0x{h:08X}"],
         callouts=[("01 PREPARE", "qubits 8 · gates {c}", "fidelity {a:.1f}%"), ("02 ENTANGLE", "pairs {c} · bell {a:.0f}%", "decoherence {b}ns"),
                   ("03 MEASURE", "shots {b} · p0 {a:.0f}%", "state |{c}>"), ("04 COLLAPSE", "basis z · result {c}", "error {a:.2f}%")],
         panels=[("lissa", "WAVE FUNCTION", None), ("spec", "ENERGY LEVELS", None), ("dials", "QUBITS", ("q0", "q1", "q2")),
                 ("bars", "AMPLITUDES", ("|000>", "|001>", "|010>", "|011>", "|100>", "|111>")), ("log", "LAB LOG", None)],
         logs=["gate applied", "qubit entangled", "decoherence check", "measurement", "state collapse", "fidelity ok"],
         ticker=["SUPERPOSITION HELD", "QUBITS ENTANGLED", "DECOHERENCE LOW", "MEASUREMENT PENDING", "FIDELITY 99.2%"],
         rose="SPIN ROSE", gauge="COHERENCE", scopes=("PSI", "PHI"), hexmode="bin"),
    dict(name="BLUEPRINT", title="ENG-LAB / BLUEPRINT-X", sub="mechanical assembly · sheet 4 of 12 · tolerance review", grid="lines",
         pal=pal((16, 56, 128), (236, 246, 255), (255, 255, 255), (255, 212, 90), (120, 220, 255), (70, 120, 200), (14, 48, 112), (10, 40, 100)),
         center="gears", ring="edge", glow=False,
         nodes=[("g1", "DRIVE GEAR"), ("g2", "IDLER"), ("g3", "PINION"), ("g4", "OUTPUT"), ("g5", "SHAFT"), ("g6", "HOUSING")],
         pill="INSPECTING {id}",
         stats=[("TORQUE", "{:.1f} N·M", 20, 90, 0.0), ("MODE", "ASSEMBLY", None, 0, 0),
                ("PARTS", "{:.0f}/6", 4.6, 6.4, 1.0), ("SHEET", "clock", None, 0, 0)],
         tele=["scale 1:{c}", "tol   ±{a:.2f} mm", "rev   {c}", "sheet 04/12", "units mm", "drawn H-24", "frame {f}", "chk   0x{h:08X}"],
         callouts=[("01 DRIVE", "ratio 24:14 · rpm {b}", "torque {a:.1f} N·m"), ("02 MESH", "backlash {a:.2f} mm", "contact {a:.0f}%"),
                   ("03 TOLERANCE", "fit h7/g6 · ±{a:.2f}", "runout {c} µm"), ("04 STRESS", "von mises {b} MPa", "safety x{a:.1f}")],
         panels=[("bars", "TOLERANCES", ("bore", "shaft", "tooth", "pitch", "face", "hub")), ("thr", "TORQUE CURVE", None),
                 ("dials", "GAUGES", ("rpm", "load", "temp")), ("mesh", "STRESS MAP", None), ("log", "REVISIONS", None)],
         logs=["rev B issued", "tolerance check", "mesh verified", "stress pass", "dimension updated", "sheet approved"],
         ticker=["REV B ISSUED", "TOLERANCE CHECK", "MESH VERIFIED", "STRESS PASS", "SHEET APPROVED"],
         rose="LOAD ROSE", gauge="TORQUE", scopes=("VIBRATION", "TORQUE"), hexmode="hex"),
]

# edges of the 4D hypercube
HV = [[(i >> k & 1) * 2 - 1 for k in range(4)] for i in range(16)]
HE = [(i, j) for i in range(16) for j in range(i + 1, 16) if bin(i ^ j).count("1") == 1]


class Hud:
    def __init__(self, start=0):
        self.t = 0.0
        self.frame = 0
        self.paused = False
        self.scene = None
        self.cw, self.ch = W, H
        self.fonts = {}
        self.cache = {}
        self.logs = deque(maxlen=9)
        self.next_log = 0.0
        self.hexrows = []
        self.next_hex = 0.0
        self.peaks = {}
        self.toast_t = -10
        self.vt = -1
        self.rng = random.Random(11)
        self.ti = start % len(THEMES)

    def configure(self, surface):
        """(Re)bind to a drawing surface and rebuild every resolution-dependent asset."""
        global S, OX, OY
        self.scene = surface
        self.cw, self.ch = surface.get_size()
        S = min(self.cw / W, self.ch / H)
        OX = (self.cw / S - W) / 2
        OY = (self.ch / S - H) / 2
        self.fonts.clear()
        self.cache.clear()
        self.set_theme(self.ti, toast=False)

    # ---------- infrastructure ----------
    def font(self, size, bold=False):
        k = (size, bold)
        if k not in self.fonts:
            self.fonts[k] = pygame.font.SysFont("consolas,couriernew,monospace", max(7, int(size * S + 0.5)), bold=bold)
        return self.fonts[k]

    def text(self, s, size, color, pos, anchor="tl", bold=False, surf=None):
        key = (s, size, color, bold)
        img = self.cache.get(key)
        if img is None:
            if len(self.cache) > 2500:
                self.cache.clear()
            img = self.font(size, bold).render(s, True, color)
            self.cache[key] = img
        r = img.get_rect()
        setattr(r, {"tl": "topleft", "tr": "topright", "tc": "midtop", "c": "center",
                    "ml": "midleft", "mr": "midright"}[anchor], (int((pos[0] + OX) * S), int((pos[1] + OY) * S)))
        (surf or self.scene).blit(img, r)

    def fillr(self, surf, color, rect):
        x, y, w, h = rect
        surf.fill(color, (int((x + OX) * S), int((y + OY) * S), max(1, int(w * S + 0.5)), max(1, int(h * S + 0.5))))

    def clip(self, surf, rect):
        surf.set_clip((int((rect.x + OX) * S), int((rect.y + OY) * S), int(rect.w * S + 1), int(rect.h * S + 1)))

    def arc(self, r, a0, a1, col, w=1, c=C, surf=None):
        n = max(6, int(abs(a1 - a0) * r / 6))
        pts = [(c[0] + math.cos(a0 + (a1 - a0) * i / n) * r, c[1] + math.sin(a0 + (a1 - a0) * i / n) * r)
               for i in range(n + 1)]
        D.lines(surf or self.scene, col, False, pts, w)

    def dashed(self, surf, r, col, dashes=90, c=C, rot=0.0, frac=0.55, w=1):
        step = TAU / dashes
        for i in range(dashes):
            a = rot + i * step
            self.arc(r, a, a + step * frac, col, w, c, surf)

    # ---------- theme setup ----------
    def set_theme(self, i, toast=True):
        self.ti = i % len(THEMES)
        self.th = th = THEMES[self.ti]
        p = th["pal"]
        self.bg, self.fg, self.acc, self.acc2, self.acc3 = p["bg"], p["fg"], p["acc"], p["acc2"], p["acc3"]
        self.dim, self.panelc, self.corec = p["dim"], p["panel"], p["core"]
        self.glow = th["glow"]
        self.dimt = (100, 100, 100) if th.get("light") else L(self.dim, self.fg, 0.55)
        self.ramp = [L(self.dim, self.acc, 0.3 + 0.7 * i / 15) for i in range(16)]
        self.ramp_hot = [L(self.dim, self.acc2, 0.3 + 0.7 * i / 15) for i in range(16)]
        self.rp = [L(self.panelc, self.acc, i / 15) for i in range(16)]
        self.rf = [L(self.bg, self.acc, i / 15) for i in range(16)]
        self.nodes = th["nodes"]
        self.hexmode = th["hexmode"]
        self.hexrows = [self.rand_hex() for _ in range(34)]
        self.logs.clear()
        self.next_log = self.t
        self.peaks = {}
        if toast:
            self.toast_t = self.t
        self.setup_center()
        self.build_static()
        self.update_vals(force=True)

    def rand_hex(self):
        r = self.rng
        if self.hexmode == "bin":
            return " ".join("".join(r.choice("01") for _ in range(4)) for _ in range(4))
        return "%04X %s" % (r.randrange(0x10000), " ".join("%02X" % r.randrange(256) for _ in range(4)))

    def setup_center(self):
        c, r = self.th["center"], random.Random(5)
        if c == "rain":
            chars = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ<>=+*/\\|:;"
            self.ng = len(chars)
            f = self.font(14, True)
            self.glyph = []
            for k in range(14):
                col = self.fg if k == 0 else L(self.acc, self.bg, (k - 1) / 13 * 0.92)
                self.glyph.append([f.render(ch, True, col) for ch in chars])
            self.cols = [(x, r.uniform(7, 16), r.uniform(0, 60), r.randint(8, 18)) for x in range(484, 1120, 15)]
        elif c == "ribbons":
            self.stars = [(r.randrange(480, 1120), r.randrange(112, 560), r.uniform(0, TAU)) for _ in range(80)]
            cols = (self.acc, self.acc2, self.acc3)
            self.aur = [[L(self.bg, cols[k], 0.25 + 0.75 * s / 8) for s in range(9)] for k in range(3)]
            self.aur_dim = [L(self.bg, cols[k], 0.22) for k in range(3)]
        elif c == "orrery":
            self.belt = [(r.uniform(0, TAU), 224 + r.uniform(-9, 9), r.random()) for _ in range(150)]
            self.pc = [self.acc, L(self.acc2, self.fg, 0.3), self.acc3, self.acc2, L(self.acc, self.fg, 0.2), self.acc]
        elif c == "contour":
            self.bubbles = [(r.uniform(480, 1120), r.uniform(0, 700), r.uniform(18, 50), r.uniform(0, TAU)) for _ in range(40)]
            self.contacts = [(r.uniform(70, 285), r.uniform(0, TAU), r.choice((-1, 1)) * r.uniform(0.01, 0.04)) for _ in range(6)]
            self.th_cache = [(math.cos(i / 120 * TAU), math.sin(i / 120 * TAU)) for i in range(121)]
        elif c == "synth":
            self.syn_stars = [(r.randrange(476, 1124), r.randrange(106, 330), r.uniform(0, TAU)) for _ in range(70)]
            self.mount = [(x, 430 - (22 + 32 * abs(math.sin(x * 0.021)) + 20 * abs(math.sin(x * 0.057 + 1)))) for x in range(470, 1131, 10)]
        elif c == "atom":
            self.cloud = []
            for _ in range(300):
                th_, ph = r.uniform(0, TAU), math.acos(r.uniform(-1, 1))
                rad = abs(r.gauss(190, 55))
                self.cloud.append((rad * math.sin(ph) * math.cos(th_), rad * math.cos(ph), rad * math.sin(ph) * math.sin(th_)))
        elif c == "reticle":
            self.tg = [(r.uniform(0.2, 0.55), r.uniform(0.15, 0.5), r.uniform(0, TAU), r.uniform(0, TAU),
                        r.uniform(160, 290), r.uniform(120, 260)) for _ in range(6)]

    def build_static(self):
        th = self.th
        bg, dim, fg, acc = self.bg, self.dim, self.fg, self.acc
        s = pygame.Surface((self.cw, self.ch)).convert()
        s.fill(bg)
        lx0, ly0 = -OX, -OY
        lx1, ly1 = self.cw / S - OX, self.ch / S - OY
        gx0, gy0 = int(lx0 // 100) * 100, int(ly0 // 100) * 100
        if th.get("grid") == "lines":
            for x in range(gx0, int(lx1) + 1, 20):
                D.line(s, L(bg, dim, 0.45 if x % 100 else 0.9), (x, ly0), (x, ly1))
            for y in range(gy0, int(ly1) + 1, 20):
                D.line(s, L(bg, dim, 0.45 if y % 100 else 0.9), (lx0, y), (lx1, y))
        else:
            for x in range(gx0, int(lx1) + 1, 40):
                for y in range(gy0, int(ly1) + 1, 40):
                    self.fillr(s, L(bg, dim, 0.9), (x, y, 1, 1))
        ring = th["ring"]
        faint = L(bg, dim, 0.8)
        if ring == "full":
            D.line(s, L(bg, dim, 0.7), (C[0] - 400, C[1]), (C[0] + 400, C[1]))
            D.line(s, L(bg, dim, 0.7), (C[0], C[1] - 360), (C[0], C[1] + 340))
            for r in (60, 110, 160, 200, 250, 280):
                D.circle(s, faint, C, r, 1)
            self.dashed(s, 300, L(bg, acc, 0.35), 90)
        if ring in ("full", "ticks"):
            self.dashed(s, 345, dim, 120)
            for d in range(0, 360, 2):
                a = math.radians(d) - PI / 2
                ln = 12 if d % 10 == 0 else 5
                D.line(s, dim if d % 10 else fg, pol(C, 330, a), pol(C, 330 + ln, a))
            for d in range(0, 360, 30):
                a = math.radians(d) - PI / 2
                self.text("%03d°" % d, 12, self.dimt, pol(C, 362, a), "c", surf=s)
        if ring == "edge":
            D.circle(s, dim, C, 340, 1)
            self.dashed(s, 350, dim, 120)
            for d in range(0, 360, 10):
                a = math.radians(d) - PI / 2
                D.line(s, dim, pol(C, 340, a), pol(C, 346, a))
        if ring == "box":
            D.rect(s, dim, BOX, 1)
            for (px, py, dx, dy) in ((BOX.x, BOX.y, 1, 1), (BOX.right, BOX.y, -1, 1), (BOX.x, BOX.bottom, 1, -1), (BOX.right, BOX.bottom, -1, -1)):
                D.line(s, acc, (px, py), (px + dx * 22, py), 2)
                D.line(s, acc, (px, py), (px, py + dy * 22), 2)
        if th["center"] == "radar":
            for ri, r in enumerate((205, 213, 221)):
                for i in range(72):
                    a = i / 72 * TAU - PI / 2
                    D.line(s, dim, pol(C, r, a), pol(C, r + 6, a))
        # scanlines + vignette baked in
        ov = pygame.Surface((self.cw, self.ch), pygame.SRCALPHA)
        sl = 38 if self.glow else 10
        step = max(3, int(3 * S + 0.5))
        for y in range(0, self.ch, step):
            _pd.line(ov, (0, 0, 0, sl), (0, y), (self.cw, y))
        vg = pygame.Surface((64, 40), pygame.SRCALPHA)
        for x in range(64):
            for y in range(40):
                d = math.hypot((x - 31.5) / 32, (y - 19.5) / 20)
                vg.set_at((x, y), (0, 0, 0, int(max(0, d - 0.65) * (190 if self.glow else 70))))
        ov.blit(pygame.transform.smoothscale(vg, (self.cw, self.ch)), (0, 0))
        s.blit(ov, (0, 0))
        # header + panel frames
        self.text(th["title"], 38, fg, (20, 8), bold=True, surf=s)
        self.text(th["sub"], 13, self.dimt, (22, 50), surf=s)
        for i, st in enumerate(th["stats"]):
            x = 780 + i * 200
            D.line(s, dim, (x - 12, 6), (x - 12, 56))
            self.text(st[0], 11, self.dimt, (x, 6), surf=s)
        D.line(s, acc, (lx0, 62), (lx1, 62))
        tk = "   //   ".join(th["ticker"] * 4) + "   //   "
        self.ticker = self.font(12).render(tk, True, L(bg, fg, 0.55))
        for i, (rect, ang) in enumerate(CALLS):
            x, y, w, h = rect
            D.rect(s, self.panelc, rect)
            D.rect(s, dim, rect, 1)
            self.text(th["callouts"][i][0], 12, acc, (x + 8, y + 6), bold=True, surf=s)
            tgt = pol(C, 346, ang)
            sx = x + w if tgt[0] > x + w else x
            D.line(s, acc, (sx, y + h // 2), tgt)
            D.circle(s, self.acc2, (int(tgt[0]), int(tgt[1])), 3)
        for i, rect in enumerate(BOTTOM):
            self.bake_frame(s, rect, th["panels"][i][1], "%02d" % (i + 1))
        for i, rect in enumerate(SCOPES):
            self.bake_frame(s, rect, th["scopes"][i], None)
        self.static = s

    def bake_frame(self, s, rect, title, num):
        x, y, w, h = rect
        D.rect(s, self.panelc, rect)
        D.rect(s, self.dim, rect, 1)
        for (px, py, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
            D.line(s, self.acc, (px, py), (px + dx * 14, py), 2)
            D.line(s, self.acc, (px, py), (px, py + dy * 14), 2)
        D.line(s, self.dim, (x + 8, y + 24), (x + w - 8, y + 24))
        if num:
            self.text(num, 12, self.acc, (x + 10, y + 6), bold=True, surf=s)
            self.text(title, 12, self.fg, (x + 36, y + 6), surf=s)
        else:
            self.text(title, 12, self.fg, (x + 10, y + 6), surf=s)

    # ---------- data ----------
    def mk(self, k):
        t = self.t + k * 1.7
        return dict(a=50 + 45 * math.sin(t * 0.37), b=int(500 + 480 * math.sin(t * 0.23 + 1)),
                    c=150 + int(t) % 9, d=10 * math.sin(t * 0.5), e=2 + int(t * 0.7) % 7,
                    f=int(self.t * 60), h=0x5ED20D9 + int(self.t * 13))

    def update_vals(self, force=False):
        t = self.t
        if not force and t - self.vt < 0.1:
            return
        self.vt = t
        th = self.th
        self.tele = []
        for i, s in enumerate(th["tele"]):
            try:
                self.tele.append(s.format(**self.mk(i)))
            except Exception:
                self.tele.append(s)
        self.call_lines = []
        for i, c in enumerate(th["callouts"]):
            try:
                self.call_lines.append([ln.format(**self.mk(10 + i * 2 + j)) for j, ln in enumerate(c[1:])])
            except Exception:
                self.call_lines.append(list(c[1:]))
        up = int(t) + 4321
        self.stat_vals = []
        for lab, fmt, lo, hi, seed in th["stats"]:
            if fmt == "clock":
                val = "%02d:%02d:%02d" % (up // 3600, up // 60 % 60, up % 60)
            elif lo is None:
                val = fmt
            else:
                val = fmt.format(lo + (hi - lo) * (0.5 + 0.5 * math.sin(t * 0.3 + seed)))
            self.stat_vals.append(val)
        self.gval = 0.5 + 0.45 * math.sin(t * 0.4)

    def update(self, dt):
        if self.paused:
            return
        self.t += dt
        self.frame += 1
        t = self.t
        if t > self.next_log:
            self.next_log = t + 0.6
            n = self.nodes[int(t * 1.7) % 6]
            self.logs.append("[%s] %s %s" % (time.strftime("%H:%M:%S"), n[0], self.th["logs"][int(t * 3.1) % len(self.th["logs"])]))
        if t > self.next_hex:
            self.next_hex = t + 0.09
            self.hexrows[self.rng.randrange(len(self.hexrows))] = self.rand_hex()
        self.update_vals()

    # ---------- render ----------
    def render(self):
        sc, t = self.scene, self.t
        sc.blit(self.static, (0, 0))
        self.draw_header()
        getattr(self, "c_" + self.th["center"])()
        self.draw_pill()
        self.draw_callouts()
        self.draw_sides()
        self.draw_bottom()
        age = t - self.toast_t
        if age < 1.6:
            fade = min(1.0, (1.6 - age) / 0.6)
            label = "%02d/%02d  %s" % (self.ti + 1, len(THEMES), self.th["name"])
            r = pygame.Rect(0, 0, 360, 64)
            r.center = (800, 440)
            D.rect(sc, self.panelc, r)
            D.rect(sc, L(self.panelc, self.acc, fade), r, 2)
            self.text(label, 30, L(self.panelc, self.fg, fade), r.center, "c", bold=True)

    def draw_header(self):
        sc = self.scene
        for i, val in enumerate(self.stat_vals):
            self.text(val, 26, self.acc2 if i == 1 else self.fg, (780 + i * 200, 22), bold=True)
        w = self.ticker.get_width()
        x = -int(self.t * 50 * S) % w - w
        ty = int((68 + OY) * S)
        while x < self.cw:
            sc.blit(self.ticker, (x, ty))
            x += w

    def draw_pill(self):
        sc = self.scene
        n = self.nodes[int(self.t / 3.5) % 6]
        pill = pygame.Rect(0, 0, 250, 26)
        pill.center = (C[0], 118)
        D.rect(sc, self.panelc, pill, border_radius=13)
        D.rect(sc, self.acc, pill, 1, border_radius=13)
        D.circle(sc, self.acc2, (pill.x + 16, pill.centery), 4)
        self.text(self.th["pill"].format(id=n[0].upper()), 13, self.fg, (pill.x + 30, pill.centery), "ml", bold=True)

    def draw_callouts(self):
        for (rect, ang), lines in zip(CALLS, self.call_lines):
            for i, ln in enumerate(lines):
                self.text(ln, 12, self.fg, (rect[0] + 8, rect[1] + 28 + i * 16))

    def draw_sides(self):
        t, sc = self.t, self.scene
        for i, ln in enumerate(self.tele):
            self.text(ln, 12, self.dimt if i % 2 else self.fg, (22, 96 + i * 16))
        for k, rect in enumerate(SCOPES):
            x, y, w, h = rect
            ix, iy, iw, ih = x + 10, y + 32, w - 20, h - 42
            mid = iy + ih // 2
            D.line(sc, self.dim, (ix, mid), (ix + iw, mid))
            seed = k * 2.0
            pts = [(ix + i, mid + (math.sin(i * 0.09 + t * 2 + seed) * math.sin(i * 0.021 - t * 0.8 + seed * 2)
                                   + 0.25 * math.sin(i * 0.4 + t * 5)) * ih * 0.38) for i in range(0, iw, 2)]
            D.lines(sc, self.acc2 if k else self.acc, False, pts, 1)
        x0 = 1440
        hl = int(t * 6) % len(self.hexrows)
        for i, row in enumerate(self.hexrows):
            col = self.acc if i == hl else (self.fg if i % 5 == 0 else self.dimt)
            self.text(row, 11, col, (x0, 96 + i * 14))
        rc = (110, 690)
        D.circle(sc, self.dim, rc, 80, 1)
        D.circle(sc, self.dim, rc, 40, 1)
        for i in range(24):
            a = i / 24 * TAU
            v = 0.25 + 0.75 * abs(math.sin(i * 0.8 + t * 0.9) * math.sin(i * 0.31 - t * 0.4))
            D.line(sc, self.acc2 if i % 6 == 0 else self.acc, pol(rc, 6, a), pol(rc, 6 + v * 72, a), 4)
        self.text(self.th["rose"], 11, self.dimt, (rc[0], rc[1] + 92), "c")
        gc = (1490, 690)
        self.arc(78, math.radians(135), math.radians(405), self.dim, 6, gc)
        self.arc(78, math.radians(135), math.radians(135 + 270 * self.gval), self.acc, 6, gc)
        self.text("%d%%" % int(self.gval * 100), 28, self.fg, gc, "c", bold=True)
        self.text(self.th["gauge"], 11, self.dimt, (gc[0], gc[1] + 92), "c")

    # ---------- bottom panels ----------
    def draw_bottom(self):
        sc, t = self.scene, self.t
        blink = int(t * 2) % 2
        for i, rect in enumerate(BOTTOM):
            x, y, w, h = rect
            D.circle(sc, self.acc2 if blink else self.dim, (x + w - 14, y + 12), 3)
            kind, _, extra = self.th["panels"][i]
            r = pygame.Rect(x + 10, y + 32, w - 20, h - 42)
            getattr(self, "p_" + kind)(r, extra, i)

    def p_bars(self, r, names, k):
        sc, t = self.scene, self.t
        for i, name in enumerate(names):
            yy = r.y + i * 25
            v = 0.5 + 0.45 * math.sin(t * (0.3 + i * 0.11) + i * 1.7 + k)
            self.text(name, 12, self.fg, (r.x, yy))
            bx, bw = r.x + 80, r.w - 130
            D.rect(sc, self.dim, (bx, yy + 3, bw, 10), 1)
            D.rect(sc, self.acc2 if i == 5 else self.acc, (bx + 2, yy + 5, int((bw - 4) * v), 6))
            self.text("%3d" % int(v * 100), 12, self.fg, (r.right, yy), "tr")

    def p_thr(self, r, _e, k):
        sc, t = self.scene, self.t
        for g in range(1, 4):
            D.line(sc, self.dim, (r.x, r.y + r.h * g // 4), (r.right, r.y + r.h * g // 4))
        pts = []
        for i in range(0, 100):
            u = t * 2.2 + i * 0.09 + k * 3
            v = 0.5 + 0.2 * math.sin(u * 0.8) + 0.12 * math.sin(u * 2.1 + 1) + 0.05 * math.sin(u * 5.3)
            pts.append((r.x + i * r.w / 99, r.bottom - v * r.h))
        D.polygon(sc, L(self.panelc, self.acc, 0.18), [(r.x, r.bottom)] + pts + [(r.right, r.bottom)])
        D.lines(sc, self.acc, False, pts, 2)
        D.circle(sc, self.acc2, pts[0], 4)

    def p_mesh(self, r, _e, k):
        sc, t = self.scene, self.t
        cw, ch = r.w / 20, r.h / 6
        for j in range(6):
            for i in range(20):
                v = 0.5 + 0.5 * math.sin(t * (0.4 + 0.13 * ((i * 7 + j * 3) % 5)) + i * 0.7 + j * 1.3 + k)
                col = self.acc2 if v > 0.985 else self.rp[int(v * 15)]
                D.rect(sc, col, (r.x + i * cw + 1, r.y + j * ch + 1, cw - 3, ch - 3))

    def p_spec(self, r, _e, k):
        sc, t = self.scene, self.t
        n = 36
        bw = r.w / n
        pk = self.peaks.setdefault(k, [0.0] * n)
        for i in range(n):
            v = abs(math.sin(i * 0.45 + t * 1.6 + k) * 0.6 + math.sin(i * 0.17 - t * 0.9) * 0.4) * (1 - 0.35 * i / n)
            pk[i] = max(v, pk[i] - 0.006)
            hh = int(v * r.h)
            D.rect(sc, self.acc2 if v > 0.88 else self.acc, (r.x + i * bw + 1, r.bottom - hh, bw - 2, hh))
            yy = r.bottom - pk[i] * r.h
            D.line(sc, self.fg, (r.x + i * bw + 1, yy), (r.x + i * bw + bw - 2, yy))

    def p_log(self, r, _e, k):
        n = len(self.logs)
        for i, ln in enumerate(self.logs):
            self.text(ln, 12, self.fg if i == n - 1 else self.dimt, (r.x, r.y + i * 16))
        self.text("> _" if int(self.t * 2) % 2 else ">", 12, self.acc, (r.x, r.y + n * 16))

    def p_dials(self, r, names, k):
        t = self.t
        rad = min(r.w // 6 - 4, r.h // 2 - 8)
        for i in range(3):
            cx, cy = r.x + int((i + 0.5) * r.w / 3), r.centery - 6
            v = 0.5 + 0.45 * math.sin(t * (0.5 + i * 0.2) + i * 2 + k)
            self.arc(rad, math.radians(135), math.radians(405), self.dim, 5, (cx, cy))
            self.arc(rad, math.radians(135), math.radians(135 + 270 * v), self.acc2 if i == 1 else self.acc, 5, (cx, cy))
            self.text("%d" % int(v * 100), 16, self.fg, (cx, cy), "c", bold=True)
            self.text(names[i], 11, self.dimt, (cx, cy + rad + 8), "c")

    def p_lissa(self, r, _e, k):
        t = self.t
        cx, cy = r.centerx, r.centery
        pts = [(cx + math.sin(3 * u + t * 0.8 + k) * r.w * 0.45, cy + math.sin(2 * u + t * 0.5) * r.h * 0.45)
               for u in [i * TAU / 120 for i in range(121)]]
        D.lines(self.scene, self.dim, False, [(cx + (x - cx) * 0.6, cy + (y - cy) * 0.6) for x, y in pts], 1)
        D.lines(self.scene, self.acc, False, pts, 2)

    # ---------- centerpieces ----------
    def gl(self, col):
        return L(self.bg, col, 0.3)

    def c_radar(self):
        t, sc, acc, acc2, bg, dim = self.t, self.scene, self.acc, self.acc2, self.bg, self.dim
        sw = t * 0.9
        for k in range(0, 46, 2):
            D.line(sc, L(bg, acc, 0.5 * (1 - k / 46) ** 2), C, pol(C, 285, sw - k * 0.018), 5)
        D.line(sc, acc, C, pol(C, 285, sw), 1)
        for ri, r in enumerate((205, 213, 221)):
            prog = 0.5 + 0.5 * math.sin(t * 0.3 + ri * 1.3)
            for i in range(int(prog * 72)):
                a = i / 72 * TAU - PI / 2
                D.line(sc, acc, pol(C, r, a), pol(C, r + 6, a), 2)
        for r, sp, span, w, col in ((260, 0.35, 1.2, 3, acc), (268, -0.5, 0.7, 2, acc2), (118, 0.8, 2.0, 2, acc), (126, -1.1, 0.9, 1, acc2)):
            if self.glow:
                self.arc(r, t * sp, t * sp + span, self.gl(col), w + 4)
            self.arc(r, t * sp, t * sp + span, col, w)
        ha = (t * 0.5) % TAU
        for i in range(360):
            c, s = CS[i]
            v = abs(math.sin(i * 0.31 + t * 1.3) + math.sin(i * 0.071 - t * 0.7) + 0.6 * math.sin(i * 0.93 + t * 2.3)) / 2.6
            v = 1.0 if v > 1 else v
            d = (i / 360 * TAU - ha + PI) % TAU - PI
            hit = abs(d) < 0.4
            col = (self.ramp_hot if hit else self.ramp)[int(v * 15)]
            ln = 286 + v * 44
            D.line(sc, col, (C[0] + c * 282, C[1] + s * 282), (C[0] + c * ln, C[1] + s * ln), 2 if hit else 1)
        active = int(t / 3.5) % 6
        orb = ((190, -0.9, 0.12), (235, -0.2, -0.08), (170, 0.8, 0.15), (225, 1.9, -0.10), (250, 3.0, 0.07), (140, 4.2, -0.13))
        for idx, (nid, name) in enumerate(self.nodes):
            r, a0, sp = orb[idx]
            p = pol(C, r, a0 + t * sp)
            on = idx == active
            lc = acc2 if on else L(bg, acc, 0.4)
            D.line(sc, lc, C, p, 1)
            pk = (t * 0.45 + idx * 0.37) % 1
            D.circle(sc, acc2 if on else self.fg, (C[0] + (p[0] - C[0]) * pk, C[1] + (p[1] - C[1]) * pk), 2)
            pr = 14 + (t * 14 + idx * 5) % 16
            D.circle(sc, L(bg, acc2 if on else acc, 1 - (pr - 14) / 16), p, int(pr), 1)
            D.circle(sc, self.corec, p, 14)
            D.circle(sc, acc2 if on else acc, p, 14, 2)
            self.text(nid, 13, (240, 240, 240) if self.th.get("light") else self.fg, p, "c", bold=True)
            self.text(name, 11, acc2 if on else self.fg, (p[0] + 20, p[1] - 6))
            if on:
                self.dashed(sc, 22, acc2, 14, c=p, rot=t)
        self.core()

    def core(self):
        t, sc, acc = self.t, self.scene, self.acc
        D.circle(sc, L(self.bg, acc, 0.25), C, int(66 + 4 * math.sin(t * 2)), 1)
        D.circle(sc, self.corec, C, 48)
        for i in range(6):
            w = int(abs(math.cos(t * 0.6 + i * PI / 6)) * 48)
            if w > 1:
                D.ellipse(sc, L(self.corec, acc, 0.55), (C[0] - w, C[1] - 48, 2 * w, 96), 1)
        for dy in (-30, -15, 0, 15, 30):
            hw = int(math.sqrt(48 ** 2 - dy ** 2))
            D.ellipse(sc, L(self.corec, acc, 0.35), (C[0] - hw, C[1] + dy - 5, 2 * hw, 10), 1)
        D.circle(sc, acc, C, 48, 2)
        self.text("AETHER", 15, (255, 255, 255), (C[0], C[1] - 6), "c", bold=True)
        self.text("0x%06X" % (0x4F2A91 + int(t * 3) % 4096), 10, acc, (C[0], C[1] + 9), "c")

    def c_reticle(self):
        t, sc, acc, acc2, bg = self.t, self.scene, self.acc, self.acc2, self.bg
        sw = t * 0.7
        for k in range(0, 40, 2):
            D.line(sc, L(bg, acc, 0.4 * (1 - k / 40) ** 2), C, pol(C, 300, sw - k * 0.02), 5)
        for r, sp, n, fr, w in ((120, 0.5, 24, 0.6, 3), (170, -0.35, 36, 0.5, 2), (240, 0.2, 48, 0.55, 2), (290, -0.12, 60, 0.4, 1)):
            self.dashed(sc, r, acc if w > 1 else self.dim, n, rot=t * sp, frac=fr, w=w)
        for r in (60, 120, 180, 240, 300):
            self.text("%dkm" % (r // 6), 10, self.dimt, (C[0] + 4, C[1] - r - 12))
        active = int(t / 3.5) % 6
        for i, (fx, fy, px, py, rx, ry) in enumerate(self.tg):
            on = i == active
            col = acc2 if on else acc
            for m in range(1, 9):
                q = (C[0] + math.sin(fx * (t - m * 0.25) + px) * rx, C[1] + math.sin(fy * (t - m * 0.25) + py) * ry)
                D.circle(sc, L(bg, col, 0.55 * (1 - m / 9)), q, 2)
            x, y = C[0] + math.sin(fx * t + px) * rx, C[1] + math.sin(fy * t + py) * ry
            D.polygon(sc, col, [(x, y - 7), (x + 7, y), (x, y + 7), (x - 7, y)], 2 if on else 1)
            self.text(self.nodes[i][0].upper(), 10, self.fg, (x + 10, y - 5))
            if on:
                s = 24 + 4 * math.sin(t * 6)
                for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                    cx, cy = x + sx * s, y + sy * s
                    D.line(sc, acc2, (cx, cy), (cx - sx * 10, cy), 2)
                    D.line(sc, acc2, (cx, cy), (cx, cy - sy * 10), 2)
                D.line(sc, L(bg, acc2, 0.45), C, (x, y), 1)
                self.text("%s  RNG %.1fkm" % (self.nodes[i][1], math.hypot(x - C[0], y - C[1]) / 6), 11, acc2, (x + 16, y + s + 6))
        for a in range(4):
            c, s = math.cos(a * PI / 2), math.sin(a * PI / 2)
            D.line(sc, acc, (C[0] + c * 14, C[1] + s * 14), (C[0] + c * 40, C[1] + s * 40), 2)
        D.circle(sc, acc, C, 8, 1)
        D.circle(sc, self.gl(acc), C, 14, 3)

    def c_rain(self):
        t, sc = self.t, self.scene
        R2 = 335 * 335
        for j, (x, sp, off, ln) in enumerate(self.cols):
            head = int(t * sp + off) % (48 + ln)
            for k in range(ln):
                row = head - k
                if 0 <= row < 48:
                    y = 100 + row * 14
                    dx, dy = x - 800, y - 440
                    if dx * dx + dy * dy < R2:
                        ch = (j * 31 + row * 17 + int(t * sp * 0.35)) % self.ng
                        sc.blit(self.glyph[min(k, 13)][ch], (int((x + OX) * S), int((y + OY) * S)))
        D.circle(sc, self.bg, C, 92)
        D.circle(sc, self.acc, C, 92, 2)
        self.dashed(sc, 104, self.acc, 36, rot=t * 0.6, frac=0.5, w=2)
        self.dashed(sc, 118, self.acc2, 24, rot=-t * 0.4, frac=0.3, w=1)
        for i in range(8):
            D.circle(sc, self.fg if i == 0 else self.acc, pol(C, 70, t * 0.8 + i * PI / 4), 3)
        self.text("NEO", 22, self.fg, (C[0], C[1] - 8), "c", bold=True)
        self.text("0x%06X" % (0x7E0001 + int(t * 9) % 4096), 11, self.acc, (C[0], C[1] + 14), "c")

    def c_ribbons(self):
        t, sc = self.t, self.scene
        self.clip(sc, BOX)
        for (px, py, ph) in self.stars:
            v = 0.5 + 0.5 * math.sin(t * 1.5 + ph)
            self.fillr(sc, self.rf[int(4 + v * 11)], (px, py, 2, 2))
        for k in range(3):
            def fy(x, s=0):
                u = x * 0.011
                return (300 + k * 95 + 55 * math.sin(u * 1.3 + t * 0.5 + k + s * 0.12)
                        + 30 * math.sin(u * 2.7 - t * 0.8 + s * 0.08) + 16 * math.sin(u * 5.1 + t * 1.3))
            for x in range(470, 1131, 10):
                y = fy(x, 4) + 20
                D.line(sc, self.aur_dim[k], (x, y), (x, y + 70 + 30 * math.sin(x * 0.05 + t)), 3)
            for s in range(9):
                pts = [(x, fy(x, s) + s * 5) for x in range(470, 1131, 14)]
                D.lines(sc, self.aur[k][s], False, pts, 2)
        D.circle(sc, self.panelc, (800, 1090), 340)
        D.circle(sc, self.acc, (800, 1090), 340, 2)
        D.circle(sc, self.gl(self.acc), (800, 1090), 345, 4)
        sc.set_clip(None)

    def c_orrery(self):
        t, sc, acc, acc2, bg = self.t, self.scene, self.acc, self.acc2, self.bg
        active = int(t / 3.5) % 6
        radii = (52, 84, 118, 156, 204, 262)
        speeds = (1.6, 1.15, 0.85, 0.62, 0.34, 0.22)
        sizes = (4, 6, 7, 5, 12, 9)
        for r in radii:
            D.ellipse(sc, L(bg, self.dim, 0.9), (C[0] - r, C[1] - r * 0.92, 2 * r, 2 * r * 0.92), 1)
        for ang, rr, br in self.belt:
            a = ang + t * 0.08
            self.fillr(sc, self.rf[5 + int(br * 6)], (C[0] + math.cos(a) * rr, C[1] + math.sin(a) * rr * 0.92, 2, 2))
        for r in (30, 25, 20):
            D.circle(sc, L(bg, acc, 0.12 + (30 - r) * 0.04 + 0.03 * math.sin(t * 3)), C, r + int(2 * math.sin(t * 2)))
        D.circle(sc, acc2, C, 17)
        D.circle(sc, (255, 240, 200), C, 11)
        for i, (r, sp, sz) in enumerate(zip(radii, speeds, sizes)):
            a = t * sp * 0.4 + i * 1.3
            pts = [(C[0] + math.cos(a - m * 0.05) * r, C[1] + math.sin(a - m * 0.05) * r * 0.92) for m in range(16)]
            D.lines(sc, L(bg, self.pc[i], 0.5), False, pts, 2)
            p = (C[0] + math.cos(a) * r, C[1] + math.sin(a) * r * 0.92)
            col = self.pc[i]
            if i == 5:
                D.ellipse(sc, self.fg, (p[0] - 20, p[1] - 5, 40, 10), 1)
                D.ellipse(sc, L(bg, col, 0.6), (p[0] - 15, p[1] - 3, 30, 6), 1)
            D.circle(sc, col, p, sz)
            if i == 2:
                D.circle(sc, self.fg, (p[0] + math.cos(t * 3) * 16, p[1] + math.sin(t * 3) * 16), 2)
            on = i == active
            if on:
                self.dashed(sc, sz + 9, acc2, 12, c=p, rot=t * 2)
            self.text(self.nodes[i][1], 10, acc2 if on else self.dimt, (p[0] + sz + 4, p[1] - 14))

    def c_contour(self):
        t, sc, acc, acc2, bg = self.t, self.scene, self.acc, self.acc2, self.bg
        tc = self.th_cache
        for lv in range(11):
            rb = 24 + lv * 27
            pts = []
            for (c, s) in tc:
                a = math.atan2(s, c)
                rr = rb * (1 + 0.12 * math.sin(3 * a + t * 0.4 + lv) + 0.08 * math.sin(5 * a - t * 0.3 + 2 * lv)
                           + 0.05 * math.sin(7 * a + t * 0.2))
                pts.append((C[0] + c * rr, C[1] + s * rr))
            idx = lv % 5 == 0
            D.lines(sc, acc2 if idx else L(self.dim, acc, lv / 11), True, pts, 2 if idx else 1)
        for (bx, by, sp, ph) in self.bubbles:
            y = 770 - (by + t * sp) % 680
            x = bx + math.sin(t + ph) * 6
            if (x - 800) ** 2 + (y - 440) ** 2 < 330 * 330:
                D.circle(sc, L(bg, acc, 0.5), (x, y), 2, 1)
        sweep = t * 0.7
        D.line(sc, L(bg, acc, 0.7), C, pol(C, 320, sweep), 1)
        pr = (t % 3) / 3 * 330
        D.circle(sc, L(bg, acc, 1 - pr / 330), C, int(pr), 2)
        for i, (r, a, dr) in enumerate(self.contacts):
            ang = a + t * dr
            p = pol(C, r, ang)
            lit = max(0.0, 1 - ((sweep - ang) % TAU) / 1.6)
            col = L(bg, acc2 if i == int(t / 3.5) % 6 else acc, 0.2 + 0.8 * lit)
            D.circle(sc, col, p, 5)
            D.circle(sc, col, p, 5 + int((1 - lit) * 8), 1)
            self.text(self.nodes[i][1], 10, col, (p[0] + 10, p[1] - 5))
        D.circle(sc, acc, C, 5)
        D.circle(sc, self.gl(acc), C, 11, 3)

    def c_synth(self):
        t, sc, acc, acc2, bg = self.t, self.scene, self.acc, self.acc2, self.bg
        self.clip(sc, BOX)
        hz = 430
        top = (30, 6, 70)
        for i in range(22):
            y0 = 100 + i * (hz - 100) / 22
            f = i / 21
            self.fillr(sc, L(L(bg, top, min(1, f * 1.6)), (170, 30, 120), max(0, f - 0.55) * 1.8), (BOX.x, y0, BOX.w, (hz - 100) / 22 + 1))
        for (px, py, ph) in self.syn_stars:
            self.fillr(sc, self.rf[int(6 + 9 * (0.5 + 0.5 * math.sin(t * 2 + ph)))], (px, py, 2, 2))
        for y in range(250, 431, 2):
            f = (y - 250) / 180
            dx = math.sqrt(max(0, 110 * 110 - (y - 360) ** 2))
            if dx > 0:
                gap = ((y - 250) // 2 + int(t * 8)) % 9 < int(f * 6) and f > 0.45
                if not gap:
                    D.line(sc, L(self.acc3, acc, f), (800 - dx, y), (800 + dx, y), 2)
        for off, col in ((0, L(bg, acc2, 0.35)), (1, acc2)):
            pts = [(x, y + 18 * (1 - off) + 6 * math.sin(x * 0.09 + off)) for x, y in self.mount]
            D.lines(sc, col, False, pts, 2)
        self.fillr(sc, L(bg, (30, 0, 50), 0.8), (BOX.x, hz, BOX.w, BOX.bottom - hz))
        D.line(sc, acc, (BOX.x, hz), (BOX.right, hz), 2)
        off = (t * 0.7) % 1
        for k in range(16):
            z = (k + off) / 16
            y = hz + (z ** 2.2) * 340
            D.line(sc, L(bg, acc2, 0.25 + 0.75 * z), (BOX.x, y), (BOX.right, y), 1 if z < 0.5 else 2)
        for i in range(-14, 15):
            D.line(sc, L(bg, acc2, 0.55), (800 + i * 14, hz), (800 + i * 105, BOX.bottom), 1)
        sc.set_clip(None)

    def c_tesseract(self):
        t, sc, acc, acc2, bg = self.t, self.scene, self.acc, self.acc2, self.bg
        for i in range(3):
            tilt = 0.15 + 0.85 * abs(math.cos(t * 0.3 + i * 1.0))
            r = 270 - i * 12
            D.ellipse(sc, L(bg, acc, 0.35), (C[0] - r, C[1] - r * tilt, 2 * r, 2 * r * tilt), 1)
        self.dashed(sc, 300, self.dim, 90, rot=t * 0.2)
        a1, a2, a3, a4 = t * 0.5, t * 0.37, t * 0.23, t * 0.19
        P = []
        for v in HV:
            x, y, z, w = v
            c, s = math.cos(a1), math.sin(a1)
            x, w = x * c - w * s, x * s + w * c
            c, s = math.cos(a2), math.sin(a2)
            y, z = y * c - z * s, y * s + z * c
            c, s = math.cos(a3), math.sin(a3)
            z, w = z * c - w * s, z * s + w * c
            c, s = math.cos(a4), math.sin(a4)
            x, y = x * c - y * s, x * s + y * c
            f4 = 1 / (2.4 - w)
            x, y, z = x * f4, y * f4, z * f4
            f3 = 2.2 / (3.2 - z)
            P.append((C[0] + x * f3 * 235, C[1] + y * f3 * 235, w))
        for i, j in HE:
            d = (P[i][2] + P[j][2]) / 4 + 0.5
            D.line(sc, self.ramp[int(max(0, min(1, d)) * 15)], P[i][:2], P[j][:2], 2)
        for x, y, w in P:
            D.circle(sc, acc2, (x, y), 3 + int((w + 1) * 1.5))
        D.circle(sc, self.gl(acc), C, 40, 2)
        for i in range(30):
            y = 110 + (i * 53 + t * (14 + i % 5 * 4)) % 660
            x = 800 + math.sin(i * 2.4 + t * 0.3) * (150 + i * 8)
            if (x - 800) ** 2 + (y - 440) ** 2 < 335 ** 2:
                self.fillr(sc, self.rf[8 + i % 7], (x, y, 2, 2))

    def c_atom(self):
        t, sc, acc, acc2, acc3, bg = self.t, self.scene, self.acc, self.acc2, self.acc3, self.bg
        ay = t * 0.2
        ca, sa = math.cos(ay), math.sin(ay)
        for (x, y, z) in self.cloud:
            xr, zr = x * ca + z * sa, -x * sa + z * ca
            br = int(3 + 8 * (zr / 280 + 0.5))
            self.fillr(sc, self.rf[max(2, min(11, br))], (C[0] + xr, C[1] + y * 0.8 + zr * 0.3, 2, 2))
        for k, (a, b) in enumerate(((220, 70), (180, 52), (250, 95))):
            phi = k * 1.05 + t * 0.12
            cp, sp = math.cos(phi), math.sin(phi)

            def op(u):
                return (C[0] + a * math.cos(u) * cp - b * math.sin(u) * sp, C[1] + a * math.cos(u) * sp + b * math.sin(u) * cp)
            D.lines(sc, L(bg, acc, 0.45), True, [op(i * TAU / 80) for i in range(80)], 1)
            ue = t * (1.4 - k * 0.3) + k * 2
            for m in range(14):
                D.circle(sc, L(bg, acc2 if k == 0 else acc3, 1 - m / 14), op(ue - m * 0.09), max(1, 5 - m // 3))
        for i in range(10):
            a = t * 0.9 + i * 1.7
            r = 14 * abs(math.sin(a * 0.7 + i))
            D.circle(sc, acc if i % 2 else acc3, (C[0] + math.cos(a) * r, C[1] + math.sin(a * 1.3) * r), 6)
        D.circle(sc, self.gl(acc), C, 26 + int(3 * math.sin(t * 3)), 4)

    def c_gears(self):
        t, sc, fg, acc2, dim = self.t, self.scene, self.fg, self.acc2, self.dim
        specs = [(C, 120, 24, t * 0.35)]

        def add(parent, ang, r, n):
            (pc, pr, pn, pth) = specs[parent]
            d = pr + r + 1
            cen = (pc[0] + math.cos(ang) * d, pc[1] + math.sin(ang) * d)
            ratio = pn / n
            specs.append((cen, r, n, ang * (1 + ratio) - pth * ratio + PI + PI / n))
        add(0, -0.62, 70, 14)
        add(0, 2.35, 52, 10)
        add(1, -1.5, 88, 18)
        add(2, 3.6, 44, 9)
        for i, (cen, r, n, th_) in enumerate(specs):
            pts = []
            step = TAU / n
            for k in range(n):
                a = th_ + k * step
                for off, rr in ((-0.32, 0.88), (-0.2, 1.04), (0.2, 1.04), (0.32, 0.88)):
                    pts.append((cen[0] + math.cos(a + off * step) * r * rr, cen[1] + math.sin(a + off * step) * r * rr))
            D.polygon(sc, self.panelc, pts)
            D.polygon(sc, fg, pts, 2)
            D.circle(sc, dim, cen, int(r * 0.62), 1)
            D.circle(sc, fg, cen, int(r * 0.22), 2)
            for k in range(5):
                a = th_ + k * TAU / 5
                D.line(sc, dim, (cen[0] + math.cos(a) * r * 0.22, cen[1] + math.sin(a) * r * 0.22),
                                 (cen[0] + math.cos(a) * r * 0.62, cen[1] + math.sin(a) * r * 0.62), 1)
            self.dashed(sc, int(r * 1.0), acc2, max(12, n), c=cen, frac=0.3)
            lab = pol(cen, r * 1.18, -PI / 4 - i * 0.7)
            D.line(sc, acc2, pol(cen, r, -PI / 4 - i * 0.7), lab, 1)
            self.text("Ø%d.00" % (r * 2), 11, acc2, (lab[0] + 3, lab[1] - 12))
        D.line(sc, acc2, (C[0] - 120, 600), (C[0] + 120, 600), 1)
        for sx in (-120, 120):
            D.line(sc, acc2, (C[0] + sx, 592), (C[0] + sx, 608), 1)
        self.text("240.00", 12, acc2, (C[0], 612), "c")



# ======================= configuration, setup screen, main loop =======================
CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "HoloGrid")
CFG_PATH = os.path.join(CFG_DIR, "config.json")
DEFAULT_CFG = {"monitor": 0, "fullscreen": True, "theme": 0}


def load_cfg():
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            cfg = dict(DEFAULT_CFG)
            cfg.update(json.load(f))
            return cfg
    except Exception:
        return None


def save_cfg(cfg):
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def desktop_sizes():
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            return list(sizes)
    except Exception:
        pass
    info = pygame.display.Info()
    return [(info.current_w, info.current_h)]


def open_identify(sizes):
    """Flash a big number on every monitor (one small borderless window per display)."""
    try:
        from pygame._sdl2.video import Window, Renderer
    except Exception:
        return []
    out = []
    for i, (mw, mh) in enumerate(sizes):
        try:
            pos = 0x2FFF0000 | i     # SDL_WINDOWPOS_CENTERED_DISPLAY(i)
            w = Window("Display %d" % (i + 1), size=(460, 280), position=(pos, pos), borderless=True, always_on_top=True)
            out.append((w, Renderer(w), i, (mw, mh)))
        except Exception:
            pass
    return out


def draw_identify(wins, sel):
    try:
        from pygame._sdl2.video import Texture
        big = pygame.font.SysFont("consolas,couriernew,monospace", 150, bold=True)
        small = pygame.font.SysFont("consolas,couriernew,monospace", 26, bold=True)
        for w, r, i, (mw, mh) in wins:
            on = i == sel
            r.draw_color = (4, 8, 15, 255)
            r.clear()
            r.draw_color = (0, 229, 255, 255) if on else (255, 176, 32, 255)
            for k in range(4):
                r.draw_rect((k, k, 460 - 2 * k, 280 - 2 * k))
            for surf, y in ((big.render(str(i + 1), True, (200, 238, 255)), 135),
                            (small.render("%d x %d%s" % (mw, mh, "  PRIMARY" if i == 0 else ""), True, (255, 176, 32)), 245)):
                tex = Texture.from_surface(r, surf)
                rc = surf.get_rect(center=(230, y))
                r.blit(tex, rc)
            r.present()
    except Exception:
        pass


def close_identify(wins):
    for w, r, i, sz in wins:
        try:
            w.destroy()
        except Exception:
            pass


def run_setup(cfg):
    """First-start setup: choose the monitor and whether to start fullscreen. Returns cfg or None."""
    sizes = desktop_sizes()
    sel = min(cfg.get("monitor", 0), len(sizes) - 1)
    full = bool(cfg.get("fullscreen", True))
    per = min(4, len(sizes))
    rows = (len(sizes) + per - 1) // per
    fy = 160 + rows * 144 + 20
    WW, WH = 820, fy + 64 + 48 + 64
    BG, FG, ACC, ACC2, DIM = (4, 8, 15), (200, 238, 255), (0, 229, 255), (255, 176, 32), (34, 62, 82)

    def open_win():
        try:
            return pygame.display.set_mode((WW, WH), 0, display=sel)
        except Exception:
            return pygame.display.set_mode((WW, WH))
    win = open_win()
    pygame.display.set_caption("HoloGrid Setup")
    fn = lambda sz, b=False: pygame.font.SysFont("consolas,couriernew,monospace", sz, bold=b)  # noqa: E731
    f_title, f_mid, f_sm = fn(34, True), fn(17), fn(14)
    clock = pygame.time.Clock()
    cards = []
    cw_, ch_ = 170, 130
    x0 = (WW - (per * cw_ + (per - 1) * 16)) // 2
    for i in range(len(sizes)):
        cards.append(pygame.Rect(x0 + (i % per) * (cw_ + 16), 160 + (i // per) * (ch_ + 14), cw_, ch_))
    check = pygame.Rect(60, fy, 26, 26)
    start_btn = pygame.Rect(WW - 260, fy + 64, 200, 48)
    ident_btn = pygame.Rect(WW - 480, fy + 64, 200, 48)
    idw, idt = [], 0.0
    t = 0.0
    while True:
        dt = clock.tick(30) / 1000
        t += dt
        change = None
        go = False
        ident = False
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return None
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return None
                if e.key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_TAB):
                    change = (sel + 1) % len(sizes)
                elif e.key in (pygame.K_LEFT, pygame.K_UP):
                    change = (sel - 1) % len(sizes)
                elif pygame.K_1 <= e.key <= pygame.K_9 and e.key - pygame.K_1 < len(sizes):
                    change = e.key - pygame.K_1
                elif e.key in (pygame.K_SPACE, pygame.K_f):
                    full = not full
                elif e.key == pygame.K_i:
                    ident = True
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    go = True
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i, r in enumerate(cards):
                    if r.collidepoint(e.pos):
                        change = i
                if check.inflate(300, 10).collidepoint(e.pos):
                    full = not full
                if start_btn.collidepoint(e.pos):
                    go = True
                if ident_btn.collidepoint(e.pos):
                    ident = True
        if ident:
            close_identify(idw)
            idw, idt = open_identify(sizes), 3.0
            if not idw:
                idt = 0.0
        if idw:
            idt -= dt
            if idt <= 0:
                close_identify(idw)
                idw = []
            else:
                draw_identify(idw, sel)
        if go:
            close_identify(idw)
            cfg = dict(cfg)
            cfg["monitor"], cfg["fullscreen"] = sel, full
            return cfg
        if change is not None and change != sel:
            sel = change
            win = open_win()
            pygame.display.set_caption("HoloGrid Setup")
        win.fill(BG)
        for gx in range(0, WW, 40):
            for gy in range(0, WH, 40):
                win.set_at((gx, gy), (14, 26, 38))
        pygame.draw.rect(win, ACC, (0, 0, WW, 3))
        win.blit(f_title.render("HOLOGRID SETUP", True, FG), (40, 28))
        win.blit(f_sm.render("Choose the monitor HoloGrid should use. This window jumps to the selected monitor.", True, (120, 160, 185)), (42, 78))
        win.blit(f_mid.render("MONITOR", True, ACC), (42, 130))
        for i, r in enumerate(cards):
            on = i == sel
            pygame.draw.rect(win, (7, 15, 25), r)
            pygame.draw.rect(win, ACC if on else DIM, r, 3 if on else 1)
            mw, mh = sizes[i]
            ar = mw / max(mh, 1)
            bw = 110 if ar >= 1 else int(110 * ar)
            bh = int(bw / ar)
            if bh > 62:
                bh = 62
                bw = int(bh * ar)
            scr = pygame.Rect(0, 0, bw, bh)
            scr.center = (r.centerx, r.y + 46)
            pygame.draw.rect(win, (0, 60, 80) if on else (14, 30, 44), scr)
            pygame.draw.rect(win, ACC if on else (60, 100, 120), scr, 2)
            pygame.draw.line(win, ACC if on else (60, 100, 120), (r.centerx - 14, scr.bottom + 6), (r.centerx + 14, scr.bottom + 6), 2)
            lab = fn(18, True).render(str(i + 1), True, ACC if on else FG)
            win.blit(lab, lab.get_rect(center=scr.center))
            nm = "Display %d%s" % (i + 1, "  (primary)" if i == 0 else "")
            win.blit(f_sm.render(nm, True, FG), f_sm.render(nm, True, FG).get_rect(center=(r.centerx, r.y + 96)))
            rs = "%d x %d" % (mw, mh)
            win.blit(f_sm.render(rs, True, ACC2 if on else (120, 160, 185)), f_sm.render(rs, True, FG).get_rect(center=(r.centerx, r.y + 114)))
        pygame.draw.rect(win, ACC if full else DIM, check, 2)
        if full:
            pygame.draw.rect(win, ACC, check.inflate(-10, -10))
        win.blit(f_mid.render("Start in fullscreen", True, FG), (100, fy - 2))
        win.blit(f_sm.render("F11 toggles fullscreen or window any time.", True, (120, 160, 185)), (100, fy + 26))
        pygame.draw.rect(win, (7, 15, 25), ident_btn, 0, border_radius=6)
        pygame.draw.rect(win, ACC2, ident_btn, 2, border_radius=6)
        lab = f_mid.render("IDENTIFY  [I]", True, ACC2)
        win.blit(lab, lab.get_rect(center=ident_btn.center))
        pulse = 0.5 + 0.5 * math.sin(t * 4)
        pygame.draw.rect(win, (0, int(120 + 80 * pulse), int(150 + 80 * pulse)), start_btn, 0, border_radius=6)
        lab = f_mid.render("START  [Enter]", True, (0, 10, 16))
        win.blit(lab, lab.get_rect(center=start_btn.center))
        win.blit(f_sm.render("Left/Right or 1-9: monitor   I: identify   Space: fullscreen   Esc: quit", True, (90, 130, 155)), (42, WH - 34))
        pygame.display.flip()


def open_display(cfg):
    sizes = desktop_sizes()
    idx = max(0, min(cfg.get("monitor", 0), len(sizes) - 1))
    mw, mh = sizes[idx]
    if cfg.get("fullscreen", True):
        size, flags = (mw, mh), pygame.FULLSCREEN
    else:
        ww = int(min(mw * 0.82, mh * 0.82 * 1.6))
        size, flags = (max(960, ww), max(600, int(ww / 1.6))), pygame.RESIZABLE
    if flags == pygame.FULLSCREEN:
        # GPU-presented, vsynced fullscreen at native resolution (logical size == monitor size -> 1:1, no resampling)
        try:
            return pygame.display.set_mode(size, flags | pygame.SCALED, display=idx, vsync=1)
        except Exception:
            pass
    try:
        return pygame.display.set_mode(size, flags, display=idx)
    except Exception:
        return pygame.display.set_mode(size, flags)


def run_app(cfg, bench=False):
    """Main HUD loop. Returns 'setup' when the user asks for the setup screen, else 'quit'."""
    win = open_display(cfg)
    pygame.display.set_caption("HOLOGRID")
    hud = Hud(cfg.get("theme", 0))
    hud.configure(win)
    clock = pygame.time.Clock()
    pending = None
    n = 0
    last = time.perf_counter()
    t_bench = last
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                cfg["theme"] = hud.ti
                save_cfg(cfg)
                return "quit"
            if e.type == pygame.VIDEORESIZE and not cfg.get("fullscreen", True):
                pending = time.perf_counter()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    cfg["theme"] = hud.ti
                    save_cfg(cfg)
                    return "quit"
                elif e.key == pygame.K_SPACE:
                    hud.paused = not hud.paused
                elif e.key == pygame.K_t:
                    hud.set_theme(hud.ti + (-1 if e.mod & pygame.KMOD_SHIFT else 1))
                elif pygame.K_1 <= e.key <= pygame.K_9:
                    hud.set_theme(e.key - pygame.K_1)
                elif e.key == pygame.K_0:
                    hud.set_theme(9)
                elif e.key == pygame.K_MINUS:
                    hud.set_theme(10)
                elif e.key == pygame.K_F11:
                    cfg["fullscreen"] = not cfg.get("fullscreen", True)
                    win = open_display(cfg)
                    hud.configure(win)
                    pending = None
                elif e.key == pygame.K_m:
                    cfg["monitor"] = (cfg.get("monitor", 0) + 1) % len(desktop_sizes())
                    win = open_display(cfg)
                    hud.configure(win)
                    pending = None
                elif e.key == pygame.K_F2:
                    cfg["theme"] = hud.ti
                    return "setup"
                elif e.key == pygame.K_s:
                    out = os.path.join(os.path.expanduser("~"), "Pictures", "hologrid_%d.png" % int(time.time()))
                    try:
                        pygame.image.save(hud.scene, out)
                    except Exception:
                        pass
        if pending is not None and time.perf_counter() - pending > 0.3:
            pending = None
            win = pygame.display.get_surface()
            if win.get_size() != (hud.cw, hud.ch):
                hud.configure(win)
        now = time.perf_counter()
        dt = min(now - last, 0.05)
        last = now
        hud.update(dt)
        if pending is None:
            hud.render()
            pygame.display.flip()
        n += 1
        if bench:
            if n == 60:
                t_bench = time.perf_counter()
            if n == 360:
                print("FPS %.1f at %dx%d (scale %.2f)" % (300 / (time.perf_counter() - t_bench), hud.cw, hud.ch, S))
                return "quit"
        clock.tick(144 if cfg.get('fullscreen', True) else 60)   # fullscreen is vsynced; windowed is paced


def main():
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # sharp, un-stretched pixels on scaled displays
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    args = sys.argv
    pygame.init()
    cfg = load_cfg()
    bench = "--bench" in args
    if "--monitor" in args:
        cfg = dict(cfg or DEFAULT_CFG)
        cfg["monitor"] = int(args[args.index("--monitor") + 1])
    if "--windowed" in args:
        cfg = dict(cfg or DEFAULT_CFG)
        cfg["fullscreen"] = False
    if "--theme" in args:
        cfg = dict(cfg or DEFAULT_CFG)
        cfg["theme"] = int(args[args.index("--theme") + 1])
    force_setup = "--setup" in args
    if (cfg is None and not bench) or force_setup:
        res = run_setup(cfg or DEFAULT_CFG)
        if res is None:
            return
        cfg = res
        save_cfg(cfg)
    cfg = cfg or dict(DEFAULT_CFG)
    while True:
        result = run_app(cfg, bench)
        if result != "setup":
            break
        pygame.display.quit()
        pygame.display.init()
        res = run_setup(cfg)
        pygame.display.quit()
        pygame.display.init()
        if res is None:
            break
        cfg = res
        save_cfg(cfg)


if __name__ == "__main__":
    main()
    pygame.quit()
