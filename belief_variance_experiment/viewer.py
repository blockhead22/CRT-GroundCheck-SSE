"""
Belief Splat Viewer — 3D Interactive WebGL Visualization
=========================================================
Loads cached embeddings, projects to 3D via UMAP, computes Gaussian splat
ellipsoids per prompt, and generates a self-contained Three.js HTML file.

Usage:
    python viewer.py --data-dir results/raw/qwen3_14b
"""

import argparse
import json
import html as html_lib
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
EMBED_DIR = BASE_DIR / "results" / "embeddings"
ANALYSIS_DIR = BASE_DIR / "results" / "analysis"
OUTPUT_DIR = BASE_DIR / "results"

TEMPERATURES = [0.0, 0.3, 0.7, 1.0, 1.5]

DOMAIN_COLORS = {
    "factual_settled":   "#4488ff",
    "factual_contested": "#00cccc",
    "moral_ambiguous":   "#ff4444",
    "moral_clear":       "#ff8800",
    "opinion_aesthetic":  "#44cc44",
}

DOMAIN_LABELS = {
    "factual_settled":   "Factual Settled",
    "factual_contested": "Factual Contested",
    "moral_ambiguous":   "Moral Ambiguous",
    "moral_clear":       "Moral Clear",
    "opinion_aesthetic":  "Opinion / Aesthetic",
}


def load_raw_data(data_dir: Path) -> dict[str, dict[float, list[dict]]]:
    """Load raw JSONL results into {prompt_id: {temperature: [records]}}."""
    data: dict[str, dict[float, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for path in sorted(data_dir.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                pid = record["prompt_id"]
                temp = record["temperature"]
                data[pid][temp].append(record)
    return data


def load_embeddings(data: dict) -> dict[str, dict[float, np.ndarray]]:
    """Load cached .npy embeddings for all prompt_id/temp combos found in data."""
    embeddings: dict[str, dict[float, np.ndarray]] = defaultdict(dict)
    for pid in data:
        for temp in data[pid]:
            cache_path = EMBED_DIR / f"{pid}_{temp}.npy"
            if cache_path.exists():
                embeddings[pid][temp] = np.load(cache_path)
            else:
                print(f"WARNING: Missing embedding cache {cache_path}")
    return embeddings


def load_analysis() -> dict:
    """Load analysis_results.json."""
    path = ANALYSIS_DIR / "analysis_results.json"
    if not path.exists():
        print(f"WARNING: No analysis results at {path}, metrics will be empty")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_umap(all_embeddings: np.ndarray) -> np.ndarray:
    """Project N x 384 embeddings to N x 3 via UMAP."""
    import umap
    print(f"Running UMAP on {all_embeddings.shape[0]} points ({all_embeddings.shape[1]}D -> 3D)...")
    reducer = umap.UMAP(
        n_components=3,
        n_neighbors=30,
        min_dist=0.1,
        metric="cosine",
        random_state=42,
    )
    projected = reducer.fit_transform(all_embeddings)
    print("UMAP complete.")
    return projected


def compute_ellipsoid_params(points_3d: np.ndarray) -> dict:
    """
    Given Nx3 points, compute mean center + covariance eigendecomposition
    for rendering as a scaled/rotated ellipsoid.
    Returns dict with center, radii (eigenvalues), rotation (3x3 eigenvector matrix).
    """
    if len(points_3d) < 3:
        center = np.mean(points_3d, axis=0) if len(points_3d) > 0 else np.zeros(3)
        return {
            "center": center.tolist(),
            "radii": [0.05, 0.05, 0.05],
            "rotation": np.eye(3).tolist(),
        }

    center = np.mean(points_3d, axis=0)
    cov = np.cov(points_3d.T)

    # Eigendecomposition
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Clamp small/negative eigenvalues
    eigenvalues = np.maximum(eigenvalues, 1e-6)
    # Radii = sqrt(eigenvalues) * scale factor for visual clarity
    radii = np.sqrt(eigenvalues) * 2.0  # 2-sigma ellipsoid

    return {
        "center": center.tolist(),
        "radii": radii.tolist(),
        "rotation": eigenvectors.tolist(),  # Column vectors are eigenvectors
    }


def build_viewer_data(
    data: dict,
    embeddings: dict,
    analysis: dict,
) -> dict:
    """
    Build all data needed for the 3D viewer.
    1. Collect all embeddings into one big matrix
    2. UMAP project once
    3. Compute per-point metadata and per-prompt ellipsoids
    """

    # --- Step 1: Collect all embeddings with metadata ---
    all_emb_list = []
    meta_list = []  # parallel list of metadata per point

    # Build a prompt text lookup from analysis data
    prompt_texts = {}
    if "per_prompt" in analysis:
        for pid, pdata in analysis["per_prompt"].items():
            prompt_texts[pid] = pdata.get("text", pid)

    for pid in sorted(data.keys()):
        for temp in sorted(data[pid].keys()):
            if pid not in embeddings or temp not in embeddings[pid]:
                continue
            emb = embeddings[pid][temp]
            records = data[pid][temp]
            domain = records[0]["domain"] if records else "unknown"
            n = min(len(emb), len(records))
            for i in range(n):
                all_emb_list.append(emb[i])
                resp_text = records[i].get("response", "")[:120]  # Truncate for tooltip
                meta_list.append({
                    "pid": pid,
                    "domain": domain,
                    "temp": temp,
                    "rep": i,
                    "response_preview": resp_text,
                })

    if not all_emb_list:
        print("ERROR: No embedding data found.")
        sys.exit(1)

    all_emb = np.array(all_emb_list, dtype=np.float32)
    print(f"Total points: {all_emb.shape[0]}")

    # --- Step 2: UMAP ---
    projected = run_umap(all_emb)

    # Normalize to roughly [-10, 10] range for Three.js
    pmin = projected.min(axis=0)
    pmax = projected.max(axis=0)
    prange = pmax - pmin
    prange[prange < 1e-6] = 1.0
    projected = (projected - pmin) / prange * 20.0 - 10.0

    # --- Step 3: Build points array ---
    points = []
    for i, meta in enumerate(meta_list):
        points.append({
            "x": float(projected[i, 0]),
            "y": float(projected[i, 1]),
            "z": float(projected[i, 2]),
            "pid": meta["pid"],
            "domain": meta["domain"],
            "temp": meta["temp"],
            "rep": meta["rep"],
            "preview": meta["response_preview"],
        })

    # --- Step 4: Per-prompt ellipsoids ---
    # Group projected points by prompt_id
    prompt_points: dict[str, list[int]] = defaultdict(list)
    for i, meta in enumerate(meta_list):
        prompt_points[meta["pid"]].append(i)

    ellipsoids = []
    for pid in sorted(prompt_points.keys()):
        indices = prompt_points[pid]
        pts_3d = projected[indices]
        domain = meta_list[indices[0]]["domain"]

        # Per-temperature ellipsoids
        temp_indices: dict[float, list[int]] = defaultdict(list)
        for idx in indices:
            temp_indices[meta_list[idx]["temp"]].append(idx)

        # Overall ellipsoid (all temps)
        params = compute_ellipsoid_params(pts_3d)

        # Get analysis metrics
        pdata = analysis.get("per_prompt", {}).get(pid, {})
        susceptibility = pdata.get("susceptibility", 0)
        held = pdata.get("held_contradiction", False)
        entropy_at_1 = analysis.get("per_prompt_per_temp", {}).get(pid, {}).get("1.0", {}).get("entropy", 0)

        ellipsoids.append({
            "pid": pid,
            "domain": domain,
            "text": prompt_texts.get(pid, pid),
            "susceptibility": round(susceptibility, 4),
            "held_contradiction": held,
            "entropy": round(entropy_at_1, 4),
            "center": params["center"],
            "radii": params["radii"],
            "rotation": params["rotation"],
        })

        # Per-temperature sub-ellipsoids
        for temp in TEMPERATURES:
            if temp not in temp_indices:
                continue
            t_pts = projected[temp_indices[temp]]
            t_params = compute_ellipsoid_params(t_pts)
            ellipsoids.append({
                "pid": pid,
                "domain": domain,
                "text": prompt_texts.get(pid, pid),
                "susceptibility": round(susceptibility, 4),
                "held_contradiction": held,
                "entropy": round(entropy_at_1, 4),
                "center": t_params["center"],
                "radii": t_params["radii"],
                "rotation": t_params["rotation"],
                "temp": temp,  # Marks this as a per-temp ellipsoid
            })

    return {
        "points": points,
        "ellipsoids": ellipsoids,
        "domain_colors": DOMAIN_COLORS,
        "domain_labels": DOMAIN_LABELS,
        "temperatures": TEMPERATURES,
    }


def generate_html(viewer_data: dict, output_path: Path) -> None:
    """Generate a self-contained HTML file with embedded Three.js visualization."""

    data_json = json.dumps(viewer_data, separators=(",", ":"))

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Belief Splat Viewer</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #111; color: #eee; font-family: 'Segoe UI', system-ui, sans-serif; overflow: hidden; }}
#container {{ width: 100vw; height: 100vh; }}
#ui-overlay {{
    position: absolute; top: 0; left: 0; pointer-events: none;
    width: 100%; height: 100%; z-index: 10;
}}
#legend {{
    position: absolute; top: 16px; left: 16px;
    background: rgba(17,17,17,0.92); padding: 14px 18px; border-radius: 8px;
    pointer-events: auto; font-size: 13px; border: 1px solid #333;
    min-width: 200px;
}}
#legend h3 {{ margin-bottom: 8px; font-size: 14px; color: #aaa; letter-spacing: 1px; }}
.domain-row {{
    display: flex; align-items: center; gap: 8px; margin: 4px 0;
    cursor: pointer; user-select: none;
}}
.domain-row:hover {{ opacity: 0.8; }}
.domain-swatch {{
    width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0;
}}
.domain-row input {{ margin: 0; cursor: pointer; }}
.domain-row label {{ cursor: pointer; }}
.domain-row.disabled label {{ text-decoration: line-through; opacity: 0.4; }}

#controls {{
    position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%);
    background: rgba(17,17,17,0.92); padding: 14px 24px; border-radius: 8px;
    pointer-events: auto; display: flex; align-items: center; gap: 16px;
    border: 1px solid #333; font-size: 13px;
}}
#temp-slider {{ width: 260px; cursor: pointer; accent-color: #ff8800; }}
#temp-label {{ font-weight: bold; min-width: 100px; text-align: center; font-size: 15px; }}
#mode-toggle {{ cursor: pointer; background: #333; color: #eee; border: 1px solid #555;
    padding: 6px 14px; border-radius: 4px; font-size: 12px; }}
#mode-toggle:hover {{ background: #444; }}
#play-btn {{ cursor: pointer; background: #ff8800; color: #111; border: none;
    padding: 6px 14px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
#play-btn:hover {{ background: #ffaa44; }}

#info-panel {{
    position: absolute; top: 16px; right: 16px;
    background: rgba(17,17,17,0.95); padding: 16px 20px; border-radius: 8px;
    pointer-events: auto; font-size: 12px; border: 1px solid #333;
    max-width: 340px; display: none; line-height: 1.5;
}}
#info-panel h3 {{ font-size: 14px; margin-bottom: 6px; color: #ff8800; }}
#info-panel .close-btn {{
    position: absolute; top: 8px; right: 12px; cursor: pointer;
    color: #888; font-size: 16px;
}}
#info-panel .close-btn:hover {{ color: #fff; }}
.info-field {{ margin: 3px 0; }}
.info-label {{ color: #888; }}
.info-value {{ color: #eee; }}
.held-badge {{
    display: inline-block; background: #ff4444; color: #fff;
    padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;
}}

#tooltip {{
    position: absolute; pointer-events: none; display: none;
    background: rgba(0,0,0,0.85); color: #eee; padding: 6px 10px;
    border-radius: 4px; font-size: 11px; white-space: nowrap;
    border: 1px solid #444;
}}

#stats-bar {{
    position: absolute; bottom: 80px; left: 50%; transform: translateX(-50%);
    background: rgba(17,17,17,0.85); padding: 6px 16px; border-radius: 6px;
    pointer-events: none; font-size: 11px; color: #888; border: 1px solid #222;
}}

#ellipsoid-toggle {{
    position: absolute; top: 16px; left: 240px;
    background: rgba(17,17,17,0.92); padding: 10px 14px; border-radius: 8px;
    pointer-events: auto; font-size: 12px; border: 1px solid #333;
}}
#ellipsoid-toggle label {{ cursor: pointer; }}
</style>
</head>
<body>
<div id="container"></div>
<div id="ui-overlay">
    <div id="legend">
        <h3>DOMAINS</h3>
        <div id="domain-filters"></div>
    </div>
    <div id="ellipsoid-toggle">
        <label><input type="checkbox" id="show-ellipsoids" checked> Show Splat Ellipsoids</label>
    </div>
    <div id="controls">
        <button id="play-btn">Play</button>
        <input type="range" id="temp-slider" min="0" max="4" step="1" value="0">
        <div id="temp-label">T = 0.0</div>
        <button id="mode-toggle">Mode: Single Temp</button>
    </div>
    <div id="stats-bar"></div>
    <div id="info-panel">
        <span class="close-btn" onclick="document.getElementById('info-panel').style.display='none'">&times;</span>
        <div id="info-content"></div>
    </div>
    <div id="tooltip"></div>
</div>

<script type="importmap">
{{
    "imports": {{
        "three": "https://cdn.jsdelivr.net/npm/three@0.162.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.162.0/examples/jsm/"
    }}
}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

// ─── Data ───
const DATA = {data_json};

const TEMPS = DATA.temperatures;
const DOMAIN_COLORS = DATA.domain_colors;
const DOMAIN_LABELS = DATA.domain_labels;

// ─── State ───
let currentTempIdx = 0;
let mode = 'single'; // 'single' | 'all'
let domainVisible = {{}};
let showEllipsoids = true;
let isPlaying = false;
let playInterval = null;

Object.keys(DOMAIN_COLORS).forEach(d => domainVisible[d] = true);

// ─── Scene setup ───
const container = document.getElementById('container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111111);

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 500);
camera.position.set(18, 14, 18);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 3;
controls.maxDistance = 80;
controls.target.set(0, 0, 0);

// ─── Lights ───
scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const dirLight = new THREE.DirectionalLight(0xffffff, 0.5);
dirLight.position.set(10, 20, 10);
scene.add(dirLight);

// ─── Grid floor ───
const gridHelper = new THREE.GridHelper(30, 30, 0x222222, 0x1a1a1a);
gridHelper.position.y = -12;
scene.add(gridHelper);

// ─── Build points using BufferGeometry ───
const pointsData = DATA.points;
const numPoints = pointsData.length;

const positions = new Float32Array(numPoints * 3);
const colors = new Float32Array(numPoints * 3);
const sizes = new Float32Array(numPoints);
const alphas = new Float32Array(numPoints);
const tempArr = new Float32Array(numPoints);
const domainArr = new Array(numPoints);

for (let i = 0; i < numPoints; i++) {{
    const p = pointsData[i];
    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y;
    positions[i * 3 + 2] = p.z;

    const col = new THREE.Color(DOMAIN_COLORS[p.domain] || '#ffffff');
    colors[i * 3] = col.r;
    colors[i * 3 + 1] = col.g;
    colors[i * 3 + 2] = col.b;

    // Size: slightly larger at higher temps
    sizes[i] = 3.0 + p.temp * 1.5;
    // Alpha: more transparent at higher temps
    alphas[i] = 1.0 - p.temp * 0.4;
    tempArr[i] = p.temp;
    domainArr[i] = p.domain;
}}

const pointGeo = new THREE.BufferGeometry();
pointGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
pointGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
pointGeo.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
pointGeo.setAttribute('alpha', new THREE.BufferAttribute(alphas, 1));

const pointMaterial = new THREE.ShaderMaterial({{
    uniforms: {{
        pixelRatio: {{ value: renderer.getPixelRatio() }},
    }},
    vertexShader: `
        attribute float size;
        attribute float alpha;
        varying vec3 vColor;
        varying float vAlpha;
        uniform float pixelRatio;
        void main() {{
            vColor = color;
            vAlpha = alpha;
            vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
            gl_PointSize = size * pixelRatio * (8.0 / -mvPosition.z);
            gl_PointSize = clamp(gl_PointSize, 1.0, 20.0);
            gl_Position = projectionMatrix * mvPosition;
        }}
    `,
    fragmentShader: `
        varying vec3 vColor;
        varying float vAlpha;
        void main() {{
            float d = length(gl_PointCoord - vec2(0.5));
            if (d > 0.5) discard;
            float a = smoothstep(0.5, 0.3, d) * vAlpha;
            gl_FragColor = vec4(vColor, a);
        }}
    `,
    transparent: true,
    vertexColors: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
}});

const pointCloud = new THREE.Points(pointGeo, pointMaterial);
scene.add(pointCloud);

// ─── Ellipsoid meshes ───
const ellipsoidGroup = new THREE.Group();
scene.add(ellipsoidGroup);

const sphereGeo = new THREE.SphereGeometry(1, 24, 16);
const ellipsoidMeshes = [];

for (const ell of DATA.ellipsoids) {{
    const col = new THREE.Color(DOMAIN_COLORS[ell.domain] || '#ffffff');
    const mat = new THREE.MeshPhongMaterial({{
        color: col,
        transparent: true,
        opacity: ell.held_contradiction ? 0.18 : 0.08,
        side: THREE.DoubleSide,
        depthWrite: false,
        wireframe: false,
    }});

    const mesh = new THREE.Mesh(sphereGeo, mat);

    // Position
    mesh.position.set(ell.center[0], ell.center[1], ell.center[2]);

    // Apply rotation from eigenvectors then scale by radii
    const rot = ell.rotation;
    const m = new THREE.Matrix4();
    m.set(
        rot[0][0], rot[1][0], rot[2][0], 0,
        rot[0][1], rot[1][1], rot[2][1], 0,
        rot[0][2], rot[1][2], rot[2][2], 0,
        0, 0, 0, 1
    );

    const r = ell.radii;
    const scaleM = new THREE.Matrix4().makeScale(r[0], r[1], r[2]);
    m.multiply(scaleM);

    // Extract rotation from combined matrix
    mesh.scale.set(1, 1, 1);
    mesh.matrixAutoUpdate = false;
    const posMat = new THREE.Matrix4().makeTranslation(ell.center[0], ell.center[1], ell.center[2]);
    mesh.matrix.copy(posMat).multiply(m);

    // Also add wireframe outline for held contradictions
    if (ell.held_contradiction && !('temp' in ell)) {{
        const wireMat = new THREE.MeshBasicMaterial({{
            color: 0xff4444,
            wireframe: true,
            transparent: true,
            opacity: 0.25,
        }});
        const wireMesh = new THREE.Mesh(sphereGeo, wireMat);
        wireMesh.matrixAutoUpdate = false;
        wireMesh.matrix.copy(mesh.matrix);
        wireMesh.userData = {{ ...ell, isWire: true }};
        ellipsoidGroup.add(wireMesh);
        ellipsoidMeshes.push(wireMesh);
    }}

    mesh.userData = ell;
    ellipsoidGroup.add(mesh);
    ellipsoidMeshes.push(mesh);
}}

// ─── UI: Domain filters ───
const filtersDiv = document.getElementById('domain-filters');
for (const [domain, label] of Object.entries(DOMAIN_LABELS)) {{
    const row = document.createElement('div');
    row.className = 'domain-row';
    row.innerHTML = `
        <input type="checkbox" id="cb-${{domain}}" checked>
        <div class="domain-swatch" style="background:${{DOMAIN_COLORS[domain]}}"></div>
        <label for="cb-${{domain}}">${{label}}</label>
    `;
    row.querySelector('input').addEventListener('change', (e) => {{
        domainVisible[domain] = e.target.checked;
        row.classList.toggle('disabled', !e.target.checked);
        updateVisibility();
    }});
    filtersDiv.appendChild(row);
}}

// ─── UI: Temperature slider ───
const slider = document.getElementById('temp-slider');
const tempLabel = document.getElementById('temp-label');
const modeBtn = document.getElementById('mode-toggle');
const playBtn = document.getElementById('play-btn');

slider.addEventListener('input', () => {{
    currentTempIdx = parseInt(slider.value);
    tempLabel.textContent = `T = ${{TEMPS[currentTempIdx]}}`;
    updateVisibility();
}});

modeBtn.addEventListener('click', () => {{
    mode = mode === 'single' ? 'all' : 'single';
    modeBtn.textContent = `Mode: ${{mode === 'single' ? 'Single Temp' : 'All Temps'}}`;
    updateVisibility();
}});

playBtn.addEventListener('click', () => {{
    if (isPlaying) {{
        clearInterval(playInterval);
        isPlaying = false;
        playBtn.textContent = 'Play';
        return;
    }}
    isPlaying = true;
    playBtn.textContent = 'Stop';
    currentTempIdx = 0;
    slider.value = 0;
    mode = 'single';
    modeBtn.textContent = 'Mode: Single Temp';
    updateVisibility();

    playInterval = setInterval(() => {{
        currentTempIdx++;
        if (currentTempIdx >= TEMPS.length) {{
            clearInterval(playInterval);
            isPlaying = false;
            playBtn.textContent = 'Play';
            return;
        }}
        slider.value = currentTempIdx;
        tempLabel.textContent = `T = ${{TEMPS[currentTempIdx]}}`;
        updateVisibility();
    }}, 1200);
}});

document.getElementById('show-ellipsoids').addEventListener('change', (e) => {{
    showEllipsoids = e.target.checked;
    updateVisibility();
}});

// ─── Visibility update ───
function updateVisibility() {{
    const alphaAttr = pointGeo.getAttribute('alpha');
    const sizeAttr = pointGeo.getAttribute('size');
    const currentTemp = TEMPS[currentTempIdx];
    let visibleCount = 0;

    for (let i = 0; i < numPoints; i++) {{
        const p = pointsData[i];
        const domainOk = domainVisible[p.domain];
        const tempOk = mode === 'all' || Math.abs(p.temp - currentTemp) < 0.01;
        const visible = domainOk && tempOk;

        if (visible) {{
            alphaAttr.array[i] = 1.0 - p.temp * 0.4;
            sizeAttr.array[i] = 3.0 + p.temp * 1.5;
            visibleCount++;
        }} else {{
            alphaAttr.array[i] = 0.0;
            sizeAttr.array[i] = 0.0;
        }}
    }}
    alphaAttr.needsUpdate = true;
    sizeAttr.needsUpdate = true;

    // Ellipsoids
    for (const mesh of ellipsoidMeshes) {{
        const ell = mesh.userData;
        if (ell.isWire) {{
            // Wire follows its parent ellipsoid's visibility
            const domOk = domainVisible[ell.domain];
            const isAllEll = !('temp' in ell);
            const tempOk = mode === 'all' ? isAllEll : false;
            mesh.visible = showEllipsoids && domOk && tempOk;
            continue;
        }}
        const domOk = domainVisible[ell.domain];
        const isAllEll = !('temp' in ell);
        let tempOk;
        if (mode === 'all') {{
            tempOk = isAllEll;
        }} else {{
            tempOk = ('temp' in ell) && Math.abs(ell.temp - currentTemp) < 0.01;
        }}
        mesh.visible = showEllipsoids && domOk && tempOk;
    }}

    // Stats
    document.getElementById('stats-bar').textContent =
        `Visible: ${{visibleCount}} / ${{numPoints}} points | Temperature: ${{currentTemp}} | Mode: ${{mode}}`;
}}

// Initial visibility
updateVisibility();

// ─── Raycasting for hover/click ───
const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 0.3;
const mouse = new THREE.Vector2();
const tooltip = document.getElementById('tooltip');

function getMouseNDC(event) {{
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
}}

container.addEventListener('mousemove', (event) => {{
    getMouseNDC(event);
    raycaster.setFromCamera(mouse, camera);

    // Check points
    const intersects = raycaster.intersectObject(pointCloud);
    if (intersects.length > 0) {{
        const idx = intersects[0].index;
        const p = pointsData[idx];
        if (domainVisible[p.domain]) {{
            tooltip.style.display = 'block';
            tooltip.style.left = (event.clientX + 12) + 'px';
            tooltip.style.top = (event.clientY + 12) + 'px';
            tooltip.innerHTML = `<b>${{p.pid}}</b> | T=${{p.temp}} | ${{p.domain.replace('_',' ')}}`;
            return;
        }}
    }}
    tooltip.style.display = 'none';
}});

container.addEventListener('click', (event) => {{
    getMouseNDC(event);
    raycaster.setFromCamera(mouse, camera);

    // Check ellipsoids first
    const visibleEllipsoids = ellipsoidMeshes.filter(m => m.visible && !m.userData.isWire);
    const eIntersects = raycaster.intersectObjects(visibleEllipsoids);
    if (eIntersects.length > 0) {{
        const ell = eIntersects[0].object.userData;
        showInfoPanel(ell);
        return;
    }}

    // Check points
    const intersects = raycaster.intersectObject(pointCloud);
    if (intersects.length > 0) {{
        const idx = intersects[0].index;
        const p = pointsData[idx];
        // Find the ellipsoid for this prompt
        const ell = DATA.ellipsoids.find(e => e.pid === p.pid && !('temp' in e));
        if (ell) {{
            showInfoPanel(ell);
            return;
        }}
    }}
}});

function showInfoPanel(ell) {{
    const panel = document.getElementById('info-panel');
    const content = document.getElementById('info-content');
    const heldBadge = ell.held_contradiction
        ? '<span class="held-badge">HELD CONTRADICTION</span>'
        : '';
    content.innerHTML = `
        <h3>${{ell.pid}} ${{heldBadge}}</h3>
        <div class="info-field"><span class="info-label">Prompt: </span><span class="info-value">${{escapeHtml(ell.text)}}</span></div>
        <div class="info-field"><span class="info-label">Domain: </span><span class="info-value" style="color:${{DOMAIN_COLORS[ell.domain]}}">${{DOMAIN_LABELS[ell.domain] || ell.domain}}</span></div>
        <div class="info-field"><span class="info-label">Susceptibility (dH/dT): </span><span class="info-value">${{ell.susceptibility}}</span></div>
        <div class="info-field"><span class="info-label">Entropy @ T=1.0: </span><span class="info-value">${{ell.entropy}}</span></div>
        <div class="info-field"><span class="info-label">Splat Radii: </span><span class="info-value">[${{ell.radii.map(r => r.toFixed(3)).join(', ')}}]</span></div>
    `;
    panel.style.display = 'block';
}}

function escapeHtml(str) {{
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}}

// ─── Resize handler ───
window.addEventListener('resize', () => {{
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}});

// ─── Render loop ───
function animate() {{
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}}
animate();
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Viewer written to {output_path}")
    print(f"Open in browser: file:///{output_path.as_posix()}")


def main():
    parser = argparse.ArgumentParser(description="Belief Splat Viewer — 3D WebGL Visualization")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="results/raw/qwen3_14b",
        help="Path to model-specific raw results directory (default: results/raw/qwen3_14b)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output HTML path (default: results/viewer.html)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = BASE_DIR / data_dir

    output_path = Path(args.output) if args.output else OUTPUT_DIR / "viewer.html"
    if not output_path.is_absolute():
        output_path = BASE_DIR / output_path

    print("=" * 60)
    print("  BELIEF SPLAT VIEWER — 3D Generator")
    print("=" * 60)
    print(f"  Data dir:  {data_dir}")
    print(f"  Output:    {output_path}")
    print()

    # Load data
    print("Loading raw results...")
    data = load_raw_data(data_dir)
    total = sum(len(recs) for pid_data in data.values() for recs in pid_data.values())
    print(f"  {total} responses across {len(data)} prompts")

    if total == 0:
        print("ERROR: No data found. Check --data-dir path.")
        sys.exit(1)

    print("Loading cached embeddings...")
    embeddings = load_embeddings(data)

    print("Loading analysis results...")
    analysis = load_analysis()

    print("Building viewer data...")
    viewer_data = build_viewer_data(data, embeddings, analysis)
    print(f"  {len(viewer_data['points'])} points, {len(viewer_data['ellipsoids'])} ellipsoids")

    print("Generating HTML...")
    generate_html(viewer_data, output_path)
    print("\nDone.")


if __name__ == "__main__":
    main()
