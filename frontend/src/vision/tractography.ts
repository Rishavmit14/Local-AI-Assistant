import { BufferGeometry, Float32BufferAttribute, Vector3 } from "three";

const LONGITUDINAL = 192;
const RING = 144;
const SEGMENTS = 72;
type Family = 0 | 1 | 2;
type Channels = { position: number[]; progress: number[]; phase: number[]; bundle: number[] };

function seeded(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function channels(): Channels {
  return { position: [], progress: [], phase: [], bundle: [] };
}

function geometryFrom(data: Channels): BufferGeometry {
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(data.position, 3));
  geometry.setAttribute("aProgress", new Float32BufferAttribute(data.progress, 1));
  geometry.setAttribute("aPhase", new Float32BufferAttribute(data.phase, 1));
  geometry.setAttribute("aBundle", new Float32BufferAttribute(data.bundle, 1));
  geometry.computeBoundingSphere();
  return geometry;
}

/**
 * One-time white-matter-inspired geometry, in the cortex generator's coordinates.
 * X is bilateral, +Y superior, +Z anterior. This is a visual model, not tract data.
 * tracts is unindexed LineSegments geometry; nuclei is Points geometry.
 * aBundle: 0 association, 1 commissural, 2 projection. aPhase is a bundle seed 0..1.
 */
export function buildTractography(hemispheres: BufferGeometry[]): {
  tracts: BufferGeometry;
  nuclei: BufferGeometry;
} {
  if (hemispheres.length !== 2) throw new Error("Tractography requires both cortical hemispheres.");
  for (const hemisphere of hemispheres) {
    if (hemisphere.getAttribute("position").count !== (LONGITUDINAL + 1) * (RING + 1)) {
      throw new Error("Tractography requires the 192 × 144 anatomical cortex grid.");
    }
  }
  // Order by the outer mid-coronal vertex, independent of the caller's lobe order.
  const lobes = [...hemispheres].sort((a, b) =>
    a.getAttribute("position").getX(96 * 145 + 36) - b.getAttribute("position").getX(96 * 145 + 36),
  );
  const random = seeded(0x46524944);
  const jitter = (width: number) => (random() + random() + random() - 1.5) * width;
  const tractData = channels();
  const nucleiData = channels();

  // Bilinear samples preserve the actual folded surface, including asymmetric lobes.
  // Endpoints use the superior/lateral/temporal arc, never the broad medial wall.
  const surface = (hemisphere: BufferGeometry, u: number, ring: number): Vector3 => {
    const row = Math.max(1, Math.min(LONGITUDINAL - 1, u * LONGITUDINAL));
    const arc = Math.max(3, Math.min(72, ring));
    const i = Math.floor(row);
    const j = Math.floor(arc);
    const du = row - i;
    const dv = arc - j;
    const position = hemisphere.getAttribute("position");
    const point = new Vector3();
    for (let di = 0; di < 2; di++) {
      for (let dj = 0; dj < 2; dj++) {
        const index = (i + di) * (RING + 1) + j + dj;
        const weight = (di ? du : 1 - du) * (dj ? dv : 1 - dv);
        point.x += position.getX(index) * weight;
        point.y += position.getY(index) * weight;
        point.z += position.getZ(index) * weight;
      }
    }
    return point;
  };

  const appendPoint = (data: Channels, point: Vector3, progress: number, phase: number, family: Family) => {
    data.position.push(point.x, point.y, point.z);
    data.progress.push(progress);
    data.phase.push(phase);
    data.bundle.push(family);
  };

  const fiber = (p0: Vector3, p1: Vector3, p2: Vector3, p3: Vector3, phase: number, family: Family) => {
    // Cubic Bézier stays inside its control hull, avoiding Catmull-Rom overshoot.
    const evaluate = (t: number) => {
      const s = 1 - t;
      return new Vector3()
        .addScaledVector(p0, s * s * s)
        .addScaledVector(p1, 3 * s * s * t)
        .addScaledVector(p2, 3 * s * t * t)
        .addScaledVector(p3, t * t * t);
    };
    let previous = p0;
    for (let segment = 1; segment <= SEGMENTS; segment++) {
      const next = evaluate(segment / SEGMENTS);
      appendPoint(tractData, previous, (segment - 1) / SEGMENTS, phase, family);
      appendPoint(tractData, next, segment / SEGMENTS, phase, family);
      previous = next;
    }
  };

  // Four longitudinal systems per lobe: superior, middle, temporal and crown.
  // Shared guide corridors give each family a readable sweep, with fine fascicles.
  const association = [
    { back: 0.17, front: 0.84, ringBack: 27, ringFront: 25, height: 0.30, depth: 0.76 },
    { back: 0.20, front: 0.82, ringBack: 51, ringFront: 24, height: 0.17, depth: 0.64 },
    { back: 0.29, front: 0.79, ringBack: 59, ringFront: 61, height: -0.025, depth: 0.72 },
    { back: 0.23, front: 0.77, ringBack: 14, ringFront: 17, height: 0.36, depth: 0.72 },
  ];
  for (const hemisphere of lobes) {
    for (const corridor of association) {
      const phase = random();
      for (let strand = 0; strand < 36; strand++) {
        const lane = jitter(0.016);
        const p0 = surface(hemisphere, corridor.back + jitter(0.022), corridor.ringBack + jitter(2.4));
        const p3 = surface(hemisphere, corridor.front + jitter(0.022), corridor.ringFront + jitter(2.4));
        const p1 = p0.clone().lerp(p3, 0.27);
        const p2 = p0.clone().lerp(p3, 0.73);
        p1.x *= corridor.depth;
        p2.x *= corridor.depth * 0.84;
        p1.y = corridor.height + lane;
        p2.y = corridor.height + lane * 0.85 + 0.038;
        fiber(p0, p1, p2, p3, (phase + jitter(0.035) + 1) % 1, 0);
      }
    }
  }

  // Six callosal sheets bridge homologous cortical territories through the core.
  // They fan anterior/posterior and arch superiorly without leaving the envelope.
  for (let bundle = 0; bundle < 6; bundle++) {
    const phase = random();
    const u = 0.25 + bundle * 0.095;
    const ring = 27 + Math.sin(bundle * 0.8) * 9;
    for (let strand = 0; strand < 42; strand++) {
      const row = u + jitter(0.019);
      const arc = ring + jitter(2.5);
      const p0 = surface(lobes[0], row, arc);
      const p3 = surface(lobes[1], row + jitter(0.006), arc + jitter(0.8));
      const z = (p0.z + p3.z) * 0.5;
      const height = 0.25 + Math.sin(bundle / 5 * Math.PI) * 0.065 + jitter(0.012);
      const p1 = new Vector3(-0.10 + jitter(0.008), height, z + jitter(0.011));
      const p2 = new Vector3(0.10 + jitter(0.008), height, z + jitter(0.011));
      fiber(p0, p1, p2, p3, (phase + jitter(0.025) + 1) % 1, 1);
    }
  }

  // Three projection fans per lobe: posterior, superior and anterior territories.
  // Their aligned lower origin reads as an internal capsule, not a random hub.
  for (let side = 0; side < 2; side++) {
    const sign = side === 0 ? -1 : 1;
    for (let bundle = 0; bundle < 3; bundle++) {
      const phase = random();
      for (let strand = 0; strand < 36; strand++) {
        const lane = jitter(0.012);
        const p0 = new Vector3(sign * (0.060 + bundle * 0.009) + lane, -0.145 + jitter(0.012), 0.10 + jitter(0.023));
        const p3 = surface(lobes[side], 0.36 + bundle * 0.18 + jitter(0.030), 22 + bundle * 9 + jitter(4));
        const p1 = new Vector3(sign * 0.09 + lane, 0.025 + jitter(0.009), 0.10 + jitter(0.010));
        const p2 = new Vector3(p3.x * 0.64, Math.max(0.09, p3.y * 0.72), p3.z * 0.78);
        fiber(p0, p1, p2, p3, (phase + jitter(0.025) + 1) % 1, 2);
      }
    }
  }

  // Twelve sparse elongated deep clusters; no uniform shell or volumetric filler.
  const clusterGuides: Array<{ center: [number, number, number]; radii: [number, number, number]; family: Family }> = [
    { center: [0.13, 0.10, -0.11], radii: [0.020, 0.026, 0.074], family: 2 },
    { center: [0.20, 0.14, 0.15], radii: [0.016, 0.030, 0.087], family: 0 },
    { center: [0.11, 0.205, 0.26], radii: [0.012, 0.019, 0.063], family: 1 },
    { center: [0.19, 0.205, -0.26], radii: [0.017, 0.020, 0.058], family: 0 },
    { center: [0.055, 0.19, -0.04], radii: [0.017, 0.016, 0.084], family: 1 },
    { center: [0.08, -0.025, 0.105], radii: [0.010, 0.058, 0.020], family: 2 },
  ];
  for (const sign of [-1, 1]) {
    for (const cluster of clusterGuides) {
      const phase = random();
      for (let point = 0; point < 25; point++) {
        const angle = random() * Math.PI * 2;
        const axial = random() * 2 - 1;
        const radius = Math.cbrt(random());
        const equator = Math.sqrt(1 - axial * axial) * radius;
        const location = new Vector3(
          sign * (cluster.center[0] + Math.cos(angle) * equator * cluster.radii[0]),
          cluster.center[1] + Math.sin(angle) * equator * cluster.radii[1],
          cluster.center[2] + axial * radius * cluster.radii[2],
        );
        appendPoint(nucleiData, location, (axial + 1) * 0.5, phase, cluster.family);
      }
    }
  }

  return { tracts: geometryFrom(tractData), nuclei: geometryFrom(nucleiData) };
}
