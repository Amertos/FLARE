import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { AtmosphereParams, FlameResponse } from "../api";
import { webglSupport } from "./webgl";

type Phase = "idle" | "burning" | "stalled" | "extinguished";

const PANEL_W = 2.3;
const PANEL_H = 0.95;
/** Relative units per second at 100% of the reference front speed. */
const SPEED_SCALE = 0.75;
/** Number of particles per pool — embers + sparks share the budget. */
const N_EMBERS = 90;
const N_STREAMERS = 40;

function makeTeardrop(geometry: THREE.SphereGeometry, teardrop: number, radius: number) {
  const pos = geometry.attributes.position as THREE.BufferAttribute;
  const base = geometry.userData.base as Float32Array | undefined;
  if (!base) return;
  for (let i = 0; i < pos.count; i++) {
    const x0 = base[i * 3];
    const y0 = base[i * 3 + 1];
    const z0 = base[i * 3 + 2];
    const up = Math.max(0, y0);
    // Buoyancy stretches the plume upward and tapers it; without buoyancy the
    // shape stays round (NASA SVS 11640; dossier §4.2.1).
    const taper = 1 - 0.6 * Math.pow(up, 1.35) * teardrop;
    const stretch = 1 + 0.95 * up * teardrop;
    pos.setXYZ(i, x0 * taper * radius, y0 * stretch * radius, z0 * taper * radius);
  }
  pos.needsUpdate = true;
  geometry.computeVertexNormals();
}

/** Emissive point sprite, generated once per scene (no texture file needed). */
function makeSpriteTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 32;
  c.height = 32;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.35, "rgba(255,255,255,0.55)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 32, 32);
  return new THREE.CanvasTexture(c);
}

/**
 * The fire in freefall.
 *
 * Engine-driven view. The front advances across the sample at a rate set by
 * the relative front speed, the flame morphs between a sphere (no buoyancy)
 * and a teardrop (buoyant plume), ember particles are recycled into the flame
 * (buoyant) or drift outward (µg), streamers show the airflow regime from the
 * engine's flow-regime bands, and the whole thing DIES below the effective LOC
 * — with a qualitative cool-flame ghost where the engine says one is possible
 * in µg (FL4/FL5). Schematic of the published regimes, not a CFD result (L8).
 */
export default function FlameChamber({
  flame,
  atmosphere,
}: {
  flame: FlameResponse;
  atmosphere: AtmosphereParams;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<{
    renderer: THREE.WebGLRenderer;
    camera: THREE.PerspectiveCamera;
    scene: THREE.Scene;
    frame: number;
    flameMesh: THREE.Mesh;
    halo: THREE.Mesh;
    front: THREE.Mesh;
    burn: THREE.Mesh;
    embers: THREE.Points;
    emberState: { x: number; y: number; z: number; vx: number; vy: number; vz: number; life: number }[];
    streamers: THREE.Points;
    streamerState: { x: number; y: number; z: number; speed: number }[];
    ghost: THREE.Mesh;
    propagation: THREE.Group;
    contours: THREE.Group;
    tick: (dt: number) => void;
    fire: (on: boolean) => void;
  } | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [fps, setFps] = useState<number | null>(null);
  // Probed during the first render so the fallback can render in the same
  // pass, without an effect that schedules a second one.
  const [error] = useState<string | null>(() => webglSupport());
  const stateRef = useRef({ phase: "idle" as Phase, front: 0, elapsed: 0, fade: 1, ghostT: 0 });

  const sustained = flame.fate.code === "sustained";
  const marginal = flame.fate.code === "marginal";
  const buoyant = flame.regime.buoyant_convection;
  const blue = flame.regime.colour_tendency.includes("blue");
  const coolPossible = flame.cool_flame_phase?.possible ?? false;
  const scale = flame.flow_regime?.streamer_speed_scale ?? 0;
  const flameTint = useMemo(() => blue ? 0x60a5fa : 0xfb923c, [blue]);
  const glowTint = useMemo(() => blue ? 0x3b82f6 : 0xf97316, [blue]);

  // ------------------------------------------------------------------ scene
  useEffect(() => {
    const host = hostRef.current;
    if (!host || error) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    } catch (err) {
      console.warn("chamber: WebGL renderer unavailable", err);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(new THREE.Color("#020617"), 1);
    // Slight blue rim on the idle scene so the empty chamber doesn't read as flat.
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    host.appendChild(renderer.domElement);
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x020617, 3.2, 7);
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(0, 0.55, 3.15);
    camera.lookAt(0, 0.1, 0);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x0f172a, 0.9));
    const key = new THREE.DirectionalLight(0xffffff, 1.2);
    key.position.set(2, 3, 3);
    scene.add(key);
    const fireLight = new THREE.PointLight(glowTint, 0, 3.2, 2);
    fireLight.position.copy(new THREE.Vector3(-0.15, 0.42, 0.16));
    scene.add(fireLight);

    // burner: small glowing disc at the flame base, visible when ignited
    const burner = new THREE.Mesh(
      new THREE.CylinderGeometry(0.07, 0.09, 0.035, 16),
      new THREE.MeshBasicMaterial({ color: 0x334155 }),
    );
    burner.position.set(-0.15, 0.16, 0.16);
    scene.add(burner);

    // chamber: an open wireframe tube with ribs
    const tube = new THREE.Mesh(
      new THREE.CylinderGeometry(1.25, 1.25, 2.7, 28, 1, true).rotateZ(Math.PI / 2),
      new THREE.MeshBasicMaterial({ color: 0x334155, wireframe: true, transparent: true, opacity: 0.5 }),
    );
    scene.add(tube);

    // sample panel
    const panel = new THREE.Mesh(
      new THREE.PlaneGeometry(PANEL_W, PANEL_H),
      new THREE.MeshLambertMaterial({ color: 0x1e293b, side: THREE.DoubleSide }),
    );
    panel.position.y = 0.05;
    scene.add(panel);
    const panelEdge = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.PlaneGeometry(PANEL_W, PANEL_H)),
      new THREE.LineBasicMaterial({ color: 0x64748b }),
    );
    panelEdge.position.copy(panel.position);
    scene.add(panelEdge);

    // fire front: a ring that expands from the ignition edge, plus the burned area
    const frontColour = new THREE.Color(sustained ? "#f97316" : marginal ? "#facc15" : "#38bdf8");
    const front = new THREE.Mesh(
      new THREE.RingGeometry(0.94, 1.0, 64, 1, -Math.PI / 2, Math.PI),
      new THREE.MeshBasicMaterial({ color: frontColour, side: THREE.DoubleSide }),
    );
    front.position.set(-PANEL_W / 2, 0.05, 0.012);
    scene.add(front);
    const burn = new THREE.Mesh(
      new THREE.CircleGeometry(1, 48, -Math.PI / 2, Math.PI),
      new THREE.MeshBasicMaterial({ color: 0x7c2d12, transparent: true, opacity: 0 }),
    );
    burn.position.set(-PANEL_W / 2, 0.05, 0.008);
    scene.add(burn);

    // flame: sphere in microgravity, teardrop where buoyancy exists
    const radius = 0.26;
    const geo = new THREE.SphereGeometry(1, 32, 24);
    geo.userData.base = Float32Array.from(geo.attributes.position.array);
    const flameMesh = new THREE.Mesh(
      geo,
      new THREE.MeshBasicMaterial({
        color: flameTint,
        transparent: true,
        opacity: 0.95,
      }),
    );
    flameMesh.position.set(-0.15, 0.42, 0.16);
    scene.add(flameMesh);
    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(radius * 1.75, 24, 18),
      new THREE.MeshBasicMaterial({
        color: glowTint,
        transparent: true,
        opacity: 0.18,
        blending: THREE.AdditiveBlending,
      }),
    );
    halo.position.copy(flameMesh.position);
    scene.add(halo);

    // cool-flame ghost: faint large sphere, PALISH blue, additive; rendered
    // where the engine says a µg cool-flame phase is possible (FL4/FL5) and
    // never opacity > 0.25 so it stays obviously schematic.
    const ghost = new THREE.Mesh(
      new THREE.SphereGeometry(radius * 1.25, 20, 14),
      new THREE.MeshBasicMaterial({
        color: 0x67e8f9,
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    ghost.position.copy(flameMesh.position);
    scene.add(ghost);

    // Front-propagation vector: an arrow along +x whose LENGTH updates from
    // the engine's relative front speed — longer arrow = faster advance. It
    // explains WHY the front reaches the far edge or dies, in geometry.
    const propagation = new THREE.Group();
    const shaft = new THREE.Mesh(
      new THREE.CylinderGeometry(0.008, 0.008, 1, 6).rotateZ(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ color: 0xf97316, transparent: true, opacity: 0.85 }),
    );
    shaft.scale.x = 1;
    const head = new THREE.Mesh(
      new THREE.ConeGeometry(0.028, 0.08, 10).rotateZ(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ color: 0xf97316, transparent: true, opacity: 0.85 }),
    );
    propagation.add(shaft, head);
    propagation.position.set(-0.15, 0.16, -0.35);
    scene.add(propagation);

    // Thermal-contour iso-lines over the burned area: rings at fixed spread
    // fractions; when the front stalls, the stall line lights up red.
    const contours = new THREE.Group();
    for (let k = 1; k <= 4; k++) {
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.94 + k * 0.006, 0.965 + k * 0.006, 48, 1,
          -Math.PI / 2, Math.PI),
        new THREE.MeshBasicMaterial({ color: 0xfb923c, side: THREE.DoubleSide,
          transparent: true, opacity: 0 }),
      );
      ring.position.set(-PANEL_W / 2, 0.05, 0.014);
      ring.userData.k = k;
      contours.add(ring);
    }
    scene.add(contours);

    // ember particles: recycled from flame origin or downward where buoyancy exists
    const spriteTex = makeSpriteTexture();
    const emberPos = new Float32Array(N_EMBERS * 3);
    const emberCol = new Float32Array(N_EMBERS * 3);
    const emberSize = new Float32Array(N_EMBERS);
    const emberState = Array.from({ length: N_EMBERS }, () =>
      ({ x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, life: 0 }));
    const emberGeo = new THREE.BufferGeometry();
    emberGeo.setAttribute("position", new THREE.BufferAttribute(emberPos, 3));
    emberGeo.setAttribute("color", new THREE.BufferAttribute(emberCol, 3));
    emberGeo.setAttribute("size", new THREE.BufferAttribute(emberSize, 1));
    const embers = new THREE.Points(emberGeo, new THREE.ShaderMaterial({
      uniforms: { spriteTex: { value: spriteTex } },
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: `
        attribute float size; varying vec3 vColor;
        void main() {
          vColor = color;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * (140.0 / -mv.z);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform sampler2D spriteTex; varying vec3 vColor;
        void main() { gl_FragColor = vec4(vColor, 1.0) * texture2D(spriteTex, gl_PointCoord); }`,
    }));
    scene.add(embers);

    // airflow streamers: move along +x at rates set by the engine's flow band
    const streamerPos = new Float32Array(N_STREAMERS * 3);
    const streamerCol = new Float32Array(N_STREAMERS * 3);
    const streamerSize = new Float32Array(N_STREAMERS);
    const streamerState = Array.from({ length: N_STREAMERS }, () => {
      const y = 0.1 + Math.random() * 0.75;
      const z = -0.6 + Math.random() * 1.4;
      const x = -1.1 + Math.random() * 2.2;
      return { x, y, z, speed: 0.4 + Math.random() * 0.25 };
    });
    streamerState.forEach((s, i) => {
      streamerPos[i * 3] = s.x; streamerPos[i * 3 + 1] = s.y; streamerPos[i * 3 + 2] = s.z;
      streamerCol[i * 3] = 0.55; streamerCol[i * 3 + 1] = 0.65; streamerCol[i * 3 + 2] = 0.85;
      streamerSize[i] = 0.09 + Math.random() * 0.06;
    });
    const streamerGeo = new THREE.BufferGeometry();
    streamerGeo.setAttribute("position", new THREE.BufferAttribute(streamerPos, 3));
    streamerGeo.setAttribute("color", new THREE.BufferAttribute(streamerCol, 3));
    streamerGeo.setAttribute("size", new THREE.BufferAttribute(streamerSize, 1));
    const streamers = new THREE.Points(streamerGeo, new THREE.ShaderMaterial({
      uniforms: { spriteTex: { value: spriteTex } },
      vertexColors: true,
      transparent: true,
      opacity: 0.7,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: `
        attribute float size; varying vec3 vColor;
        void main() {
          vColor = color;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * (140.0 / -mv.z);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform sampler2D spriteTex; varying vec3 vColor;
        void main() { gl_FragColor = vec4(vColor, 1.0) * texture2D(spriteTex, gl_PointCoord) * 0.55; }`,
    }));
    scene.add(streamers);

    const rate = Math.max(0, flame.front_speed_relative) / 100;
    const teardrop = buoyant ? 1 : 0;

    const tick = (dt: number) => {
      const st = stateRef.current;
      // propagation arrow: visible while burning, length ∝ engine front rate
      const pAlive = st.phase === "burning";
      propagation.visible = pAlive;
      if (pAlive) {
        const len = 0.35 + rate * 0.9;  // engine-driven, relative units
        shaft.scale.x = len;
        shaft.position.x = len / 2;
        head.position.x = len;
      }
      // thermal contours: opacity follows the front position; the stall line
      // (last ring in a stalled/sub-LOC state) turns red
      contours.children.forEach((ring, idx) => {
        const r = ring as THREE.Mesh;
        const mat = r.material as THREE.MeshBasicMaterial;
        if (st.phase === "burning" && st.front > 0.05) {
          const frac = Math.max(0, 1 - Math.abs(st.front - ring.userData.k * 0.25) * 4);
          mat.opacity = frac * 0.42;
          mat.color.set(marginal && idx === 3 ? 0xef4444 : 0xfb923c);
        } else {
          mat.opacity = 0;
        }
      });
      // --- front / flame update
      if (st.phase === "burning") {
        st.elapsed += dt;
        const cap = sustained ? 1.0 : 0.42; // a sub-LOC front stalls early
        const next = st.front + rate * SPEED_SCALE * dt;
        st.front = Math.min(cap, next);
        if (!sustained && st.front >= cap - 1e-3) {
          st.phase = "stalled";
          setPhase("stalled");
        }
      } else if (st.phase === "stalled") {
        st.elapsed += dt;
        const t = Math.min(1, (st.elapsed - 0.2) / 1.1);
        st.fade = 1 - t;
        st.ghostT = Math.max(0, Math.min(1, st.ghostT + dt * 0.35));
        if (t >= 1) {
          st.phase = "extinguished";
          setPhase("extinguished");
        }
      }
      const st2 = stateRef.current;
      front.scale.setScalar(Math.max(0.001, st2.front));
      burn.scale.setScalar(Math.max(0.001, st2.front));
      (burn.material as THREE.MeshBasicMaterial).opacity = 0.55 * st2.front;
      front.visible = st2.phase !== "idle" && st2.front > 0.02;

      const alive = st2.phase !== "extinguished" && st2.phase !== "idle";
      const wobble = 1 + Math.sin(st2.elapsed * 9) * 0.045 + Math.sin(st2.elapsed * 21) * 0.02;
      const size = (alive ? (marginal ? 0.55 : 0.95) : 0) * st2.fade * wobble;
      // flow lean: the flame bends downstream with the imposed flow (FL2)
      const lean = alive && !buoyant ? Math.min(0.22, scale * 0.3) : 0;
      // The core geometry is built at unit radius (so the teardrop reshape is
      // resolution-independent); scale it by the declared physical radius.
      // Without this the core came out 4x its own halo and poked through the
      // chamber wall.
      const core = Math.max(0.001, size * radius);
      flameMesh.scale.set(core * (1 + lean * 0.3), core, core);
      halo.scale.setScalar(Math.max(0.001, size));
      flameMesh.position.x = -0.15 + lean * st2.fade;
      (flameMesh.material as THREE.MeshBasicMaterial).opacity = 0.95 * st2.fade;
      (halo.material as THREE.MeshBasicMaterial).opacity = 0.18 * st2.fade;
      flameMesh.rotation.y += dt * 0.6;
      // flicker upward in a buoyant plume, quiver in place without one
      flameMesh.position.y = 0.42 + (teardrop ? 0.05 : 0.012) * Math.sin(st2.elapsed * 6);
      halo.position.copy(flameMesh.position);
      fireLight.intensity = alive ? 2.2 * st2.fade * (marginal ? 0.55 : 1) : Math.max(0, fireLight.intensity - dt * 3);
      fireLight.position.set(flameMesh.position.x, flameMesh.position.y, flameMesh.position.z);
      (burner.material as THREE.MeshBasicMaterial).color.setScalar(
        alive ? 0.35 + st2.fade * 0.45 : 0.2);

      // --- embers
      if (alive) {
        for (const e of emberState) {
          e.life -= dt / 1.6;
          if (e.life <= 0) {
            e.life = 0.4 + Math.random() * 0.8;
            e.x = flameMesh.position.x;
            e.y = flameMesh.position.y - 0.03;
            e.z = flameMesh.position.z;
            // buoyant plume: embers ride up strongly; µg: they spread outward slowly
            e.vx = (Math.random() - 0.5) * 0.35 + lean * 0.9;
            e.vy = (teardrop ? 0.8 : 0.12) + Math.random() * 0.3 + lean * 0.3;
            e.vz = (Math.random() - 0.5) * 0.35;
          }
          e.x += e.vx * dt;
          e.y += e.vy * dt;
          e.z += e.vz * dt;
          if (teardrop) e.vy -= dt * 0.35; // buoyancy weakens as they rise
        }
      } else {
        emberState.forEach((e) => { e.life = Math.max(0, e.life - dt * 2); });
      }
      const ep = emberGeo.attributes.position as THREE.BufferAttribute;
      const ec = emberGeo.attributes.color as THREE.BufferAttribute;
      const es = emberGeo.attributes.size as THREE.BufferAttribute;
      for (let i = 0; i < emberState.length; i++) {
        const e = emberState[i];
        ep.setXYZ(i, e.x, e.y, e.z);
        const l = Math.min(1, e.life);
        ec.setXYZ(i, l * 1.0, l * 0.55, l * 0.25);
        // Point size in the sprite shader is size * (140 / distance): at 0.01-
        // 0.07 the embers were sub-pixel and the HUD's "embers recycled" line
        // was visually a lie. 0.10-0.16 lands at 4-7 px at the camera distance.
        es.setX(i, 0.13 * l + 0.03);
      }
      ep.needsUpdate = true;
      ec.needsUpdate = true;
      es.needsUpdate = true;

      // --- airflow streamers, always moving at the engine's band rate
      const sp = streamerGeo.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < streamerState.length; i++) {
        const s = streamerState[i];
        s.x += s.speed * scale * dt * 1.4;
        if (s.x > 1.15) { s.x = -1.15; }
        sp.setXYZ(i, s.x, s.y, s.z);
      }
      sp.needsUpdate = true;
      (streamers.material as THREE.ShaderMaterial).opacity = 0.7 * (scale > 0.1 ? 1 : 0.2);

      // --- cool-flame ghost, gated by the engine flag and the fade
      const targetGhost = (coolPossible && (st2.phase === "stalled" || st2.phase === "extinguished"))
        ? st2.ghostT * 0.22 : 0;
      const gm = ghost.material as THREE.MeshBasicMaterial;
      gm.opacity += (targetGhost - gm.opacity) * Math.min(1, dt * 2.5);
      ghost.position.set(flameMesh.position.x, flameMesh.position.y - 0.02, flameMesh.position.z);
      ghost.scale.setScalar(1 + Math.sin(st2.elapsed * 3) * 0.04);
    };

    const fire = (on: boolean) => {
      const st = stateRef.current;
      st.phase = on ? "burning" : "idle";
      st.front = on ? 0.02 : 0;
      st.elapsed = 0;
      st.fade = 1;
      st.ghostT = 0;
      setPhase(st.phase);
      setElapsed(0);
    };

    sceneRef.current = { renderer, camera, scene, frame: 0, flameMesh, halo, front, burn,
      embers, emberState, streamers, streamerState, ghost, propagation, contours,
      tick, fire };

    let last = performance.now();
    let windowStart = performance.now();
    let frames = 0;
    const loop = () => {
      const s = sceneRef.current;
      if (!s) return;
      const now = performance.now();
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      // Wall-clock fps window — see HazardTerrain: a dt-accumulated counter
      // reads ~1e5 fps on throttled rAF loops.
      frames++;
      if (now - windowStart > 500) {
        setFps(Math.round((frames * 1000) / (now - windowStart)));
        frames = 0;
        windowStart = now;
      }
      s.tick(dt);
      s.renderer.render(s.scene, s.camera);
      s.frame = requestAnimationFrame(loop);
    };
    loop();

    const resize = () => {
      const s = sceneRef.current;
      if (!s) return;
      const w = host.clientWidth;
      const h = host.clientHeight;
      if (!w || !h) return;
      s.renderer.setSize(w, h, false);
      s.camera.aspect = w / h;
      s.camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(host);

    return () => {
      ro.disconnect();
      if (sceneRef.current) cancelAnimationFrame(sceneRef.current.frame);
      scene.traverse((obj) => {
        const m = obj as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose();
      });
      spriteTex.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === host) host.removeChild(renderer.domElement);
      sceneRef.current = null;
    };
    // the flame colour and shape follow the atmosphere, so rebuild on change
  }, [flame, marginal, sustained, error, glowTint, flameTint, buoyant, coolPossible, scale]);

  // reshape the flame when the regime changes
  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    const geo = s.flameMesh.geometry as THREE.SphereGeometry;
    makeTeardrop(geo, flame.regime.buoyant_convection ? 1 : 0, 1);
  }, [flame.regime.buoyant_convection]);

  // restart the burn whenever the atmosphere changes
  const atmKey = `${atmosphere.pressure}|${atmosphere.o2}|${atmosphere.gravity}|${atmosphere.flow}|${atmosphere.temperature}|${atmosphere.material}`;
  useEffect(() => {
    sceneRef.current?.fire(false);
  }, [atmKey]);

  // Ignite / reset from the keyboard, as the button labels promise. Ignored
  // while the user is typing in one of the console's inputs.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)) return;
      if (e.key === "f" || e.key === "F") sceneRef.current?.fire(true);
      if (e.key === "r" || e.key === "R") sceneRef.current?.fire(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (phase !== "burning" && phase !== "stalled") return;
    const id = window.setInterval(() => setElapsed(stateRef.current.elapsed), 100);
    return () => window.clearInterval(id);
  }, [phase]);

  return (
    <div className="space-y-2">
      <div className="relative">
        <div ref={hostRef} className="w-full h-[300px] rounded-lg overflow-hidden bg-slate-950"
          role="img"
          aria-label={`Schematic flame chamber: ${flame.regime.label}; ${flame.fate.label}; airflow ${flame.flow_regime?.band ?? "n/a"}`} />
        {error && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-amber-300 bg-slate-950/90 p-6 text-center">
            3D view unavailable on this device ({error}). The numbers are below.
          </div>
        )}
        <div className="absolute top-2 left-3 text-[10px] font-mono text-slate-400 pointer-events-none">
          <div>{flame.regime.shape === "spherical" ? "◯ spherical — no buoyancy" : "△ teardrop — buoyant plume"}</div>
          <div>{flame.regime.colour_tendency}</div>
          <div>airflow: {flame.flow_regime?.band ?? "n/a"} · embers recycled per frame</div>
          <div className="text-slate-500">schematic · time is presentation-clock, not seconds of experiment</div>
        </div>
        {/* Mission-control HUD: live engine telemetry, NASA-control-room style. */}
        <div className="absolute bottom-2 right-3 text-right text-[10px] font-mono text-cyan-300/90 pointer-events-none leading-4"
          aria-live="off">
          <div className="border border-cyan-900/60 bg-slate-950/60 rounded px-2 py-1">
            <div>P&nbsp;&nbsp;{atmosphere.pressure.toFixed(1)} psia · pO₂ {flame.hazard.crew.po2_psia.toFixed(2)}</div>
            <div>O₂&nbsp;{atmosphere.o2.toFixed(1)}% · LOC {flame.hazard.effective_loc_pct.toFixed(2)}%</div>
            <div>v&nbsp;&nbsp;{atmosphere.flow.toFixed(2)} m/s · g&nbsp;&nbsp;{atmosphere.gravity}</div>
            <div className={flame.hazard.margin_above_loc_pct > 0 ? "text-orange-400" : "text-emerald-400"}>
              margin {flame.hazard.margin_above_loc_pct > 0 ? "+" : ""}{flame.hazard.margin_above_loc_pct.toFixed(2)} pt
            </div>
          </div>
        </div>
        <div className="absolute top-2 right-3 text-[10px] font-mono text-slate-500 pointer-events-none">
          {fps != null && fps < 5000 ? `${fps} fps` : ""}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => sceneRef.current?.fire(true)}
          className="text-sm font-semibold px-3 py-1.5 rounded bg-orange-600 hover:bg-orange-500">
          🔥 Ignite (F)
        </button>
        <button type="button" onClick={() => sceneRef.current?.fire(false)}
          className="text-xs px-3 py-1.5 rounded border border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-300">
          reset (R)
        </button>
        <span className="text-xs font-mono text-slate-400">
          front {flame.front_speed_relative.toFixed(0)}% of the {flame.reference.experiment_id} anchor
        </span>
      </div>

      <div className="text-xs space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`px-2 py-0.5 rounded border font-mono text-[10px] ${
            sustained ? "bg-red-950/60 text-red-300 border-red-800"
            : marginal ? "bg-amber-950/60 text-amber-300 border-amber-800"
            : "bg-emerald-950/60 text-emerald-300 border-emerald-800"}`}>
            {flame.fate.label}
          </span>
          {(flame.cool_flame_phase?.possible ?? false) && (
            <span className="px-2 py-0.5 rounded border font-mono text-[10px] border-cyan-700 bg-cyan-950/50 text-cyan-300"
              title={flame.cool_flame_phase.note}>
              cool-flame phase possible (qualitative)
            </span>
          )}
          <span className="text-slate-400">
            {phase === "idle" ? "press Ignite to run the front across the sample"
              : phase === "burning" ? `front advancing · t ${elapsed.toFixed(1)}`
              : phase === "stalled" ? `front stalled at t ${elapsed.toFixed(1)} — out of fuel/flow`
              : `extinguished at t ${elapsed.toFixed(1)}`}
          </span>
        </div>
        <p className="text-slate-400 leading-relaxed">{flame.fate.detail}</p>
        <p className="text-slate-500 leading-relaxed">{flame.regime.note}</p>
        {(flame.cool_flame_phase?.possible ?? false) && (
          <p className="text-[11px] text-cyan-200/70 leading-relaxed">{flame.cool_flame_phase.note}</p>
        )}
      </div>
    </div>
  );
}
