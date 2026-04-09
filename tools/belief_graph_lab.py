"""
Belief Graph Visualization Lab
===============================
Standalone visualization of the CRT belief graph.
Reads directly from memory DB + BDG + ledger.
Generates an interactive HTML file with force-directed layout.

Usage:
  python tools/belief_graph_lab.py
  python tools/belief_graph_lab.py --kind user_fact   # filter by kind
  python tools/belief_graph_lab.py --min-trust 0.3    # trust threshold

Output: tools/belief_graph_output/belief_graph.html
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OUTPUT_DIR = Path(__file__).parent / "belief_graph_output"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_data(db_path: str, ledger_path: str, kinds: set = None, min_trust: float = 0.0):
    """Load memories, BDG edges, and contradictions."""
    from personal_agent.crt_memory import CRTMemorySystem
    from personal_agent.crt_ledger import ContradictionLedger
    from personal_agent.memory_graph import LiveBDG

    mem = CRTMemorySystem(db_path=db_path)
    ledger = ContradictionLedger(db_path=ledger_path)

    # Load all memories with vectors
    all_mems = mem._load_all_memories()
    filtered = [
        m for m in all_mems
        if m.vector is not None
        and len(m.vector) > 0
        and m.trust >= min_trust
        and (kinds is None or m.kind in kinds)
    ]
    print(f"Loaded {len(filtered)} memories (from {len(all_mems)} total)")

    # Build BDG
    bdg = LiveBDG(memory_system=mem, ledger=ledger)
    bdg.ensure_built()
    graph = bdg.bdg.graph
    print(f"BDG: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    # Get contradictions
    opens = ledger.get_open_contradictions(limit=100)
    print(f"Open contradictions: {len(opens)}")

    return filtered, graph, opens, ledger


def pca_project(memories, dimensions=2):
    """PCA project memory vectors to 2D/3D."""
    from sklearn.decomposition import PCA

    vectors = np.array([m.vector for m in memories])
    if len(vectors) < 2:
        return np.zeros((len(vectors), dimensions))

    pca = PCA(n_components=min(dimensions, len(vectors)))
    coords = pca.fit_transform(vectors)
    if coords.shape[1] < dimensions:
        coords = np.hstack([coords, np.zeros((len(coords), dimensions - coords.shape[1]))])

    # Normalize to [-1, 1]
    for d in range(dimensions):
        vmin, vmax = coords[:, d].min(), coords[:, d].max()
        span = vmax - vmin
        if span > 1e-8:
            coords[:, d] = 2.0 * (coords[:, d] - vmin) / span - 1.0

    return coords


def build_html_3d(memories, coords, graph, contradictions):
    """Build an interactive 3D Three.js visualization."""
    mem_ids = {m.memory_id for m in memories}
    id_to_idx = {m.memory_id: i for i, m in enumerate(memories)}

    nodes = []
    for i, m in enumerate(memories):
        nodes.append({
            "id": i,
            "mid": m.memory_id[:12],
            "x": float(coords[i, 0]) * 5,
            "y": float(coords[i, 1]) * 5,
            "z": float(coords[i, 2]) * 5 if coords.shape[1] >= 3 else 0,
            "trust": round(m.trust, 2),
            "kind": m.kind,
            "text": m.text[:120].replace('"', "'").replace("\n", " ").replace("\\", "/"),
            "contradiction_count": getattr(m, "contradiction_count", 0),
            "authority": getattr(m, "authority", "unknown"),
        })

    edges = []
    for src, tgt, edata in graph.edges(data=True):
        if src in id_to_idx and tgt in id_to_idx:
            edges.append({
                "source": id_to_idx[src],
                "target": id_to_idx[tgt],
                "type": edata.get("edge_type", "related_to"),
                "weight": round(float(edata.get("weight", 0.5)), 3),
            })

    contra_edges = []
    for c in contradictions:
        if c.old_memory_id in id_to_idx and c.new_memory_id in id_to_idx:
            contra_edges.append({
                "source": id_to_idx[c.old_memory_id],
                "target": id_to_idx[c.new_memory_id],
            })

    print(f"3D Visualization: {len(nodes)} nodes, {len(edges)} edges, {len(contra_edges)} contradictions")

    kind_colors = {
        "user_fact": "0xD4845C",
        "user_belief": "0xC4A055",
        "preference": "0x7CAD8A",
        "observation": "0x635c50",
        "ops": "0x5580AA",
        "narrative_note": "0x8866AA",
    }

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>CRT Belief Graph 3D — {len(nodes)} nodes</title>
<style>
  body {{ margin: 0; background: #141210; color: #F0EBE1; font-family: monospace; overflow: hidden; }}
  #info {{
    position: fixed; top: 12px; left: 12px; padding: 12px 16px;
    background: rgba(20,18,16,0.92); border: 1px solid rgba(240,235,225,0.1);
    border-radius: 6px; font-size: 12px; max-width: 300px; z-index: 10;
  }}
  #info h3 {{ margin: 0 0 8px 0; font-size: 14px; color: #D4845C; }}
  #tooltip {{
    position: fixed; display: none; padding: 10px 14px;
    background: rgba(26,23,20,0.95); border: 1px solid rgba(240,235,225,0.15);
    border-radius: 6px; font-size: 11px; max-width: 280px; z-index: 20;
    pointer-events: none;
  }}
  #inspector {{
    position: fixed; top: 60px; right: 12px; width: 360px; max-height: calc(100vh - 80px);
    overflow-y: auto; padding: 16px; display: none;
    background: rgba(20,18,16,0.96); border: 1px solid rgba(240,235,225,0.12);
    border-radius: 8px; font-size: 11px; z-index: 15;
  }}
  #inspector h4 {{ margin: 0 0 10px 0; color: #D4845C; font-size: 13px; }}
  .insp-close {{ float: right; cursor: pointer; color: #a89d8a; font-size: 16px; padding: 0 4px; }}
  .insp-close:hover {{ color: #F0EBE1; }}
  .insp-text {{ color: #F0EBE1; margin: 8px 0; line-height: 1.5; font-size: 12px; }}
  .insp-meta {{ color: #a89d8a; font-size: 10px; margin: 2px 0; }}
  .insp-section {{ margin-top: 14px; padding-top: 10px; border-top: 1px solid rgba(240,235,225,0.08); }}
  .insp-section-title {{ color: #D47058; font-size: 10px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }}
  .insp-card {{
    margin: 6px 0; padding: 8px 10px; border-radius: 4px; cursor: pointer;
    transition: background 0.15s;
  }}
  .insp-card:hover {{ background: rgba(240,235,225,0.06); }}
  .insp-card-contra {{ background: rgba(212,112,88,0.06); border-left: 2px solid #D47058; }}
  .insp-card-neighbor {{ background: rgba(212,132,92,0.04); border-left: 2px solid rgba(212,132,92,0.3); }}
  .insp-card-text {{ color: #F0EBE1; font-size: 11px; line-height: 1.4; }}
  .insp-card-meta {{ color: #a89d8a; font-size: 9px; margin-top: 3px; }}
  .insp-trust {{ color: #D4845C; }}
  .insp-kind {{ color: #a89d8a; }}
  .insp-contra-label {{ color: #D47058; }}
  #controls {{
    position: fixed; top: 12px; right: 12px; padding: 10px 14px;
    background: rgba(20,18,16,0.92); border: 1px solid rgba(240,235,225,0.1);
    border-radius: 6px; font-size: 11px; z-index: 10;
  }}
  button {{
    background: rgba(212,132,92,0.2); border: 1px solid rgba(212,132,92,0.3);
    color: #D4845C; padding: 4px 10px; border-radius: 4px; cursor: pointer;
    font-family: monospace; font-size: 10px; margin: 2px;
  }}
  button:hover {{ background: rgba(212,132,92,0.4); }}
  button.active {{ background: rgba(212,132,92,0.5); border-color: #D4845C; }}
  #legend {{
    position: fixed; bottom: 12px; left: 12px; padding: 10px 14px;
    background: rgba(20,18,16,0.92); border: 1px solid rgba(240,235,225,0.1);
    border-radius: 6px; font-size: 10px; z-index: 10;
  }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; margin: 3px 0; }}
  .legend-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
</style>
</head>
<body>
<div id="info">
  <h3>CRT Belief Graph 3D</h3>
  <div>{len(nodes)} nodes | {len(edges)} edges | {len(contra_edges)} contradictions</div>
  <div style="color:#a89d8a;margin-top:4px">Scroll zoom | Drag rotate | Right-drag pan</div>
</div>
<div id="tooltip"></div>
<div id="inspector"></div>
<div id="controls">
  <button onclick="toggleEdges()" id="edgeBtn" class="active">Edges</button>
  <button onclick="toggleContra()" id="contraBtn" class="active">Contradictions</button>
  <button onclick="toggleRotate()" id="rotBtn" class="active">Auto-Rotate</button>
</div>
<div id="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#D4845C"></div>user_fact</div>
  <div class="legend-item"><div class="legend-dot" style="background:#C4A055"></div>user_belief</div>
  <div class="legend-item"><div class="legend-dot" style="background:#7CAD8A"></div>preference</div>
  <div class="legend-item"><div class="legend-dot" style="background:#635c50"></div>observation</div>
  <div class="legend-item"><div class="legend-dot" style="background:#5580AA"></div>ops</div>
  <div class="legend-item" style="margin-top:6px"><div style="width:16px;height:1px;background:rgba(212,132,92,0.4)"></div>related</div>
  <div class="legend-item"><div style="width:16px;height:2px;background:#D47058"></div>contradiction</div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const nodes = {json.dumps(nodes)};
const edges = {json.dumps(edges)};
const contraEdges = {json.dumps(contra_edges)};
const kindColorMap = {{ user_fact: 0xD4845C, user_belief: 0xC4A055, preference: 0x7CAD8A, observation: 0x635c50, ops: 0x5580AA, narrative_note: 0x8866AA }};

let showEdges = true, showContra = true, autoRotate = true;
let edgeGroup, contraGroup;

// Scene setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x141210);
const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 0, 15);
const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.body.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.autoRotate = true;
controls.autoRotateSpeed = 0.5;
controls.enableDamping = true;
controls.dampingFactor = 0.05;

// Nodes
const spheres = [];
for (const n of nodes) {{
  const r = 0.04 + n.trust * 0.12;
  const color = kindColorMap[n.kind] || 0x635c50;
  const geo = new THREE.SphereGeometry(r, 12, 8);
  const mat = new THREE.MeshBasicMaterial({{ color, transparent: true, opacity: 0.85 }});
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(n.x, n.y, n.z);
  mesh.userData = n;
  scene.add(mesh);
  spheres.push(mesh);

  // Glow for high trust
  if (n.trust > 0.7) {{
    const glowGeo = new THREE.SphereGeometry(r + 0.06, 12, 8);
    const glowMat = new THREE.MeshBasicMaterial({{ color, transparent: true, opacity: 0.12 }});
    const glow = new THREE.Mesh(glowGeo, glowMat);
    glow.position.copy(mesh.position);
    scene.add(glow);
  }}

  // Contradiction ring
  if (n.contradiction_count > 0) {{
    const ringGeo = new THREE.RingGeometry(r + 0.02, r + 0.05, 16);
    const ringMat = new THREE.MeshBasicMaterial({{ color: 0xD47058, transparent: true, opacity: 0.5, side: THREE.DoubleSide }});
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.copy(mesh.position);
    ring.lookAt(camera.position);
    scene.add(ring);
  }}
}}

// BDG Edges
edgeGroup = new THREE.Group();
const edgeMat = new THREE.LineBasicMaterial({{ color: 0xD4845C, transparent: true, opacity: 0.06 }});
for (const e of edges) {{
  const a = nodes[e.source], b = nodes[e.target];
  const geo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(a.x, a.y, a.z),
    new THREE.Vector3(b.x, b.y, b.z),
  ]);
  edgeGroup.add(new THREE.Line(geo, edgeMat));
}}
scene.add(edgeGroup);

// Contradiction edges
contraGroup = new THREE.Group();
const contraMat = new THREE.LineBasicMaterial({{ color: 0xD47058, transparent: true, opacity: 0.6, linewidth: 2 }});
for (const c of contraEdges) {{
  const a = nodes[c.source], b = nodes[c.target];
  const geo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(a.x, a.y, a.z),
    new THREE.Vector3(b.x, b.y, b.z),
  ]);
  contraGroup.add(new THREE.Line(geo, contraMat));
}}
scene.add(contraGroup);

// Build adjacency map for ripple propagation
const adj = {{}};
for (let i = 0; i < nodes.length; i++) adj[i] = [];
for (const e of edges) {{
  adj[e.source].push(e.target);
  adj[e.target].push(e.source);
}}
for (const c of contraEdges) {{
  adj[c.source].push(c.target);
  adj[c.target].push(c.source);
}}

// Build edge index for highlighting
const edgeIndex = {{}};
for (let i = 0; i < edges.length; i++) {{
  const e = edges[i];
  const key1 = e.source + ',' + e.target;
  const key2 = e.target + ',' + e.source;
  edgeIndex[key1] = i;
  edgeIndex[key2] = i;
}}

// Selection state
let selectedNode = null;
let rippleDepths = {{}}; // nodeId -> depth (0=selected, 1=direct, 2=second, 3=third)

// Highlight group for selected edges
let highlightGroup = new THREE.Group();
scene.add(highlightGroup);

function computeRipple(nodeId, maxDepth) {{
  const depths = {{}};
  const queue = [[nodeId, 0]];
  depths[nodeId] = 0;
  while (queue.length > 0) {{
    const [current, depth] = queue.shift();
    if (depth >= maxDepth) continue;
    for (const neighbor of (adj[current] || [])) {{
      if (!(neighbor in depths)) {{
        depths[neighbor] = depth + 1;
        queue.push([neighbor, depth + 1]);
      }}
    }}
  }}
  return depths;
}}

function applySelection(nodeId) {{
  // Clear previous highlights
  scene.remove(highlightGroup);
  highlightGroup = new THREE.Group();
  scene.add(highlightGroup);

  if (nodeId === null) {{
    // Deselect — restore all
    rippleDepths = {{}};
    for (const s of spheres) {{
      s.material.opacity = 0.85;
      s.scale.set(1, 1, 1);
    }}
    edgeGroup.children.forEach(l => {{ l.material.opacity = 0.06; }});
    contraGroup.children.forEach(l => {{ l.material.opacity = 0.6; }});
    return;
  }}

  rippleDepths = computeRipple(nodeId, 3);

  // Dim all nodes, then brighten by depth
  for (let i = 0; i < spheres.length; i++) {{
    const depth = rippleDepths[i];
    if (depth === undefined) {{
      // Not connected — very dim
      spheres[i].material.opacity = 0.04;
      spheres[i].scale.set(0.7, 0.7, 0.7);
    }} else if (depth === 0) {{
      // Selected node — full bright, enlarged
      spheres[i].material.opacity = 1.0;
      spheres[i].scale.set(1.8, 1.8, 1.8);
    }} else if (depth === 1) {{
      // Direct neighbors — bright
      spheres[i].material.opacity = 0.9;
      spheres[i].scale.set(1.3, 1.3, 1.3);
    }} else if (depth === 2) {{
      // Second hop — medium
      spheres[i].material.opacity = 0.5;
      spheres[i].scale.set(1.0, 1.0, 1.0);
    }} else {{
      // Third hop — faint
      spheres[i].material.opacity = 0.2;
      spheres[i].scale.set(0.85, 0.85, 0.85);
    }}
  }}

  // Dim all base edges
  edgeGroup.children.forEach(l => {{ l.material.opacity = 0.02; }});
  contraGroup.children.forEach(l => {{ l.material.opacity = 0.15; }});

  // Draw highlighted edges from selected node
  const selectedPos = new THREE.Vector3(nodes[nodeId].x, nodes[nodeId].y, nodes[nodeId].z);
  for (const neighborId of (adj[nodeId] || [])) {{
    const depth = rippleDepths[neighborId];
    if (depth === undefined) continue;
    const nPos = new THREE.Vector3(nodes[neighborId].x, nodes[neighborId].y, nodes[neighborId].z);
    const isContra = contraEdges.some(c =>
      (c.source === nodeId && c.target === neighborId) ||
      (c.target === nodeId && c.source === neighborId)
    );
    const color = isContra ? 0xD47058 : 0xD4845C;
    const opacity = depth <= 1 ? 0.8 : (depth <= 2 ? 0.3 : 0.12);
    const geo = new THREE.BufferGeometry().setFromPoints([selectedPos, nPos]);
    const mat = new THREE.LineBasicMaterial({{ color, transparent: true, opacity }});
    highlightGroup.add(new THREE.Line(geo, mat));
  }}

  // Also draw faint second-hop edges
  for (const [nId, depth] of Object.entries(rippleDepths)) {{
    if (depth < 1 || depth > 2) continue;
    const nIdNum = parseInt(nId);
    for (const neighbor2 of (adj[nIdNum] || [])) {{
      const d2 = rippleDepths[neighbor2];
      if (d2 !== undefined && d2 === depth + 1) {{
        const p1 = new THREE.Vector3(nodes[nIdNum].x, nodes[nIdNum].y, nodes[nIdNum].z);
        const p2 = new THREE.Vector3(nodes[neighbor2].x, nodes[neighbor2].y, nodes[neighbor2].z);
        const geo = new THREE.BufferGeometry().setFromPoints([p1, p2]);
        const mat = new THREE.LineBasicMaterial({{ color: 0xD4845C, transparent: true, opacity: 0.08 }});
        highlightGroup.add(new THREE.Line(geo, mat));
      }}
    }}
  }}
}}

// Raycaster
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
const tooltip = document.getElementById('tooltip');

window.addEventListener('mousemove', (e) => {{
  mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const intersects = raycaster.intersectObjects(spheres);
  if (intersects.length > 0) {{
    const n = intersects[0].object.userData;
    const depth = rippleDepths[n.id];
    const depthLabel = depth === 0 ? ' [SELECTED]' : depth !== undefined ? ` [depth ${{depth}}]` : '';
    tooltip.style.display = 'block';
    tooltip.style.left = (e.clientX + 15) + 'px';
    tooltip.style.top = (e.clientY + 15) + 'px';
    tooltip.innerHTML = `
      <span style="color:#D4845C">T:${{n.trust}}</span>
      <span style="color:#a89d8a">${{n.kind}}</span>
      <span style="color:#a89d8a">${{n.authority}}</span>
      ${{n.contradiction_count > 0 ? '<span style="color:#D47058"> ' + n.contradiction_count + 'x</span>' : ''}}
      <span style="color:#7CAD8A">${{depthLabel}}</span>
      <div style="color:#F0EBE1;margin-top:4px">${{n.text}}</div>
      <div style="color:#635c50;margin-top:2px">${{n.mid}}</div>
    `;
    document.body.style.cursor = 'pointer';
  }} else {{
    tooltip.style.display = 'none';
    document.body.style.cursor = 'default';
  }}
}});

// Build contradiction lookup per node
const nodeContras = {{}};
for (const c of contraEdges) {{
  if (!nodeContras[c.source]) nodeContras[c.source] = [];
  if (!nodeContras[c.target]) nodeContras[c.target] = [];
  nodeContras[c.source].push({{ other: c.target, role: 'old' }});
  nodeContras[c.target].push({{ other: c.source, role: 'new' }});
}}

function inspectNode(nodeId) {{
  const n = nodes[nodeId];
  const inspector = document.getElementById('inspector');
  const contras = nodeContras[nodeId] || [];
  const neighbors = (adj[nodeId] || []).filter(nid => !contras.some(c => c.other === nid));

  let html = `<span class="insp-close" onclick="closeInspector()">&times;</span>`;
  html += `<h4>${{n.kind}}</h4>`;
  html += `<div class="insp-text">${{n.text}}</div>`;
  html += `<div class="insp-meta">
    <span class="insp-trust">trust: ${{n.trust}}</span> &middot;
    <span class="insp-kind">${{n.authority}}</span> &middot;
    ${{n.contradiction_count > 0 ? '<span class="insp-contra-label">' + n.contradiction_count + 'x contradicted</span> &middot;' : ''}}
    <span>${{n.mid}}</span>
  </div>`;

  // Contradiction section
  if (contras.length > 0) {{
    html += `<div class="insp-section">
      <div class="insp-section-title">Contradictions (${{contras.length}})</div>`;
    for (const c of contras) {{
      const other = nodes[c.other];
      html += `<div class="insp-card insp-card-contra" onclick="selectAndInspect(${{c.other}})">
        <div class="insp-card-meta">
          <span class="insp-contra-label">${{c.role === 'old' ? 'contradicted by' : 'contradicts'}}</span>
          <span class="insp-trust">T:${{other.trust}}</span>
          <span class="insp-kind">${{other.kind}}</span>
        </div>
        <div class="insp-card-text">${{other.text}}</div>
      </div>`;
    }}
    html += `</div>`;
  }}

  // Connected neighbors (non-contradiction)
  const topNeighbors = neighbors.slice(0, 15);
  if (topNeighbors.length > 0) {{
    html += `<div class="insp-section">
      <div class="insp-section-title" style="color:#D4845C">Connected (${{neighbors.length}})</div>`;
    for (const nid of topNeighbors) {{
      const nb = nodes[nid];
      html += `<div class="insp-card insp-card-neighbor" onclick="selectAndInspect(${{nid}})">
        <div class="insp-card-meta">
          <span class="insp-trust">T:${{nb.trust}}</span>
          <span class="insp-kind">${{nb.kind}}</span>
        </div>
        <div class="insp-card-text">${{nb.text}}</div>
      </div>`;
    }}
    if (neighbors.length > 15) {{
      html += `<div class="insp-meta">+ ${{neighbors.length - 15}} more</div>`;
    }}
    html += `</div>`;
  }}

  inspector.innerHTML = html;
  inspector.style.display = 'block';
}}

function closeInspector() {{
  document.getElementById('inspector').style.display = 'none';
  selectedNode = null;
  applySelection(null);
}}

function selectAndInspect(nodeId) {{
  selectedNode = nodeId;
  applySelection(nodeId);
  controls.autoRotate = false;
  inspectNode(nodeId);
}}

// Click to select + inspect
window.addEventListener('click', (e) => {{
  // Ignore clicks on the inspector panel
  if (e.target.closest('#inspector') || e.target.closest('#controls') || e.target.closest('#info') || e.target.closest('#legend')) return;

  raycaster.setFromCamera(mouse, camera);
  const intersects = raycaster.intersectObjects(spheres);
  if (intersects.length > 0) {{
    const n = intersects[0].object.userData;
    if (selectedNode === n.id) {{
      closeInspector();
    }} else {{
      selectedNode = n.id;
      applySelection(n.id);
      controls.autoRotate = false;
      inspectNode(n.id);
    }}
  }} else {{
    // Click on empty space — deselect
    closeInspector();
  }}
}});

function toggleEdges() {{ showEdges = !showEdges; edgeGroup.visible = showEdges; document.getElementById('edgeBtn').classList.toggle('active'); }}
function toggleContra() {{ showContra = !showContra; contraGroup.visible = showContra; document.getElementById('contraBtn').classList.toggle('active'); }}
function toggleRotate() {{ autoRotate = !autoRotate; controls.autoRotate = autoRotate; document.getElementById('rotBtn').classList.toggle('active'); }}

window.addEventListener('resize', () => {{
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}});

function animate() {{
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}}
animate();
</script>
</body>
</html>"""
    return html


def build_html(memories, coords, graph, contradictions):
    """Build an interactive 2D canvas visualization."""
    mem_ids = {m.memory_id for m in memories}
    id_to_idx = {m.memory_id: i for i, m in enumerate(memories)}

    # Build nodes
    nodes = []
    for i, m in enumerate(memories):
        nodes.append({
            "id": i,
            "mid": m.memory_id[:12],
            "x": float(coords[i, 0]) * 400 + 500,
            "y": float(coords[i, 1]) * 400 + 400,
            "trust": round(m.trust, 2),
            "kind": m.kind,
            "text": m.text[:120].replace('"', "'").replace("\n", " "),
            "contradiction_count": getattr(m, "contradiction_count", 0),
            "authority": getattr(m, "authority", "unknown"),
        })

    # Build edges from BDG (only between nodes in our filtered set)
    edges = []
    for src, tgt, edata in graph.edges(data=True):
        if src in id_to_idx and tgt in id_to_idx:
            edges.append({
                "source": id_to_idx[src],
                "target": id_to_idx[tgt],
                "type": edata.get("edge_type", "related_to"),
                "weight": round(float(edata.get("weight", 0.5)), 3),
            })

    # Build contradiction edges
    contra_edges = []
    for c in contradictions:
        if c.old_memory_id in id_to_idx and c.new_memory_id in id_to_idx:
            contra_edges.append({
                "source": id_to_idx[c.old_memory_id],
                "target": id_to_idx[c.new_memory_id],
                "slots": getattr(c, "affects_slots", "") or "",
                "summary": (getattr(c, "summary", "") or "")[:100],
            })

    print(f"Visualization: {len(nodes)} nodes, {len(edges)} edges, {len(contra_edges)} contradictions")

    # Color scheme
    kind_colors = {
        "user_fact": "#D4845C",
        "user_belief": "#C4A055",
        "preference": "#7CAD8A",
        "observation": "#635c50",
        "ops": "#5580AA",
        "narrative_note": "#8866AA",
    }

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>CRT Belief Graph — {len(nodes)} nodes, {len(edges)} edges</title>
<style>
  body {{ margin: 0; background: #141210; color: #F0EBE1; font-family: monospace; overflow: hidden; }}
  canvas {{ display: block; }}
  #info {{
    position: fixed; top: 12px; left: 12px; padding: 12px 16px;
    background: rgba(20,18,16,0.92); border: 1px solid rgba(240,235,225,0.1);
    border-radius: 6px; font-size: 12px; max-width: 300px; z-index: 10;
  }}
  #info h3 {{ margin: 0 0 8px 0; font-size: 14px; color: #D4845C; }}
  #tooltip {{
    position: fixed; display: none; padding: 10px 14px;
    background: rgba(26,23,20,0.95); border: 1px solid rgba(240,235,225,0.15);
    border-radius: 6px; font-size: 11px; max-width: 280px; z-index: 20;
    pointer-events: none;
  }}
  #tooltip .trust {{ color: #D4845C; }}
  #tooltip .kind {{ color: #a89d8a; }}
  #tooltip .text {{ color: #F0EBE1; margin-top: 4px; }}
  #legend {{
    position: fixed; bottom: 12px; left: 12px; padding: 10px 14px;
    background: rgba(20,18,16,0.92); border: 1px solid rgba(240,235,225,0.1);
    border-radius: 6px; font-size: 10px; z-index: 10;
  }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; margin: 3px 0; }}
  .legend-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
  #controls {{
    position: fixed; top: 12px; right: 12px; padding: 10px 14px;
    background: rgba(20,18,16,0.92); border: 1px solid rgba(240,235,225,0.1);
    border-radius: 6px; font-size: 11px; z-index: 10;
  }}
  button {{
    background: rgba(212,132,92,0.2); border: 1px solid rgba(212,132,92,0.3);
    color: #D4845C; padding: 4px 10px; border-radius: 4px; cursor: pointer;
    font-family: monospace; font-size: 10px; margin: 2px;
  }}
  button:hover {{ background: rgba(212,132,92,0.4); }}
  button.active {{ background: rgba(212,132,92,0.5); border-color: #D4845C; }}
</style>
</head>
<body>
<canvas id="c"></canvas>

<div id="info">
  <h3>CRT Belief Graph</h3>
  <div>{len(nodes)} memories | {len(edges)} edges | {len(contra_edges)} contradictions</div>
</div>

<div id="tooltip"></div>

<div id="legend">
  {"".join(f'<div class="legend-item"><div class="legend-dot" style="background:{c}"></div>{k}</div>' for k, c in kind_colors.items())}
  <div class="legend-item" style="margin-top:6px">
    <div style="width:20px;height:1px;background:rgba(212,132,92,0.3)"></div>related
  </div>
  <div class="legend-item">
    <div style="width:20px;height:1px;background:#D47058;border-top:1px dashed #D47058"></div>contradiction
  </div>
</div>

<div id="controls">
  <button onclick="toggleEdges()" id="edgeBtn" class="active">Edges</button>
  <button onclick="toggleContra()" id="contraBtn" class="active">Contradictions</button>
  <button onclick="toggleLabels()" id="labelBtn">Labels</button>
  <button onclick="resetView()">Reset</button>
</div>

<script>
const nodes = {json.dumps(nodes)};
const edges = {json.dumps(edges)};
const contraEdges = {json.dumps(contra_edges)};
const kindColors = {json.dumps(kind_colors)};

const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const tooltip = document.getElementById('tooltip');

let showEdges = true, showContra = true, showLabels = false;
let cam = {{ x: 0, y: 0, zoom: 1 }};
let drag = {{ active: false, lx: 0, ly: 0 }};
let hovered = null;

function resize() {{
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  draw();
}}
window.addEventListener('resize', resize);

function worldToScreen(wx, wy) {{
  return {{
    sx: canvas.width/2 + (wx - 500 + cam.x) * cam.zoom,
    sy: canvas.height/2 + (wy - 400 + cam.y) * cam.zoom,
  }};
}}

function draw() {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#141210';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Edges
  if (showEdges) {{
    ctx.globalAlpha = 0.06;
    ctx.strokeStyle = 'rgba(212,132,92,0.3)';
    ctx.lineWidth = 0.5;
    for (const e of edges) {{
      const a = worldToScreen(nodes[e.source].x, nodes[e.source].y);
      const b = worldToScreen(nodes[e.target].x, nodes[e.target].y);
      ctx.beginPath();
      ctx.moveTo(a.sx, a.sy);
      ctx.lineTo(b.sx, b.sy);
      ctx.stroke();
    }}
    ctx.globalAlpha = 1.0;
  }}

  // Contradiction edges
  if (showContra) {{
    ctx.strokeStyle = '#D47058';
    ctx.lineWidth = 1.5 * cam.zoom;
    ctx.setLineDash([4, 4]);
    ctx.globalAlpha = 0.7;
    for (const c of contraEdges) {{
      const a = worldToScreen(nodes[c.source].x, nodes[c.source].y);
      const b = worldToScreen(nodes[c.target].x, nodes[c.target].y);
      ctx.beginPath();
      ctx.moveTo(a.sx, a.sy);
      ctx.lineTo(b.sx, b.sy);
      ctx.stroke();
    }}
    ctx.setLineDash([]);
    ctx.globalAlpha = 1.0;
  }}

  // Nodes
  for (let i = 0; i < nodes.length; i++) {{
    const n = nodes[i];
    const s = worldToScreen(n.x, n.y);
    const r = (3 + n.trust * 8) * cam.zoom;
    const color = kindColors[n.kind] || '#635c50';

    // Glow for high trust
    if (n.trust > 0.7) {{
      ctx.globalAlpha = 0.15;
      ctx.beginPath();
      ctx.arc(s.sx, s.sy, r + 4 * cam.zoom, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }}

    // Contradiction ring
    if (n.contradiction_count > 0) {{
      ctx.globalAlpha = 0.4;
      ctx.strokeStyle = '#D47058';
      ctx.lineWidth = 1.5 * cam.zoom;
      ctx.beginPath();
      ctx.arc(s.sx, s.sy, r + 2 * cam.zoom, 0, Math.PI * 2);
      ctx.stroke();
    }}

    ctx.globalAlpha = hovered === i ? 1.0 : 0.85;
    ctx.beginPath();
    ctx.arc(s.sx, s.sy, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.globalAlpha = 1.0;

    // Labels
    if (showLabels && r * cam.zoom > 4) {{
      ctx.font = `${{Math.max(8, 10 * cam.zoom)}}px monospace`;
      ctx.fillStyle = 'rgba(240,235,225,0.5)';
      ctx.textAlign = 'left';
      ctx.fillText(n.text.substring(0, 30), s.sx + r + 3, s.sy + 3);
    }}
  }}

  // Hover highlight: show connected edges
  if (hovered !== null) {{
    const hn = nodes[hovered];
    const hs = worldToScreen(hn.x, hn.y);

    // Draw connected edges highlighted
    ctx.strokeStyle = '#D4845C';
    ctx.lineWidth = 1.5 * cam.zoom;
    ctx.globalAlpha = 0.4;
    for (const e of edges) {{
      if (e.source === hovered || e.target === hovered) {{
        const other = e.source === hovered ? e.target : e.source;
        const os = worldToScreen(nodes[other].x, nodes[other].y);
        ctx.beginPath();
        ctx.moveTo(hs.sx, hs.sy);
        ctx.lineTo(os.sx, os.sy);
        ctx.stroke();
      }}
    }}
    ctx.globalAlpha = 1.0;
  }}
}}

// Mouse interactions
canvas.addEventListener('mousemove', (e) => {{
  if (drag.active) {{
    cam.x += (e.clientX - drag.lx) / cam.zoom;
    cam.y += (e.clientY - drag.ly) / cam.zoom;
    drag.lx = e.clientX;
    drag.ly = e.clientY;
    draw();
    return;
  }}

  // Hit test
  let found = null;
  for (let i = nodes.length - 1; i >= 0; i--) {{
    const n = nodes[i];
    const s = worldToScreen(n.x, n.y);
    const r = (3 + n.trust * 8) * cam.zoom;
    const dx = e.clientX - s.sx, dy = e.clientY - s.sy;
    if (dx*dx + dy*dy < r*r + 100) {{
      found = i;
      break;
    }}
  }}

  if (found !== hovered) {{
    hovered = found;
    draw();
  }}

  if (found !== null) {{
    const n = nodes[found];
    tooltip.style.display = 'block';
    tooltip.style.left = (e.clientX + 15) + 'px';
    tooltip.style.top = (e.clientY + 15) + 'px';
    tooltip.innerHTML = `
      <span class="trust">T:${{n.trust}}</span>
      <span class="kind">${{n.kind}}</span>
      <span class="kind">${{n.authority}}</span>
      ${{n.contradiction_count > 0 ? '<span style="color:#D47058"> ' + n.contradiction_count + 'x contradicted</span>' : ''}}
      <div class="text">${{n.text}}</div>
      <div style="color:#635c50;margin-top:4px">${{n.mid}}</div>
    `;
  }} else {{
    tooltip.style.display = 'none';
  }}
}});

canvas.addEventListener('mousedown', (e) => {{
  drag.active = true;
  drag.lx = e.clientX;
  drag.ly = e.clientY;
}});
canvas.addEventListener('mouseup', () => {{ drag.active = false; }});
canvas.addEventListener('wheel', (e) => {{
  e.preventDefault();
  const factor = e.deltaY > 0 ? 0.9 : 1.1;
  cam.zoom *= factor;
  cam.zoom = Math.max(0.1, Math.min(10, cam.zoom));
  draw();
}});

function toggleEdges() {{ showEdges = !showEdges; document.getElementById('edgeBtn').classList.toggle('active'); draw(); }}
function toggleContra() {{ showContra = !showContra; document.getElementById('contraBtn').classList.toggle('active'); draw(); }}
function toggleLabels() {{ showLabels = !showLabels; document.getElementById('labelBtn').classList.toggle('active'); draw(); }}
function resetView() {{ cam = {{ x: 0, y: 0, zoom: 1 }}; draw(); }}

resize();
</script>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="CRT Belief Graph Visualization Lab")
    parser.add_argument("--db", default="personal_agent/crt_memory_shared.db")
    parser.add_argument("--ledger", default="personal_agent/crt_ledger_shared.db")
    parser.add_argument("--kind", nargs="*", default=None,
                        help="Filter by kind (user_fact, user_belief, preference, observation)")
    parser.add_argument("--min-trust", type=float, default=0.0)
    parser.add_argument("--max-nodes", type=int, default=500)
    parser.add_argument("--3d", dest="three_d", action="store_true", help="3D Three.js visualization")
    args = parser.parse_args()

    kinds = set(args.kind) if args.kind else None
    memories, graph, contradictions, ledger = load_data(
        args.db, args.ledger, kinds=kinds, min_trust=args.min_trust,
    )

    # Cap nodes for performance
    if len(memories) > args.max_nodes:
        # Keep highest trust + all user_facts
        user_facts = [m for m in memories if m.kind in ("user_fact", "user_belief", "preference")]
        others = [m for m in memories if m.kind not in ("user_fact", "user_belief", "preference")]
        others.sort(key=lambda m: m.trust, reverse=True)
        memories = user_facts + others[:args.max_nodes - len(user_facts)]
        print(f"Capped to {len(memories)} nodes ({len(user_facts)} user facts + {len(memories) - len(user_facts)} others)")

    dims = 3 if args.three_d else 2
    coords = pca_project(memories, dimensions=dims)
    if args.three_d:
        html = build_html_3d(memories, coords, graph, contradictions)
    else:
        html = build_html(memories, coords, graph, contradictions)

    out_path = OUTPUT_DIR / "belief_graph.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nSaved to: {out_path}")
    print("Open in browser to explore.")


if __name__ == "__main__":
    main()
