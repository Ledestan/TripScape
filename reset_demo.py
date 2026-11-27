"""
行旅识景 TripScape / reset_demo

项目展示状态：在初始状态之上铺一层可直接演示的内容，完成:
    1. 先执行 reset_project 的完整重置（清产物 + 重建库 + 索引 + 前端）
    2. 创建 3 个演示账号（demo / linwan / zhouyu）
    3. 生成 10 篇手账：9 篇已发布（含画布）、1 篇草稿、1 篇私密，覆盖不同地标
    4. 生成评论与回复（含"回复的回复"）、点赞、收藏、分享链接与站内通知
    5. 触发足迹聚合与徽章发放，让个人主页、看板、徽章页都有内容

依赖:
    需求文件: requirements.txt
    依赖库:
        Django>=5.2
    运行前提:
        与 reset_project.py 相同（.env 可用、frontend/node_modules 已安装）

用法（项目根目录执行）:
    python reset_demo.py --yes
    python reset_demo.py --yes --no-frontend    # 只重置数据与演示内容，不重建前端

输出:
    各阶段横幅与耗时；结束打印账号、手账数、评论数、点赞数与分享链接

注意:
    1. 本脚本会先删库再播种，执行前确认不需要保留现有数据。
    2. 演示图片使用 frontend/public/landmarks 下已有的地标图，不额外占空间。
    3. 种子账号密码为演示用途；正式展示前请按需要修改。
"""

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
DEMO_PASSWORD = "tripscape-demo"

# 复用地标 / 徽章 / 内容素材（与 reset_project 的初始化口径保持一致）
sys.path.insert(0, str(ROOT))
import reset_project as base  # noqa: E402

PHOTOS = {
    "EiffelTower": "/landmarks/EiffelTower.jpg",
    "GizaPyramids": "/landmarks/GizaPyramids.jpg",
    "MachuPicchu": "/landmarks/MachuPicchu.jpg",
    "TajMahal": "/landmarks/TajMahal.jpg",
    "GreatWall": "/landmarks/GreatWall.jpg",
    "Petra": "/landmarks/Petra.jpg",
    "LibertyStatue": "/landmarks/LibertyStatue.jpg",
    "RomanColosseum": "/landmarks/RomanColosseum.jpg",
    "Potala": "/landmarks/Potala.jpg",
    "Qomolangma": "/landmarks/Qomolangma.jpg",
}


def setup_django() -> None:
    """在重置子进程结束后，用同一套设置在本进程里操作 ORM。"""
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_DEPLOY", "dev")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    import django

    django.setup()


def build_canvas(photo: str, title: str, note: str, accent: str, variant: str) -> dict:
    """3:4 画布：一张照片 + 标题 + 备注 + 贴纸 + 纸胶带，服务端归一化保证结构合法。"""
    from services.journal_canvas import normalize_canvas

    return normalize_canvas(
        {
            "background": "#12161d",
            "elements": [
                {
                    "type": "photo",
                    "src": photo,
                    "x": 36,
                    "y": 56,
                    "width": 648,
                    "height": 432,
                    "rotation": -1.5,
                    "cornerRadius": 10,
                    "shadow": True,
                    "borderWidth": 6,
                    "borderColor": "#f6f1e7",
                    "z": 0,
                },
                {
                    "type": "text",
                    "text": title,
                    "x": 48,
                    "y": 516,
                    "width": 620,
                    "height": 88,
                    "fontSize": 40,
                    "color": "#f3ece1",
                    "align": "left",
                    "z": 1,
                },
                {
                    "type": "text",
                    "text": note,
                    "x": 48,
                    "y": 610,
                    "width": 620,
                    "height": 190,
                    "fontSize": 22,
                    "color": "#c9bfae",
                    "align": "left",
                    "z": 2,
                },
                {
                    "type": "sticker",
                    "variant": variant,
                    "color": accent,
                    "x": 596,
                    "y": 70,
                    "width": 66,
                    "height": 66,
                    "rotation": 12,
                    "z": 3,
                },
                {
                    "type": "tape",
                    "color": "#d6ba84",
                    "pattern": "stripe",
                    "x": 280,
                    "y": 22,
                    "width": 160,
                    "height": 42,
                    "rotation": -3,
                    "z": 4,
                },
            ],
        }
    )


def seed_demo() -> dict[str, int]:
    """写入演示账号与内容；全部走服务层，保证足迹、徽章、通知行为与真实使用一致。"""
    from apps.accounts.models import User
    from apps.comments.models import Comment
    from apps.comments.models_like import Like
    from apps.journals.models import Journal
    from apps.landmarks.models import Landmark
    from services import (
        badge_service,
        comment_service,
        journal_service,
        notification_service,
        share_service,
    )

    def make_user(username: str, nickname: str, bio: str) -> User:
        user = User.objects.filter(username=username).first()
        if user:
            return user
        user = User.objects.create_user(
            username=username, password=DEMO_PASSWORD, nickname=nickname, bio=bio
        )
        return user

    demo = make_user("demo", "演示用户", "把走过的路收进手账。")
    linwan = make_user("linwan", "林晚", "在黄昏里找机位。")
    zhouyu = make_user("zhouyu", "周屿", "一年去一次高原。")

    def landmark(target_id: str) -> Landmark:
        item = Landmark.objects.filter(target_id=target_id).first()
        if not item:
            raise SystemExit(f"缺少地标种子: {target_id}")
        return item

    def journal(user: User, target_id: str, title: str, note: str, visited: date,
                accent: str, variant: str, is_public: bool = True,
                is_draft: bool = False) -> Journal:
        lm = landmark(target_id)
        ok, result = journal_service.create_journal(
            user=user,
            landmark_id=lm.id,
            title=title,
            content=note,
            images=[PHOTOS[target_id]],
            visited_at=visited,
            is_public=is_public,
            canvas=build_canvas(PHOTOS[target_id], title, note, accent, variant),
            is_draft=is_draft,
        )
        if not ok:
            raise SystemExit(f"手账创建失败: {result}")
        return result

    # 1. 已经发布的手账：覆盖不同地区、不同作者，保证地球上的足迹分布自然
    published = [
        journal(demo, "EiffelTower", "在巴黎的第七区醒来",
                "清晨六点的战神广场几乎没有游客，铁塔的影子刚好落在草坪上。",
                date(2026, 4, 12), "#d9a441", "star"),
        journal(demo, "MachuPicchu", "云雾散开的那十五分钟",
                "上山时整片山谷都是白的，等到十点，雾突然退开，石墙一层层露出来。",
                date(2026, 3, 2), "#3d7a68", "pin"),
        journal(demo, "TajMahal", "白色大理石上的晨光",
                "从西门进去，先看到的是倒影池，泰姬陵在水里比在天上更安静。",
                date(2026, 2, 18), "#c05a4a", "heart"),
        journal(demo, "GizaPyramids", "金字塔：私人记录",
                "骑骆驼绕了一圈，最深的印象不是高，而是石块之间的缝隙几乎插不进刀片。",
                date(2025, 12, 30), "#d9a441", "burst"),
        journal(linwan, "Petra", "玫瑰色的峡谷",
                "穿过蛇道时两侧岩壁有一人多高，尽头卡兹尼神殿只露出一条金色的缝。",
                date(2026, 4, 25), "#c05a4a", "heart"),
        journal(linwan, "LibertyStatue", "自由女神的背面",
                "从斯塔滕岛渡轮回望，她在逆光里只剩轮廓，比正面更像一座灯塔。",
                date(2026, 1, 9), "#8fa6ad", "circle"),
        journal(zhouyu, "RomanColosseum", "斗兽场的黄昏",
                "闭馆前四十分钟，拱门里的光变成橘色，游客散得只剩脚步声。",
                date(2026, 5, 6), "#d9a441", "star"),
        journal(zhouyu, "Potala", "布达拉宫的第一场雪",
                "雪落在红宫的墙面上不化，远远看像有人给宫殿描了一道白边。",
                date(2026, 1, 21), "#3d7a68", "pin"),
        journal(zhouyu, "Qomolangma", "珠峰大本营的星空",
                "夜里零下十几度，银河从山脊后面升起来，曝光三十秒才勉强拍到。",
                date(2026, 6, 11), "#5b6b3d", "burst"),
    ]

    # 2. 草稿与私密：让"我的手账"能看出状态差异
    journal(demo, "GreatWall", "长城：还没写完的一页",
            "风很大，照片先放上来，文字周末补。",
            date(2026, 6, 20), "#8a6d3b", "star", is_draft=True)

    private = journal(demo, "GizaPyramids", "只给自己看的一张",
                      "这次没有发朋友圈，留个私密记录。",
                      date(2025, 11, 6), "#6b4a6a", "heart", is_public=False)

    # 3. 评论：手账评论 + 地标评论 + 回复 + 回复的回复（两级平铺）
    def comment(user: User, content: str, journal_id=None, landmark_id=None,
                parent_id=None):
        ok, result = comment_service.create_comment(
            user=user,
            landmark_id=landmark_id,
            journal_id=journal_id,
            content=content,
            parent_id=parent_id,
        )
        if not ok:
            raise SystemExit(f"评论创建失败: {result}")
        return result

    first = comment(linwan, "这张的色调太喜欢了，像旧胶片。", journal_id=published[0].id)
    reply = comment(demo, "谢谢！那天正好有雾，光被压得很软。", journal_id=published[0].id,
                    parent_id=first.id)
    comment(zhouyu, "同感，尤其是塞纳河那一段。", journal_id=published[0].id,
            parent_id=reply.id)

    comment(zhouyu, "第一次上去的时候腿都软了，但真的值得。",
            landmark_id=landmark("EiffelTower").id)
    comment(demo, "下次挑日落前半小时上去，排队会短一些。",
            journal_id=published[1].id)
    comment(linwan, "珠峰那张银河是几点拍的？", journal_id=published[8].id)
    comment(demo, "凌晨两点多，风小的时候。", journal_id=published[8].id)

    # 4. 点赞：手账 / 商品文章 / 评论都铺一点，看板才有数字
    def like(user: User, target_type: str, target_id: int) -> None:
        Like.objects.get_or_create(
            user=user, target_type=target_type, target_id=target_id
        )

    for item in published[:6]:
        like(linwan, "journal", item.id)
    for item in published[2:8]:
        like(zhouyu, "journal", item.id)
    like(linwan, "comment", first.id)
    like(demo, "article", landmark("EiffelTower").id)
    like(linwan, "article", landmark("Petra").id)

    # 5. 收藏与分享链接（收藏是 through 表，不能直接 add 地标对象）
    from apps.landmarks.models import UserFavorite

    for user, target_ids in (
        (demo, ("EiffelTower", "MachuPicchu", "TajMahal")),
        (linwan, ("Petra", "LibertyStatue")),
    ):
        for target_id in target_ids:
            UserFavorite.objects.get_or_create(user=user, landmark=landmark(target_id))
    share_token = share_service.create_share_token("journal", published[0].id, demo)

    # 6. 通知：回复与徽章，右侧通知中心一打开就有内容
    notification_service.notify_reply(linwan, first, reply)
    badge_service.on_journal_created(demo)
    badge_service.on_comment_created(demo)

    for user, text in (
        (linwan, "你关注的地标有了新的手账"),
        (zhouyu, "你的手账《斗兽场的黄昏》获得 3 个赞"),
    ):
        notification_service.push(user, "system", "系统提醒", text, "/")

    return {
        "users": User.objects.count(),
        "journals": Journal.objects.count(),
        "drafts": Journal.objects.filter(status="draft").count(),
        "comments": Comment.objects.count(),
        "likes": Like.objects.count(),
        "share": share_token,
        "private_id": private.id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TripScape 展示状态（重置 + 演示内容）",
        epilog="示例: python reset_demo.py --yes",
    )
    parser.add_argument("--yes", action="store_true", help="跳过确认，直接执行")
    parser.add_argument("--no-frontend", action="store_true", help="不重建前端产物")
    args = parser.parse_args()

    overall = time.time()
    if not args.yes:
        print("本操作会删库并写入演示数据。")
        if input("确认继续？输入 y 回车: ").strip().lower() not in {"y", "yes"}:
            sys.exit("已取消，未做任何修改")

    # 先重置到干净初始状态，再播种；复用同一套阶段函数，避免两份逻辑漂移
    base.ensure_no_bytecode_hook()
    base.clean_runtime()
    base.reset_database()
    base.ensure_qa_index(force=False)

    print("\n========== 第 5 步 / 写入演示内容 ==========")
    started = time.time()
    setup_django()
    stats = seed_demo()
    base.print_step_done("写入演示内容", started)

    if not args.no_frontend:
        base.build_frontend()

    print("\n" + "=" * 50)
    for title, cost in base.TIMINGS:
        print(f"[耗时] {title}: {cost:.2f} 秒")
    print(f"展示状态就绪，总运行时间: {time.time() - overall:.2f} 秒")
    print(f"  账号: demo / linwan / zhouyu（密码 {DEMO_PASSWORD}）")
    print(f"  手账: {stats['journals']} 篇（草稿 {stats['drafts']} 篇）")
    print(f"  评论: {stats['comments']} 条 · 点赞: {stats['likes']} 次")
    print(f"  分享链接: /share/{stats['share']}")
    print("启动: python backend/manage.py runserver 127.0.0.1:8000")


if __name__ == "__main__":
    main()
