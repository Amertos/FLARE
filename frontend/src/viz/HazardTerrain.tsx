import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import * as d3 from "d3";
import type { TradeSpaceResponse } from "../api";
import { webglSupport } from "./webgl";

/** Height of a full-scale (100) ignition index, in world units. */
const HEIGHT = 0.62;
/** Colour of the surface outside the fitted pressure envelope: no evidence. */
const SLATE = new THREE.Color("#334155");
/** Restore-point camera pose for the reset-view button. */
const HOME = { pos: new THREE.Vector3(2.15, 1.85, 2.35), target: new THREE.Vector3(0, 0, 0) };

/**
 * The published P x O2 ignition field as a rotatable surface.
 *
 * Three things this view shows that the 2D map cannot:
 *   - the *shape* of the hazard over the whole design space at once,
 *   - the LOC boundary as a ridge lying on that surface,
 *   - the edge of the calibration envelope as a hatched vertical face, so the
 *     extrapolated region is visibly a cliff rather than a coloured area that
 *     quietly continues (dossier §4.7 L2).
 *
 * Plus a translucent GHOST surface showing the same field at 1g: the micro-
 * gravity money-shot is seeing the boundary *move* as gravity flips, without
 * switching screens. Nothing is computed here: heights and colours come from
 * /api/tradespace for the current gravity and the /api/flame crossover series
 * for the 1g comparison — the same engine outputs the 2D screens draw.
 */
export default function HazardTerrain({
  trade,
  pressure,
  o2,
  ghost,
  className = "",
}: {
  trade: TradeSpaceResponse;
  pressure: number;
  o2: number;
  ghost?: boolean;
  className?: string;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<{
    renderer: THREE.WebGLRenderer;
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    scene: THREE.Scene;
    marker: THREE.Group;
    raycaster: THREE.Raycaster;
    pointer: THREE.Vector2;
    hoverPlane: THREE.Mesh;
    grid: number[][];
    ps: number[];
    o2s: number[];
    axes: { x: (p: number) => number; z: (o: number) => number };
    frame: number;
    ghostMesh: THREE.Mesh | null;
    stars: THREE.Points | null;
  } | null>(null);

  const [autoRotate, setAutoRotate] = useState(true);
  const [showGhost, setShowGhost] = useState(ghost ?? false);
  const [fps, setFps] = useState<number | null>(null);
  const [hover, setHover] = useState<{ p: number; o: number; v: number } | null>(null);
  // Probe WebGL once, during the first render, instead of reporting a failure
  // from inside the effect: the screen can then decide to show its fallback
  // text without a second render pass.
  const [webglError] = useState<string | null>(() => webglSupport());

  // ---------------------------------------------------------------- geometry
  useEffect(() => {
    const host = hostRef.current;
    if (!host || webglError) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    } catch (err) {
      // The probe passed but context creation still failed (a lost context at
      // start-up). The probe's value is already rendered as the fallback panel
      // in the browser case, so just bail out of 3D here.
      console.warn("terrain: WebGL renderer unavailable", err);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(new THREE.Color("#020617"), 1);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    host.appendChild(renderer.domElement);
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x020617, 3.5, 8.5);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 200);
    camera.position.copy(HOME.pos);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 1.4;
    controls.maxDistance = 6;
    controls.maxPolarAngle = Math.PI / 2.05;
    controls.autoRotateSpeed = 0.55;
    controls.autoRotate = true;

    scene.add(new THREE.HemisphereLight(0xffffff, 0x1e293b, 1.15));
    const key = new THREE.DirectionalLight(0xffffff, 1.35);
    key.position.set(3, 5, 2.5);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x60a5fa, 0.7);
    rim.position.set(-2.5, 1.5, -2.2);
    scene.add(rim);

    // ---- starfield: perspective dots behind everything (cosmetic only)
    const starN = 340;
    const starPos = new Float32Array(starN * 3);
    for (let i = 0; i < starN; i++) {
      const r = 9 + Math.random() * 4;
      const t = Math.random() * Math.PI * 2;
      const u = Math.random() * 0.75;
      starPos[i * 3] = Math.cos(t) * Math.sin(u + 0.3) * r;
      starPos[i * 3 + 1] = -2 + Math.cos(u) * r * 0.4 + 1.4;
      starPos[i * 3 + 2] = Math.sin(t) * Math.sin(u + 0.3) * r;
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({
      color: 0x94a3b8, size: 0.035, sizeAttenuation: true,
      transparent: true, opacity: 0.55, depthWrite: false,
    }));
    scene.add(stars);

    const ps = trade.p_psia;
    const o2s = trade.o2_pct;
    const grid = trade.grid.map((row) => row.map((cell) => cell.ignition));

    // x: pressure, z: O2, both normalised to [-1, 1] so the surface is centred.
    const x = (p: number) => ((p - ps[0]) / (ps[ps.length - 1] - ps[0]) - 0.5) * 2;
    const z = (o: number) => ((o - o2s[0]) / (o2s[o2s.length - 1] - o2s[0]) - 0.5) * 2;
    const yOf = (v: number) => (v / 100) * HEIGHT;
    const envelope = trade.p_envelope_kpa.map((kpa) => kpa / 6.89476) as [number, number];

    const heat = (v: number) => new THREE.Color(d3.interpolateRdYlGn(1 - Math.min(1, v / 90)));
    const inside = (p: number) => p >= envelope[0] && p <= envelope[1];

    const positions: number[] = [];
    const colours: number[] = [];
    const push = (p: number, o: number) => {
      const i = Math.max(0, Math.min(ps.length - 1, ps.indexOf(p)));
      const j = Math.max(0, Math.min(o2s.length - 1, o2s.indexOf(o)));
      const v = grid[i][j];
      positions.push(x(p), yOf(v), z(o));
      // Outside the fitted envelope the height is still the model's value but
      // the colour is neutral: the region is not evidence, and a coloured
      // pixel there would imply it is (dossier §4.7 L2).
      if (inside(p)) {
        const c = heat(v);
        colours.push(c.r, c.g, c.b);
      } else {
        colours.push(SLATE.r, SLATE.g, SLATE.b);
      }
    };
    for (let i = 0; i < ps.length - 1; i++) {
      for (let j = 0; j < o2s.length - 1; j++) {
        push(ps[i], o2s[j]);
        push(ps[i], o2s[j + 1]);
        push(ps[i + 1], o2s[j + 1]);
        push(ps[i], o2s[j]);
        push(ps[i + 1], o2s[j + 1]);
        push(ps[i + 1], o2s[j]);
      }
    }
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geom.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
    geom.computeVertexNormals();
    const surface = new THREE.Mesh(
      geom,
      new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide }),
    );
    scene.add(surface);

    // ---- LOC ridge: boundary points sitting on the surface --------------
    const ridge = new THREE.Group();
    trade.loc_boundary.forEach((b) => {
      if (b.loc_pct == null) return;
      const i = ps.indexOf(b.p_psia);
      if (i < 0) return;
      // height at the boundary interpolates between the two O2 rows that
      // bracket the LOC value, so the ridge hugs the terrain
      let lo = 0;
      while (lo < o2s.length - 2 && o2s[lo + 1] < b.loc_pct!) lo++;
      const t = (b.loc_pct - o2s[lo]) / Math.max(1e-6, o2s[lo + 1] - o2s[lo]);
      const v = grid[i][lo] * (1 - t) + grid[i][lo + 1] * t;
      const bead = new THREE.Mesh(
        new THREE.SphereGeometry(0.019, 10, 8),
        new THREE.MeshBasicMaterial({ color: 0xffffff }),
      );
      bead.position.set(x(b.p_psia), yOf(v) + 0.012, z(b.loc_pct));
      ridge.add(bead);
    });
    scene.add(ridge);

    // ---- the data cliff -------------------------------------------------
    const hatchCanvas = document.createElement("canvas");
    hatchCanvas.width = 64;
    hatchCanvas.height = 64;
    const hctx = hatchCanvas.getContext("2d");
    if (hctx) {
      hctx.fillStyle = "#020617";
      hctx.fillRect(0, 0, 64, 64);
      hctx.strokeStyle = "rgba(245,158,11,0.65)";
      hctx.lineWidth = 5;
      for (let d = -64; d < 128; d += 18) {
        hctx.beginPath();
        hctx.moveTo(d, 0);
        hctx.lineTo(d + 64, 64);
        hctx.stroke();
      }
    }
    const hatchTex = new THREE.CanvasTexture(hatchCanvas);
    hatchTex.wrapS = THREE.RepeatWrapping;
    hatchTex.wrapT = THREE.RepeatWrapping;
    hatchTex.repeat.set(8, 3);
    const cliffMat = new THREE.MeshBasicMaterial({
      map: hatchTex,
      transparent: true,
      opacity: 0.92,
      side: THREE.DoubleSide,
    });
    const edgeX = [x(envelope[0]), x(envelope[1])].filter((v) => v > -1.0001 && v < 1.0001);
    edgeX.forEach((ex) => {
      const wall = new THREE.Mesh(new THREE.PlaneGeometry(2, HEIGHT * 1.02), cliffMat);
      wall.rotation.y = Math.PI / 2;
      wall.position.set(ex, (HEIGHT * 1.02) / 2, 0);
      scene.add(wall);
      // floor strip beyond the cliff, so the region reads as "no data" from
      // every camera angle
      const beyond = envelope[0] > ps[0] && ex < 0;
      const other = envelope[1] < ps[ps.length - 1] && ex > 0;
      if (beyond || other) {
        const strip = new THREE.Mesh(new THREE.PlaneGeometry(1, 2), cliffMat);
        strip.rotation.x = -Math.PI / 2;
        strip.position.set(beyond ? ex - 0.5 : ex + 0.5, 0.002, 0);
        scene.add(strip);
      }
    });

    // ---- grid floor + axes ---------------------------------------------
    const floor = new THREE.GridHelper(2, 8, 0x334155, 0x1e293b);
    floor.position.y = -0.002;
    scene.add(floor);

    // ---- current-state marker ------------------------------------------
    const marker = new THREE.Group();
    const ball = new THREE.Mesh(
      new THREE.SphereGeometry(0.045, 16, 12),
      new THREE.MeshBasicMaterial({ color: 0xfacc15 }),
    );
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.07, 0.095, 32),
      new THREE.MeshBasicMaterial({ color: 0xfacc15, side: THREE.DoubleSide }),
    );
    ring.rotation.x = -Math.PI / 2;
    const stem = new THREE.Mesh(
      new THREE.CylinderGeometry(0.006, 0.006, 1, 6),
      new THREE.MeshBasicMaterial({ color: 0xfacc15, transparent: true, opacity: 0.55 }),
    );
    marker.add(ball, ring, stem);
    scene.add(marker);

    // ---- hover probe: an invisible plane matched to the XY half-space of
    // the panel (used only for pointer raycast) and a visible highlight ring.
    const hoverPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(2, 2),
      new THREE.MeshBasicMaterial({ visible: false }),
    );
    hoverPlane.rotation.x = -Math.PI / 2;
    hoverPlane.position.y = yOf(40);
    scene.add(hoverPlane);
    const hoverRing = new THREE.Mesh(
      new THREE.RingGeometry(0.03, 0.05, 24),
      new THREE.MeshBasicMaterial({ color: 0x60a5fa, side: THREE.DoubleSide, transparent: true, opacity: 0 }),
    );
    hoverRing.rotation.x = -Math.PI / 2;
    scene.add(hoverRing);

    // ---- ghost surface: the same field at 1g, loaded lazily. Enabled by the
    // screen's toggle; a sibling mesh, transparent blue, so the two gravity
    // regimes can be compared in one orbit.
    let ghostMesh: THREE.Mesh | null = null;
    if (showGhost && trade.ghost_grid_1g != null) {
      // The 1g ghost is drawn BELOW the µg surface (height_offset_pct is the
      // engine-declared vertical offset in ignition points): two translucent
      // sheets, with the LOC separation visible as the gap between them.
      const gg = trade.ghost_grid_1g;
      const gpos: number[] = [];
      const gcol: number[] = [];
      const gheat = (v: number) => new THREE.Color(d3.interpolateBlues(0.25 + 0.55 * Math.min(1, v / 90)));
      const ghostOffset = (row: { ignition: number; height_offset_pct: number }) =>
        (row.height_offset_pct ?? -2) / 100 * HEIGHT;
      for (let i = 0; i < ps.length - 1; i++) {
        for (let j = 0; j < o2s.length - 1; j++) {
          const quad = [
            [ps[i], o2s[j]], [ps[i], o2s[j + 1]], [ps[i + 1], o2s[j + 1]],
            [ps[i], o2s[j]], [ps[i + 1], o2s[j + 1]], [ps[i + 1], o2s[j]],
          ];
          for (const [p, o] of quad) {
            const ii = Math.max(0, Math.min(ps.length - 1, ps.indexOf(p)));
            const jj = Math.max(0, Math.min(o2s.length - 1, o2s.indexOf(o)));
            const v = gg[ii][jj].ignition;
            gpos.push(x(p), yOf(v) + ghostOffset(gg[ii][jj]), z(o));
            const c = gheat(v);
            gcol.push(c.r, c.g, c.b);
          }
        }
      }
      const ggeom = new THREE.BufferGeometry();
      ggeom.setAttribute("position", new THREE.Float32BufferAttribute(gpos, 3));
      ggeom.setAttribute("color", new THREE.Float32BufferAttribute(gcol, 3));
      ggeom.computeVertexNormals();
      ghostMesh = new THREE.Mesh(
        ggeom,
        new THREE.MeshBasicMaterial({
          vertexColors: true, transparent: true, opacity: 0.5,
          side: THREE.DoubleSide, depthWrite: false,
        }),
      );
      scene.add(ghostMesh);
    }

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    sceneRef.current = {
      renderer, camera, controls, scene, marker, raycaster, pointer, hoverPlane,
      grid, ps, o2s, axes: { x, z }, frame: 0, ghostMesh, stars,
    };

    let last = performance.now();
    let windowStart = performance.now();
    let frames = 0;
    const tick = () => {
      const s = sceneRef.current;
      if (!s) return;
      const now = performance.now();
      const dt = now - last;
      last = now;
      // Wall-clock fps window: sub-millisecond rAF deltas (high-refresh
      // monitors) would otherwise inflate a dt-accumulated counter to nonsense.
      frames++;
      if (now - windowStart > 500) {
        setFps(Math.round((frames * 1000) / (now - windowStart)));
        frames = 0;
        windowStart = now;
      }
      if (s.stars) s.stars.rotation.y += dt * 0.00001;
      // hover raycast against the invisible plane, report (P, O2, ignition)
      const r = s.hoverPlane as THREE.Mesh;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObject(r, false)[0];
      if (hit && hit.point) {
        const p = Math.round(((hit.point.x / 2) + 0.5) * (ps[ps.length - 1] - ps[0]) + ps[0]);
        const o = Math.round(((hit.point.z / 2) + 0.5) * (o2s[o2s.length - 1] - o2s[0]) + o2s[0]);
        const i = ps.indexOf(Math.max(ps[0], Math.min(ps[ps.length - 1], p)));
        const j = o2s.indexOf(Math.max(o2s[0], Math.min(o2s[o2s.length - 1], o)));
        if (i >= 0 && j >= 0) {
          const v = grid[i][j];
          hoverRing.position.copy(hit.point);
          hoverRing.position.y = yOf(v) + 0.01;
          (hoverRing.material as THREE.MeshBasicMaterial).opacity = 0.7;
          if (v !== hover?.v || p !== hover?.p || o !== hover?.o) {
            setHover({ p, o, v });
          }
        }
      } else {
        (hoverRing.material as THREE.MeshBasicMaterial).opacity = 0;
      }
      s.controls.update();
      s.renderer.render(s.scene, s.camera);
      s.frame = requestAnimationFrame(tick);
    };
    tick();

    const resize = () => {
      const s = sceneRef.current;
      if (!s) return;
      const w = host.clientWidth;
      const h = host.clientHeight;
      if (w === 0 || h === 0) return;
      s.renderer.setSize(w, h, false);
      s.camera.aspect = w / h;
      s.camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(host);

    const onMove = (e: PointerEvent) => {
      const rect = host.getBoundingClientRect();
      pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    };
    const onLeave = () => { pointer.set(-2, -2); };
    host.addEventListener("pointermove", onMove);
    host.addEventListener("pointerleave", onLeave);

    return () => {
      host.removeEventListener("pointermove", onMove);
      host.removeEventListener("pointerleave", onLeave);
      ro.disconnect();
      const s = sceneRef.current;
      if (s) cancelAnimationFrame(s.frame);
      scene.traverse((obj) => {
        const m = obj as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose();
      });
      hatchTex.dispose();
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === host) host.removeChild(renderer.domElement);
      sceneRef.current = null;
    };
  }, [trade, webglError, showGhost]);

  // ------------------------------------------------------------ marker sync
  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    const { ps, o2s, grid, axes, marker } = s;
    const clampNearest = (arr: number[], v: number) =>
      arr.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a));
    const p = clampNearest(ps, pressure);
    const o = clampNearest(o2s, Math.min(45, o2));
    const i = ps.indexOf(p);
    const j = o2s.indexOf(o);
    const y = (grid[i][j] / 100) * HEIGHT;
    const pos = s.marker.position;
    pos.set(axes.x(p), y + 0.045, axes.z(o));
    const ball = marker.children[0] as THREE.Mesh;
    const ring = marker.children[1] as THREE.Mesh;
    const stem = marker.children[2] as THREE.Mesh;
    ball.position.set(0, 0, 0);
    ring.position.set(0, -y - 0.045, 0);
    stem.position.set(0, -y / 2 - 0.0225, 0);
    stem.scale.set(1, Math.max(0.001, y), 1);
  }, [pressure, o2]);

  useEffect(() => {
    const s = sceneRef.current;
    if (s) s.controls.autoRotate = autoRotate;
  }, [autoRotate]);

  const resetView = () => {
    const s = sceneRef.current;
    if (!s) return;
    s.camera.position.copy(HOME.pos);
    s.controls.target.copy(HOME.target);
    s.controls.update();
  };

  const exportPng = () => {
    const s = sceneRef.current;
    if (!s) return;
    s.renderer.render(s.scene, s.camera);
    const url = s.renderer.domElement.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url;
    a.download = `flare-hazard-terrain-${pressure}psia-${o2}pct.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className={`relative ${className}`}>
      <div ref={hostRef} className="w-full h-[420px] rounded-lg overflow-hidden bg-slate-950"
        role="img"
        aria-label="3D surface of the ignition index over total pressure and oxygen concentration, with the limiting-oxygen-concentration boundary as a white ridge and a hatched vertical face where the fitted pressure envelope ends" />
      {webglError && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-amber-300 bg-slate-950/90 p-6 text-center">
          3D view unavailable on this device ({webglError}). The same field is on the Trade Space
          screen as a 2D map.
        </div>
      )}
      <div className="absolute top-2 left-3 text-[10px] text-slate-400 font-mono leading-4 pointer-events-none">
        <div>↑ ignition index (relative 0-100)</div>
        <div>pressure → / O₂ ↘</div>
      </div>
      <div className="absolute top-2 right-3 flex items-center gap-2">
        <span className="text-[10px] font-mono text-slate-500">{fps != null ? `${fps} fps` : ""}</span>
        <button type="button" onClick={() => setAutoRotate((v) => !v)}
          className="text-[11px] px-2 py-1 rounded border border-slate-700 bg-slate-900/80 hover:bg-slate-800 text-slate-300">
          {autoRotate ? "⏸ stop rotation" : "▶ auto-rotate"}
        </button>
        <button type="button" onClick={() => setShowGhost((v) => !v)}
          disabled={trade.ghost_grid_1g == null}
          title={trade.ghost_grid_1g == null
            ? "1g comparison surface not loaded"
            : "Overlay the same ignition field computed at 1g, to see the microgravity boundary stand apart"}
          className={`text-[11px] px-2 py-1 rounded border bg-slate-900/80 text-slate-300 ${
            showGhost ? "border-sky-500 text-sky-200" : "border-slate-700 hover:bg-slate-800"
          } ${trade.ghost_grid_1g == null ? "opacity-40 cursor-not-allowed" : ""}`}>
          👻 1g ghost
        </button>
        <button type="button" onClick={resetView}
          className="text-[11px] px-2 py-1 rounded border border-slate-700 bg-slate-900/80 hover:bg-slate-800 text-slate-300">
          ⤾ reset view
        </button>
        <button type="button" onClick={exportPng}
          className="text-[11px] px-2 py-1 rounded border border-slate-700 bg-slate-900/80 hover:bg-slate-800 text-slate-300">
          ⬇ PNG
        </button>
      </div>
      {hover && (
        <div className="absolute bottom-8 left-3 rounded border border-slate-700 bg-slate-900/85 px-2 py-1
                        text-[11px] font-mono text-slate-200 pointer-events-none">
          P {hover.p.toFixed(1)} psia · O₂ {hover.o.toFixed(1)}% · ignition {hover.v.toFixed(1)}
        </div>
      )}
      <div className="absolute bottom-2 left-3 text-[10px] text-slate-400 pointer-events-none">
        white beads = LOC boundary · hatched face = outside the fitted envelope (no data)
      </div>
    </div>
  );
}
