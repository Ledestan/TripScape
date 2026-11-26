"""
行旅识景 TripScape / 启动图生成
创建日期: 2026-11-26

用自有数据重绘启动页的两张背景图，替换掉原先的 Google Earth 素材，完成:
    1. stars.jpg      —— 按 HYG 星表的真实星位/星等/色指数做小视场投影渲染
    2. earth-arc.jpg  —— 从仓库内地球贴图按球面正交投影渲染地平线弧与大气

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        numpy
        Pillow
    外部数据（仅生成时需要，产物已入库）:
        HYG 星表 CSV：https://github.com/astronexus/HYG-Database（CC BY-SA 4.0）
        地球贴图：frontend/public/earth.webp

用法（在项目根目录执行）:
    python scripts/make_boot_art.py --catalog D:/tmp/hyg_v41.csv
    python scripts/make_boot_art.py --catalog ... --only stars
    python scripts/make_boot_art.py --catalog ... --only arc

注意:
    1. 只生成两张背景图，不改业务代码；覆盖 frontend/public/ 下同名文件即生效。
    2. 星位、星等、颜色全部来自星表，不做随机撒点；同一份星表生成结果确定。
    3. 星野用透视（小视场）投影而不是等距圆柱：赤道仪照片就是这个视角，
       也避免极区被拉伸成条纹。
    4. 星表只用于生成阶段，不随仓库分发；产物是渲染图，可自由使用并注明数据来源。
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "frontend" / "public"

# B-V 色指数 → RGB 的分段映射，区间取自常见恒星色温表
COLOR_STOPS = [
    (-0.30, (0.62, 0.72, 1.00)),  # O/B 蓝白
    (0.00, (0.78, 0.85, 1.00)),
    (0.30, (0.93, 0.95, 1.00)),
    (0.58, (1.00, 0.97, 0.93)),  # 太阳型
    (0.90, (1.00, 0.92, 0.82)),
    (1.30, (1.00, 0.83, 0.66)),
    (2.00, (1.00, 0.70, 0.52)),  # M 红
]

# 星野取景：视场 46°（竖向），对应 16:9 约 74° 横向，接近 35mm 相机 50mm 镜头
FIELD_FOV_Y = math.radians(46.0)
LIMITING_MAG = 10.2


# ----------------------------------------------------------------------
# 数据
# ----------------------------------------------------------------------
def load_catalog(path: Path) -> dict:
    """读取 HYG 星表，只保留绘图需要的四列并换算成单位向量。

    参数：
        path : Path，hyg_v41.csv 等星表文件

    返回：
        dict，含 ra_h（小时）、dec（度）、mag、ci、vec（形状 N×3 的单位向量）
    """
    import csv

    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                ra = float(row["ra"])
                dec = float(row["dec"])
                mag = float(row["mag"])
            except (TypeError, ValueError, KeyError):
                continue
            if abs(ra) < 1e-9 and abs(dec) < 1e-9:
                continue  # 太阳自身不该出现在星野里
            if mag > LIMITING_MAG:
                continue  # 更暗的星对背景没有贡献，只会拖慢渲染
            try:
                ci = float(row.get("ci") or 0.58)
            except ValueError:
                ci = 0.58
            rows.append((ra, dec, mag, ci))

    data = np.array(rows, dtype=np.float64)
    ra_rad = np.radians(data[:, 0] * 15.0)
    dec_rad = np.radians(data[:, 1])
    vec = np.stack(
        [
            np.cos(dec_rad) * np.cos(ra_rad),
            np.cos(dec_rad) * np.sin(ra_rad),
            np.sin(dec_rad),
        ],
        axis=1,
    )
    return {
        "ra_h": data[:, 0],
        "dec": data[:, 1],
        "mag": data[:, 2],
        "ci": data[:, 3],
        "vec": vec,
    }


def color_for(ci: np.ndarray) -> np.ndarray:
    """按 B-V 色指数插值出 RGB（0–1），整体降饱和以避免塑料感。"""
    stops = np.array([stop for stop, _ in COLOR_STOPS], dtype=np.float32)
    palette = np.array([rgb for _, rgb in COLOR_STOPS], dtype=np.float32)
    out = np.empty((len(ci), 3), dtype=np.float32)
    for channel in range(3):
        out[:, channel] = np.interp(ci, stops, palette[:, channel])
    gray = out.mean(axis=1, keepdims=True)
    return out * 0.6 + gray * 0.4


# ----------------------------------------------------------------------
# 星野：小视场投影
# ----------------------------------------------------------------------
def camera_basis(ra_h: float, dec_deg: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """给出以某赤经赤纬为中心的相机三轴（forward / right / up）。"""
    ra = math.radians(ra_h * 15.0)
    dec = math.radians(dec_deg)
    forward = np.array(
        [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]
    )
    right = np.array([-math.sin(ra), math.cos(ra), 0.0])
    up = np.cross(forward, right)
    return forward, right, up


def project(
    stars: dict, ra_h: float, dec_deg: float, width: int, height: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """把恒星投影到画布像素坐标。

    参数：
        stars    : dict，星表数据（含 vec）
        ra_h     : float，视场中心赤经（小时）
        dec_deg  : float，视场中心赤纬（度）
        width    : int，画布宽
        height   : int，画布高

    返回：
        tuple，像素 x、像素 y、是否落在画布内的布尔数组
    """
    forward, right, up = camera_basis(ra_h, dec_deg)
    vec = stars["vec"]

    denom = vec @ forward
    tan_y = math.tan(FIELD_FOV_Y / 2)
    tan_x = tan_y * (width / height)

    with np.errstate(divide="ignore", invalid="ignore"):
        sx = (vec @ right) / denom
        sy = (vec @ up) / denom

    inside = (
        (denom > 0) & (np.abs(sx) <= tan_x) & (np.abs(sy) <= tan_y)
    )
    px = (sx / tan_x + 1.0) * 0.5 * width
    py = (1.0 - sy / tan_y) * 0.5 * height
    return px, py, inside


def score_field(stars: dict, ra_h: float, dec_deg: float, width: int, height: int) -> float:
    """给候选视场打分：星点密度适中、中央不要有亮星抢标题。"""
    px, py, inside = project(stars, ra_h, dec_deg, width, height)
    mag = stars["mag"]
    count = int(np.count_nonzero(inside & (mag < 7.0)))
    if count < 500:
        return 1e6

    # 画面中央 40%×40% 区域内，亮于 3 等的星会被标题压住，尽量避开
    cx0, cx1 = width * 0.3, width * 0.7
    cy0, cy1 = height * 0.3, height * 0.7
    central_bright = int(
        np.count_nonzero(
            inside
            & (mag < 3.0)
            & (px > cx0)
            & (px < cx1)
            & (py > cy0)
            & (py < cy1)
        )
    )
    density_penalty = abs(count - 2600) / 2600.0
    return density_penalty + central_bright * 0.9


def pick_field(stars: dict, width: int, height: int) -> tuple[float, float]:
    """在赤道附近扫一遍候选视场，取评分最好的中心。

    只在 |dec| ≤ 55° 内选：极区星流稀疏，且投影拉伸明显。
    """
    best = (1e9, 6.0, 0.0)
    for ra_h in np.arange(0.0, 24.0, 0.75):
        for dec in np.arange(-55.0, 55.1, 5.0):
            score = score_field(stars, float(ra_h), float(dec), width, height)
            if score < best[0]:
                best = (score, float(ra_h), float(dec))
    return best[1], best[2]


def render_field(
    stars: dict, ra_h: float, dec_deg: float, width: int, height: int
) -> np.ndarray:
    """渲染一帧星野（浮点 RGB，未调色）。

    亮星画高斯光斑、暗星累加到像素上：真实照片里星点从不只有一个像素。
    """
    canvas = np.zeros((height, width, 3), dtype=np.float32)
    px, py, inside = project(stars, ra_h, dec_deg, width, height)

    mag = stars["mag"]
    energy = np.clip(10.0 ** (-0.4 * (mag - 7.4)), 0.006, 2.4).astype(np.float32)
    rgb = color_for(np.clip(stars["ci"], -0.3, 2.0))

    # 暗星：单像素累加，之后统一做轻微模糊
    faint = inside & (mag >= 5.0)
    xi = np.clip(px[faint].astype(np.int32), 0, width - 1)
    yi = np.clip(py[faint].astype(np.int32), 0, height - 1)
    np.add.at(canvas, (yi, xi), rgb[faint] * energy[faint][:, None])

    # 亮星：高斯光斑，亮度越高光斑越大
    bright = inside & (mag < 5.0)
    for x, y, e, c, m in zip(
        px[bright], py[bright], energy[bright], rgb[bright], mag[bright]
    ):
        sigma = float(np.clip(2.2 - 0.16 * (7.0 - m), 0.9, 3.0))
        radius = int(math.ceil(sigma * 3))
        x0, x1 = max(int(x) - radius, 0), min(int(x) + radius + 1, width)
        y0, y1 = max(int(y) - radius, 0), min(int(y) + radius + 1, height)
        if x0 >= x1 or y0 >= y1:
            continue
        gx = np.arange(x0, x1) - x
        gy = np.arange(y0, y1) - y
        patch = np.exp(-(gx[None, :] ** 2 + gy[:, None] ** 2) / (2 * sigma**2))
        canvas[y0:y1, x0:x1] += (
            patch[:, :, None] * c[None, None, :] * (e * 0.5)
        ).astype(np.float32)

    noise = np.random.default_rng(20261126).normal(0.0, 0.0032, (height, width, 1))
    return np.clip(canvas + noise, 0.0, 1.0)


def grade_and_save(sky: np.ndarray, out_path: Path) -> None:
    """调色（压暗、偏冷、轻噪）并保存 JPEG。"""
    image = Image.fromarray((np.clip(sky, 0, 1) * 255).astype(np.uint8))
    image = image.filter(ImageFilter.GaussianBlur(0.45))
    data = np.asarray(image, dtype=np.float32) / 255.0

    data *= np.array([0.90, 0.96, 1.06], dtype=np.float32)
    data = np.clip(data, 0.0, 1.0) ** 1.12
    data *= 1.28
    data = np.clip(data, 0.0, 1.0)

    grain = np.random.default_rng(7).normal(0.0, 0.0038, data.shape[:2])[:, :, None]
    data = np.clip(data + grain, 0.0, 1.0)

    Image.fromarray((data * 255).astype(np.uint8)).save(
        out_path, "JPEG", quality=84, optimize=True, progressive=True
    )


def make_stars(catalog: Path, out_path: Path) -> None:
    """生成星野背景：选视场 → 投影渲染 → 调色输出。"""
    print(f"[1/3] 读取星表 {catalog.name} …")
    stars = load_catalog(catalog)
    print(f"      星数（≤{LIMITING_MAG:g} 等）：{len(stars['mag'])}")

    width, height = 3840, 2160
    print(f"[2/3] 选择视场 …")
    ra_h, dec = pick_field(stars, width, height)
    print(f"      中心 RA={ra_h:.2f}h Dec={dec:+.1f}°（视场 {math.degrees(FIELD_FOV_Y):.0f}°）")

    print(f"[3/3] 渲染 {width}×{height} …")
    sky = render_field(stars, ra_h, dec, width, height)
    grade_and_save(sky, out_path)
    print(f"      已写出 {out_path}（{out_path.stat().st_size / 1024:.0f} KB）")


# ----------------------------------------------------------------------
# 地球弧：球面正交投影
# ----------------------------------------------------------------------
def sample_earth(texture: np.ndarray, dx, dy, nz, lon_offset: float, lat_offset: float):
    """把正交投影的球面坐标映射到等距圆柱贴图并取色。"""
    height, width = texture.shape[:2]
    lat = np.arcsin(np.clip(dy, -1.0, 1.0)) + lat_offset
    lon = np.arctan2(dx, np.maximum(nz, 1e-6)) + lon_offset
    u = ((lon / (2 * math.pi) + 0.5) % 1.0 * (width - 1)).astype(np.int32)
    v = np.clip((0.5 - lat / math.pi) * (height - 1), 0, height - 1).astype(np.int32)
    return texture[v, u]


def make_arc(
    earth_path: Path, out_path: Path, width: int = 2560, height: int = 800
) -> None:
    """渲染地球地平线：球面正交投影 + 边缘大气，输出带黑底的 JPEG。

    参数：
        earth_path : Path，等距圆柱地球贴图
        out_path   : Path，输出文件
        width      : int，输出宽
        height     : int，输出高
    """
    texture = np.asarray(Image.open(earth_path).convert("RGB"), dtype=np.float32) / 255.0
    print(f"[1/2] 地球贴图 {texture.shape[1]}×{texture.shape[0]}，渲染 {width}×{height} …")

    # 用一个极大的球半径换取平缓的地平线弧度
    radius_px = 2.6 * width
    cx = width / 2.0
    # 地平线放在画面 70% 高度：CSS 用 background-size:100% auto 会裁掉顶部，
    # 这个位置在 16:9、超宽、笔记本、手机四种取景下都落在可见带里
    cy = height * 0.70 + radius_px

    xs = np.arange(width) + 0.5
    ys = np.arange(height) + 0.5
    dx, dy = np.meshgrid((xs - cx) / radius_px, (ys - cy) / radius_px)
    r2 = dx * dx + dy * dy
    inside = r2 <= 1.0
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))

    # 挑一对经纬偏移：可见区域里海陆都有，不要整屏是海
    best = (1e9, 0.0, 0.0)
    for lat_offset in np.radians([-20.0, -5.0, 10.0, 25.0]):
        for lon_offset in np.linspace(-math.pi, math.pi, 24, endpoint=False):
            probe = sample_earth(
                texture, dx[inside], dy[inside], nz[inside], float(lon_offset), float(lat_offset)
            )
            if probe.size == 0:
                continue
            land = np.clip(probe[:, 1] - probe[:, 0] * 0.5 - probe[:, 2] * 0.5, 0.0, 1.0)
            score = abs(float(land.mean()) - 0.30)
            if score < best[0]:
                best = (score, float(lon_offset), float(lat_offset))

    _, lon_offset, lat_offset = best
    color = sample_earth(texture, dx, dy, nz, lon_offset, lat_offset)

    normals = np.stack([dx, dy, nz], axis=-1)
    sun = np.array([-0.32, 0.52, 0.79], dtype=np.float32)
    sun /= np.linalg.norm(sun)
    diffuse = np.clip((normals * sun).sum(axis=-1), 0.0, 1.0)

    # 正交投影下 nz 就是入射角余弦：越小越贴边缘，用来做临边昏暗
    limb = 0.20 + 0.80 * np.power(np.clip(nz, 0.0, 1.0), 0.45)
    surface = color * ((0.07 + 1.02 * diffuse) * limb)[:, :, None]

    atmosphere = np.array([0.40, 0.60, 1.00], dtype=np.float32)
    # 夜侧补一点"气辉"：完全不反光的黑半球在片头里会像一块缺口
    surface += atmosphere * (0.055 * np.power(np.clip(nz, 0.0, 1.0), 0.6))[:, :, None]
    # 贴边的一圈亮大气（内侧）
    surface += atmosphere * (np.exp(-nz / 0.055) * 1.15)[:, :, None]

    image = np.empty((height, width, 3), dtype=np.float32)
    image[:] = np.array([0.004, 0.006, 0.011], dtype=np.float32)
    image = np.where(inside[:, :, None], surface, image)

    outside = ~inside
    if outside.any():
        altitude_px = (np.sqrt(r2[outside]) - 1.0) * radius_px
        glow = np.exp(-np.clip(altitude_px, 0.0, None) / 7.0) * 0.75 + np.exp(
            -np.clip(altitude_px, 0.0, None) / 42.0
        ) * 0.22
        image[outside] += atmosphere[None, :] * glow[:, None]

    frame = Image.fromarray((np.clip(image, 0, 1) * 255).astype(np.uint8))
    frame = frame.filter(ImageFilter.GaussianBlur(0.45))
    frame.save(out_path, "JPEG", quality=88, optimize=True, progressive=True)
    print(
        f"      已写出 {out_path}（{out_path.stat().st_size / 1024:.0f} KB，"
        f"经度偏移 {lon_offset:.2f}，纬度偏移 {math.degrees(lat_offset):.0f}°）"
    )


def main() -> None:
    """命令行入口：默认生成两张图。"""
    parser = argparse.ArgumentParser(description="生成启动页星野与地球弧")
    parser.add_argument("--catalog", type=Path, help="HYG 星表 CSV 路径（生成星野需要）")
    parser.add_argument("--earth", type=Path, default=PUBLIC / "earth.webp", help="地球贴图路径")
    parser.add_argument("--out", type=Path, default=PUBLIC, help="输出目录，默认 frontend/public")
    parser.add_argument(
        "--only", choices=("stars", "arc"), help="只生成其中一张（另一张需已有数据）"
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    if args.only in (None, "stars"):
        if not args.catalog or not args.catalog.exists():
            raise SystemExit("生成星野需要 --catalog 指向 HYG 星表 CSV")
        make_stars(args.catalog, args.out / "stars.jpg")

    if args.only in (None, "arc"):
        if not args.earth.exists():
            raise SystemExit(f"找不到地球贴图：{args.earth}")
        make_arc(args.earth, args.out / "earth-arc.jpg")


if __name__ == "__main__":
    main()
