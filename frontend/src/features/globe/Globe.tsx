import { useEffect, useMemo, useRef, useState, Suspense, useCallback } from "react";
import { Canvas, useFrame, useThree, useLoader } from "@react-three/fiber";
import * as THREE from "three";
import { Html, OrbitControls } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three/examples/jsm/controls/OrbitControls.js";
import { useQuery } from "@tanstack/react-query";
import { Flag } from "lucide-react";
import { createRoot } from "react-dom/client";
import { api } from "@/api/client";

export interface Spot {
  id: number;
  target_id: string;
  name: string;
  name_en: string;
  region: string;
  country: string;
  lat: number;
  lon: number;
  image_url: string;
  view_count: number;
  journal_count?: number;
  comment_count?: number;
  visitor_count?: number;
  visited?: boolean;
}

declare global {
  interface Window {
    __tsDragging?: boolean;
    __tsDragMoved?: boolean;
    __tsCamDist?: number;
  }
}

/** 经纬度 -> 球面坐标 */
function latLonToVector3(lat: number, lon: number, radius = 1.02): THREE.Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((lon + 180) * Math.PI) / 180;
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

/* ================================================================== */
/* 事件桥（外部 <-> Canvas 内）                                        */
/* ================================================================== */
type FlyPayload = { lat: number; lon: number; id?: number; dist?: number };
const flyListeners = new Set<(p: FlyPayload) => void>();
const bearingListeners = new Set<(deg: number) => void>();
const resetViewListeners = new Set<() => void>();
/** 用户是否设定过方位（设定后本次会话停用自转，重置后恢复） */
let userSetBearing = false;
const bearingChangeHooks = new Set<(v: boolean) => void>();

export const globeBus = {
  /** 飞到地标（点搜索结果/消息卡片） */
  flyTo(lat: number, lon: number, id?: number, dist?: number) {
    flyListeners.forEach((fn) => fn({ lat, lon, id, dist }));
  },
  /** 设定方向角（0-360，真实旋转相机方位） */
  setBearing(deg: number) {
    userSetBearing = true;
    bearingChangeHooks.forEach((fn) => fn(true));
    bearingListeners.forEach((fn) => fn(deg));
  },
  /** 重置：只恢复方向角与缩放距离，不改变看向的地点 */
  resetView() {
    userSetBearing = false;
    bearingChangeHooks.forEach((fn) => fn(false));
    resetViewListeners.forEach((fn) => fn());
  },
  /** 当前是否处于用户设定方位状态（控件禁用自转用） */
  get hasUserBearing() {
    return userSetBearing;
  },
};

/* ================================================================== */
/* 相机距离探针                                                        */
/* ================================================================== */
function CameraDistanceProbe({ distRef }: { distRef: React.MutableRefObject<number> }) {
  const { camera } = useThree();
  useFrame(() => {
    const d = camera.position.length();
    distRef.current = d;
    window.__tsCamDist = d;
  });
  return null;
}

/* ================================================================== */
/* 背面隐藏：地球组静止（自转由相机方位角承担），方向恒定               */
/* ================================================================== */
function useBackfaceHide(markerCoords: { lat: number; lon: number }[]) {
  const { camera } = useThree();
  const dirs = useMemo(
    () => markerCoords.map((m) => latLonToVector3(m.lat, m.lon, 1).normalize()),
    [markerCoords]
  );
  useFrame(() => {
    const els = document.querySelectorAll<HTMLElement>("[data-marker-idx]");
    els.forEach((el) => {
      const idx = Number(el.dataset.markerIdx);
      const n = dirs[idx];
      if (!n) return;
      // 可见 ⟺ 标记法线与"球心->相机"方向同侧（正面半球）
      const camDir = camera.position.clone().normalize();
      el.style.visibility = camDir.dot(n) > 0.12 ? "visible" : "hidden";
    });
  });
}

/** 给 group 的每个子节点挂 Html 元素引用（供背面隐藏） */
function HtmlRefBinder({ el }: { el: HTMLElement }) {
  useEffect(() => {
    // 父 group 上标记，由 useBackfaceHide 读取
    const holder = (el as any).__tsHolder as THREE.Group | undefined;
    if (holder) (holder as any).__htmlEl = el;
  }, [el]);
  return null;
}

/* ================================================================== */
/* 点位徽章（DOM 徽章：散点=旗子圆 / 气泡=旗子+数字）                  */
/* ================================================================== */

/** 散点徽章：圆形白边内色突出，中间白旗，无数字（紧凑尺寸） */
function SpotBadge({
  spot,
  visited,
  highlighted,
  dimmed,
  onClick,
}: {
  spot: Spot;
  visited: boolean;
  highlighted: boolean;
  dimmed: boolean;
  onClick: (s: Spot) => void;
}) {
  return (
    <div className="group relative flex items-center justify-center" style={{ width: 22, height: 22 }}>
      <div className="absolute inset-0 rounded-full transition group-hover:bg-white/20" />
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (!window.__tsDragMoved) onClick(spot);
        }}
        title={spot.name}
        className="relative flex items-center justify-center rounded-full border shadow-md transition-transform group-hover:scale-125"
        style={{
          width: 14,
          height: 14,
          borderWidth: 1.5,
          borderColor: "rgba(255,255,255,0.95)",
          background: highlighted
            ? "linear-gradient(135deg,#ffb020,#ff8c00)"
            : visited
              ? "linear-gradient(135deg,#ffb020,#ff8c00)"
              : "linear-gradient(135deg,#3d8bd4,#2563a8)",
          opacity: dimmed ? 0.3 : 1,
          boxShadow: highlighted ? "0 0 0 3px rgba(255,200,80,0.35)" : undefined,
        }}
      >
        <Flag className="h-[9px] w-[9px] text-white" strokeWidth={2.5} />
      </button>
      <div className="pointer-events-none absolute bottom-full left-1/2 mb-1 -translate-x-1/2 whitespace-nowrap rounded-md bg-black/75 px-1.5 py-0.5 text-[10px] text-white opacity-0 transition group-hover:opacity-100">
        {spot.name}
      </div>
    </div>
  );
}

/** 聚合气泡徽章：圆角白边 + 左旗右数 */
function ClusterBadge({
  label,
  count,
  heat,
  onClick,
}: {
  label: string;
  count: number;
  heat: number; // 0-1，决定内色
  onClick: () => void;
}) {
  const bg =
    heat > 0.66
      ? "linear-gradient(135deg,#ff9a3c,#f2703d)"
      : heat > 0.33
        ? "linear-gradient(135deg,#57b0e8,#3d8bd4)"
        : "linear-gradient(135deg,#4a86c8,#3568a4)";
  return (
    <div className="group relative flex items-center" style={{ height: 24 }}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (!window.__tsDragMoved) onClick();
        }}
        title={`${label}（${count} 个地标）`}
        className="flex items-center gap-1 rounded-full border px-2 py-0.5 shadow-md transition-transform group-hover:scale-105"
        style={{ borderWidth: 1.5, borderColor: "rgba(255,255,255,0.95)", background: bg }}
      >
        <Flag className="h-[9px] w-[9px] text-white" strokeWidth={2.5} />
        <span className="text-[10px] font-bold text-white" style={{ textShadow: "0 1px 2px rgba(0,0,0,.4)" }}>
          {count}
        </span>
      </button>
      <div className="pointer-events-none absolute bottom-full left-1/2 mb-1 -translate-x-1/2 whitespace-nowrap rounded-md bg-black/75 px-1.5 py-0.5 text-[10px] text-white opacity-0 transition group-hover:opacity-100">
        {label}
      </div>
    </div>
  );
}

/* ================================================================== */
/* 区域聚簇：按 region 聚类，中心取区域地标质心（必在陆地侧）           */
/* ================================================================== */
interface Cluster {
  key: string;
  label: string;
  lat: number;
  lon: number;
  count: number;
  spots: Spot[];
  heat: number;
}

/** 区域锚点（保证气泡落在陆地而非海面；锚点即该区域地标的地理重心参照） */
const REGION_ANCHORS: Record<string, { lat: number; lon: number }> = {
  亚洲: { lat: 30, lon: 95 },
  欧洲: { lat: 46, lon: 12 },
  非洲: { lat: 22, lon: 28 },
  北美洲: { lat: 35, lon: -100 },
  南美洲: { lat: -12, lon: -60 },
  大洋洲: { lat: -25, lon: 140 },
};

function buildRegionClusters(spots: Spot[]): Cluster[] {
  const buckets = new Map<string, Spot[]>();
  for (const s of spots) {
    const region = s.region?.trim() || "其他";
    if (!buckets.has(region)) buckets.set(region, []);
    buckets.get(region)!.push(s);
  }
  const clusters: Cluster[] = [];
  for (const [region, list] of buckets) {
    const anchor = REGION_ANCHORS[region];
    // 质心；若有区域锚点则与锚点混合（0.5/0.5），确保落点贴陆地重心
    const avgLat = list.reduce((a, s) => a + s.lat, 0) / list.length;
    const avgLon = list.reduce((a, s) => a + s.lon, 0) / list.length;
    const lat = anchor ? anchor.lat * 0.5 + avgLat * 0.5 : avgLat;
    const lon = anchor ? anchor.lon * 0.5 + avgLon * 0.5 : avgLon;
    const visitors = list.reduce((a, s) => a + (s.visitor_count || 0), 0);
    clusters.push({
      key: region,
      label: region,
      lat,
      lon,
      count: list.length,
      spots: list,
      heat: Math.min(1, visitors / (list.length * 6)),
    });
  }
  return clusters;
}

/* ================================================================== */
/* 点位容器（group + Html；背面隐藏由 useBackfaceHide 处理）            */
/* ================================================================== */
function MarkerSlot({
  position,
  markerIndex,
  children,
}: {
  position: THREE.Vector3;
  markerIndex: number;
  children: React.ReactNode;
}) {
  return (
    <group position={position}>
      <Html center zIndexRange={[10, 0]}>
        <div data-marker-idx={markerIndex}>{children}</div>
      </Html>
    </group>
  );
}

/* ================================================================== */
/* 地球内容（Canvas 内）                                               */
/* ================================================================== */
function EarthContent({
  spots,
  highlightIds,
  flyTargetId,
  onSpotClick,
  onClusterClick,
}: {
  spots?: Spot[];
  highlightIds?: Set<number>;
  flyTargetId: number | null;
  onSpotClick: (s: Spot) => void;
  onClusterClick: (c: Cluster) => void;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const markersGroupRef = useRef<THREE.Group>(null);
  const idleRef = useRef(0);
  const camDistRef = useRef(2.6);
  // 缩放档位（React state，带滞回）：散点 <1.85 / 气泡 >2.05
  const [zoomedIn, setZoomedIn] = useState(false);
  const controls = useThree((s) => s.controls) as any;

  // 自转：转相机方位角（组静止，标记方向恒定；用户设定方位后停用）
  useFrame((state) => {
    if (window.__tsDragging) {
      idleRef.current = state.clock.elapsedTime;
    }
    const idle = state.clock.elapsedTime - idleRef.current > 3;
    if (controls && idle && !globeBus.hasUserBearing && !window.__tsDragging) {
      controls.setAzimuthalAngle?.((controls.getAzimuthalAngle?.() ?? 0) + state.clock.getDelta() * 0.05);
      controls.update?.();
    }

    const d = camDistRef.current;
    if (!zoomedIn && d < 1.85) setZoomedIn(true);
    else if (zoomedIn && d > 2.05) setZoomedIn(false);
  });

  const clusters = useMemo(() => buildRegionClusters(spots || []), [spots]);
  // 背面隐藏（组静止，方向恒定）
  const markerCoords = useMemo(
    () =>
      zoomedIn
        ? (spots || []).map((s) => ({ lat: s.lat, lon: s.lon }))
        : clusters.map((c) => ({ lat: c.lat, lon: c.lon })),
    [zoomedIn, spots, clusters]
  );
  useBackfaceHide(markerCoords);

  return (
    <>
      <CameraDistanceProbe distRef={camDistRef} />
      <group ref={groupRef}>
        <mesh>
          <sphereGeometry args={[1, 64, 64]} />
          <meshBasicMaterial color="#2c5a8f" />
        </mesh>
        <Suspense fallback={<EarthTextureFallback />}>
          <EarthTexture />
        </Suspense>
        <Atmosphere />
        {/* 点位层：远=区域气泡 / 近=散点徽章 */}
        <group ref={markersGroupRef}>
          {zoomedIn
            ? (spots || []).map((s, i) => (
                <MarkerSlot key={s.id} position={latLonToVector3(s.lat, s.lon, 1.02)} markerIndex={i}>
                  <SpotBadge
                    spot={s}
                    visited={!!s.visited}
                    highlighted={highlightIds?.has(s.id) || flyTargetId === s.id}
                    dimmed={!!highlightIds && highlightIds.size > 0 && !highlightIds.has(s.id)}
                    onClick={onSpotClick}
                  />
                </MarkerSlot>
              ))
            : clusters.map((c, i) => (
                <MarkerSlot key={c.key} position={latLonToVector3(c.lat, c.lon, 1.02)} markerIndex={i}>
                  <ClusterBadge
                    label={c.label}
                    count={c.count}
                    heat={c.heat}
                    onClick={() => onClusterClick(c)}
                  />
                </MarkerSlot>
              ))}
        </group>
      </group>
      <Stars />
    </>
  );
}

/* ================================================================== */
/* 贴图 / 大气 / 星空                                                  */
/* ================================================================== */
function EarthTextureFallback() {
  return (
    <mesh>
      <sphereGeometry args={[1.001, 64, 64]} />
      <meshBasicMaterial color="#3a6ea5" toneMapped={false} />
    </mesh>
  );
}

function EarthTexture() {
  const tex = useLoader(THREE.TextureLoader, "/earth.png");
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return (
    <mesh>
      <sphereGeometry args={[1.001, 64, 64]} />
      <meshBasicMaterial map={tex} toneMapped={false} />
    </mesh>
  );
}

function Atmosphere() {
  return (
    <mesh>
      <sphereGeometry args={[1.028, 64, 64]} />
      <meshBasicMaterial
        color="#6aa9ff"
        transparent
        opacity={0.12}
        side={THREE.BackSide}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  );
}

function Stars() {
  const ref = useRef<THREE.Points>(null);
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const n = 600;
    const arr = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const r = 1.6 + Math.random() * 3;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = r * Math.cos(phi);
    }
    g.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    return g;
  }, []);
  useFrame((_, d) => {
    if (ref.current) ref.current.rotation.y += d * 0.008;
  });
  return (
    <points ref={ref} geometry={geo}>
      <pointsMaterial
        color="#ffe9c4"
        size={0.009}
        transparent
        opacity={0.7}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

/* ================================================================== */
/* 相机控制（飞行 / 方向角 / 重置）                                    */
/* ================================================================== */
function CameraRig({
  flyTarget,
  onFlyDone,
}: {
  flyTarget: { lat: number; lon: number; dist?: number } | null;
  onFlyDone: () => void;
}) {
  const { camera } = useThree();
  const controls = useThree((s) => s.controls) as OrbitControlsImpl | null;

  // ---- 飞行动画 ----
  const anim = useRef<{ from: THREE.Vector3; to: THREE.Vector3; start: number } | null>(null);
  const lastTarget = useRef<string | null>(null);

  useEffect(() => {
    if (!flyTarget) return;
    const key = `${flyTarget.lat.toFixed(3)},${flyTarget.lon.toFixed(3)},${flyTarget.dist ?? 1.6}`;
    if (key === lastTarget.current) return;
    lastTarget.current = key;
    const dir = latLonToVector3(flyTarget.lat, flyTarget.lon, 1).normalize();
    anim.current = {
      from: camera.position.clone(),
      to: dir.multiplyScalar(flyTarget.dist ?? 1.6),
      start: performance.now(),
    };
  }, [flyTarget, camera]);

  // ---- 方向角设定（绕纬线：改 polar angle，南北向移动视点） ----
  useEffect(() => {
    const onBearing = (deg: number) => {
      const c = controls as any;
      if (c?.setPolarAngle) {
        // 0°=北极正上方，180°=南极；限制在 OrbitControls 极角安全区间
        const polar = THREE.MathUtils.clamp(
          THREE.MathUtils.degToRad(deg),
          c.minPolarAngle ?? 0.01,
          c.maxPolarAngle ?? Math.PI - 0.01
        );
        c.setPolarAngle(polar);
        c.update();
      }
    };
    bearingListeners.add(onBearing);
    return () => {
      bearingListeners.delete(onBearing);
    };
  }, [controls]);

  // ---- 重置：方向角(极角)归零 + 距离恢复默认（不改变看向经度） ----
  useEffect(() => {
    const onReset = () => {
      const c = controls as any;
      if (c?.setPolarAngle) {
        c.setPolarAngle(THREE.MathUtils.degToRad(80));
        c.update();
      }
      // 只改半径：沿当前视线方向把距离拉回默认
      const dir = camera.position.clone().normalize();
      camera.position.copy(dir.multiplyScalar(2.6));
      c?.update();
    };
    resetViewListeners.add(onReset);
    return () => {
      resetViewListeners.delete(onReset);
    };
  }, [controls, camera]);

  useFrame(() => {
    const a = anim.current;
    if (!a) return;
    const t = Math.min(1, (performance.now() - a.start) / 1100);
    const eased = 1 - Math.pow(1 - t, 3);
    const fromDir = a.from.clone().normalize();
    const toDir = a.to.clone().normalize();
    const dir = fromDir.lerp(toDir, eased).normalize();
    const radius = THREE.MathUtils.lerp(a.from.length(), a.to.length(), eased);
    camera.position.copy(dir.multiplyScalar(radius));
    controls?.update?.();
    if (t >= 1) {
      anim.current = null;
      onFlyDone();
    }
  });
  return null;
}

/* ================================================================== */
/* 对外组件                                                            */
/* ================================================================== */
export function useSpotList() {
  return useQuery({
    queryKey: ["landmarks", "spots"],
    queryFn: async () => (await api.get("/landmarks/spots")).data.data as Spot[],
    staleTime: 60_000,
  });
}

const Globe = ({
  onSpotClick,
  highlightIds,
}: {
  onSpotClick: (s: Spot) => void;
  highlightIds?: Set<number>;
}) => {
  const { data: spots } = useSpotList();
  const [flying, setFlying] = useState<{ lat: number; lon: number; dist?: number } | null>(null);
  const [flyTargetId, setFlyTargetId] = useState<number | null>(null);

  useEffect(() => {
    const onFly = (p: FlyPayload) => {
      setFlying({ lat: p.lat, lon: p.lon });
      setFlyTargetId(p.id ?? null);
    };
    flyListeners.add(onFly);
    return () => {
      flyListeners.delete(onFly);
    };
  }, []);

  // 拖拽与点击分离：只有按住(button>0)移动才算拖动，纯悬停不影响
  const downPos = useRef<{ x: number; y: number } | null>(null);
  const onPointerDown = useCallback((e: React.PointerEvent) => {
    downPos.current = { x: e.clientX, y: e.clientY };
    window.__tsDragMoved = false;
  }, []);
  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (e.buttons === 0) {
      // 未按住：不算拖动（避免鼠标移向资料卡时误收起）
      window.__tsDragging = false;
      return;
    }
    window.__tsDragging = true;
    if (downPos.current) {
      const dx = e.clientX - downPos.current.x;
      const dy = e.clientY - downPos.current.y;
      if (Math.hypot(dx, dy) > 6) window.__tsDragMoved = true;
    }
  }, []);
  const onPointerUp = useCallback(() => {
    window.__tsDragging = false;
    setTimeout(() => (window.__tsDragMoved = false), 80);
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="globe-bg pointer-events-none absolute inset-0" />
      <Canvas
        camera={{ position: [0, 0.6, 2.6], fov: 42 }}
        dpr={[1, 1.75]}
        gl={{ antialias: true, alpha: true }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.7} />
        <directionalLight position={[10, 20, 10]} intensity={1.8} />
        {/* 不套外层 Suspense：贴图在内层自兜底，避免整树挂起时标记一起消失 */}
        <EarthContent
          spots={spots}
          highlightIds={highlightIds}
          flyTargetId={flyTargetId}
          onSpotClick={onSpotClick}
          onClusterClick={(c) => {
            // 点气泡：飞近到散点档位以内（<1.85），确保稳定散开
            setFlying({ lat: c.lat, lon: c.lon, dist: 1.65 });
          }}
        />
        <CameraRig flyTarget={flying} onFlyDone={() => setFlying(null)} />
        <OrbitControls
          enableDamping
          dampingFactor={0.08}
          enablePan={false}
          minDistance={1.18}
          maxDistance={3.6}
          rotateSpeed={0.55}
          zoomSpeed={0.8}
          makeDefault
        />
      </Canvas>
    </div>
  );
};

export default Globe;
