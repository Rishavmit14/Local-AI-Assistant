import { BufferGeometry, Float32BufferAttribute } from "three";

type Lobe = -1 | 1;

/**
 * Procedural cerebral hemisphere extracted from NeuralCore's actual body mesh.
 * X is bilateral (lobe -1/+1), +Y superior, +Z anterior. Dimensions are unscaled.
 * Retains physical major/secondary/tertiary/micro sulci and cortical attributes.
 * Call once for each lobe; share/dispose geometry at the scene ownership boundary.
 * Original tessellation: 192 longitudinal x 144 coronal segments per hemisphere.
 */
export function buildBrainGeometry(
  lobe: Lobe,
): BufferGeometry {
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
      [-0.42, -0.142],
      [-0.32, -0.184],
      [-0.22, -0.235],
      [-0.10, -0.292],
      [ 0.02, -0.338],
      [ 0.14, -0.365],
      [ 0.27, -0.372],
      [ 0.40, -0.356],
      [ 0.52, -0.322],
      [ 0.63, -0.278],
      [ 0.73, -0.230],
      [ 0.82, -0.181],
      [ 0.89, -0.133],
      [ 0.94, -0.086],
      [ 0.975,-0.035],
      [ 1.00,  0.030],
    ];
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
  const CORONAL_PROFILE:
    Array<
      [number, number]
    > =
    [
      [0.040,  1.000],
      [0.160,  0.994],
      [0.350,  0.970],
      [0.550,  0.920],
      [0.730,  0.830],
      [0.875,  0.690],
      [0.965,  0.510],
      [1.000,  0.290],
      [0.995,  0.070],
      [0.965, -0.150],
      [0.900, -0.350],
      [0.810, -0.520],
      [0.700, -0.650],
      [0.570, -0.735],
      [0.430, -0.775],
      [0.310, -0.760],
      [0.215, -0.700],
      [0.145, -0.610],
      [0.095, -0.490],
      [0.060, -0.330],
      [0.040, -0.150],
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
  type CorticalPath =
    Array<
      [number, number]
    >;
  const MAJOR_CORTICAL_PATHS:
    CorticalPath[] =
    [
      [
        [ 0.12,  0.88],
        [ 0.08,  0.70],
        [ 0.04,  0.50],
        [ 0.00,  0.30],
        [-0.05,  0.10],
        [-0.09, -0.04],
      ],
      [
        [ 0.55,  0.02],
        [ 0.39, -0.05],
        [ 0.20, -0.12],
        [ 0.00, -0.18],
        [-0.20, -0.21],
        [-0.38, -0.20],
      ],
      [
        [-0.08,  0.63],
        [-0.22,  0.57],
        [-0.38,  0.49],
        [-0.52,  0.39],
        [-0.62,  0.28],
      ],
      [
        [ 0.43, -0.38],
        [ 0.25, -0.43],
        [ 0.05, -0.47],
        [-0.16, -0.46],
        [-0.34, -0.40],
        [-0.46, -0.32],
      ],
      [
        [-0.40,  0.82],
        [-0.49,  0.66],
        [-0.57,  0.50],
        [-0.64,  0.34],
      ],
    ];
  const SECONDARY_CORTICAL_PATHS:
    CorticalPath[] =
    [
      [
        [0.26, 0.84],
        [0.21, 0.66],
        [0.17, 0.47],
        [0.14, 0.28],
        [0.11, 0.14],
      ],
      [
        [-0.07, 0.87],
        [-0.11, 0.69],
        [-0.14, 0.50],
        [-0.17, 0.31],
        [-0.20, 0.12],
      ],
      [
        [0.83, 0.73],
        [0.68, 0.68],
        [0.53, 0.60],
        [0.39, 0.50],
        [0.29, 0.40],
      ],
      [
        [0.84, 0.47],
        [0.68, 0.40],
        [0.54, 0.32],
        [0.40, 0.24],
        [0.29, 0.18],
      ],
      [
        [0.79, 0.22],
        [0.64, 0.15],
        [0.50, 0.08],
        [0.38, 0.03],
      ],
      [
        [0.76, -0.10],
        [0.62, -0.14],
        [0.49, -0.16],
        [0.38, -0.15],
      ],
      [
        [0.60, 0.90],
        [0.47, 0.82],
        [0.35, 0.73],
        [0.26, 0.66],
      ],
      [
        [0.30, 0.94],
        [0.18, 0.84],
        [0.08, 0.76],
      ],
      [
        [-0.18, 0.82],
        [-0.31, 0.73],
        [-0.44, 0.62],
        [-0.54, 0.52],
      ],
      [
        [-0.21, 0.38],
        [-0.36, 0.31],
        [-0.51, 0.22],
        [-0.64, 0.10],
      ],
      [
        [-0.22, 0.14],
        [-0.39, 0.07],
        [-0.54, -0.01],
        [-0.67, -0.09],
      ],
      [
        [-0.57, 0.72],
        [-0.70, 0.59],
        [-0.82, 0.42],
        [-0.89, 0.27],
      ],
      [
        [-0.61, 0.36],
        [-0.74, 0.25],
        [-0.85, 0.11],
        [-0.91, -0.02],
      ],
      [
        [-0.59, -0.07],
        [-0.71, -0.17],
        [-0.82, -0.28],
      ],
      [
        [0.46, -0.57],
        [0.27, -0.62],
        [0.07, -0.65],
        [-0.14, -0.62],
        [-0.31, -0.55],
      ],
      [
        [0.43, -0.75],
        [0.23, -0.79],
        [0.02, -0.79],
        [-0.18, -0.74],
        [-0.33, -0.66],
      ],
      [
        [-0.08, -0.31],
        [-0.25, -0.34],
        [-0.41, -0.30],
        [-0.54, -0.22],
      ],
      [
        [0.04, 0.94],
        [-0.08, 0.85],
        [-0.18, 0.76],
      ],
      [
        [-0.30, 0.92],
        [-0.42, 0.82],
        [-0.54, 0.69],
      ],
    ];
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
  const MICRO_CORTICAL_PATHS:
    CorticalPath[] =
    [
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
      [[0.86,0.70],[0.78,0.65],[0.70,0.58]],
      [[0.78,0.65],[0.74,0.75],[0.66,0.80]],
      [[0.76,0.48],[0.68,0.43],[0.60,0.36]],
      [[0.68,0.43],[0.63,0.52],[0.55,0.57]],
      [[0.82,0.27],[0.74,0.22],[0.66,0.16]],
      [[0.74,0.22],[0.68,0.31],[0.60,0.35]],
      [[0.69,0.03],[0.61,-0.02],[0.53,-0.07]],
      [[0.61,-0.02],[0.55,0.06],[0.48,0.10]],
      [[0.25,0.68],[0.18,0.62],[0.13,0.55]],
      [[0.18,0.62],[0.11,0.70],[0.04,0.73]],
      [[0.18,0.40],[0.11,0.34],[0.06,0.27]],
      [[0.11,0.34],[0.04,0.41],[-0.03,0.44]],
      [[0.10,0.13],[0.04,0.08],[-0.02,0.01]],
      [[0.04,0.08],[-0.03,0.15],[-0.10,0.18]],
      [[-0.29,0.69],[-0.37,0.63],[-0.45,0.55]],
      [[-0.37,0.63],[-0.44,0.71],[-0.52,0.75]],
      [[-0.32,0.43],[-0.40,0.37],[-0.48,0.30]],
      [[-0.40,0.37],[-0.47,0.45],[-0.55,0.48]],
      [[-0.39,0.17],[-0.47,0.11],[-0.55,0.04]],
      [[-0.47,0.11],[-0.54,0.19],[-0.61,0.22]],
      [[-0.64,0.61],[-0.72,0.54],[-0.79,0.45]],
      [[-0.72,0.54],[-0.79,0.61],[-0.86,0.62]],
      [[-0.70,0.29],[-0.78,0.22],[-0.85,0.14]],
      [[-0.78,0.22],[-0.85,0.29],[-0.91,0.31]],
      [[-0.69,-0.02],[-0.77,-0.09],[-0.84,-0.17]],
      [[-0.77,-0.09],[-0.84,-0.02],[-0.90,0.00]],
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
  const corticalDisplacements:
    number[] =
    [];
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
      let width =
        baseWidth;
      width *=
        1 +
        parietal *
        superior *
        0.055;
      width *=
        1 +
        frontal *
        superior *
        0.025;
      width *=
        1 -
        occipital *
        inferior *
        0.045;
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
      const temporalLower =
        temporal *
        inferior *
        lateral;
      x +=
        lobe *
        temporalLower *
        0.050;
      y -=
        temporalLower *
        0.046;
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
      y +=
        frontal *
        superior *
        0.004;
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
      const majorSulcus =
        corticalPathField(
          MAJOR_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.033,
        );
      const secondarySulcus =
        corticalPathField(
          SECONDARY_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.026,
        );
      const tertiarySulcus =
        corticalPathField(
          TERTIARY_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.019,
        );
      const microSulcus =
        corticalPathField(
          MICRO_CORTICAL_PATHS,
          foldS,
          foldQ,
          0.0145,
        );
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
      const superiorBoost =
        1 +
        superior *
          0.22;
      const temporalBoost =
        1 +
        temporal *
        inferior *
        lateral *
        0.16;
      const broadGyrusRise =
        (
          0.0065 +
          gyrusField *
            0.0135
        ) *
        superiorBoost *
        temporalBoost;
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
  geometry.setAttribute(
    "aCorticalDisplacement",
    new Float32BufferAttribute(
      new Float32Array(
        corticalDisplacements,
      ),
      1,
    ),
  );
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
