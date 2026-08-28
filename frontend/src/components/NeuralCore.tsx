import { useMemo, useRef } from "react";
import type { RefObject } from "react";

import { Canvas, useFrame } from "@react-three/fiber";
import {
  Bloom,
  EffectComposer,
} from "@react-three/postprocessing";
import {
  AdditiveBlending,
  BufferGeometry,
  Float32BufferAttribute,
  Group,
  Mesh,
  Points,
  ShaderMaterial,
  Vector3,
} from "three";

import type { FridayRuntimeState } from "../runtime";

interface NeuralCoreProps {
  state: FridayRuntimeState;
}

type Lobe = -1 | 1;

interface ClusterSpec {
  lobe: Lobe;
  u: number;
  v: number;
  spreadU: number;
  spreadV: number;
  count: number;
  color: readonly [number, number, number];
}

const TAU = Math.PI * 2;

const CYAN =
  [0.24, 0.92, 1.0] as const;

const BLUE =
  [0.3, 0.56, 1.0] as const;

const MAGENTA =
  [0.92, 0.2, 0.86] as const;

const GREEN =
  [0.2, 0.94, 0.54] as const;

const AMBER =
  [1.0, 0.68, 0.22] as const;

const RED =
  [0.96, 0.2, 0.3] as const;

const WHITE =
  [0.94, 1.0, 1.0] as const;

const CLUSTERS: readonly ClusterSpec[] = [
  {
    lobe: -1,
    u: Math.PI,
    v: 1.42,
    spreadU: 1.0,
    spreadV: 0.92,
    count: 320,
    color: CYAN,
  },
  {
    lobe: 1,
    u: 0.05,
    v: 1.48,
    spreadU: 1.05,
    spreadV: 0.94,
    count: 300,
    color: MAGENTA,
  },
  {
    lobe: -1,
    u: 3.7,
    v: 2.18,
    spreadU: 0.96,
    spreadV: 0.58,
    count: 230,
    color: GREEN,
  },
  {
    lobe: -1,
    u: 3.22,
    v: 0.76,
    spreadU: 0.9,
    spreadV: 0.52,
    count: 210,
    color: RED,
  },
  {
    lobe: 1,
    u: 0.32,
    v: 0.78,
    spreadU: 0.9,
    spreadV: 0.55,
    count: 220,
    color: AMBER,
  },
  {
    lobe: 1,
    u: 5.45,
    v: 1.95,
    spreadU: 0.82,
    spreadV: 0.6,
    count: 190,
    color: GREEN,
  },
  {
    lobe: -1,
    u: 2.15,
    v: 1.16,
    spreadU: 0.75,
    spreadV: 0.65,
    count: 200,
    color: BLUE,
  },
];

function seeded(seed: number): () => number {
  let value = seed >>> 0;

  return () => {
    value =
      (
        value * 1664525 +
        1013904223
      ) >>> 0;

    return value / 4294967296;
  };
}

function stateEnergy(
  state: FridayRuntimeState,
): number {
  switch (state) {
    case "sleeping":
      return 0.24;

    case "idle":
      return 0.56;

    case "listening":
      return 0.94;

    case "transcribing":
    case "retrieving":
      return 0.84;

    case "thinking":
    case "planning":
      return 1.08;

    case "waiting_for_approval":
      return 0.76;

    case "executing":
    case "validating":
    case "reviewing":
      return 1.17;

    case "speaking":
      return 1.02;

    case "completed":
      return 0.68;

    case "error":
    case "cancelled":
      return 0.9;

    default:
      return 0.6;
  }
}

/* ==========================================================
   BRAIN GEOMETRY
   ========================================================== */

function brainSurfacePoint(
  lobe: Lobe,
  u: number,
  v: number,
  scale = 1,
): Vector3 {
  /*
   * FEATURE 2
   *
   * IMPORTANT:
   *
   * This is the particle/network/fibre surface sampler.
   * It intentionally mirrors Feature 1.7's approved procedural
   * cerebral anatomy so every future neural layer shares the
   * SAME brain rather than forming a second floating shell.
   */

  const sinV =
    Math.sin(v);

  const sy =
    Math.cos(v);

  const sx =
    Math.cos(u) *
    sinV;

  const sz =
    Math.sin(u) *
    sinV;


  /* ========================================================
     ANATOMICAL REGIONS — MATCH FEATURE 1.7
     ======================================================== */

  const outerSide =
    Math.max(
      0,
      lobe * sx,
    );


  const frontal =
    Math.exp(
      -Math.pow(
        (
          sz -
          0.58
        ) /
          0.48,
        2,
      ) -
      Math.pow(
        (
          sy -
          0.04
        ) /
          0.72,
        2,
      ),
    );


  const occipital =
    Math.exp(
      -Math.pow(
        (
          sz +
          0.67
        ) /
          0.40,
        2,
      ) -
      Math.pow(
        (
          sy -
          0.02
        ) /
          0.68,
        2,
      ),
    );


  const parietal =
    Math.exp(
      -Math.pow(
        (
          sy -
          0.53
        ) /
          0.39,
        2,
      ),
    ) *
    (
      0.72 +
      outerSide *
        0.28
    );


  const temporal =
    Math.exp(
      -Math.pow(
        (
          sy +
          0.38
        ) /
          0.27,
        2,
      ),
    ) *
    (
      0.48 +
      outerSide *
        0.72
    );


  const posteriorLower =
    Math.exp(
      -Math.pow(
        (
          sz +
          0.46
        ) /
          0.48,
        2,
      ) -
      Math.pow(
        (
          sy +
          0.37
        ) /
          0.30,
        2,
      ),
    );


  /* ========================================================
     GYRI — MATCH FEATURE 1.7
     ======================================================== */

  const broadGyri =
    Math.sin(
      u * 2.65 +
      v * 1.55 +
      lobe * 0.38,
    ) *
      0.052 +
    Math.sin(
      u * 4.35 -
      v * 2.18,
    ) *
      0.034 +
    Math.cos(
      u * 5.85 +
      v * 2.72 +
      lobe * 0.21,
    ) *
      0.024;


  const mediumGyri =
    Math.sin(
      u * 7.4 +
      v * 3.25,
    ) *
      0.018 +
    Math.cos(
      u * 10.1 -
      v * 4.35,
    ) *
      0.011;


  const foldMask =
    Math.pow(
      Math.max(
        0,
        sinV,
      ),
      0.48,
    );


  const foldScale =
    1 +
    (
      broadGyri +
      mediumGyri
    ) *
      foldMask;


  /* ========================================================
     SHALLOW SULCI — MATCH FEATURE 1.7
     ======================================================== */

  const sulcusSignal =
    Math.sin(
      u * 5.2 +
      v * 2.6 +
      lobe * 0.42,
    ) +
    Math.sin(
      u * 8.15 -
      v * 3.75,
    ) *
      0.48;


  const sulcus =
    Math.pow(
      Math.max(
        0,
        -sulcusSignal,
      ),
      2.0,
    ) *
    foldMask;


  const sulcusScale =
    1 -
    Math.min(
      0.032,
      sulcus *
        0.023,
    );


  /* ========================================================
     BASE ANATOMICAL PROPORTIONS
     ======================================================== */

  const centerX =
    lobe *
    0.145;


  const radiusX =
    0.34 *
    (
      1 +
      temporal *
        0.20 +
      parietal *
        0.055 +
      frontal *
        0.045 +
      posteriorLower *
        0.035
    );


  const radiusY =
    0.415 *
    (
      1 +
      parietal *
        0.075 +
      frontal *
        0.022
    );


  const radiusZ =
    0.48 *
    (
      1 +
      frontal *
        0.145 +
      temporal *
        0.10 +
      occipital *
        0.035 +
      posteriorLower *
        0.055
    );


  const lowerTaper =
    sy < -0.67
      ? 1 -
        Math.min(
          0.075,
          (
            -sy -
            0.67
          ) *
            0.12,
        )
      : 1;


  let x =
    centerX +
    sx *
      radiusX *
      foldScale *
      sulcusScale *
      lowerTaper;


  let y =
    sy *
      radiusY *
      (
        1 +
        (
          foldScale -
          1
        ) *
          0.36
      ) +
    parietal *
      0.026 -
    temporal *
      0.012;


  let z =
    sz *
      radiusZ *
      foldScale *
      sulcusScale *
      lowerTaper;


  /* ========================================================
     ANTERIOR / POSTERIOR CHARACTER
     ======================================================== */

  z +=
    frontal *
    0.052;

  z -=
    occipital *
    0.028;

  z -=
    posteriorLower *
    0.018;


  x +=
    lobe *
    frontal *
    outerSide *
    0.014;


  /* ========================================================
     SUPERIOR MEDIAL FISSURE
     ======================================================== */

  const superior =
    Math.pow(
      Math.max(
        0,
        Math.min(
          1,
          (
            sy +
            0.12
          ) /
            1.02,
        ),
      ),
      1.65,
    );


  const medialDistance =
    Math.exp(
      -Math.pow(
        x /
          0.115,
        2,
      ),
    );


  const fissure =
    medialDistance *
    superior;


  x +=
    lobe *
    fissure *
    0.023;


  y -=
    fissure *
    0.008;


  /* ========================================================
     NATURAL ASYMMETRY
     ======================================================== */

  if (
    lobe === 1
  ) {
    y -=
      0.007;

    z +=
      0.009;

    x +=
      frontal *
      0.004;
  } else {
    y +=
      0.005;

    z -=
      0.006;
  }


  return new Vector3(
    x * scale,
    y * scale,
    z * scale,
  );
}

function approximateNormal(
  lobe: Lobe,
  u: number,
  v: number,
): Vector3 {
  const center =
    new Vector3(
      lobe * 0.145,
      0,
      0,
    );

  return brainSurfacePoint(
    lobe,
    u,
    v,
  )
    .sub(center)
    .normalize();
}

function colorForPosition(
  point: Vector3,
): readonly [
  number,
  number,
  number,
] {
  if (
    point.y < -0.29
  ) {
    return GREEN;
  }

  if (
    point.y > 0.27 &&
    point.x < -0.06
  ) {
    return RED;
  }

  if (
    point.y > 0.24 &&
    point.x >= -0.06
  ) {
    return AMBER;
  }

  if (
    point.x > 0.23
  ) {
    return MAGENTA;
  }

  if (
    point.x < -0.2
  ) {
    return CYAN;
  }

  return BLUE;
}

/* ==========================================================
   BRAIN SURFACE PARTICLES
   ========================================================== */

function buildSurfaceGeometry(
  count: number,
  seed: number,
): BufferGeometry {
  /*
   * ========================================================
   * GS-2A — FOLD-AWARE MICROSCOPIC PARTICLE SKIN
   * ========================================================
   *
   * This particle shell no longer approximates the brain using
   * brainSurfacePoint().
   *
   * Instead it samples the ACTUAL GS-1G folded triangle mesh.
   *
   * Therefore particles:
   *
   * - sit directly on real gyri
   * - fall into real sulci
   * - rotate with the exact anatomical mesh
   * - preserve the approved GS-0R silhouette
   */


  const random =
    seeded(
      seed,
    );


  const leftBrain =
    buildBrainBodyGeometry(
      -1,
    );


  const rightBrain =
    buildBrainBodyGeometry(
      1,
    );


  const geometries =
    [
      leftBrain,
      rightBrain,
    ] as const;


  const positions:
    number[] =
    [];


  const colors:
    number[] =
    [];


  const seeds:
    number[] =
    [];


  const sizes:
    number[] =
    [];


  type TriangleSampler = {
    geometry: BufferGeometry;
    cumulativeAreas: number[];
    totalArea: number;
  };


  /*
   * --------------------------------------------------------
   * Build an area-weighted triangle sampler.
   * --------------------------------------------------------
   */
  function makeSampler(
    geometry: BufferGeometry,
  ): TriangleSampler {
    const position =
      geometry.getAttribute(
        "position",
      );


    const index =
      geometry.getIndex();


    if (
      !index
    ) {
      throw new Error(
        "GS-2A requires indexed folded brain geometry.",
      );
    }


    const cumulativeAreas:
      number[] =
      [];


    let totalArea =
      0;


    const a =
      new Vector3();


    const b =
      new Vector3();


    const c =
      new Vector3();


    const ab =
      new Vector3();


    const ac =
      new Vector3();


    const cross =
      new Vector3();


    for (
      let triangle = 0;
      triangle < index.count;
      triangle += 3
    ) {
      const ia =
        index.getX(
          triangle,
        );


      const ib =
        index.getX(
          triangle + 1,
        );


      const ic =
        index.getX(
          triangle + 2,
        );


      a.fromBufferAttribute(
        position,
        ia,
      );


      b.fromBufferAttribute(
        position,
        ib,
      );


      c.fromBufferAttribute(
        position,
        ic,
      );


      ab.subVectors(
        b,
        a,
      );


      ac.subVectors(
        c,
        a,
      );


      cross.crossVectors(
        ab,
        ac,
      );


      const area =
        cross.length() *
        0.5;


      totalArea +=
        area;


      cumulativeAreas.push(
        totalArea,
      );
    }


    return {
      geometry,
      cumulativeAreas,
      totalArea,
    };
  }


  const samplers =
    geometries.map(
      makeSampler,
    );


  /*
   * Binary search one weighted triangle.
   */
  function chooseTriangle(
    sampler: TriangleSampler,
  ): number {
    const target =
      random() *
      sampler.totalArea;


    let low =
      0;


    let high =
      sampler.cumulativeAreas.length -
      1;


    while (
      low <
      high
    ) {
      const middle =
        Math.floor(
          (
            low +
            high
          ) /
            2,
        );


      if (
        sampler.cumulativeAreas[
          middle
        ] <
        target
      ) {
        low =
          middle + 1;
      } else {
        high =
          middle;
      }
    }


    return (
      low *
      3
    );
  }


  function clamp01(
    value: number,
  ): number {
    return Math.max(
      0,
      Math.min(
        1,
        value,
      ),
    );
  }


  function smoothstep(
    edge0: number,
    edge1: number,
    value: number,
  ): number {
    const t =
      clamp01(
        (
          value -
          edge0
        ) /
          (
            edge1 -
            edge0
          ),
      );


    return (
      t *
      t *
      (
        3 -
        2 *
          t
      )
    );
  }


  function mixColor(
    a:
      readonly [
        number,
        number,
        number,
      ],
    b:
      readonly [
        number,
        number,
        number,
      ],
    t: number,
  ):
    readonly [
      number,
      number,
      number,
    ] {
    const blend =
      clamp01(
        t,
      );


    return [
      a[0] +
        (
          b[0] -
          a[0]
        ) *
          blend,

      a[1] +
        (
          b[1] -
          a[1]
        ) *
          blend,

      a[2] +
        (
          b[2] -
          a[2]
        ) *
          blend,
    ] as const;
  }


  /*
   * Localized neural-activity fields.
   *
   * These remain restrained for GS-2A.
   * Radiating excitation comes later.
   */
  const clusterFields:
    ReadonlyArray<{
      center:
        readonly [
          number,
          number,
          number,
        ];
      radius:
        readonly [
          number,
          number,
          number,
        ];
      color:
        readonly [
          number,
          number,
          number,
        ];
    }> =
    [
      {
        center: [
          -0.22,
          0.17,
          0.23,
        ],
        radius: [
          0.18,
          0.17,
          0.20,
        ],
        color:
          CYAN,
      },

      {
        center: [
          0.25,
          0.11,
          0.03,
        ],
        radius: [
          0.18,
          0.18,
          0.20,
        ],
        color:
          MAGENTA,
      },

      {
        center: [
          -0.20,
          -0.18,
          0.04,
        ],
        radius: [
          0.19,
          0.15,
          0.20,
        ],
        color:
          GREEN,
      },

      {
        center: [
          0.17,
          0.27,
          -0.08,
        ],
        radius: [
          0.17,
          0.16,
          0.20,
        ],
        color:
          AMBER,
      },

      {
        center: [
          -0.15,
          0.24,
          -0.25,
        ],
        radius: [
          0.17,
          0.16,
          0.19,
        ],
        color:
          RED,
      },
    ];


  const point =
    new Vector3();


  const normal =
    new Vector3();


  let attempts =
    0;


  const maxAttempts =
    count *
    8;


  while (
    positions.length /
      3 <
      count &&
    attempts <
      maxAttempts
  ) {
    attempts +=
      1;


    const sampler =
      samplers[
        random() <
        0.5
          ? 0
          : 1
      ];


    const geometry =
      sampler.geometry;


    const position =
      geometry.getAttribute(
        "position",
      );


    const normalAttribute =
      geometry.getAttribute(
        "normal",
      );


    const corticalAttribute =
      geometry.getAttribute(
        "aCorticalDisplacement",
      );


    const index =
      geometry.getIndex();


    if (
      !index ||
      !corticalAttribute
    ) {
      throw new Error(
        "GS-2A folded cortical attributes are missing.",
      );
    }


    const triangleOffset =
      chooseTriangle(
        sampler,
      );


    const ia =
      index.getX(
        triangleOffset,
      );


    const ib =
      index.getX(
        triangleOffset + 1,
      );


    const ic =
      index.getX(
        triangleOffset + 2,
      );


    /*
     * Uniform barycentric triangle sampling.
     */
    const sqrtR1 =
      Math.sqrt(
        random(),
      );


    const r2 =
      random();


    const wa =
      1 -
      sqrtR1;


    const wb =
      sqrtR1 *
      (
        1 -
        r2
      );


    const wc =
      sqrtR1 *
      r2;


    point.set(
      position.getX(
        ia,
      ) *
        wa +
      position.getX(
        ib,
      ) *
        wb +
      position.getX(
        ic,
      ) *
        wc,

      position.getY(
        ia,
      ) *
        wa +
      position.getY(
        ib,
      ) *
        wb +
      position.getY(
        ic,
      ) *
        wc,

      position.getZ(
        ia,
      ) *
        wa +
      position.getZ(
        ib,
      ) *
        wb +
      position.getZ(
        ic,
      ) *
        wc,
    );


    normal.set(
      normalAttribute.getX(
        ia,
      ) *
        wa +
      normalAttribute.getX(
        ib,
      ) *
        wb +
      normalAttribute.getX(
        ic,
      ) *
        wc,

      normalAttribute.getY(
        ia,
      ) *
        wa +
      normalAttribute.getY(
        ib,
      ) *
        wb +
      normalAttribute.getY(
        ic,
      ) *
        wc,

      normalAttribute.getZ(
        ia,
      ) *
        wa +
      normalAttribute.getZ(
        ib,
      ) *
        wb +
      normalAttribute.getZ(
        ic,
      ) *
        wc,
    ).normalize();


    const corticalValue =
      corticalAttribute.getX(
        ia,
      ) *
        wa +
      corticalAttribute.getX(
        ib,
      ) *
        wb +
      corticalAttribute.getX(
        ic,
      ) *
        wc;


    /*
     * Fold classification.
     */
    const gyrus =
      smoothstep(
        -0.002,
        0.012,
        corticalValue,
      );


    const sulcus =
      1 -
      smoothstep(
        -0.024,
        -0.004,
        corticalValue,
      );


    /*
     * FOLD-AWARE DENSITY
     *
     * Raised gyri receive dense particles.
     * Deep sulci retain some particles, but noticeably fewer.
     */
    const acceptance =
      clamp01(
        0.36 +
        gyrus *
          0.62 -
        sulcus *
          0.22,
      );


    if (
      random() >
      acceptance
    ) {
      continue;
    }


    /*
     * Keep particles microscopically above the actual mesh.
     */
    point.addScaledVector(
      normal,
      0.0010 +
        gyrus *
          0.0015 +
        random() *
          0.0013,
    );


    /*
     * ------------------------------------------------------
     * COLOR
     * ------------------------------------------------------
     *
     * Quiet substrate:
     * deep blue with cyan lift on raised gyri.
     */
    let color =
      mixColor(
        BLUE,
        CYAN,
        0.22 +
          gyrus *
            0.34,
      );


    let strongestCluster =
      0;


    let strongestColor:
      readonly [
        number,
        number,
        number,
      ] =
      CYAN;


    for (
      const cluster of clusterFields
    ) {
      const dx =
        (
          point.x -
          cluster.center[0]
        ) /
        cluster.radius[0];


      const dy =
        (
          point.y -
          cluster.center[1]
        ) /
        cluster.radius[1];


      const dz =
        (
          point.z -
          cluster.center[2]
        ) /
        cluster.radius[2];


      const strength =
        Math.exp(
          -(
            dx * dx +
            dy * dy +
            dz * dz
          ),
        );


      if (
        strength >
        strongestCluster
      ) {
        strongestCluster =
          strength;


        strongestColor =
          cluster.color;
      }
    }


    /*
     * Local activity should be more visible on gyri than inside
     * deep sulci.
     */
    const clusterBlend =
      clamp01(
        (
          strongestCluster -
          0.24
        ) *
          0.88 *
          (
            0.58 +
            gyrus *
              0.42
          ),
      );


    color =
      mixColor(
        color,
        strongestColor,
        clusterBlend,
      );


    /*
     * Darken particles inside deep sulci.
     */
    const sulcusDarkening =
      1 -
      sulcus *
        0.46;


    color = [
      clamp01(
        color[0] *
          sulcusDarkening,
      ),

      clamp01(
        color[1] *
          sulcusDarkening,
      ),

      clamp01(
        color[2] *
          (
            sulcusDarkening +
            0.04
          ),
      ),
    ] as const;


    positions.push(
      point.x,
      point.y,
      point.z,
    );


    /*
     * IMPORTANT:
     * SURFACE_VERTEX_SHADER expects aColor.
     */
    colors.push(
      color[0],
      color[1],
      color[2],
    );


    seeds.push(
      random(),
    );


    /*
     * Raised gyri carry slightly larger microscopic particles.
     *
     * Still tiny—these are not signal particles.
     */
    sizes.push(
      Math.max(
        0.22,
        0.34 +
          random() *
            0.30 +
          gyrus *
            0.42 -
          sulcus *
            0.13,
      ),
    );
  }


  if (
    positions.length /
      3 <
      count
  ) {
    throw new Error(
      "GS-2A could not generate the requested particle count.",
    );
  }


  const geometry =
    new BufferGeometry();


  geometry.setAttribute(
    "position",
    new Float32BufferAttribute(
      positions,
      3,
    ),
  );


  geometry.setAttribute(
    "aColor",
    new Float32BufferAttribute(
      colors,
      3,
    ),
  );


  geometry.setAttribute(
    "aSeed",
    new Float32BufferAttribute(
      seeds,
      1,
    ),
  );


  geometry.setAttribute(
    "aSize",
    new Float32BufferAttribute(
      sizes,
      1,
    ),
  );


  /*
   * Temporary folded meshes were created only for particle
   * sampling; free their GPU-side resources.
   */
  leftBrain.dispose();
  rightBrain.dispose();


  return geometry;
}

function buildBrainScaffoldGeometry(
  seed: number,
  edgeCount: number,
): BufferGeometry {
  const random =
    seeded(seed);

  const positions: number[] = [];
  const colors: number[] = [];

  for (
    let index = 0;
    index < edgeCount;
    index += 1
  ) {
    const lobe: Lobe =
      random() < 0.5
        ? -1
        : 1;

    const u =
      random() * TAU;

    const v =
      0.18 +
      random() *
        (
          Math.PI -
          0.36
        );

    /*
     * Short local connection across nearby surface territory.
     */
    const du =
      (
        random() -
        0.5
      ) *
      0.23;

    const dv =
      (
        random() -
        0.5
      ) *
      0.18;

    const nextV =
      Math.max(
        0.16,
        Math.min(
          Math.PI -
            0.16,
          v + dv,
        ),
      );

    const start =
      brainSurfacePoint(
        lobe,
        u,
        v,
        1.035,
      );

    const end =
      brainSurfacePoint(
        lobe,
        u + du,
        nextV,
        1.04,
      );

    const territory =
      colorForPosition(
        start,
      );

    /*
     * Mostly cyan/blue scaffold with restrained territory color.
     */
    const color =
      random() < 0.46
        ? (
            random() < 0.52
              ? CYAN
              : BLUE
          )
        : territory;

    positions.push(
      start.x,
      start.y,
      start.z,
      end.x,
      end.y,
      end.z,
    );

    colors.push(
      color[0],
      color[1],
      color[2],
      color[0],
      color[1],
      color[2],
    );
  }

  const geometry =
    new BufferGeometry();

  geometry.setAttribute(
    "position",
    new Float32BufferAttribute(
      positions,
      3,
    ),
  );

  geometry.setAttribute(
    "color",
    new Float32BufferAttribute(
      colors,
      3,
    ),
  );

  return geometry;
}

/* ==========================================================
   NEURAL CLUSTERS + GRAPH EDGES
   ========================================================== */

interface NetworkGeometry {
  nodes: BufferGeometry;
  edges: BufferGeometry;
}

function buildNetworkGeometry(
  seed: number,
): NetworkGeometry {
  const random =
    seeded(seed);

  const nodePositions: number[] = [];
  const nodeColors: number[] = [];
  const nodeSeeds: number[] = [];
  const nodeSizes: number[] = [];

  const edgePositions: number[] = [];
  const edgeColors: number[] = [];

  for (
    const cluster of CLUSTERS
  ) {
    const clusterPoints:
      Vector3[] = [];

    const effectiveCount =
      Math.floor(
        cluster.count * 1.18,
      );

    for (
      let index = 0;
      index < effectiveCount;
      index += 1
    ) {
      const u =
        cluster.u +
        (
          random() -
          0.5
        ) *
          cluster.spreadU;

      const v =
        Math.max(
          0.14,
          Math.min(
            Math.PI -
              0.14,
            cluster.v +
              (
                random() -
                0.5
              ) *
                cluster.spreadV,
          ),
        );

      const normal =
        approximateNormal(
          cluster.lobe,
          u,
          v,
        );

      const point =
        brainSurfacePoint(
          cluster.lobe,
          u,
          v,
          1.045 +
            random() *
              0.045,
        )
          .add(
            normal.multiplyScalar(
              0.008 +
              random() *
                0.025,
            ),
          );

      clusterPoints.push(
        point,
      );

      nodePositions.push(
        point.x,
        point.y,
        point.z,
      );

      nodeColors.push(
        cluster.color[0],
        cluster.color[1],
        cluster.color[2],
      );

      nodeSeeds.push(
        random(),
      );

      nodeSizes.push(
        0.85 +
        random() *
          1.45,
      );
    }

    /*
     * Dense local graph:
     * neighboring links plus sparse cross-links.
     */
    for (
      let index = 1;
      index < clusterPoints.length;
      index += 1
    ) {
      const current =
        clusterPoints[
          index
        ];

      const previous =
        clusterPoints[
          Math.max(
            0,
            index -
              1 -
              Math.floor(
                random() *
                  Math.min(
                    index,
                    7,
                  ),
              ),
          )
        ];

      edgePositions.push(
        current.x,
        current.y,
        current.z,
        previous.x,
        previous.y,
        previous.z,
      );

      edgeColors.push(
        cluster.color[0],
        cluster.color[1],
        cluster.color[2],
        cluster.color[0],
        cluster.color[1],
        cluster.color[2],
      );

      if (
        index > 8 &&
        random() < 0.42
      ) {
        const cross =
          clusterPoints[
            Math.floor(
              random() *
                index,
            )
          ];

        edgePositions.push(
          current.x,
          current.y,
          current.z,
          cross.x,
          cross.y,
          cross.z,
        );

        edgeColors.push(
          cluster.color[0],
          cluster.color[1],
          cluster.color[2],
          cluster.color[0],
          cluster.color[1],
          cluster.color[2],
        );
      }
    }
  }

  const nodeGeometry =
    new BufferGeometry();

  nodeGeometry.setAttribute(
    "position",
    new Float32BufferAttribute(
      nodePositions,
      3,
    ),
  );

  nodeGeometry.setAttribute(
    "aColor",
    new Float32BufferAttribute(
      nodeColors,
      3,
    ),
  );

  nodeGeometry.setAttribute(
    "aSeed",
    new Float32BufferAttribute(
      nodeSeeds,
      1,
    ),
  );

  nodeGeometry.setAttribute(
    "aSize",
    new Float32BufferAttribute(
      nodeSizes,
      1,
    ),
  );

  const edgeGeometry =
    new BufferGeometry();

  edgeGeometry.setAttribute(
    "position",
    new Float32BufferAttribute(
      edgePositions,
      3,
    ),
  );

  edgeGeometry.setAttribute(
    "color",
    new Float32BufferAttribute(
      edgeColors,
      3,
    ),
  );

  return {
    nodes:
      nodeGeometry,

    edges:
      edgeGeometry,
  };
}

/* ==========================================================
   EXTERNAL PLASMA FIBERS
   ========================================================== */

function buildFiberGeometry(
  seed: number,
  fiberCount: number,
  surfaceGeometry: BufferGeometry,
): BufferGeometry {
  /*
   * ========================================================
   * GS-4E — CORTEX-FOLLOWING NEURAL FIBERS
   * ========================================================
   *
   * IMPORTANT:
   *
   * Do NOT use brainSurfacePoint().
   *
   * GS-4D2 already contains 48k points sampled directly from
   * the true GS-4C1 folded mesh.
   *
   * Those exact cortical points become a spatial graph.
   *
   * Each fiber performs a short direction-biased walk between
   * neighboring cortical samples.
   *
   * Therefore the fibers:
   *
   * - stay close to the real cortex
   * - follow local curvature
   * - remain short
   * - avoid long radial tentacles
   * - preserve the new anatomical brain
   */

  const random =
    seeded(
      seed,
    );


  const sourcePosition =
    surfaceGeometry.getAttribute(
      "position",
    );


  const sourceColor =
    surfaceGeometry.getAttribute(
      "aColor",
    );


  if (
    !sourcePosition ||
    !sourceColor
  ) {
    throw new Error(
      "GS-4E requires GS-4D2 cortical surface attributes.",
    );
  }


  /*
   * --------------------------------------------------------
   * Spatial hash
   * --------------------------------------------------------
   *
   * Searching all 48k particles for every fiber point would
   * be unnecessarily expensive.
   */

  const cellSize =
    0.060;


  const buckets =
    new Map<
      string,
      number[]
    >();


  function cellCoordinate(
    value: number,
  ): number {
    return Math.floor(
      value /
      cellSize,
    );
  }


  function cellKey(
    x: number,
    y: number,
    z: number,
  ): string {
    return (
      `${x},${y},${z}`
    );
  }


  for (
    let index = 0;
    index < sourcePosition.count;
    index += 1
  ) {
    const key =
      cellKey(
        cellCoordinate(
          sourcePosition.getX(
            index,
          ),
        ),
        cellCoordinate(
          sourcePosition.getY(
            index,
          ),
        ),
        cellCoordinate(
          sourcePosition.getZ(
            index,
          ),
        ),
      );


    const bucket =
      buckets.get(
        key,
      );


    if (
      bucket
    ) {
      bucket.push(
        index,
      );
    } else {
      buckets.set(
        key,
        [
          index,
        ],
      );
    }
  }


  function corticalSignal(
    index: number,
  ): number {
    return Math.max(
      sourceColor.getX(
        index,
      ),
      sourceColor.getY(
        index,
      ),
      sourceColor.getZ(
        index,
      ),
    );
  }


  function positionAt(
    index: number,
  ): Vector3 {
    return new Vector3(
      sourcePosition.getX(
        index,
      ),
      sourcePosition.getY(
        index,
      ),
      sourcePosition.getZ(
        index,
      ),
    );
  }


  /*
   * Find one nearby cortical point.
   *
   * Direction continuity keeps the path filament-like rather
   * than producing random scribbles.
   */

  function chooseNext(
    currentIndex: number,
    previousDirection:
      Vector3 | null,
  ): number | null {
    const current =
      positionAt(
        currentIndex,
      );


    const cx =
      cellCoordinate(
        current.x,
      );

    const cy =
      cellCoordinate(
        current.y,
      );

    const cz =
      cellCoordinate(
        current.z,
      );


    let bestIndex:
      number | null =
      null;


    let bestScore =
      -Infinity;


    for (
      let dx = -1;
      dx <= 1;
      dx += 1
    ) {
      for (
        let dy = -1;
        dy <= 1;
        dy += 1
      ) {
        for (
          let dz = -1;
          dz <= 1;
          dz += 1
        ) {
          const bucket =
            buckets.get(
              cellKey(
                cx + dx,
                cy + dy,
                cz + dz,
              ),
            );


          if (
            !bucket
          ) {
            continue;
          }


          for (
            const candidateIndex
            of bucket
          ) {
            if (
              candidateIndex ===
              currentIndex
            ) {
              continue;
            }


            /*
             * Prefer gyri / cortical ridges.
             */
            const signal =
              corticalSignal(
                candidateIndex,
              );


            if (
              signal <
              0.28
            ) {
              continue;
            }


            const candidate =
              positionAt(
                candidateIndex,
              );


            const delta =
              candidate
                .clone()
                .sub(
                  current,
                );


            const distance =
              delta.length();


            /*
             * Short local steps only.
             *
             * This is what keeps the fiber hugging cortex.
             */
            if (
              distance <
                0.018 ||
              distance >
                0.072
            ) {
              continue;
            }


            const direction =
              delta
                .clone()
                .normalize();


            let continuity =
              0;


            if (
              previousDirection
            ) {
              continuity =
                previousDirection.dot(
                  direction,
                );


              /*
               * Never reverse sharply.
               */
              if (
                continuity <
                0.18
              ) {
                continue;
              }
            }


            const idealDistance =
              0.042;


            const distanceScore =
              1 -
              Math.min(
                1,
                Math.abs(
                  distance -
                  idealDistance
                ) /
                idealDistance,
              );


            const score =
              continuity *
                1.05 +
              distanceScore *
                0.52 +
              signal *
                0.30 +
              random() *
                0.24;


            if (
              score >
              bestScore
            ) {
              bestScore =
                score;

              bestIndex =
                candidateIndex;
            }
          }
        }
      }
    }


    return bestIndex;
  }


  const positions:
    number[] =
    [];


  const colors:
    number[] =
    [];


  const progresses:
    number[] =
    [];


  const seeds:
    number[] =
    [];


  const sizes:
    number[] =
    [];


  let generatedFibers =
    0;


  let attempts =
    0;


  while (
    generatedFibers <
      fiberCount &&
    attempts <
      fiberCount *
      12
  ) {
    attempts +=
      1;


    /*
     * Find a gyrus-biased starting point.
     */
    let startIndex =
      Math.floor(
        random() *
        sourcePosition.count,
      );


    let startAttempts =
      0;


    while (
      corticalSignal(
        startIndex,
      ) <
        0.36 &&
      startAttempts <
        20
    ) {
      startIndex =
        Math.floor(
          random() *
          sourcePosition.count,
        );

      startAttempts +=
        1;
    }


    if (
      corticalSignal(
        startIndex,
      ) <
      0.30
    ) {
      continue;
    }


    const path:
      number[] =
      [
        startIndex,
      ];


    const desiredSteps =
      7 +
      Math.floor(
        random() *
        7,
      );


    let currentIndex =
      startIndex;


    let previousDirection:
      Vector3 | null =
      null;


    for (
      let step = 0;
      step < desiredSteps;
      step += 1
    ) {
      const nextIndex =
        chooseNext(
          currentIndex,
          previousDirection,
        );


      if (
        nextIndex ===
        null
      ) {
        break;
      }


      const current =
        positionAt(
          currentIndex,
        );


      const next =
        positionAt(
          nextIndex,
        );


      previousDirection =
        next
          .clone()
          .sub(
            current,
          )
          .normalize();


      path.push(
        nextIndex,
      );


      currentIndex =
        nextIndex;
    }


    /*
     * Reject tiny fragments.
     */
    if (
      path.length <
      5
    ) {
      continue;
    }


    const fiberSeed =
      random();


    /*
     * Mostly dark blue/cyan.
     *
     * A small minority borrow the cortical color family.
     */
    const useCorticalColor =
      random() >
      0.84;


    const baseColor:
      [number, number, number] =
      useCorticalColor
        ? [
            sourceColor.getX(
              startIndex,
            ),
            sourceColor.getY(
              startIndex,
            ),
            sourceColor.getZ(
              startIndex,
            ),
          ]
        : (
            random() <
            0.72
              ? [
                  0.075,
                  0.42,
                  0.72,
                ]
              : [
                  0.10,
                  0.62,
                  0.82,
                ]
          );


    /*
     * Three samples per cortical edge make the path appear
     * continuous without producing thick tubes.
     */

    /*
     * ======================================================
     * GS-4F2 — CONTINUOUS SIGNAL SAMPLING
     * ======================================================
     *
     * Same cortical path.
     *
     * Higher interpolation density prevents the travelling
     * pulse from visually jumping between sparse points.
     */
    const subdivisions =
      8;


    const totalSamples =
      (
        path.length -
        1
      ) *
      subdivisions +
      1;


    let sampleNumber =
      0;


    for (
      let segment = 0;
      segment <
        path.length - 1;
      segment += 1
    ) {
      const a =
        positionAt(
          path[
            segment
          ],
        );


      const b =
        positionAt(
          path[
            segment + 1
          ],
        );


      for (
        let sub = 0;
        sub < subdivisions;
        sub += 1
      ) {
        const t =
          sub /
          subdivisions;


        const point =
          a
            .clone()
            .lerp(
              b,
              t,
            );


        /*
         * Microscopic outward bias.
         *
         * Only enough to prevent depth fighting with the solid
         * cortical material.
         */
        const radial =
          point
            .clone()
            .normalize();


        point.addScaledVector(
          radial,
          0.0035,
        );


        const progress =
          sampleNumber /
          Math.max(
            1,
            totalSamples -
            1,
          );


        positions.push(
          point.x,
          point.y,
          point.z,
        );


        colors.push(
          baseColor[0],
          baseColor[1],
          baseColor[2],
        );


        progresses.push(
          progress,
        );


        seeds.push(
          fiberSeed,
        );


        sizes.push(
          0.48 +
          random() *
            0.32,
        );


        sampleNumber +=
          1;
      }
    }


    /*
     * Final point.
     */
    const finalPoint =
      positionAt(
        path[
          path.length -
          1
        ],
      );


    finalPoint.addScaledVector(
      finalPoint
        .clone()
        .normalize(),
      0.0035,
    );


    positions.push(
      finalPoint.x,
      finalPoint.y,
      finalPoint.z,
    );


    colors.push(
      baseColor[0],
      baseColor[1],
      baseColor[2],
    );


    progresses.push(
      1,
    );


    seeds.push(
      fiberSeed,
    );


    sizes.push(
      0.48 +
      random() *
        0.32,
    );


    generatedFibers +=
      1;
  }


  const geometry =
    new BufferGeometry();


  geometry.setAttribute(
    "position",
    new Float32BufferAttribute(
      positions,
      3,
    ),
  );


  geometry.setAttribute(
    "aColor",
    new Float32BufferAttribute(
      colors,
      3,
    ),
  );


  geometry.setAttribute(
    "aProgress",
    new Float32BufferAttribute(
      progresses,
      1,
    ),
  );


  geometry.setAttribute(
    "aSeed",
    new Float32BufferAttribute(
      seeds,
      1,
    ),
  );


  geometry.setAttribute(
    "aSize",
    new Float32BufferAttribute(
      sizes,
      1,
    ),
  );


  return geometry;
}


/* ==========================================================
   EJECTION PARTICLES
   ========================================================== */

function buildEjectionGeometry(
  count: number,
  seed: number,
): BufferGeometry {
  const random =
    seeded(seed);

  const positions: number[] = [];
  const directions: number[] = [];
  const phases: number[] = [];
  const distances: number[] = [];
  const sizes: number[] = [];
  const colors: number[] = [];

  for (
    let index = 0;
    index < count;
    index += 1
  ) {
    const lobe: Lobe =
      random() < 0.5
        ? -1
        : 1;

    const u =
      random() *
      TAU;

    const v =
      0.2 +
      random() *
        (
          Math.PI -
          0.4
        );

    const normal =
      approximateNormal(
        lobe,
        u,
        v,
      );

    const start =
      brainSurfacePoint(
        lobe,
        u,
        v,
        1.07,
      );

    const direction =
      normal
        .clone()
        .add(
          new Vector3(
            (
              random() -
              0.5
            ) *
              0.28,
            (
              random() -
              0.5
            ) *
              0.28,
            (
              random() -
              0.5
            ) *
              0.28,
          ),
        )
        .normalize();

    const color =
      random() < 0.82
        ? WHITE
        : colorForPosition(
            start,
          );

    positions.push(
      start.x,
      start.y,
      start.z,
    );

    directions.push(
      direction.x,
      direction.y,
      direction.z,
    );

    phases.push(
      random(),
    );

    sizes.push(
      0.78 +
      random() *
        0.72,
    );

    const distanceRoll =
      random();

    distances.push(
      distanceRoll < 0.78
        ? 0.58 +
          random() *
            0.52
        : 1.15 +
          random() *
            0.82,
    );

    colors.push(
      color[0],
      color[1],
      color[2],
    );
  }

  const geometry =
    new BufferGeometry();

  geometry.setAttribute(
    "position",
    new Float32BufferAttribute(
      positions,
      3,
    ),
  );

  geometry.setAttribute(
    "aDirection",
    new Float32BufferAttribute(
      directions,
      3,
    ),
  );

  geometry.setAttribute(
    "aPhase",
    new Float32BufferAttribute(
      phases,
      1,
    ),
  );

  geometry.setAttribute(
    "aDistance",
    new Float32BufferAttribute(
      distances,
      1,
    ),
  );

  geometry.setAttribute(
    "aSize",
    new Float32BufferAttribute(
      sizes,
      1,
    ),
  );

  geometry.setAttribute(
    "aColor",
    new Float32BufferAttribute(
      colors,
      3,
    ),
  );

  return geometry;
}

/* ==========================================================
   SHADERS
   ========================================================== */

/*
 * ==========================================================
 * GS-6D2 — CONTINUOUS NEURAL FILAMENT WEB
 * GS-6C — REEL NEURAL WEB
 * GS-6B — CORTICAL ENERGY TRACER SKIN
 * ==========================================================
 *
 * Reel-oriented neural hierarchy:
 *
 * graphite GS-6A cortex
 *       ↓
 * cyan / violet gyrus tracers
 *       ↓
 * magenta / amber synaptic activity
 *       ↓
 * multicolor F2 travelling signals
 *       ↓
 * magenta plasma wake
 *       ↓
 * white / cyan plasma head
 *
 * No anatomy, depth, material, lighting, camera,
 * rotation, timing, geometry count or Bloom changes.
 * ==========================================================
 */

const SURFACE_VERTEX_SHADER = `
  attribute vec3 aColor;
  attribute float aSeed;
  attribute float aSize;

  uniform float uTime;
  uniform float uEnergy;
  uniform vec3 uHotPosition;
  uniform float uPlasmaX;
  uniform float uPlasmaStrength;
  uniform float uPointScale;

  varying vec3 vColor;
  varying float vAlpha;
  varying float vActivity;
  varying float vSpark;
  varying float vHot;
  varying float vPlasma;
  varying float vTracer;


  float gaussianZone(
    vec3 p,
    vec3 center,
    float radius
  ) {
    float d =
      distance(
        p,
        center
      ) /
      radius;

    return exp(
      -(d * d)
    );
  }


  void main() {
    vec3 p =
      position;


    /*
     * ======================================================
     * FOLD CLASSIFICATION
     * ======================================================
     *
     * buildSurfaceGeometry already encoded:
     *
     * dark/deep blue = sulcus
     * brighter cyan  = gyrus
     */
    float colorSignal =
      max(
        max(
          aColor.r,
          aColor.g
        ),
        aColor.b
      );


    float foldSignal =
      smoothstep(
        0.25,
        0.82,
        colorSignal
      );


    /*
     * Deterministic per-particle variation.
     */
    float particleNoise =
      fract(
        sin(
          aSeed * 91.713 +
          1.71
        ) *
        43758.5453
      );


    float sparkNoise =
      fract(
        sin(
          aSeed * 173.31 +
          7.91
        ) *
        24634.6345
      );


    /*
     * ======================================================
     * LOCALIZED ACTIVITY ZONES
     * ======================================================
     *
     * Object-space positions mean these stay attached to
     * the rotating cortex.
     */

    float cyanZone =
      gaussianZone(
        p,
        vec3(
          0.31,
          0.24,
          0.12
        ),
        0.22
      );


    float magentaZone =
      gaussianZone(
        p,
        vec3(
          -0.34,
          0.13,
          -0.18
        ),
        0.20
      );


    float greenZone =
      gaussianZone(
        p,
        vec3(
          0.32,
          0.29,
          -0.24
        ),
        0.19
      );


    float amberZone =
      gaussianZone(
        p,
        vec3(
          0.34,
          0.01,
          0.37
        ),
        0.18
      );


    float redZone =
      gaussianZone(
        p,
        vec3(
          -0.33,
          -0.12,
          0.24
        ),
        0.16
      );


    float zoneStrength =
      max(
        max(
          cyanZone,
          magentaZone
        ),
        max(
          greenZone,
          max(
            amberZone,
            redZone
          )
        )
      );


    /*
     * Activity zones should mostly illuminate gyri,
     * not fill deep sulci.
     */
    zoneStrength *=
      0.18 +
      foldSignal *
      0.82;


    /*
     * Only a small fraction become very bright signals.
     */
    float spark =
      smoothstep(
        0.910,
        0.992,
        sparkNoise
      ) *
      foldSignal *
      (
        0.30 +
        zoneStrength *
        0.70
      );


    /*
     * ======================================================
     * GS-6B — FUTURISTIC CORTICAL RIDGE TRACERS
     * ======================================================
     *
     * Sparse cyan/violet points preferentially climb the
     * high-relief gyrus crowns. They create a neural tracer
     * skin without filling the sulci or creating a blue shell.
     */
    float ridgeTracer =
      smoothstep(
        0.58,
        0.94,
        foldSignal
      ) *
      (
        0.18 +
        smoothstep(
          0.76,
          0.985,
          particleNoise
        ) *
          0.82
      ) *
      (
        0.42 +
        zoneStrength *
          0.58
      );


    /*
     * Existing dynamic hotspot remains, but is now restrained.
     */
    /*
     * ======================================================
     * GS-4G — LOCALIZED CORTICAL EXCITATION
     * ======================================================
     *
     * The legacy uHotPosition hotspot remains supported for
     * later runtime interaction, but is still disabled during
     * this visual stage.
     *
     * Instead, four small object-space cortical regions pulse
     * independently.
     *
     * Their positions rotate naturally with the brain because
     * p is local brain space.
     */


    float hotDistance =
      distance(
        p,
        uHotPosition
      );


    float legacyHot =
      exp(
        -pow(
          hotDistance /
          0.25,
          2.0
        )
      ) *
      0.32;


    /*
     * ------------------------------------------------------
     * TEMPORAL ENVELOPES
     * ------------------------------------------------------
     *
     * High-power sine envelopes create:
     *
     * quiet -> swelling -> peak -> fading -> quiet
     *
     * rather than continuously pulsating blobs.
     */


    float excitationPulseA =
      pow(
        max(
          0.0,
          sin(
            uTime *
              0.91 +
            0.20
          )
        ),
        3.8
      );


    float excitationPulseB =
      pow(
        max(
          0.0,
          sin(
            uTime *
              0.79 +
            2.35
          )
        ),
        3.8
      );


    float excitationPulseC =
      pow(
        max(
          0.0,
          sin(
            uTime *
              1.03 +
            4.25
          )
        ),
        3.8
      );


    float excitationPulseD =
      pow(
        max(
          0.0,
          sin(
            uTime *
              0.86 +
            5.55
          )
        ),
        3.8
      );


    /*
     * ------------------------------------------------------
     * SMALL CORTICAL EXCITATION REGIONS
     * ------------------------------------------------------
     *
     * Radii intentionally remain much smaller than the
     * GS-4D2 broad color zones.
     */


    float excitationA =
      gaussianZone(
        p,
        vec3(
          0.25,
          0.34,
          0.13
        ),
        0.158
      ) *
      excitationPulseA;


    float excitationB =
      gaussianZone(
        p,
        vec3(
          -0.30,
          0.21,
          -0.19
        ),
        0.163
      ) *
      excitationPulseB;


    float excitationC =
      gaussianZone(
        p,
        vec3(
          0.30,
          -0.01,
          -0.27
        ),
        0.148
      ) *
      excitationPulseC;


    float excitationD =
      gaussianZone(
        p,
        vec3(
          -0.27,
          -0.07,
          0.25
        ),
        0.153
      ) *
      excitationPulseD;


    float corticalExcitation =
      max(
        max(
          excitationA,
          excitationB
        ),
        max(
          excitationC,
          excitationD
        )
      );


    /*
     * Excitation should primarily climb gyri.
     *
     * Deep sulci remain substantially dark.
     */
    corticalExcitation *=
      0.16 +
      foldSignal *
        0.84;


    corticalExcitation =
      clamp(
        corticalExcitation,
        0.0,
        1.0
      );


    float hot =
      max(
        legacyHot,
        corticalExcitation
      );


    /*
     * ======================================================
     * GS-4H — LOCALIZED CORTICAL PLASMA FRONT
     * ======================================================
     *
     * Do NOT use a simple p.x slicing plane.
     *
     * A slightly oblique + curved sweep coordinate makes the
     * front follow the cortex more organically.
     */


    /*
     * ======================================================
     * GS-4H3A — LONGITUDINAL PLASMA AXIS
     * ======================================================
     *
     * z is now the dominant sweep coordinate.
     *
     * This moves the energy front across the visible cortical
     * side instead of tracing the lateral hemisphere contour.
     *
     * Small x/y terms preserve an organic oblique curvature.
     */
    /*
     * ======================================================
     * GS-6G — PROJECTED CORTICAL ENERGY SWEEP
     * ======================================================
     *
     * H3C is rendered using a projected view-space path.
     *
     * The 48k cortical particles now follow that same visual
     * trajectory instead of using the old object-space slice.
     *
     * This keeps the surge readable while the brain rotates.
     */

    float plasmaProgress =
      clamp(
        (
          uPlasmaX +
          0.64
        ) /
          1.28,
        0.0,
        1.0
      );


    vec4 corticalPlasmaView =
      modelViewMatrix *
      vec4(
        p,
        1.0
      );


    vec2 corticalViewPoint =
      corticalPlasmaView.xy;


    vec2 plasmaHeadCenter =
      vec2(
        mix(
          0.52,
          -0.52,
          plasmaProgress
        ),
        -0.12 +
        plasmaProgress *
          0.24 +
        sin(
          plasmaProgress *
            3.14159265
        ) *
          0.085 +
        sin(
          plasmaProgress *
            7.20 +
          0.40
        ) *
          0.018
      );


    vec2 plasmaHeadDelta =
      (
        corticalViewPoint -
        plasmaHeadCenter
      ) /
      vec2(
        0.105,
        0.064
      );


    float plasmaCore =
      exp(
        -dot(
          plasmaHeadDelta,
          plasmaHeadDelta
        )
      );


    float plasmaWake =
      0.0;


    for (
      int i = 1;
      i <= 6;
      i++
    ) {
      float index =
        float(i);


      float lag =
        index *
          0.045;


      float valid =
        step(
          lag,
          plasmaProgress
        );


      float wakeProgress =
        clamp(
          plasmaProgress -
            lag,
          0.0,
          1.0
        );


      vec2 wakeCenter =
        vec2(
          mix(
            0.52,
            -0.52,
            wakeProgress
          ),
          -0.12 +
          wakeProgress *
            0.24 +
          sin(
            wakeProgress *
              3.14159265
          ) *
            0.085 +
          sin(
            wakeProgress *
              7.20 +
            0.40
          ) *
            0.018
        );


      vec2 wakeDelta =
        (
          corticalViewPoint -
          wakeCenter
        ) /
        vec2(
          0.145,
          0.086
        );


      float wakeSample =
        exp(
          -dot(
            wakeDelta,
            wakeDelta
          )
        );


      float decay =
        1.0 -
        index /
          7.0;


      plasmaWake =
        max(
          plasmaWake,
          wakeSample *
          decay *
          valid
        );
    }


    /*
     * High-relief gyri participate much more strongly.
     * Sulci remain dark.
     */
    float projectedSurfaceMask =
      0.12 +
      foldSignal *
        0.88;


    float plasma =
      (
        plasmaCore +
        plasmaWake *
          0.60
      ) *
      projectedSurfaceMask *
      uPlasmaStrength;


    plasma =
      clamp(
        plasma,
        0.0,
        1.0
      );


    /*
     * ======================================================
     * GS-6H — CINEMATIC PLASMA COLOR SWEEP
     * ======================================================
     *
     * GS-6G established the projected trajectory.
     *
     * GS-6H gives that trajectory an unmistakable visual
     * hierarchy:
     *
     * violet / magenta wake
     *          ->
     * electric cyan
     *          ->
     * white-cyan leading head
     */

    float plasmaWakeColorStrength =
      clamp(
        plasmaWake *
        projectedSurfaceMask *
        uPlasmaStrength *
        1.18,
        0.0,
        1.0
      );


    float plasmaHeadColorStrength =
      clamp(
        plasmaCore *
        projectedSurfaceMask *
        uPlasmaStrength *
        1.42,
        0.0,
        1.0
      );


    /*
     * ======================================================
     * INTENSITY HIERARCHY
     * ======================================================
     *
     * deep sulcus   ~ almost invisible
     * quiet cortex  ~ very faint
     * normal gyrus  ~ visible
     * active gyrus  ~ bright
     * spark         ~ rare high intensity
     */

    float quietActivity =
      0.035 +
      particleNoise *
      0.055;


    float gyrusActivity =
      foldSignal *
      (
        0.10 +
        particleNoise *
        0.20
      );


    float activeActivity =
      zoneStrength *
      (
        0.30 +
        particleNoise *
        0.28
      );


    float activity =
      clamp(
        quietActivity +
        gyrusActivity +
        activeActivity +
        spark *
        0.48 +
        ridgeTracer *
        0.34 +
        hot *
        0.82,
        0.0,
        1.0
      );


    /*
     * ======================================================
     * COLOR
     * ======================================================
     */

    vec3 darkCortex =
      vec3(
        0.010,
        0.024,
        0.075
      );


    vec3 quietBlue =
      vec3(
        0.040,
        0.18,
        0.40
      );


    vec3 cyanColor =
      vec3(
        0.06,
        0.88,
        1.00
      );


    vec3 magentaColor =
      vec3(
        0.98,
        0.14,
        1.00
      );


    vec3 greenColor =
      vec3(
        0.42,
        0.24,
        1.00
      );


    vec3 amberColor =
      vec3(
        1.00,
        0.56,
        0.07
      );


    vec3 redColor =
      vec3(
        1.00,
        0.25,
        0.08
      );


    vec3 color =
      mix(
        darkCortex,
        quietBlue,
        foldSignal *
        (
          0.24 +
          particleNoise *
          0.22
        )
      );


    color =
      mix(
        color,
        cyanColor,
        cyanZone *
        foldSignal *
        0.92
      );


    color =
      mix(
        color,
        magentaColor,
        magentaZone *
        foldSignal *
        0.90
      );


    color =
      mix(
        color,
        greenColor,
        greenZone *
        foldSignal *
        0.86
      );


    color =
      mix(
        color,
        amberColor,
        amberZone *
        foldSignal *
        0.88
      );


    color =
      mix(
        color,
        redColor,
        redZone *
        foldSignal *
        0.82
      );


    /*
     * GS-6B:
     *
     * Ridge tracers alternate between electric cyan and violet.
     * Magenta / violet territories bias them toward purple.
     */
    vec3 tracerColor =
      mix(
        vec3(
          0.08,
          0.72,
          1.00
        ),
        vec3(
          0.90,
          0.20,
          1.00
        ),
        clamp(
          magentaZone +
          greenZone *
            0.72,
          0.0,
          1.0
        )
      );


    color =
      mix(
        color,
        tracerColor,
        ridgeTracer *
          0.72
      );


    /*
     * Rare spark cores approach cyan-white.
     */
    vec3 sparkCore =
      mix(
        vec3(
          0.78,
          0.98,
          1.00
        ),
        vec3(
          1.00,
          0.74,
          0.18
        ),
        clamp(
          amberZone *
            1.25 +
          redZone *
            0.45,
          0.0,
          1.0
        )
      );


    color =
      mix(
        color,
        sparkCore,
        spark *
          0.86
      );


    /*
     * Tiny neural vibration only.
     *
     * Much smaller than the old particle breathing so the
     * particles remain visually attached to gyri.
     */
    vec3 radial =
      normalize(
        p +
        vec3(
          0.0001
        )
      );


    float breathing =
      sin(
        uTime *
        1.25 +
        aSeed *
        19.0
      ) *
      0.0017;


    p +=
      radial *
      breathing;


    /*
     * Quiet sulcal particles are tiny.
     * Active gyri / signals become moderately larger.
     */
    float sizeHierarchy =
      0.56 +
      foldSignal *
      0.18 +
      zoneStrength *
      0.16 +
      spark *
      0.42 +
      ridgeTracer *
      0.22;


    /*
     * GS-6H surge colorization.
     *
     * This runs after normal GS-6B particle coloration,
     * therefore the quiet-state palette is completely
     * unaffected when the plasma envelope is zero.
     */
    vec3 plasmaWakeColor =
      vec3(
        0.92,
        0.08,
        1.00
      );


    vec3 plasmaHeadColor =
      vec3(
        0.80,
        0.98,
        1.00
      );


    color =
      mix(
        color,
        plasmaWakeColor,
        plasmaWakeColorStrength *
          0.82
      );


    color =
      mix(
        color,
        plasmaHeadColor,
        plasmaHeadColorStrength *
          0.98
      );


    vColor =
      color;


    vActivity =
      activity;


    vSpark =
      spark;


    vHot =
      hot;


    vPlasma =
      clamp(
        plasma +
        plasmaHeadColorStrength *
          0.32,
        0.0,
        1.0
      );

    vTracer =
      ridgeTracer;


    /*
     * Notice the extremely low base alpha.
     *
     * This is the key difference from the old cyan shell.
     */
    /*
     * ======================================================
     * GS-4D2 — READABLE NEURAL SKIN
     * ======================================================
     *
     * Quiet cortex becomes readable while deep sulci remain
     * strongly suppressed.
     */
    /*
     * GS-4D2
     *
     * Readable microscopic cortex while preserving the dark
     * anatomical substrate underneath.
     */
    vAlpha =
      0.052 +
      foldSignal *
      (
        0.095 +
        particleNoise *
          0.095
      ) +
      zoneStrength *
        0.52 +
      spark *
        0.78 +
      hot *
        0.14 +
      plasma *
        0.26 +
      ridgeTracer *
        0.30;


    vec4 mvPosition =
      modelViewMatrix *
      vec4(
        p,
        1.0
      );


    /*
     * ======================================================
     * GS-4H1 — READABLE PLASMA FRONT
     * ======================================================
     *
     * Plasma locally enlarges microscopic cortical particles.
     *
     * Outside the wave:
     * multiplier = 1.0
     *
     * At plasma peak:
     * multiplier = 2.35
     */
    /*
     * GS-6F:
     *
     * The travelling cortical surge grows locally without
     * changing the normal 48k particle size.
     */
    float plasmaPointLift =
      1.0 +
      plasma *
        1.55 +
      plasmaHeadColorStrength *
        0.70;


    gl_PointSize =
      uPointScale *
      aSize *
      sizeHierarchy *
      plasmaPointLift *
      (
        300.0 /
        max(
          1.0,
          -mvPosition.z
        )
      );


    gl_Position =
      projectionMatrix *
      mvPosition;
  }
`;

const SURFACE_FRAGMENT_SHADER = `
  varying vec3 vColor;
  varying float vAlpha;
  varying float vActivity;
  varying float vSpark;
  varying float vHot;
  varying float vPlasma;
  varying float vTracer;


  void main() {
    vec2 delta =
      gl_PointCoord -
      vec2(
        0.5
      );


    float radius =
      length(
        delta
      );


    if (
      radius >
      0.5
    ) {
      discard;
    }


    /*
     * Crisp microscopic core.
     */
    float core =
      smoothstep(
        0.50,
        0.055,
        radius
      );


    /*
     * Halo is intentionally restrained.
     *
     * Only active/spark particles get a meaningful luminous
     * envelope.
     */
    float halo =
      smoothstep(
        0.50,
        0.22,
        radius
      );


    float brightness =
      0.27 +
      vActivity *
        1.36 +
      vSpark *
        2.42 +
      vHot *
        4.05 +
      vPlasma *
        4.25 +
      vTracer *
        1.18;


    float coreWeight =
      0.64 +
      vActivity *
        0.48 +
      vSpark *
        0.28 +
      vHot *
        0.70 +
      vPlasma *
        0.26 +
      vTracer *
        0.24;


    float haloWeight =
      0.010 +
      vActivity *
        0.135 +
      vSpark *
        0.36 +
      vHot *
        0.62 +
      vPlasma *
        0.22 +
      vTracer *
        0.16;


    float alpha =
      (
        core *
        coreWeight +
        halo *
        haloWeight
      ) *
      clamp(
        vAlpha +
        vHot *
          0.48 +
        vPlasma *
          0.28 +
        vTracer *
          0.22,
        0.0,
        1.0
      );


    /*
     * Deep/quiet points remain restrained.
     * Rare sparks can exceed 1.0 and selectively reach Bloom.
     */
    /*
     * GS-4G1 — READABLE CORTICAL EXCITATION
     *
     * GS-4G local excitation now remains visible long enough
     * to read clearly as a cortical energy event.
     *
     * Local cortical excitation approaches cyan-white as its
     * intensity rises, but never replaces the underlying
     * GS-4D2 particle color globally.
     */
    vec3 excitationColor =
      mix(
        vColor,
        vec3(
          0.72,
          0.965,
          1.00
        ),
        smoothstep(
          0.10,
          0.90,
          vHot
        ) *
        0.90
      );


    /*
     * GS-4H:
     *
     * The plasma front approaches white/cyan at peak energy.
     * Outside the band, GS-4G1 color remains unchanged.
     */
    vec3 plasmaColor =
      mix(
        excitationColor,
        vec3(
          0.82,
          0.985,
          1.00
        ),
        smoothstep(
          0.08,
          0.82,
          vPlasma
        ) *
          0.96
      );


    vec3 outputColor =
      plasmaColor *
      brightness;


    gl_FragColor =
      vec4(
        outputColor,
        alpha
      );
  }
`;

const FIBER_VERTEX_SHADER = `
  attribute vec3 aColor;
  attribute float aProgress;
  attribute float aSeed;
  attribute float aSize;

  uniform float uTime;
  uniform float uEnergy;
  uniform float uPointScale;

  varying vec3 vColor;
  varying float vAlpha;
  varying float vPulse;


  float randomSignal(
    float value
  ) {
    return fract(
      sin(
        value
      ) *
      43758.5453123
    );
  }


  void main() {
    /*
     * ======================================================
     * GS-4F — TRAVELLING NEURAL SIGNALS
     * ======================================================
     *
     * GS-4E cortical fibers remain structurally unchanged.
     * Only selected fibers carry visible neural excitation.
     */


    /*
     * Approximately 43% of fibers carry travelling signals.
     *
     * aSeed is constant along each fiber.
     */
    float activitySelector =
      randomSignal(
        aSeed *
          173.71 +
        4.17
      );


    /*
     * GS-4F1 — READABLE TRAVELLING SIGNALS
     *
     * Slightly more signal-active fibers.
     */
    float activeFiber =
      step(
        0.30,
        activitySelector
      );


    /*
     * Slow, readable signal travel.
     *
     * Roughly one traversal every 9–12 seconds.
     */
    float signalSpeed =
      0.082 +
      uEnergy *
        0.014;


    float signalPosition =
      fract(
        uTime *
          signalSpeed +
        aSeed *
          1.731
      );


    /*
     * No circular distance:
     *
     * signal enters at one side,
     * moves along the fiber,
     * exits at the other side,
     * then later restarts.
     */
    float signalDistance =
      abs(
        aProgress -
        signalPosition
      );


    /*
     * Bright travelling signal head.
     */
    float pulse =
      exp(
        -pow(
          signalDistance /
            0.078,
          2.0
        )
      ) *
      activeFiber;


    /*
     * Short, weaker trail behind the signal head.
     */
    float trailPosition =
      signalPosition -
      0.125;


    float trailDistance =
      abs(
        aProgress -
        trailPosition
      );


    float trail =
      exp(
        -pow(
          trailDistance /
            0.145,
          2.0
        )
      ) *
      activeFiber *
      step(
        0.0,
        trailPosition
      ) *
      0.48;


    float excitation =
      clamp(
        pulse +
          trail,
        0.0,
        1.0
      );


    /*
     * Keep the underlying fiber naturally faded at both ends.
     */
    float endFade =
      smoothstep(
        0.0,
        0.12,
        aProgress
      ) *
      (
        1.0 -
        smoothstep(
          0.88,
          1.0,
          aProgress
        )
      );


    /*
     * ======================================================
     * SIGNAL COLOR FAMILY
     * ======================================================
     *
     * Most signals = cyan / cyan-white.
     *
     * Smaller populations:
     * magenta
     * green
     * amber
     */

    float colorSelector =
      randomSignal(
        aSeed *
          271.93 +
        8.41
      );


    vec3 signalColor =
      vec3(
        0.30,
        0.90,
        1.00
      );


    if (
      colorSelector >
        0.72 &&
      colorSelector <=
        0.86
    ) {
      signalColor =
        vec3(
          1.00,
          0.18,
          0.94
        );
    }


    if (
      colorSelector >
        0.86 &&
      colorSelector <=
        0.95
    ) {
      signalColor =
        vec3(
          0.48,
          0.28,
          1.00
        );
    }


    if (
      colorSelector >
      0.95
    ) {
      signalColor =
        vec3(
          1.00,
          0.60,
          0.10
        );
    }


    /*
     * Signal head moves toward white while retaining some
     * of its underlying color.
     */
    vec3 hotSignal =
      mix(
        signalColor,
        vec3(
          0.92,
          0.995,
          1.00
        ),
        pulse *
          0.68
      );


    vColor =
      mix(
        aColor,
        hotSignal,
        excitation *
          0.92
      );


    vPulse =
      excitation;


    /*
     * Static GS-4E fibers remain faint.
     *
     * The moving signal supplies most of the brightness.
     */
    float staticFiber =
      endFade *
      (
        0.165 +
        activeFiber *
          0.042
      );


    vAlpha =
      clamp(
        staticFiber +
        pulse *
          1.00 +
        trail *
          0.54,
        0.0,
        1.00
      );


    vec4 mvPosition =
      modelViewMatrix *
      vec4(
        position,
        1.0
      );


    /*
     * Local signal head grows.
     *
     * Rest of fiber stays microscopic.
     */
    gl_PointSize =
      uPointScale *
      aSize *
      (
        0.90 +
        pulse *
          6.40 +
        trail *
          2.05
      ) *
      (
        300.0 /
        max(
          1.0,
          -mvPosition.z
        )
      );


    gl_Position =
      projectionMatrix *
      mvPosition;
  }
`;

const FIBER_FRAGMENT_SHADER = `
  varying vec3 vColor;
  varying float vAlpha;
  varying float vPulse;


  void main() {
    vec2 delta =
      gl_PointCoord -
      vec2(
        0.5
      );


    float radius =
      length(
        delta
      );


    if (
      radius >
      0.5
    ) {
      discard;
    }


    /*
     * ======================================================
     * GS-4F — TRAVELLING SIGNAL CORE
     * ======================================================
     */

    float core =
      smoothstep(
        0.50,
        0.060,
        radius
      );


    float halo =
      smoothstep(
        0.50,
        0.20,
        radius
      );


    /*
     * Static fiber remains narrow.
     *
     * Moving excitation receives a stronger core and halo.
     */
    float coreWeight =
      0.70 +
      vPulse *
        0.56;


    float haloWeight =
      0.034 +
      vPulse *
        0.66;


    float alpha =
      (
        core *
          coreWeight +
        halo *
          haloWeight
      ) *
      vAlpha;


    /*
     * Only travelling excitation becomes strongly emissive.
     *
     * This allows selective Bloom without turning all fibers
     * into glowing lines.
     */
    float brightness =
      0.92 +
      vPulse *
        5.10;


    gl_FragColor =
      vec4(
        vColor *
          brightness,
        alpha
      );
  }
`;

const EJECTION_VERTEX_SHADER = `
  attribute vec3 aDirection;
  attribute float aPhase;
  attribute float aDistance;
  attribute float aSize;
  attribute vec3 aColor;

  uniform float uTime;
  uniform float uEnergy;
  uniform float uPointScale;

  varying vec3 vColor;
  varying float vAlpha;
  varying float vHeat;

  void main() {
    float life =
      fract(
        uTime *
          (
            0.13 +
            uEnergy * 0.025
          ) +
        aPhase
      );

    /*
     * Benchmark particles leave quickly enough to read,
     * but remain visible for several seconds.
     */
    float travel =
      pow(
        life,
        0.72
      );

    vec3 p =
      position +
      aDirection *
        aDistance *
        travel;

    float birthHeat =
      exp(
        -pow(
          life /
          0.27,
          1.45
        )
      );

    float distanceFade =
      1.0 -
      smoothstep(
        0.16,
        0.95,
        travel
      );

    float death =
      1.0 -
      smoothstep(
        0.72,
        0.98,
        life
      );

    float emergence =
      smoothstep(
        0.0,
        0.035,
        life
      );

    vColor =
      mix(
        aColor,
        vec3(1.0),
        birthHeat * 0.66
      );

    vHeat =
      birthHeat;

    vAlpha =
      emergence *
      distanceFade *
      death *
      (
        0.48 +
        birthHeat * 1.18
      );

    vec4 mvPosition =
      modelViewMatrix *
      vec4(
        p,
        1.0
      );

    gl_PointSize =
      uPointScale *
      aSize *
      (
        0.72 +
        birthHeat * 3.2
      ) *
      (
        300.0 /
        max(
          1.0,
          -mvPosition.z
        )
      );

    gl_Position =
      projectionMatrix *
      mvPosition;
  }
`;

const EJECTION_FRAGMENT_SHADER = `
  varying vec3 vColor;
  varying float vAlpha;
  varying float vHeat;

  void main() {
    vec2 delta =
      gl_PointCoord -
      vec2(0.5);

    float radius =
      length(
        delta
      );

    if (
      radius > 0.5
    ) {
      discard;
    }

    float core =
      smoothstep(
        0.5,
        0.025,
        radius
      );

    float halo =
      smoothstep(
        0.5,
        0.18,
        radius
      );

    float alpha =
      (
        core * 0.76 +
        halo * 0.36
      ) *
      vAlpha;

    gl_FragColor =
      vec4(
        vColor *
        (
          0.86 +
          vHeat * 2.10
        ),
        alpha
      );
  }
`;

/* ==========================================================
   GS-4H3 — FOLDED-SURFACE PLASMA RIBBON
   ==========================================================

   Continuous plasma rendering directly on the exact GS-4C1
   cortical mesh.

   The underlying BrainBody geometry already includes the real
   cortical relief through aCorticalDisplacement.
   ========================================================== */

const PLASMA_RIBBON_VERTEX_SHADER = `
  attribute float aCorticalDisplacement;
  attribute float aCorticalU;
  attribute float aCorticalQ;
  attribute float aCorticalLateral;

  varying vec3 vLocalPosition;
  varying float vCorticalSignal;
  varying float vCorticalU;
  varying float vCorticalQ;
  varying float vCorticalLateral;
  varying float vViewFacing;
  varying vec2 vPlasmaViewPosition;


  void main() {
    /*
     * Real GS-4C1 physical cortical relief.
     */
    vCorticalSignal =
      smoothstep(
        -0.024,
        0.006,
        aCorticalDisplacement
      );


    /*
     * Keep generator-space cortical information available.
     */
    vCorticalU =
      aCorticalU;

    vCorticalQ =
      aCorticalQ;

    vCorticalLateral =
      aCorticalLateral;

    vLocalPosition =
      position;


    /*
     * ======================================================
     * GS-4H3B5 — FACE-WEIGHTED PLASMA VISIBILITY
     * ======================================================
     *
     * Retained only as restrained surface weighting.
     */
    vec3 plasmaViewNormal =
      normalize(
        normalMatrix *
        normal
      );


    vViewFacing =
      clamp(
        abs(
          plasmaViewNormal.z
        ),
        0.0,
        1.0
      );


    /*
     * ======================================================
     * GS-4H3B2 — CORTICAL OVERLAY DEPTH SEPARATION
     * ======================================================
     *
     * Keep the proven microscopic surface lift.
     */
    vec3 overlayPosition =
      position +
      normal *
        0.0045;


    /*
     * ======================================================
     * GS-4H3C — PROJECTED CORTICAL PLASMA PATH
     * ======================================================
     *
     * The effect is still rendered on actual folded cortical
     * triangles.
     *
     * We simply measure those triangles in VIEW SPACE so the
     * travelling head remains readable while the brain turns.
     */
    vec4 plasmaViewPosition =
      modelViewMatrix *
      vec4(
        overlayPosition,
        1.0
      );


    vPlasmaViewPosition =
      plasmaViewPosition.xy;


    gl_Position =
      projectionMatrix *
      plasmaViewPosition;
  }
`;


const PLASMA_RIBBON_FRAGMENT_SHADER = `
  uniform float uTime;
  uniform float uPlasmaProgress;
  uniform float uPlasmaStrength;

  varying vec3 vLocalPosition;
  varying float vCorticalSignal;
  varying float vCorticalU;
  varying float vCorticalQ;
  varying float vCorticalLateral;
  varying float vViewFacing;
  varying vec2 vPlasmaViewPosition;


  /*
   * ========================================================
   * GS-4H3C — PROJECTED CORTICAL PLASMA PATH
   * ========================================================
   *
   * A compact curved path across the CURRENTLY VISIBLE brain.
   *
   * The path exists only as a shader coordinate.
   * The emitted pixels still belong to the actual brain mesh.
   */
  vec2 plasmaPathPoint(
    float t
  ) {
    float x =
      mix(
        0.52,
        -0.52,
        t
      );


    float y =
      -0.12 +
      t *
        0.24 +
      sin(
        t *
          3.14159265
      ) *
        0.085 +
      sin(
        t *
          7.20 +
        0.40
      ) *
        0.018;


    return vec2(
      x,
      y
    );
  }


  float plasmaEllipse(
    vec2 position,
    vec2 center,
    vec2 radius
  ) {
    vec2 d =
      (
        position -
        center
      ) /
      radius;


    return exp(
      -dot(
        d,
        d
      )
    );
  }


  void main() {
    vec2 p =
      vPlasmaViewPosition;


    /*
     * ======================================================
     * LEADING WHITE/CYAN HEAD
     * ======================================================
     */
    vec2 headCenter =
      plasmaPathPoint(
        uPlasmaProgress
      );


    float headEnergy =
      plasmaEllipse(
        p,
        headCenter,
        vec2(
          0.082,
          0.051
        )
      );


    /*
     * ======================================================
     * CONTINUOUS DIRECTIONAL WAKE
     * ======================================================
     *
     * Seven overlapping previous positions generate a short
     * continuous curved trail behind the moving head.
     *
     * This avoids:
     * - complete rings
     * - coordinate slices
     * - long permanent stripes
     */
    float wakeEnergy =
      0.0;


    for (
      int i = 1;
      i <= 7;
      i++
    ) {
      float index =
        float(i);


      float lag =
        index *
          0.045;


      float valid =
        step(
          lag,
          uPlasmaProgress
        );


      float trailProgress =
        clamp(
          uPlasmaProgress -
          lag,
          0.0,
          1.0
        );


      vec2 trailCenter =
        plasmaPathPoint(
          trailProgress
        );


      float sampleEnergy =
        plasmaEllipse(
          p,
          trailCenter,
          vec2(
            0.102,
            0.060
          )
        );


      float decay =
        1.0 -
        index /
          8.0;


      wakeEnergy =
        max(
          wakeEnergy,
          sampleEnergy *
          decay *
          valid
        );
    }


    /*
     * ======================================================
     * REAL CORTICAL SURFACE MASK
     * ======================================================
     *
     * The path is projected for readability, but it remains
     * modulated by actual cortical anatomy.
     */
    float foldMask =
      0.40 +
      vCorticalSignal *
        0.60;


    /*
     * Keep medial-wall contribution restrained without
     * completely destroying the projected path.
     */
    float lateralResponse =
      smoothstep(
        0.12,
        0.55,
        vCorticalLateral
      );


    float lateralMask =
      0.32 +
      lateralResponse *
        0.68;


    /*
     * H3B5's view weighting becomes intentionally mild here.
     *
     * Projection already solves visibility.
     * This only prevents the silhouette from dominating.
     */
    float facingResponse =
      smoothstep(
        0.08,
        0.68,
        vViewFacing
      );


    float facingGain =
      mix(
        0.48,
        1.12,
        facingResponse
      );


    float surfaceMask =
      foldMask *
      lateralMask *
      facingGain;


    float head =
      headEnergy *
      surfaceMask *
      uPlasmaStrength;


    float wake =
      wakeEnergy *
      surfaceMask *
      uPlasmaStrength *
      0.82;


    /*
     * Small cortical shimmer prevents an absolutely sterile
     * vector-graphics appearance.
     */
    float organic =
      0.96 +
      sin(
        vCorticalU *
          31.0 +
        vCorticalQ *
          17.0 +
        uTime *
          0.65
      ) *
        0.04;


    head *=
      organic;

    wake *=
      organic;


    /*
     * ======================================================
     * GS-6I — CINEMATIC TRAVELLING ACTIVATION FRONT
     * ======================================================
     *
     * The older H3C / GS-6H event correctly travels, but the
     * motion is visually distributed over too many cortical
     * fragments.
     *
     * GS-6I adds one deliberately readable event-only front:
     *
     * MAGENTA TAIL -> CYAN BODY -> WHITE LEADING EDGE
     *
     * It still renders on real folded cortical triangles.
     * No screen-space quad and no new brain geometry.
     */

    float activationSurfaceMask =
      (
        0.52 +
        vCorticalSignal *
          0.48
      ) *
      mix(
        0.66,
        1.00,
        facingResponse
      );


    /*
     * Cyan body centered on the current plasma position.
     */
    float activationBody =
      plasmaEllipse(
        p,
        headCenter,
        vec2(
          0.066,
          0.034
        )
      ) *
      activationSurfaceMask *
      uPlasmaStrength;


    /*
     * Wider soft glow gives the body continuity.
     */
    float activationHalo =
      plasmaEllipse(
        p,
        headCenter,
        vec2(
          0.138,
          0.074
        )
      ) *
      activationSurfaceMask *
      uPlasmaStrength;


    /*
     * A tiny point slightly AHEAD of the cyan body establishes
     * an unmistakable direction of travel.
     */
    float activationLeadProgress =
      min(
        1.0,
        uPlasmaProgress +
          0.020
      );


    vec2 activationLeadCenter =
      plasmaPathPoint(
        activationLeadProgress
      );


    float activationLead =
      plasmaEllipse(
        p,
        activationLeadCenter,
        vec2(
          0.035,
          0.019
        )
      ) *
      activationSurfaceMask *
      uPlasmaStrength;


    /*
     * Existing directional wake becomes the magenta tail.
     */
    float activationTail =
      wakeEnergy *
      activationSurfaceMask *
      uPlasmaStrength *
      0.82;


    float ribbon =
      clamp(
        head +
        wake,
        0.0,
        1.0
      );


    /*
     * Keep GS-6I alive even where the old ribbon would have
     * been below its discard threshold.
     */
    ribbon =
      max(
        ribbon,
        clamp(
          activationLead +
          activationBody +
          activationHalo *
            0.52 +
          activationTail *
            0.42,
          0.0,
          1.0
        )
      );


    if (
      ribbon <
      0.004
    ) {
      discard;
    }


    /*
     * ======================================================
     * COLOR
     * ======================================================
     */
    vec3 cyan =
      vec3(
        0.05,
        0.82,
        1.00
      );


    vec3 violetMagenta =
      vec3(
        0.96,
        0.15,
        1.00
      );


    vec3 whiteCyan =
      vec3(
        0.92,
        1.00,
        1.00
      );


    /*
     * GS-6B:
     *
     * Magenta/violet wake -> cyan -> white/cyan head.
     */
    vec3 ribbonColor =
      mix(
        violetMagenta,
        cyan,
        smoothstep(
          0.04,
          0.52,
          head
        )
      );


    ribbonColor =
      mix(
        ribbonColor,
        whiteCyan,
        smoothstep(
          0.12,
          0.78,
          head
        ) *
          0.94
      );


    /*
     * Preserve H3B1's local HDR hierarchy.
     *
     * Global Bloom is unchanged.
     */
    /*
     * ======================================================
     * GS-6I COLOR CHOREOGRAPHY
     * ======================================================
     */

    vec3 activationMagenta =
      vec3(
        1.00,
        0.055,
        0.92
      );


    vec3 activationCyan =
      vec3(
        0.025,
        0.89,
        1.00
      );


    vec3 activationWhite =
      vec3(
        0.98,
        1.00,
        1.00
      );


    /*
     * Tail first.
     */
    ribbonColor =
      mix(
        ribbonColor,
        activationMagenta,
        clamp(
          activationTail *
            0.92,
          0.0,
          0.88
        )
      );


    /*
     * Cyan body replaces magenta as the head approaches.
     */
    ribbonColor =
      mix(
        ribbonColor,
        activationCyan,
        clamp(
          activationHalo *
            0.76 +
          activationBody *
            0.58,
          0.0,
          0.96
        )
      );


    /*
     * Tiny white-hot directional tip.
     */
    ribbonColor =
      mix(
        ribbonColor,
        activationWhite,
        clamp(
          activationBody *
            0.52 +
          activationLead *
            1.20,
          0.0,
          1.0
        )
      );


    float brightness =
      0.86 +
      head *
        10.60 +
      wake *
        5.20;


    /*
     * GS-6I HDR hierarchy.
     *
     * The white tip is intentionally much brighter than its
     * tail so direction remains obvious even in motion.
     */
    brightness +=
      activationTail *
        3.20 +
      activationHalo *
        4.60 +
      activationBody *
        10.80 +
      activationLead *
        17.50;


    float alpha =
      clamp(
        head *
          1.00 +
        wake *
          0.68,
        0.0,
        0.95
      );


    /*
     * Event visibility only.
     *
     * When uPlasmaStrength is zero, every GS-6I term is zero.
     */
    alpha =
      clamp(
        alpha +
        activationTail *
          0.26 +
        activationHalo *
          0.42 +
        activationBody *
          0.72 +
        activationLead *
          0.96,
        0.0,
        0.98
      );


    gl_FragColor =
      vec4(
        ribbonColor *
          brightness,
        alpha
      );
  }
`;

/* ==========================================================
   BRAIN BODY
   ========================================================== */

function buildBrainBodyGeometry(
  lobe: Lobe,
): BufferGeometry {
  /*
   * ========================================================
   * GS-4C1 — DENSE CORTICAL REFINEMENT
   * ========================================================
   *
   * Replace GS-4B's segmented regional-union + separate
   * medial-wall architecture.
   *
   * Each hemisphere is now ONE continuous closed coronal loop.
   *
   * This eliminates:
   * - black rectangular cavity
   * - disconnected medial wall
   * - obvious spherical/lobar segmentation
   *
   * Smooth anatomy validation only.
   * Gyri/sulci remain OFF.
   */


  const longitudinalSegments =
    192;

  const ringSegments =
    144;

  const positions:
    number[] =
    [];

  const indices:
    number[] =
    [];


  function clamp01(
    value: number,
  ): number {
    return Math.max(
      0,
      Math.min(
        1,
        value,
      ),
    );
  }


  function gaussian(
    value: number,
    center: number,
    radius: number,
  ): number {
    const d =
      (
        value -
        center
      ) /
      radius;

    return Math.exp(
      -d * d,
    );
  }


  function sampleProfile(
    profile:
      Array<
        [number, number]
      >,
    value: number,
  ): number {
    if (
      value <=
      profile[0][0]
    ) {
      return profile[0][1];
    }

    const last =
      profile.length - 1;

    if (
      value >=
      profile[last][0]
    ) {
      return profile[last][1];
    }

    for (
      let index = 0;
      index < last;
      index += 1
    ) {
      const a =
        profile[index];

      const b =
        profile[index + 1];

      if (
        value >= a[0] &&
        value <= b[0]
      ) {
        const raw =
          (
            value -
            a[0]
          ) /
          (
            b[0] -
            a[0]
          );

        const smooth =
          raw *
          raw *
          (
            3 -
            2 *
              raw
          );

        return (
          a[1] +
          (
            b[1] -
            a[1]
          ) *
            smooth
        );
      }
    }

    return profile[last][1];
  }


  /*
   * SIDE PROFILE
   *
   * -1 = posterior
   * +1 = anterior
   */
  const TOP_PROFILE:
    Array<
      [number, number]
    > =
    [
      [-1.00,  0.030],
      [-0.96,  0.120],
      [-0.90,  0.210],
      [-0.82,  0.296],
      [-0.72,  0.368],
      [-0.60,  0.424],
      [-0.46,  0.468],
      [-0.30,  0.500],
      [-0.12,  0.520],
      [ 0.06,  0.528],
      [ 0.23,  0.522],
      [ 0.39,  0.504],
      [ 0.54,  0.478],
      [ 0.68,  0.440],
      [ 0.80,  0.392],
      [ 0.89,  0.332],
      [ 0.95,  0.250],
      [ 0.985, 0.150],
      [ 1.00,  0.030],
    ];


  const BOTTOM_PROFILE:
    Array<
      [number, number]
    > =
    [
      [-1.00,  0.030],
      [-0.96, -0.002],
      [-0.90, -0.034],
      [-0.82, -0.060],
      [-0.72, -0.082],
      [-0.62, -0.099],
      [-0.52, -0.116],

      /*
       * Posterior underside rises before the temporal lobe.
       */
      [-0.42, -0.142],
      [-0.32, -0.184],
      [-0.22, -0.235],

      /*
       * Genuine temporal descent.
       */
      [-0.10, -0.292],
      [ 0.02, -0.338],
      [ 0.14, -0.365],
      [ 0.27, -0.372],
      [ 0.40, -0.356],
      [ 0.52, -0.322],

      /*
       * Frontal underside rises progressively.
       */
      [ 0.63, -0.278],
      [ 0.73, -0.230],
      [ 0.82, -0.181],
      [ 0.89, -0.133],
      [ 0.94, -0.086],
      [ 0.975,-0.035],
      [ 1.00,  0.030],
    ];


  /*
   * TOP VIEW WIDTH
   */
  const WIDTH_PROFILE:
    Array<
      [number, number]
    > =
    [
      [-1.00, 0.000],
      [-0.96, 0.120],
      [-0.90, 0.215],
      [-0.82, 0.296],
      [-0.72, 0.360],
      [-0.60, 0.408],
      [-0.46, 0.444],
      [-0.30, 0.466],
      [-0.12, 0.480],
      [ 0.06, 0.484],
      [ 0.23, 0.476],
      [ 0.40, 0.458],
      [ 0.56, 0.428],
      [ 0.70, 0.386],
      [ 0.82, 0.328],
      [ 0.90, 0.258],
      [ 0.96, 0.160],
      [ 1.00, 0.000],
    ];


  /*
   * Human coronal hemisphere.
   *
   * X:
   * 0 = medial
   * 1 = lateral
   *
   * Y:
   * +1 = superior
   * -1 = inferior
   *
   * CLOSED clockwise loop.
   */
  const CORONAL_PROFILE:
    Array<
      [number, number]
    > =
    [
      /*
       * Superior-medial crown.
       */
      [0.040,  1.000],
      [0.160,  0.994],
      [0.350,  0.970],
      [0.550,  0.920],
      [0.730,  0.830],
      [0.875,  0.690],
      [0.965,  0.510],

      /*
       * Maximum lateral convexity.
       */
      [1.000,  0.290],
      [0.995,  0.070],
      [0.965, -0.150],
      [0.900, -0.350],

      /*
       * Inferolateral / temporal surface.
       *
       * Broader and substantially less pointy than GS-4B1.
       */
      [0.810, -0.520],
      [0.700, -0.650],
      [0.570, -0.735],
      [0.430, -0.775],
      [0.310, -0.760],
      [0.215, -0.700],

      /*
       * Inferomedial cortex returns gently toward the midline.
       */
      [0.145, -0.610],
      [0.095, -0.490],
      [0.060, -0.330],
      [0.040, -0.150],

      /*
       * Medial wall / longitudinal fissure.
       */
      [0.032,  0.050],
      [0.030,  0.270],
      [0.032,  0.490],
      [0.034,  0.700],
      [0.037,  0.870],
    ];


  function catmullRom(
    p0: number,
    p1: number,
    p2: number,
    p3: number,
    t: number,
  ): number {
    const t2 =
      t * t;

    const t3 =
      t2 * t;

    return (
      0.5 *
      (
        2 * p1 +
        (
          -p0 +
          p2
        ) *
          t +
        (
          2 * p0 -
          5 * p1 +
          4 * p2 -
          p3
        ) *
          t2 +
        (
          -p0 +
          3 * p1 -
          3 * p2 +
          p3
        ) *
          t3
      )
    );
  }


  function sampleClosedCoronal(
    t: number,
  ): [
    number,
    number,
  ] {
    const count =
      CORONAL_PROFILE.length;

    const scaled =
      t * count;

    const floorValue =
      Math.floor(
        scaled,
      );

    const index =
      floorValue %
      count;

    const local =
      scaled -
      floorValue;

    const i0 =
      (
        index -
        1 +
        count
      ) %
      count;

    const i1 =
      index;

    const i2 =
      (
        index +
        1
      ) %
      count;

    const i3 =
      (
        index +
        2
      ) %
      count;

    const x =
      catmullRom(
        CORONAL_PROFILE[i0][0],
        CORONAL_PROFILE[i1][0],
        CORONAL_PROFILE[i2][0],
        CORONAL_PROFILE[i3][0],
        local,
      );

    const y =
      catmullRom(
        CORONAL_PROFILE[i0][1],
        CORONAL_PROFILE[i1][1],
        CORONAL_PROFILE[i2][1],
        CORONAL_PROFILE[i3][1],
        local,
      );

    return [
      clamp01(
        x,
      ),

      Math.max(
        -1,
        Math.min(
          1,
          y,
        ),
      ),
    ];
  }


  /*
   * ========================================================
   * GS-4C — CORTICAL TOPOLOGY
   * ========================================================
   *
   * Coordinates:
   *
   * s  = posterior <-> anterior
   * q  = inferior  <-> superior
   *
   * Major sulci establish human cortical organization.
   * Secondary and tertiary paths break the cortex into
   * irregular branching gyri.
   *
   * These are PHYSICAL mesh folds.
   */


  type CorticalPath =
    Array<
      [number, number]
    >;


  /*
   * --------------------------------------------------------
   * MAJOR ANATOMICAL SULCI
   * --------------------------------------------------------
   *
   * Includes approximate:
   *
   * - central sulcus
   * - lateral / Sylvian fissure
   * - intraparietal sulcus
   * - superior temporal sulcus
   * - parieto-occipital transition
   */
  const MAJOR_CORTICAL_PATHS:
    CorticalPath[] =
    [
      /*
       * Central sulcus.
       */
      [
        [ 0.12,  0.88],
        [ 0.08,  0.70],
        [ 0.04,  0.50],
        [ 0.00,  0.30],
        [-0.05,  0.10],
        [-0.09, -0.04],
      ],

      /*
       * Sylvian / lateral fissure.
       */
      [
        [ 0.55,  0.02],
        [ 0.39, -0.05],
        [ 0.20, -0.12],
        [ 0.00, -0.18],
        [-0.20, -0.21],
        [-0.38, -0.20],
      ],

      /*
       * Intraparietal.
       */
      [
        [-0.08,  0.63],
        [-0.22,  0.57],
        [-0.38,  0.49],
        [-0.52,  0.39],
        [-0.62,  0.28],
      ],

      /*
       * Superior temporal sulcus.
       */
      [
        [ 0.43, -0.38],
        [ 0.25, -0.43],
        [ 0.05, -0.47],
        [-0.16, -0.46],
        [-0.34, -0.40],
        [-0.46, -0.32],
      ],

      /*
       * Posterior/parieto-occipital.
       */
      [
        [-0.40,  0.82],
        [-0.49,  0.66],
        [-0.57,  0.50],
        [-0.64,  0.34],
      ],
    ];


  /*
   * --------------------------------------------------------
   * SECONDARY CORTICAL PATHS
   * --------------------------------------------------------
   */
  const SECONDARY_CORTICAL_PATHS:
    CorticalPath[] =
    [
      /* precentral */
      [
        [0.26, 0.84],
        [0.21, 0.66],
        [0.17, 0.47],
        [0.14, 0.28],
        [0.11, 0.14],
      ],

      /* postcentral */
      [
        [-0.07, 0.87],
        [-0.11, 0.69],
        [-0.14, 0.50],
        [-0.17, 0.31],
        [-0.20, 0.12],
      ],

      /* superior frontal */
      [
        [0.83, 0.73],
        [0.68, 0.68],
        [0.53, 0.60],
        [0.39, 0.50],
        [0.29, 0.40],
      ],

      /* middle frontal */
      [
        [0.84, 0.47],
        [0.68, 0.40],
        [0.54, 0.32],
        [0.40, 0.24],
        [0.29, 0.18],
      ],

      /* inferior frontal */
      [
        [0.79, 0.22],
        [0.64, 0.15],
        [0.50, 0.08],
        [0.38, 0.03],
      ],

      /* frontal orbital */
      [
        [0.76, -0.10],
        [0.62, -0.14],
        [0.49, -0.16],
        [0.38, -0.15],
      ],

      /* superior frontal crown */
      [
        [0.60, 0.90],
        [0.47, 0.82],
        [0.35, 0.73],
        [0.26, 0.66],
      ],

      /* medial-superior frontal continuation */
      [
        [0.30, 0.94],
        [0.18, 0.84],
        [0.08, 0.76],
      ],

      /* superior parietal */
      [
        [-0.18, 0.82],
        [-0.31, 0.73],
        [-0.44, 0.62],
        [-0.54, 0.52],
      ],

      /* mid parietal */
      [
        [-0.21, 0.38],
        [-0.36, 0.31],
        [-0.51, 0.22],
        [-0.64, 0.10],
      ],

      /* lower parietal */
      [
        [-0.22, 0.14],
        [-0.39, 0.07],
        [-0.54, -0.01],
        [-0.67, -0.09],
      ],

      /* superior occipital */
      [
        [-0.57, 0.72],
        [-0.70, 0.59],
        [-0.82, 0.42],
        [-0.89, 0.27],
      ],

      /* middle occipital */
      [
        [-0.61, 0.36],
        [-0.74, 0.25],
        [-0.85, 0.11],
        [-0.91, -0.02],
      ],

      /* inferior occipital */
      [
        [-0.59, -0.07],
        [-0.71, -0.17],
        [-0.82, -0.28],
      ],

      /* middle temporal */
      [
        [0.46, -0.57],
        [0.27, -0.62],
        [0.07, -0.65],
        [-0.14, -0.62],
        [-0.31, -0.55],
      ],

      /* inferior temporal */
      [
        [0.43, -0.75],
        [0.23, -0.79],
        [0.02, -0.79],
        [-0.18, -0.74],
        [-0.33, -0.66],
      ],

      /* posterior temporal */
      [
        [-0.08, -0.31],
        [-0.25, -0.34],
        [-0.41, -0.30],
        [-0.54, -0.22],
      ],

      /* crown transverse 1 */
      [
        [0.04, 0.94],
        [-0.08, 0.85],
        [-0.18, 0.76],
      ],

      /* crown transverse 2 */
      [
        [-0.30, 0.92],
        [-0.42, 0.82],
        [-0.54, 0.69],
      ],
    ];


  /*
   * --------------------------------------------------------
   * TERTIARY BRANCHES
   * --------------------------------------------------------
   *
   * Shorter interrupted paths are critical.
   *
   * Without these, the cortex looks like a few long carved
   * stripes instead of interlocking gyri.
   */
  const TERTIARY_CORTICAL_PATHS:
    CorticalPath[] =
    [
      [[0.72,0.83],[0.64,0.75],[0.57,0.70]],
      [[0.54,0.54],[0.45,0.48],[0.38,0.40]],
      [[0.73,0.57],[0.64,0.53],[0.57,0.46]],
      [[0.59,0.27],[0.52,0.23],[0.46,0.17]],
      [[0.69,0.03],[0.60,-0.02],[0.53,-0.06]],

      [[0.37,0.78],[0.30,0.72],[0.24,0.64]],
      [[0.29,0.57],[0.23,0.50],[0.19,0.42]],
      [[0.31,0.31],[0.25,0.25],[0.21,0.18]],

      [[-0.02,0.72],[-0.08,0.65],[-0.12,0.58]],
      [[-0.25,0.68],[-0.32,0.60],[-0.38,0.53]],
      [[-0.29,0.48],[-0.36,0.42],[-0.42,0.36]],
      [[-0.36,0.25],[-0.44,0.19],[-0.50,0.12]],

      [[-0.52,0.80],[-0.60,0.72],[-0.66,0.64]],
      [[-0.66,0.52],[-0.74,0.43],[-0.80,0.34]],
      [[-0.68,0.17],[-0.77,0.10],[-0.83,0.03]],
      [[-0.67,-0.02],[-0.75,-0.09],[-0.82,-0.16]],

      [[0.34,-0.29],[0.25,-0.34],[0.17,-0.36]],
      [[0.29,-0.50],[0.19,-0.54],[0.10,-0.56]],
      [[0.14,-0.70],[0.04,-0.72],[-0.06,-0.70]],
      [[-0.10,-0.53],[-0.20,-0.55],[-0.28,-0.51]],

      [[0.47,0.88],[0.39,0.84],[0.33,0.78]],
      [[0.11,0.89],[0.03,0.83],[-0.04,0.77]],
      [[-0.17,0.90],[-0.25,0.84],[-0.32,0.77]],
      [[-0.46,0.91],[-0.54,0.84],[-0.61,0.75]],

      [[0.84,0.35],[0.77,0.31],[0.71,0.26]],
      [[0.87,0.12],[0.79,0.08],[0.71,0.04]],
      [[-0.85,0.52],[-0.90,0.43],[-0.93,0.34]],
      [[-0.81,-0.32],[-0.87,-0.25],[-0.91,-0.17]],
    ];


  /*
   * ========================================================
   * GS-4C1 — SHORT BRANCHING CORTICAL DETAIL
   * ========================================================
   *
   * These deliberately short paths create:
   *
   * - forks
   * - interrupted sulci
   * - terminating sulci
   * - denser superior cortex
   * - finer frontal/parietal/temporal/occipital structure
   *
   * They remain subordinate to the major anatomical sulci.
   */
  const MICRO_CORTICAL_PATHS:
    CorticalPath[] =
    [
      /* superior / crown */
      [[ 0.82, 0.90],[ 0.75, 0.84],[ 0.68, 0.77]],
      [[ 0.75, 0.84],[ 0.67, 0.91],[ 0.58, 0.94]],
      [[ 0.58, 0.84],[ 0.50, 0.78],[ 0.43, 0.72]],
      [[ 0.50, 0.78],[ 0.43, 0.87],[ 0.35, 0.92]],
      [[ 0.29, 0.93],[ 0.21, 0.86],[ 0.13, 0.79]],
      [[ 0.21, 0.86],[ 0.13, 0.94],[ 0.04, 0.96]],
      [[-0.08, 0.91],[-0.17, 0.84],[-0.25, 0.76]],
      [[-0.17, 0.84],[-0.26, 0.92],[-0.35, 0.94]],
      [[-0.40, 0.87],[-0.48, 0.80],[-0.56, 0.72]],
      [[-0.48, 0.80],[-0.57, 0.87],[-0.66, 0.86]],

      /* frontal */
      [[0.86,0.70],[0.78,0.65],[0.70,0.58]],
      [[0.78,0.65],[0.74,0.75],[0.66,0.80]],
      [[0.76,0.48],[0.68,0.43],[0.60,0.36]],
      [[0.68,0.43],[0.63,0.52],[0.55,0.57]],
      [[0.82,0.27],[0.74,0.22],[0.66,0.16]],
      [[0.74,0.22],[0.68,0.31],[0.60,0.35]],
      [[0.69,0.03],[0.61,-0.02],[0.53,-0.07]],
      [[0.61,-0.02],[0.55,0.06],[0.48,0.10]],

      /* central / pericentral */
      [[0.25,0.68],[0.18,0.62],[0.13,0.55]],
      [[0.18,0.62],[0.11,0.70],[0.04,0.73]],
      [[0.18,0.40],[0.11,0.34],[0.06,0.27]],
      [[0.11,0.34],[0.04,0.41],[-0.03,0.44]],
      [[0.10,0.13],[0.04,0.08],[-0.02,0.01]],
      [[0.04,0.08],[-0.03,0.15],[-0.10,0.18]],

      /* parietal */
      [[-0.29,0.69],[-0.37,0.63],[-0.45,0.55]],
      [[-0.37,0.63],[-0.44,0.71],[-0.52,0.75]],
      [[-0.32,0.43],[-0.40,0.37],[-0.48,0.30]],
      [[-0.40,0.37],[-0.47,0.45],[-0.55,0.48]],
      [[-0.39,0.17],[-0.47,0.11],[-0.55,0.04]],
      [[-0.47,0.11],[-0.54,0.19],[-0.61,0.22]],

      /* occipital */
      [[-0.64,0.61],[-0.72,0.54],[-0.79,0.45]],
      [[-0.72,0.54],[-0.79,0.61],[-0.86,0.62]],
      [[-0.70,0.29],[-0.78,0.22],[-0.85,0.14]],
      [[-0.78,0.22],[-0.85,0.29],[-0.91,0.31]],
      [[-0.69,-0.02],[-0.77,-0.09],[-0.84,-0.17]],
      [[-0.77,-0.09],[-0.84,-0.02],[-0.90,0.00]],

      /* temporal / inferolateral */
      [[0.47,-0.31],[0.39,-0.36],[0.31,-0.39]],
      [[0.39,-0.36],[0.33,-0.29],[0.26,-0.26]],
      [[0.41,-0.49],[0.33,-0.53],[0.25,-0.56]],
      [[0.33,-0.53],[0.27,-0.46],[0.20,-0.43]],
      [[0.29,-0.66],[0.20,-0.69],[0.11,-0.70]],
      [[0.20,-0.69],[0.14,-0.62],[0.07,-0.59]],
      [[0.05,-0.54],[-0.04,-0.57],[-0.13,-0.55]],
      [[-0.04,-0.57],[-0.10,-0.49],[-0.17,-0.45]],
      [[-0.21,-0.64],[-0.29,-0.61],[-0.37,-0.56]],
      [[-0.29,-0.61],[-0.35,-0.52],[-0.42,-0.47]],
    ];


  function smoothstep01(
    value: number,
  ): number {
    const v =
      clamp01(
        value,
      );

    return (
      v *
      v *
      (
        3 -
        2 *
          v
      )
    );
  }


  function distanceToSegment2D(
    px: number,
    py: number,
    ax: number,
    ay: number,
    bx: number,
    by: number,
  ): number {
    const abx =
      bx - ax;

    const aby =
      by - ay;

    const apx =
      px - ax;

    const apy =
      py - ay;

    const denominator =
      abx * abx +
      aby * aby;

    if (
      denominator <
      1e-8
    ) {
      const dx =
        px - ax;

      const dy =
        py - ay;

      return Math.sqrt(
        dx * dx +
        dy * dy,
      );
    }

    const t =
      clamp01(
        (
          apx * abx +
          apy * aby
        ) /
        denominator,
      );

    const cx =
      ax +
      abx * t;

    const cy =
      ay +
      aby * t;

    const dx =
      px - cx;

    const dy =
      py - cy;

    return Math.sqrt(
      dx * dx +
      dy * dy,
    );
  }


  function distanceToPath(
    s: number,
    q: number,
    path: CorticalPath,
  ): number {
    let minimum =
      Number.POSITIVE_INFINITY;

    for (
      let index = 0;
      index < path.length - 1;
      index += 1
    ) {
      const a =
        path[index];

      const b =
        path[index + 1];

      minimum =
        Math.min(
          minimum,
          distanceToSegment2D(
            s,
            q,
            a[0],
            a[1],
            b[0],
            b[1],
          ),
        );
    }

    return minimum;
  }


  function corticalPathField(
    paths: CorticalPath[],
    s: number,
    q: number,
    width: number,
  ): number {
    let field =
      0;

    for (
      const path
      of paths
    ) {
      const distance =
        distanceToPath(
          s,
          q,
          path,
        );

      const strength =
        Math.exp(
          -Math.pow(
            distance /
              width,
            2,
          ),
        );

      field =
        Math.max(
          field,
          strength,
        );
    }

    return field;
  }


  /*
   * Retain the physical displacement field for the future
   * fold-aware particle skin.
   */
  const corticalDisplacements:
    number[] =
    [];


  /*
   * ========================================================
   * GS-4H3B — PARAMETRIC CORTICAL COORDINATES
   * ========================================================
   *
   * These attributes preserve the brain generator's OWN
   * cortical coordinate system on every folded vertex.
   *
   * U:
   * posterior -> anterior longitudinal progress, 0..1
   *
   * Q:
   * inferior -> superior coronal position, -1..1
   *
   * lateral:
   * medial wall -> outer cortex, approximately 0..1
   */
  const corticalUs:
    number[] =
    [];


  const corticalQs:
    number[] =
    [];


  const corticalLaterals:
    number[] =
    [];


  const row =
    ringSegments + 1;


  /*
   * ========================================================
   * ONE CLOSED SURFACE
   * ========================================================
   */
  for (
    let longitudinalIndex = 0;
    longitudinalIndex <= longitudinalSegments;
    longitudinalIndex += 1
  ) {
    const progress =
      longitudinalIndex /
      longitudinalSegments;

    const s =
      progress *
        2 -
      1;

    const top =
      sampleProfile(
        TOP_PROFILE,
        s,
      );

    const bottom =
      sampleProfile(
        BOTTOM_PROFILE,
        s,
      );

    const centerY =
      (
        top +
        bottom
      ) *
      0.5;

    const upperHeight =
      top -
      centerY;

    const lowerHeight =
      centerY -
      bottom;

    const baseWidth =
      sampleProfile(
        WIDTH_PROFILE,
        s,
      );

    const frontal =
      gaussian(
        s,
        0.60,
        0.34,
      );

    const parietal =
      gaussian(
        s,
        -0.02,
        0.45,
      );

    const temporal =
      gaussian(
        s,
        0.13,
        0.34,
      );

    const occipital =
      gaussian(
        s,
        -0.72,
        0.25,
      );

    /*
     * GS-4B2
     *
     * Human cerebrum is longitudinally elongated rather than
     * nearly spherical.
     */
    const z =
      s *
        0.660 +
      frontal *
        0.042 -
      occipital *
        0.014;

    const endFade =
      Math.max(
        0,
        Math.sin(
          progress *
            Math.PI,
        ),
      );

    for (
      let ringIndex = 0;
      ringIndex <= ringSegments;
      ringIndex += 1
    ) {
      /*
       * The final duplicated ring vertex closes each strip
       * cleanly without requiring a separate medial wall.
       */
      const t =
        ringIndex === ringSegments
          ? 0
          : ringIndex /
            ringSegments;

      const [
        coronalX,
        coronalY,
      ] =
        sampleClosedCoronal(
          t,
        );

      const superior =
        Math.max(
          0,
          coronalY,
        );

      const inferior =
        Math.max(
          0,
          -coronalY,
        );

      const lateral =
        Math.pow(
          coronalX,
          1.35,
        );

      const medial =
        Math.pow(
          1 -
            coronalX,
          2.0,
        );

      let y =
        coronalY >= 0
          ? centerY +
            coronalY *
              upperHeight

          : centerY +
            coronalY *
              lowerHeight;


      /*
       * Start from genuine top-view width.
       */
      let width =
        baseWidth;


      /*
       * Superior parietal fullness.
       */
      width *=
        1 +
        parietal *
        superior *
        0.055;


      /*
       * Slight frontal-superior fullness.
       */
      width *=
        1 +
        frontal *
        superior *
        0.025;


      /*
       * Tighter posterior underside.
       */
      width *=
        1 -
        occipital *
        inferior *
        0.045;


      /*
       * Longitudinal fissure.
       */
      const medialGap =
        0.0018 +
        endFade *
        (
          0.0025 +
          superior *
          medial *
          0.0120
        );


      let x =
        lobe *
        (
          medialGap +
          width *
            coronalX
        );


      /*
       * =====================================================
       * TEMPORAL PROJECTION
       * =====================================================
       */
      const temporalLower =
        temporal *
        inferior *
        lateral;


      /*
       * GS-4B2:
       * temporal cortex must visibly project below and lateral
       * to the frontal/parietal cerebrum.
       */
      x +=
        lobe *
        temporalLower *
        0.050;


      y -=
        temporalLower *
        0.046;


      /*
       * =====================================================
       * SYLVIAN DEPRESSION
       * =====================================================
       */
      const sylvian =
        gaussian(
          s,
          0.18,
          0.35,
        ) *
        gaussian(
          coronalY,
          -0.08,
          0.20,
        ) *
        lateral;


      x -=
        lobe *
        sylvian *
        0.032;


      y -=
        sylvian *
        0.014;


      /*
       * =====================================================
       * ROUNDED PARIETAL CROWN
       * =====================================================
       */
      const crown =
        parietal *
        superior *
        (
          0.35 +
          lateral *
            0.65
        );


      y +=
        crown *
        0.012;


      /*
       * Frontal forehead roll.
       */
      y +=
        frontal *
        superior *
        0.004;


      /*
       * Tiny bilateral asymmetry only.
       */
      if (
        lobe === 1
      ) {
        x +=
          frontal *
          lateral *
          0.0018;

        y -=
          0.0012;

      } else {

        y +=
          0.0010;
      }


      /*
       * =====================================================
       * GS-4C — PHYSICAL CORTICAL RELIEF
       * =====================================================
       *
       * Slightly warp cortical coordinates first so even the
       * explicit paths do not remain mathematically perfect.
       */
      const foldS =
        s +
        Math.sin(
          coronalY *
            5.2 +
          s *
            3.1
        ) *
          0.017 +
        Math.sin(
          s *
            8.3 -
          coronalY *
            2.4
        ) *
          0.006;


      const foldQ =
        coronalY +
        Math.sin(
          s *
            5.7 -
          coronalY *
            2.6
        ) *
          0.015 +
        Math.cos(
          s *
            8.5 +
          coronalY *
            4.3
        ) *
          0.005;


      /*
       * Deep major anatomical sulci.
       */
      const majorSulcus =
        corticalPathField(
          MAJOR_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.033,
        );


      /*
       * Medium secondary branches.
       */
      const secondarySulcus =
        corticalPathField(
          SECONDARY_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.026,
        );


      /*
       * Fine tertiary divisions.
       */
      const tertiarySulcus =
        corticalPathField(
          TERTIARY_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.019,
        );


      /*
       * GS-4C1:
       * short terminating/forking cortical branches
       */
      const microSulcus =
        corticalPathField(
          MICRO_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.0145,
        );


      /*
       * Break uniform groove continuity.
       */
      const tertiaryContinuity =
        0.62 +
        smoothstep01(
          0.5 +
          Math.sin(
            foldS * 19.3 +
            foldQ * 12.7 +
            lobe * 0.71
          ) * 0.5
        ) *
          0.38;


      const microContinuity =
        0.48 +
        smoothstep01(
          0.5 +
          Math.sin(
            foldS * 27.1 -
            foldQ * 17.9 +
            lobe * 1.13
          ) *
          Math.cos(
            foldS * 9.7 +
            foldQ * 21.2
          ) *
          0.5
        ) *
          0.52;


      /*
       * Wider shoulder fields determine the broad rounded
       * gyrus crowns between the actual grooves.
       */
      const majorShoulder =
        corticalPathField(
          MAJOR_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.100,
        );


      const secondaryShoulder =
        corticalPathField(
          SECONDARY_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.078,
        );


      const tertiaryShoulder =
        corticalPathField(
          TERTIARY_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.054,
        );


      const microShoulder =
        corticalPathField(
          MICRO_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.040,
        );


      const shoulderField =
        Math.max(
          majorShoulder,
          secondaryShoulder *
            0.92,
          tertiaryShoulder *
            0.76,
          microShoulder *
            0.58,
        );


      /*
       * Farther from sulci = center of a broad gyrus.
       */
      const gyrusField =
        Math.pow(
          Math.max(
            0,
            1 -
              clamp01(
                shoulderField *
                  0.96,
              ),
          ),
          0.72,
        );


      /*
       * Keep folds off the deep medial wall, but preserve
       * substantial superior folding almost to the fissure.
       */
      const lateralCortexMask =
        smoothstep01(
          (
            coronalX -
            0.035
          ) /
          0.30,
        );


      const inferiorMedialMask =
        1 -
        medial *
        inferior *
        0.78;


      /*
       * Do not completely kill folds at frontal/occipital poles.
       */
      const poleInterior =
        smoothstep01(
          (
            1 -
            Math.abs(
              s,
            )
          ) /
          0.12,
        );


      const poleCoverage =
        0.48 +
        poleInterior *
          0.52;


      const cortexCoverage =
        lateralCortexMask *
        inferiorMedialMask *
        poleCoverage;


      /*
       * Top cortex receives extra relief so the superior crown
       * can no longer remain visually blank.
       */
      const superiorBoost =
        1 +
        superior *
          0.22;


      /*
       * Temporal folds also need enough relief to visually
       * separate the lower lobe.
       */
      const temporalBoost =
        1 +
        temporal *
        inferior *
        lateral *
        0.16;


      /*
       * Broad gyri physically rise above the smaller substrate.
       */
      const broadGyrusRise =
        (
          0.0065 +
          gyrusField *
            0.0135
        ) *
        superiorBoost *
        temporalBoost;


      /*
       * Primary sulci are materially deeper than secondary
       * and tertiary branches.
       */
      /*
       * Extra fine-fold strength at superior crown and temporal
       * cortex, without changing the GS-4C macro shape.
       */
      const fineFoldBoost =
        1 +
        superior *
          0.22 +
        temporal *
        inferior *
        lateral *
          0.08;


      const sulcusDepth =
        Math.min(
          0.042,
          majorSulcus *
            0.030 +
          secondarySulcus *
            0.018 +
          tertiarySulcus *
            tertiaryContinuity *
            0.0095 *
            fineFoldBoost +
          microSulcus *
            microContinuity *
            0.0060 *
            fineFoldBoost,
        );


      /*
       * Tiny organic variation prevents completely planar
       * gyrus crowns without introducing noisy bumps.
       */
      const organicGyrus =
        (
          Math.sin(
            foldS *
              11.2 +
            foldQ *
              7.1
          ) *
            0.0014 +
          Math.cos(
            foldS *
              16.7 -
            foldQ *
              9.3
          ) *
            0.0008
        ) *
        (
          0.30 +
          gyrusField *
            0.70
        );


      /*
       * Shrink substrate slightly inward.
       *
       * Gyri therefore define more of the outer silhouette.
       */
      const substrateInset =
        -0.0065;


      const corticalDisplacement =
        (
          substrateInset +
          broadGyrusRise -
          sulcusDepth +
          organicGyrus
        ) *
        cortexCoverage;


      /*
       * Approximate outward normal of the procedural surface.
       *
       * Near the lateral cortex -> primarily X.
       * Near crown/base       -> increasingly Y.
       * Near frontal/rear pole -> increasingly Z.
       */
      let normalX =
        lobe *
        (
          0.20 +
          coronalX *
            0.80
        ) *
        (
          1 -
          Math.abs(
            s,
          ) *
            0.28
        );


      let normalY =
        coronalY *
        0.92;


      let normalZ =
        s *
        Math.pow(
          Math.abs(
            s,
          ),
          1.45,
        ) *
        0.72;


      const normalLength =
        Math.max(
          1e-5,
          Math.sqrt(
            normalX *
              normalX +
            normalY *
              normalY +
            normalZ *
              normalZ,
          ),
        );


      normalX /=
        normalLength;


      normalY /=
        normalLength;


      normalZ /=
        normalLength;


      let vertexZ =
        z;


      x +=
        normalX *
        corticalDisplacement;


      y +=
        normalY *
        corticalDisplacement;


      vertexZ +=
        normalZ *
        corticalDisplacement;


      corticalDisplacements.push(
        corticalDisplacement,
      );


      /*
       * GS-4H3B:
       *
       * Preserve generator-space cortical coordinates.
       */
      corticalUs.push(
        progress,
      );


      corticalQs.push(
        coronalY,
      );


      corticalLaterals.push(
        coronalX,
      );


      positions.push(
        x,
        y,
        vertexZ,
      );
    }
  }


  /*
   * ========================================================
   * TRIANGULATE CLOSED CORONAL STRIPS
   * ========================================================
   */
  for (
    let longitudinalIndex = 0;
    longitudinalIndex < longitudinalSegments;
    longitudinalIndex += 1
  ) {
    for (
      let ringIndex = 0;
      ringIndex < ringSegments;
      ringIndex += 1
    ) {
      const a =
        longitudinalIndex *
          row +
        ringIndex;

      const b =
        a + 1;

      const c =
        a + row;

      const d =
        c + 1;


      if (
        lobe === 1
      ) {
        indices.push(
          a,
          b,
          c,
        );

        indices.push(
          b,
          d,
          c,
        );

      } else {

        indices.push(
          a,
          c,
          b,
        );

        indices.push(
          b,
          c,
          d,
        );
      }
    }
  }


  const geometry =
    new BufferGeometry();


  geometry.setAttribute(
    "position",
    new Float32BufferAttribute(
      positions,
      3,
    ),
  );


  geometry.setIndex(
    indices,
  );


  geometry.computeVertexNormals();


  /*
   * GS-4C:
   *
   * Store the REAL physical cortical relief.
   *
   * The future particle skin can therefore classify
   * gyri/sulci from the actual anatomical surface.
   */
  geometry.setAttribute(
    "aCorticalDisplacement",
    new Float32BufferAttribute(
      new Float32Array(
        corticalDisplacements,
      ),
      1,
    ),
  );


  /*
   * ========================================================
   * GS-4H3B — CORTICAL PARAMETRIC ATTRIBUTES
   * ========================================================
   */
  geometry.setAttribute(
    "aCorticalU",
    new Float32BufferAttribute(
      new Float32Array(
        corticalUs,
      ),
      1,
    ),
  );


  geometry.setAttribute(
    "aCorticalQ",
    new Float32BufferAttribute(
      new Float32Array(
        corticalQs,
      ),
      1,
    ),
  );


  geometry.setAttribute(
    "aCorticalLateral",
    new Float32BufferAttribute(
      new Float32Array(
        corticalLaterals,
      ),
      1,
    ),
  );


  return geometry;
}


/* ==========================================================
   GS-5N — FINAL VISIBLE BLUE CORTEX
   GS-5M3 — DIRECT SOLID CORTEX

   Sentinel-confirmed production visibility path.

   The two physical cerebral hemispheres now use:
   MeshBasicMaterial + fixed dark-blue cortical color.

   This deliberately removes cortex dependence on:
   - scene-light response
   - PBR exposure
   - custom cortex GLSL

   Neural particles, signals and plasma remain independent.
   ========================================================== */

function BrainBody({
  plasmaMaterial,
  plasmaMeshRef,
}: {
  plasmaMaterial: ShaderMaterial;
  plasmaMeshRef: RefObject<Mesh | null>;
}) {
  const leftBrain =
    useMemo(
      () =>
        buildBrainBodyGeometry(
          -1,
        ),
      [],
    );

  const rightBrain =
    useMemo(
      () =>
        buildBrainBodyGeometry(
          1,
        ),
      [],
    );

  /*
   * IMPORTANT:
   *
   * This material is intentionally brighter than the eventual
   * reel version.
   *
   * Right now we are calibrating SHAPE only. Once the geometry
   * passes, we will darken it underneath the neural particles.
   */
  return (
    <group
      rotation={[
        -0.035,
        0,
        -0.025,
      ]}
    >
      {/* ====================================================
          GS-6A — FUTURISTIC REEL RESTYLE
          GS-5Q — FINAL REEL MATERIAL POLISH
          GS-5P — SHADED SOLID CORTEX
          GS-5O2 — REAL CORTEX OWNS DEPTH
          GS-2B2 — EXACT FOLDED-BRAIN DEPTH SHELL

          Unlike GS-2B1, this does NOT approximate the brain
          with spheres.

          It reuses the ACTUAL folded GS-1G hemisphere geometry,
          slightly inset beneath the visible cortical surface.

          Result:
          - near particles remain visible
          - far particles fail depth testing
          - no X-ray transparency
          - no spherical holes
          ==================================================== */}


      {/* LEFT EXACT DEPTH SHELL */}
      <mesh
        visible={false}
        geometry={
          leftBrain
        }
        scale={0.988}
      >
        <meshBasicMaterial
          colorWrite={false}
          depthWrite
          depthTest
          side={2}
        />
      </mesh>


      {/* RIGHT EXACT DEPTH SHELL */}
      <mesh
        visible={false}
        geometry={
          rightBrain
        }
        scale={0.988}
      >
        <meshBasicMaterial
          colorWrite={false}
          depthWrite
          depthTest
          side={2}
        />
      </mesh>



      {/* ====================================================
          GS-5 — FINAL REEL INTEGRATION
          GS-5A — CINEMATIC CORTICAL MATERIAL
          GS-5H — DIRECT CORTICAL VISIBILITY

          Keep GS-4C1 physical anatomy unchanged.

          Dark navy / violet tissue now sits beneath the neural
          particle skin. Reduced ambient response makes deep sulci
          retain substantially more contrast while gyrus crowns
          still receive controlled highlights.
          ==================================================== */}

      {/* LEFT CEREBRAL HEMISPHERE */}
      <mesh
        geometry={
          leftBrain
        }
      >
        <meshPhongMaterial
          color="#17182b"
          emissive="#050617"
          emissiveIntensity={0.13}
          specular="#596388"
          shininess={13}
          toneMapped={false}
          depthWrite
          depthTest
          side={2}
        />
      </mesh>

      {/* RIGHT CEREBRAL HEMISPHERE */}
      <mesh
        geometry={
          rightBrain
        }
      >
        <meshPhongMaterial
          color="#17182b"
          emissive="#050617"
          emissiveIntensity={0.13}
          specular="#596388"
          shininess={13}
          toneMapped={false}
          depthWrite
          depthTest
          side={2}
        />
      </mesh>


      {/* ====================================================
          GS-4H3 — EXACT FOLDED-SURFACE PLASMA RIBBON

          These are NOT replacement brain meshes.

          They are transparent emissive overlays that reuse the
          exact GS-4C1 hemisphere geometry underneath.
          ==================================================== */}

      <mesh
        ref={plasmaMeshRef}
        geometry={
          leftBrain
        }
        material={
          plasmaMaterial
        }
        renderOrder={4}
      />

      <mesh
        geometry={
          rightBrain
        }
        material={
          plasmaMaterial
        }
        renderOrder={4}
      />


      {/* ====================================================
          SUBTLE GEOMETRY GRID FOR ROTATION VALIDATION
          ==================================================== */}

      <mesh
        visible={false}
        geometry={
          leftBrain
        }
        scale={1.004}
      >
        <meshBasicMaterial
          color="#6a82c0"
          wireframe
          transparent
          opacity={0.055}
          depthWrite={false}
        />
      </mesh>

      <mesh
        visible={false}
        geometry={
          rightBrain
        }
        scale={1.004}
      >
        <meshBasicMaterial
          color="#6a82c0"
          wireframe
          transparent
          opacity={0.055}
          depthWrite={false}
        />
      </mesh>


      {/* ====================================================
          MEDIAL FISSURE SHADOW
          ==================================================== */}

      <mesh
        visible={false}
        position={[
          0,
          0.13,
          0,
        ]}
        scale={[
          0.014,
          0.39,
          0.31,
        ]}
      >
        <sphereGeometry
          args={[
            1,
            26,
            22,
          ]}
        />

        <meshBasicMaterial
          color="#010207"
        />
      </mesh>


      {/* ====================================================
          CEREBELLUM
          ==================================================== */}

      <mesh
        visible={false}
        position={[
          -0.105,
          -0.318,
          -0.335,
        ]}
        rotation={[
          0.12,
          -0.10,
          0,
        ]}
        scale={[
          0.205,
          0.118,
          0.170,
        ]}
      >
        <sphereGeometry
          args={[
            1,
            30,
            24,
          ]}
        />

        <meshStandardMaterial
          color="#141f40"
          emissive="#09132e"
          emissiveIntensity={0.36}
          roughness={0.82}
        />
      </mesh>

      <mesh
        visible={false}
        position={[
          0.105,
          -0.318,
          -0.335,
        ]}
        rotation={[
          0.12,
          0.10,
          0,
        ]}
        scale={[
          0.205,
          0.118,
          0.170,
        ]}
      >
        <sphereGeometry
          args={[
            1,
            30,
            24,
          ]}
        />

        <meshStandardMaterial
          color="#141f40"
          emissive="#09132e"
          emissiveIntensity={0.36}
          roughness={0.82}
        />
      </mesh>


      {/* ====================================================
          BRAIN STEM
          ==================================================== */}

      <mesh
        visible={false}
        position={[
          0,
          -0.432,
          -0.195,
        ]}
        rotation={[
          0.42,
          0,
          0,
        ]}
        scale={[
          0.042,
          0.118,
          0.050,
        ]}
      >
        <sphereGeometry
          args={[
            1,
            26,
            22,
          ]}
        />

        <meshStandardMaterial
          color="#111a37"
          emissive="#08112a"
          emissiveIntensity={0.3}
          roughness={0.84}
        />
      </mesh>
    </group>
  );
}

/* ==========================================================
   SCENE
   ========================================================== */

function NeuralScene({
  state,
}: NeuralCoreProps) {
  /*
   * ========================================================
   * GS-5S — FINAL REEL FX CALIBRATION
   * GS-5R — FINAL NEURAL ENERGY PASS
   * ========================================================
   *
   * FX calibration only.
   *
   * GS-4C1 geometry, GS-5O2 depth architecture and
   * GS-5Q cortical material remain frozen.
   * ========================================================
   */

  const root =
    useRef<Group>(null);

  const surfacePoints =
    useRef<Points>(null);

  const nodePoints =
    useRef<Points>(null);

  const fiberPoints =
    useRef<Points>(null);

  const ejectionPoints =
    useRef<Points>(null);


  /*
   * GS-4H3
   *
   * Reference only one hemisphere overlay because both
   * hemispheres share the same plasma ShaderMaterial.
   */
  const plasmaRibbonMesh =
    useRef<Mesh>(null);

  /*
   * ========================================================
   * GS-4C1P — STARTUP PERFORMANCE GATE
   * ========================================================
   *
   * Anatomy-validation mode currently renders none of these:
   *
   * - surface particles
   * - neural network
   * - scaffold
   * - fibers
   * - ejections
   *
   * Do NOT spend startup time constructing them.
   *
   * GS-4D can switch this back on when neural effects return.
   */
  /*
   * ========================================================
   * GS-4D — SELECTIVE MICROSCOPIC CORTEX
   * ========================================================
   *
   * Restore ONLY cortical surface particles.
   *
   * Auxiliary effects remain disabled:
   * - network
   * - scaffold
   * - fibers
   * - ejections
   */
  const surfaceParticlesEnabled =
    true;


  const neuralEffectsEnabled =
    false;


  /*
   * ========================================================
   * GS-4E — FIBERS ONLY
   * ========================================================
   *
   * Surface particles remain GS-4D2.
   * Network/scaffold/ejections remain OFF.
   */
  const fiberEffectsEnabled =
    true;


  /*
   * ========================================================
   * GS-5B — RESTRAINED CORTICAL EJECTIONS
   * ========================================================
   *
   * Enable only a tiny ejection layer.
   *
   * Network/scaffold stay OFF.
   * GS-4F2 fibers stay untouched.
   */
  const ejectionEffectsEnabled =
    true;


  /*
   * ========================================================
   * GS-4H3 — CONTINUOUS PLASMA RIBBON MATERIAL
   * ========================================================
   *
   * Unlike GS-4H2's point-sprite plasma, this material renders
   * directly on the folded cortical triangles.
   */
  const plasmaRibbonMaterial =
    useMemo(
      () =>
        new ShaderMaterial({
          vertexShader:
            PLASMA_RIBBON_VERTEX_SHADER,

          fragmentShader:
            PLASMA_RIBBON_FRAGMENT_SHADER,

          transparent: true,

          depthWrite: false,

          depthTest: true,

          blending:
            AdditiveBlending,

          polygonOffset: true,

          /*
           * GS-4H3B2:
           *
           * Stronger depth bias only.
           *
           * depthTest stays enabled, so far-side plasma still
           * cannot show through the brain.
           */
          polygonOffsetFactor:
            -3,

          polygonOffsetUnits:
            -6,

          toneMapped: false,

          uniforms: {
            uTime: {
              value: 0,
            },

            uPlasmaProgress: {
              value: 0,
            },

            uPlasmaStrength: {
              value: 0,
            },
          },
        }),
      [],
    );


  const surfaceGeometry =
    useMemo(
      () =>
        surfaceParticlesEnabled
          ? buildSurfaceGeometry(
              48000,
              1107,
            )
          : new BufferGeometry(),
      [
        surfaceParticlesEnabled,
      ],
    );

  const networkGeometry =
    useMemo(
      () =>
        neuralEffectsEnabled
          ? buildNetworkGeometry(
              2207,
            )
          : {
              nodes:
                new BufferGeometry(),
              edges:
                new BufferGeometry(),
            },
      [
        neuralEffectsEnabled,
      ],
    );

  const scaffoldGeometry =
    useMemo(
      () =>
        neuralEffectsEnabled
          ? buildBrainScaffoldGeometry(
              2607,
              4200,
            )
          : new BufferGeometry(),
      [
        neuralEffectsEnabled,
      ],
    );

  const fiberGeometry =
    useMemo(
      () =>
        fiberEffectsEnabled
          ? buildFiberGeometry(
              3307,
              88,
              surfaceGeometry,
            )
          : new BufferGeometry(),
      [
        fiberEffectsEnabled,
        surfaceGeometry,
      ],
    );

  const ejectionGeometry =
    useMemo(
      () =>
        ejectionEffectsEnabled
          ? buildEjectionGeometry(
              34,
              4407,
            )
          : new BufferGeometry(),
      [
        ejectionEffectsEnabled,
      ],
    );

  const surfaceMaterial =
    useMemo(
      () =>
        new ShaderMaterial({
          vertexShader:
            SURFACE_VERTEX_SHADER,

          fragmentShader:
            SURFACE_FRAGMENT_SHADER,

          /*
           * GS-2A1 — OPAQUE FOLD CONTRAST
           *
           * Keep transparent point sprites, but make them obey
           * the real brain depth buffer.
           *
           * Normal ShaderMaterial alpha blending preserves
           * individual particle colors.
           */
          transparent: true,

          depthWrite: false,

          depthTest: true,

          /*
           * ==================================================
           * GS-5I — ADDITIVE CORTICAL PARTICLE COMPOSITE
           * ==================================================
           *
           * GS-4D2's 48k cortical points previously used
           * default NormalBlending.
           *
           * Dark transparent point sprites could therefore
           * attenuate the physical cortex underneath them.
           *
           * AdditiveBlending means:
           *
           * - quiet/dark particles add almost nothing
           * - physical cortical tissue remains visible
           * - active colored particles still illuminate cortex
           * - depth testing remains intact
           * - far-side particles remain hidden
           */
          blending:
            AdditiveBlending,

          uniforms: {
            uTime: {
              value: 0,
            },

            uEnergy: {
              value: 0.6,
            },

            uHotPosition: {
              value:
                new Vector3(),
            },

            uPlasmaX: {
              value: 0,
            },

            uPlasmaStrength: {
              value: 0,
            },

            /*
             * GS-4D2 — READABLE NEURAL SKIN
             *
             * Slightly larger microscopic points.
             * Still substantially smaller than the old
             * luminous-shell treatment.
             */
            uPointScale: {
              value: 0.00255,
            },
          },
        }),
      [],
    );

  const nodeMaterial =
    useMemo(
      () =>
        new ShaderMaterial({
          vertexShader:
            SURFACE_VERTEX_SHADER,

          fragmentShader:
            SURFACE_FRAGMENT_SHADER,

          transparent: true,

          depthWrite: false,

          depthTest: false,

          blending:
            AdditiveBlending,

          uniforms: {
            uTime: {
              value: 0,
            },

            uEnergy: {
              value: 0.6,
            },

            uHotPosition: {
              value:
                new Vector3(),
            },

            uPlasmaX: {
              value: 0,
            },

            uPlasmaStrength: {
              value: 0,
            },

            uPointScale: {
              value: 0.00375,
            },
          },
        }),
      [],
    );

    /*
   * ========================================================
   * GS-6D2 — CONTINUOUS NEURAL FILAMENT WEB
   * ========================================================
   *
   * F2 point sprites remain the animated travelling-signal
   * layer.
   *
   * This adds a persistent hairline neural network beneath
   * them using exactly the existing F2 sampled paths.
   */
  /*
   * GS-6E5 — SURFACE-HUGGING FILAMENTS
   *
   * Persistent lines remain subordinate to the moving
   * GS-4F2 neural signals.
   */
  const fiberLineGeometry =
    // eslint-disable-next-line react-hooks/preserve-manual-memoization
    useMemo(
      () => {
        const sourcePosition =
          fiberGeometry.getAttribute(
            "position",
          );

        const sourceProgress =
          fiberGeometry.getAttribute(
            "aProgress",
          );

        const sourceSeed =
          fiberGeometry.getAttribute(
            "aSeed",
          );


        if (
          !sourcePosition ||
          !sourceProgress ||
          !sourceSeed
        ) {
          return new BufferGeometry();
        }


        const positions:
          number[] =
          [];


        const colors:
          number[] =
          [];


        for (
          let i = 0;
          i <
            sourcePosition.count -
              1;
          i++
        ) {
          const seedA =
            sourceSeed.getX(i);

          const seedB =
            sourceSeed.getX(
              i + 1,
            );


          /*
           * aSeed is constant along each F2 cortical path.
           *
           * A changed seed means a new fiber begins.
           */
          if (
            Math.abs(
              seedA -
              seedB,
            ) >
            0.000001
          ) {
            continue;
          }


          const progressA =
            sourceProgress.getX(i);

          const progressB =
            sourceProgress.getX(
              i + 1,
            );


          if (
            progressB <=
            progressA
          ) {
            continue;
          }


          const progressStep =
            progressB -
            progressA;


          /*
           * GS-6E5 — SURFACE-HUGGING FILAMENTS
           *
           * Reject coarse jumps along the existing cortical
           * F2 paths.
           */
          if (
            progressStep >
            0.18
          ) {
            continue;
          }


          const ax =
            sourcePosition.getX(i);

          const ay =
            sourcePosition.getY(i);

          const az =
            sourcePosition.getZ(i);


          const bx =
            sourcePosition.getX(
              i + 1,
            );

          const by =
            sourcePosition.getY(
              i + 1,
            );

          const bz =
            sourcePosition.getZ(
              i + 1,
            );


          const dx =
            bx - ax;

          const dy =
            by - ay;

          const dz =
            bz - az;


          const distanceSquared =
            dx * dx +
            dy * dy +
            dz * dz;


          /*
           * Secondary protection against cross-cortex jumps.
           */
          if (
            distanceSquared >
            0.0049
          ) {
            continue;
          }


          positions.push(
            ax,
            ay,
            az,
            bx,
            by,
            bz,
          );


          /*
           * Match GS-6B's futuristic signal palette.
           *
           * cyan      dominant
           * magenta   secondary
           * violet    secondary
           * amber     sparse
           */
          const colorSelector =
            (
              Math.sin(
                seedA *
                  271.93 +
                8.41,
              ) *
              43758.5453123
            );


          const selector =
            colorSelector -
            Math.floor(
              colorSelector
            );


          let r =
            0.025;

          let g =
            0.27;

          let b =
            0.62;


          if (
            selector >
              0.72 &&
            selector <=
              0.86
          ) {
            r =
              0.52;

            g =
              0.035;

            b =
              0.62;
          }


          if (
            selector >
              0.86 &&
            selector <=
              0.95
          ) {
            r =
              0.20;

            g =
              0.055;

            b =
              0.68;
          }


          if (
            selector >
            0.95
          ) {
            r =
              0.62;

            g =
              0.20;

            b =
              0.025;
          }


          colors.push(
            r,
            g,
            b,
            r,
            g,
            b,
          );
        }


        const geometry =
          new BufferGeometry();


        geometry.setAttribute(
          "position",
          new Float32BufferAttribute(
            positions,
            3,
          ),
        );


        geometry.setAttribute(
          "color",
          new Float32BufferAttribute(
            colors,
            3,
          ),
        );


        geometry.computeBoundingSphere();


        return geometry;
      },
      [
        fiberGeometry,
      ],
    );


const fiberMaterial =
    useMemo(
      () =>
        new ShaderMaterial({
          vertexShader:
            FIBER_VERTEX_SHADER,

          fragmentShader:
            FIBER_FRAGMENT_SHADER,

          transparent: true,

          depthWrite: false,

          depthTest: true,

          blending:
            AdditiveBlending,

          uniforms: {
            uTime: {
              value: 0,
            },

            uEnergy: {
              value: 0.6,
            },

            /*
             * GS-4E — hairline cortical fiber particles
             */
            uPointScale: {
              value: 0.00190,
            },
          },
        }),
      [],
    );

  const ejectionMaterial =
    useMemo(
      () =>
        new ShaderMaterial({
          vertexShader:
            EJECTION_VERTEX_SHADER,

          fragmentShader:
            EJECTION_FRAGMENT_SHADER,

          transparent: true,

          /*
           * GS-5B:
           *
           * Ejections must obey the solid brain depth buffer.
           * Rear-side sparks therefore remain hidden.
           */
          depthWrite: false,

          depthTest: true,

          blending:
            AdditiveBlending,

          uniforms: {
            uTime: {
              value: 0,
            },

            uEnergy: {
              value: 0,
            },

            /*
             * GS-5B:
             *
             * Previous experimental ejection points were huge.
             * Reel pass uses tiny spark-sized fragments.
             */
            uPointScale: {
              value: 0.0125,
            },
          },
        }),
      [],
    );

  const hotPosition =
    useMemo(
      () =>
        new Vector3(),
      [],
    );

  useFrame(
    ({
      clock,
    }) => {
      const elapsed =
        clock.getElapsedTime();

      const energy =
        stateEnergy(
          state,
        );

      /*
       * NEW BENCHMARK:
       * recognizable brain means we no longer need the old
       * overly-fast rotation.
       */
      if (
        root.current
      ) {
        root.current.rotation.y =
          elapsed *
          (
            0.145 +
            energy *
              0.010
          );

        root.current.rotation.x =
          0.035 +
          Math.sin(
            elapsed *
              0.19,
          ) *
            0.026;

        root.current.rotation.z =
          Math.sin(
            elapsed *
              0.13 +
              0.7,
          ) *
          0.014;

        /*
         * Tiny organism-wide pulse while preserving brain shape.
         */
        const breath =
          1 +
          Math.sin(
            elapsed *
              1.05,
          ) *
            0.004 +
          Math.sin(
            elapsed *
              2.1 +
              0.4,
          ) *
            0.0015;

        root.current.scale.setScalar(
          breath,
        );
      }

      /*
       * Hotspot travels over actual brain surface.
       */
      const hotspotPhase =
        elapsed *
        0.24;

      const hotLobe:
        Lobe =
        Math.sin(
          hotspotPhase *
            0.57,
        ) >
        0
          ? 1
          : -1;

      const hotU =
        hotspotPhase %
        TAU;

      const hotV =
        1.42 +
        Math.sin(
          hotspotPhase *
            0.72,
        ) *
          0.52;

      hotPosition.copy(
        brainSurfacePoint(
          hotLobe,
          hotU,
          Math.max(
            0.28,
            Math.min(
              Math.PI -
                0.28,
              hotV,
            ),
          ),
          1.06,
        ),
      );

      /*
       * ====================================================
       * GS-4H — RARE SYNCHRONIZED PLASMA PASS
       * ====================================================
       *
       * One event roughly every 17.5 seconds.
       *
       * The visible crossing lasts about five seconds.
       *
       * Position and intensity share the same phase, so the
       * plasma reads as ONE travelling wave instead of an
       * unrelated flashing band.
       */
      const plasmaPeriod =
        17.5;


      const plasmaPhase =
        (
          elapsed %
          plasmaPeriod
        ) /
        plasmaPeriod;


      const plasmaStart =
        0.24;


      const plasmaEnd =
        0.53;


      const plasmaTravel =
        Math.max(
          0,
          Math.min(
            1,
            (
              plasmaPhase -
              plasmaStart
            ) /
            (
              plasmaEnd -
              plasmaStart
            ),
          ),
        );


      const plasmaActive =
        plasmaPhase >=
          plasmaStart &&
        plasmaPhase <=
          plasmaEnd;


      const plasmaStrength =
        plasmaActive
          ? Math.pow(
              Math.sin(
                Math.PI *
                  plasmaTravel,
              ),
              1.35,
            )
          : 0;


      /*
       * GS-4H3A:
       *
       * Extended longitudinal entrance/exit range.
       */
      const plasmaX =
        -0.64 +
        plasmaTravel *
          1.28;


      /*
       * ====================================================
       * GS-4H3 — UPDATE CONTINUOUS RIBBON
       * ====================================================
       */
      if (
        plasmaRibbonMesh.current
      ) {
        const material =
          plasmaRibbonMesh.current.material as ShaderMaterial;

        material.uniforms
          .uTime
          .value =
          elapsed;

        material.uniforms
          .uPlasmaProgress
          .value =
          plasmaTravel;

        material.uniforms
          .uPlasmaStrength
          .value =
          plasmaStrength;
      }

      /*
       * Update mounted Three.js materials through object refs.
       *
       * React 19's immutability lint rule correctly treats
       * values returned from useMemo() as render-owned values.
       * The Three.js material attached to a mounted Points object,
       * however, is runtime state and can be updated inside
       * useFrame().
       */
      const surfaceTargets = [
        surfacePoints.current,
        nodePoints.current,
      ];

      for (
        const target
        of surfaceTargets
      ) {
        if (
          !target
        ) {
          continue;
        }

        const material =
          target.material as ShaderMaterial;

        material.uniforms
          .uTime
          .value =
          elapsed;

        material.uniforms
          .uEnergy
          .value =
          energy;

        material.uniforms
          .uHotPosition
          .value
          .copy(
            hotPosition,
          );

        material.uniforms
          .uPlasmaX
          .value =
          plasmaX;

        material.uniforms
          .uPlasmaStrength
          .value =
          plasmaStrength;
      }

      /*
       * ====================================================
       * GS-6F — SYNCHRONIZED CORTICAL SURGE
       * GS-4H — SURFACE PLASMA ENABLED
       * ====================================================
       *
       * Legacy moving hotspot remains OFF.
       *
       * Only the synchronized plasma channel is enabled.
       */
      if (
        surfacePoints.current
      ) {
        const material =
          surfacePoints.current.material as ShaderMaterial;

        material.uniforms
          .uHotPosition
          .value
          .set(
            99,
            99,
            99,
          );

        /*
         * GS-4H3B:
         *
         * Old point-sprite plasma is OFF.
         *
         * Base cortical particles + GS-4G1 remain active.
         * The continuous parametric mesh now owns plasma.
         */
        /*
         * GS-6F — SYNCHRONIZED CORTICAL SURGE
         *
         * H3C remains the dominant ribbon.
         * The existing cortical particle plasma channel now
         * participates at restrained strength.
         */
        material.uniforms
          .uPlasmaStrength
          .value =
          plasmaStrength *
            0.72;
      }


      if (
        fiberPoints.current
      ) {
        const material =
          fiberPoints.current.material as ShaderMaterial;

        material.uniforms
          .uTime
          .value =
          elapsed;

        material.uniforms
          .uEnergy
          .value =
          energy;
      }

      /*
       * ====================================================
       * GS-5C — SYNCHRONIZED CORTICAL EJECTION BURSTS
       * ====================================================
       *
       * Ejections occur only inside the existing rare energy
       * event. Short sub-peaks keep them sparse rather than
       * creating a permanent fountain around the brain.
       */
      const ejectionPulse =
        plasmaStrength *
        (
          0.40 +
          Math.pow(
            Math.max(
              0,
              Math.sin(
                plasmaTravel *
                  Math.PI *
                  5.0,
              ),
            ),
            10,
          ) *
            0.60
        );


      if (
        ejectionPoints.current
      ) {
        const material =
          ejectionPoints.current.material as ShaderMaterial;

        material.uniforms
          .uTime
          .value =
          elapsed;

        material.uniforms
          .uEnergy
          .value =
          Math.min(
            1,
            ejectionPulse *
              (
                0.78 +
                energy *
                  0.22
              ),
          );
      }
    },
  );

  return (
    <group
      ref={root}
      position={[
        0,
        0.03,
        0,
      ]}
      scale={2.05}
    >
      <BrainBody
        plasmaMaterial={
          plasmaRibbonMaterial
        }
        plasmaMeshRef={
          plasmaRibbonMesh
        }
      />

      <lineSegments
        visible={false}
        geometry={
          scaffoldGeometry
        }
      >
        <lineBasicMaterial
          vertexColors
          transparent
          opacity={0.11}
          blending={
            AdditiveBlending
          }
          depthWrite={false}
          depthTest
        />
      </lineSegments>

      <lineSegments
        visible={false}
        geometry={
          networkGeometry.edges
        }
      >
        <lineBasicMaterial
          vertexColors
          transparent
          opacity={0.21}
          blending={
            AdditiveBlending
          }
          depthWrite={false}
          depthTest={false}
        />
      </lineSegments>

      {/* GS-4D — SELECTIVE MICROSCOPIC CORTEX */}
      <points
        visible
        ref={surfacePoints}
        geometry={
          surfaceGeometry
        }
        material={
          surfaceMaterial
        }
      />

      <points
        visible={false}
        ref={nodePoints}
        geometry={
          networkGeometry.nodes
        }
        material={
          nodeMaterial
        }
      />

      {/*
          ====================================================
          GS-4F — TRAVELLING NEURAL SIGNALS
          ====================================================

          GS-4E cortical paths remain intact.
          Selected paths now carry slow travelling excitation.
      */}
      {/*
          GS-6D2 — CONTINUOUS CORTICAL FILAMENTS

          Thin additive lines provide the persistent network.
          Existing GS-4F2 point signals animate above them.
      */}
      <lineSegments
        geometry={
          fiberLineGeometry
        }
        frustumCulled={false}
      >
        <lineBasicMaterial
          vertexColors
          transparent
          opacity={0.16}
          depthTest
          depthWrite={false}
          blending={
            AdditiveBlending
          }
          toneMapped={false}
        />
      </lineSegments>

      <points
        visible
        ref={fiberPoints}
        geometry={
          fiberGeometry
        }
        material={
          fiberMaterial
        }
      />

      {/*
          ====================================================
          GS-5B — RESTRAINED CORTICAL EJECTIONS

          18 tiny depth-tested sparks.
          Their uEnergy is normally zero and is raised only by
          GS-5C's synchronized event envelope.
          ====================================================
      */}
      <points
        visible
        ref={ejectionPoints}
        geometry={
          ejectionGeometry
        }
        material={
          ejectionMaterial
        }
      />
    </group>
  );
}

export function NeuralCore({
  state,
}: NeuralCoreProps) {
  return (
    <section
      className="neural-core-stage"
      data-state={state}
      aria-label={`Friday neural intelligence core ${state}`}
    >
      <Canvas
        className="neural-core-canvas"
        camera={{
          position: [
            0,
            0.02,
            4.25,
          ],
          fov: 34,
        }}
        dpr={[
          1,
          1.5,
        ]}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference:
            "high-performance",
        }}
      >
        <color
          attach="background"
          args={[
            "#010208",
          ]}
        />

        {/* ==================================================
            GS-5D — FINAL REEL CINEMATIC LIGHTING

            Temporary matte-studio lighting.

            Purpose:
            reveal REAL gyri/sulci geometry without particles,
            emissive glow or Bloom hiding the anatomy.
            ================================================== */}

        {/*
            GS-5G — FINAL REEL VISIBILITY BALANCE

            Final numeric calibration only.
            No architecture or effect redesign.

            GS-5F — FINAL VISIBILITY POLISH

            Lift the physical cortex without turning it into
            an emissive shell. Neural events remain dominant.
        */}
        <ambientLight
          intensity={0.25}
        />

        {/* GS-5D — controlled cool upper/front key */}
        <directionalLight
          position={[
            4.5,
            4.2,
            5.5,
          ]}
          intensity={1.18}
          color="#d8e4ff"
        />

        {/* restrained violet-blue opposite fill */}
        <directionalLight
          position={[
            -4.0,
            1.2,
            3.2,
          ]}
          intensity={0.34}
          color="#7850c7"
        />

        {/* purple posterior rim separates silhouette from black */}
        <directionalLight
          position={[
            1.5,
            2.0,
            -5.0,
          ]}
          intensity={0.92}
          color="#24cfff"
        />

        {/* deep-blue low fill retains sulcus separation */}
        <directionalLight
          position={[
            -2.5,
            -2.2,
            2.5,
          ]}
          intensity={0.20}
          color="#47366f"
        />


        {/*
            Tiny cinematic color accents.
            These illuminate tissue only; they do not create
            new particle systems or blanket glow.
        */}
        <pointLight
          position={[
            2.1,
            0.65,
            2.4,
          ]}
          intensity={0.28}
          color="#00d9ff"
          distance={5.5}
        />

        <pointLight
          position={[
            -2.0,
            0.25,
            1.9,
          ]}
          intensity={0.23}
          color="#ef43ff"
          distance={5.0}
        />

        <NeuralScene
          state={state}
        />

        <EffectComposer
          multisampling={0}
        >
          {/*
              GS-5E — FINAL SELECTIVE REEL BLOOM

              Slightly richer than the inspection baseline while
              keeping the threshold high enough that the solid
              cortical mass itself does not become a glowing fog.
          */}
          <Bloom
            intensity={1.00}
            luminanceThreshold={
              0.82
            }
            luminanceSmoothing={
              0.060
            }
            mipmapBlur
          />
        </EffectComposer>
      </Canvas>

      <div
        className="neural-core-glow"
      />
    </section>
  );
}
