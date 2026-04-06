import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

type MapPoint = {
  entry_id: number; x: number; y: number; z?: number
  is_belief: boolean; trust_avg: number | null
  topic_id: number | null; topic_label: string | null
  query: string; response_preview: string; timestamp: number
}
type MapTopic = {
  topic_id: number; label: string
  centroid_x: number; centroid_y: number; centroid_z?: number
}
type MapData = {
  points: MapPoint[]
  contradictions: { entry_id_a: number; entry_id_b: number; ledger_id: string }[]
  topics: MapTopic[]
}

const COLORS = {
  bg: 0x141210,
  belief: 0xD4845C,
  speech: 0x635c50,
  contradiction: 0xD47058,
  grid: 0x1a1714,
  topicLabel: 0xa89d8a,
}

const SCALE = 3

export default function BeliefMap3DView({ data }: { data: MapData }) {
  const mountRef = useRef<HTMLDivElement>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount || !data) return

    const width = mount.clientWidth
    const height = mount.clientHeight

    // Scene
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(COLORS.bg)

    // Camera
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 100)
    camera.position.set(4, 3, 4)

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(window.devicePixelRatio)
    mount.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.autoRotate = true
    controls.autoRotateSpeed = 0.3
    controls.maxDistance = 12
    controls.minDistance = 2

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.4))
    const point1 = new THREE.PointLight(0xffffff, 0.8)
    point1.position.set(5, 5, 5)
    scene.add(point1)
    const point2 = new THREE.PointLight(COLORS.belief, 0.3)
    point2.position.set(-5, -3, -5)
    scene.add(point2)

    // Grid
    const grid = new THREE.GridHelper(6, 12, COLORS.grid, COLORS.grid)
    grid.position.y = -3
    scene.add(grid)

    // Points
    const pointGeom = new THREE.SphereGeometry(1, 12, 12)
    for (const p of data.points) {
      const trust = p.trust_avg ?? 0.5
      const size = 0.04 + trust * 0.12
      const color = p.is_belief ? COLORS.belief : COLORS.speech

      const mat = new THREE.MeshStandardMaterial({
        color,
        transparent: true,
        opacity: 0.5 + trust * 0.5,
        emissive: new THREE.Color(color),
        emissiveIntensity: 0.15,
      })
      const mesh = new THREE.Mesh(pointGeom, mat)
      mesh.scale.setScalar(size)
      mesh.position.set(p.x * SCALE, (p.z ?? 0) * SCALE, p.y * SCALE)
      scene.add(mesh)

      // Glow for high-trust beliefs
      if (p.is_belief && trust > 0.7) {
        const glowMat = new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: 0.1,
        })
        const glow = new THREE.Mesh(pointGeom, glowMat)
        glow.scale.setScalar(size * 2)
        glow.position.copy(mesh.position)
        scene.add(glow)
      }
    }

    // Contradiction edges
    const lineMat = new THREE.LineBasicMaterial({
      color: COLORS.contradiction,
      transparent: true,
      opacity: 0.4,
    })
    for (const c of data.contradictions) {
      const a = data.points.find(p => p.entry_id === c.entry_id_a)
      const b = data.points.find(p => p.entry_id === c.entry_id_b)
      if (!a || !b) continue
      const geom = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(a.x * SCALE, (a.z ?? 0) * SCALE, a.y * SCALE),
        new THREE.Vector3(b.x * SCALE, (b.z ?? 0) * SCALE, b.y * SCALE),
      ])
      scene.add(new THREE.Line(geom, lineMat))
    }

    // Topic centroid wireframes
    const wireGeom = new THREE.SphereGeometry(0.08, 8, 8)
    const wireMat = new THREE.MeshBasicMaterial({
      color: COLORS.topicLabel,
      wireframe: true,
      transparent: true,
      opacity: 0.4,
    })
    for (const t of data.topics) {
      const mesh = new THREE.Mesh(wireGeom, wireMat)
      mesh.position.set(t.centroid_x * SCALE, (t.centroid_z ?? 0) * SCALE, t.centroid_y * SCALE)
      scene.add(mesh)

      // Label using sprite
      const canvas = document.createElement('canvas')
      canvas.width = 256
      canvas.height = 64
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.fillStyle = '#a89d8a'
        ctx.font = '24px monospace'
        ctx.textAlign = 'center'
        ctx.fillText(t.label || `topic ${t.topic_id}`, 128, 40)
        const texture = new THREE.CanvasTexture(canvas)
        const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: 0.6 })
        const sprite = new THREE.Sprite(spriteMat)
        sprite.scale.set(1, 0.25, 1)
        sprite.position.set(t.centroid_x * SCALE, (t.centroid_z ?? 0) * SCALE + 0.25, t.centroid_y * SCALE)
        scene.add(sprite)
      }
    }

    // Animation loop
    let animId: number
    function animate() {
      animId = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    // Resize handler
    const onResize = () => {
      const w = mount.clientWidth
      const h = mount.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', onResize)
      controls.dispose()
      renderer.dispose()
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement)
      }
      rendererRef.current = null
    }
  }, [data])

  return (
    <div ref={mountRef} className="w-full h-full relative">
      {/* Legend */}
      <div className="absolute bottom-4 left-4 flex flex-col gap-1 text-[10px] font-mono" style={{ color: '#a89d8a' }}>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: '#D4845C' }} />
          <span>Belief</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: '#635c50' }} />
          <span>Speech</span>
        </div>
        <div className="mt-1" style={{ color: 'rgba(240,235,225,0.2)' }}>
          {data.points.length} points · {data.topics.length} topics · drag to orbit
        </div>
      </div>
    </div>
  )
}
