"""
行旅识景 TripScape / api/uploads
创建日期: 2026-11-26

文件上传 API（目前只有图片）。

POST /api/uploads/image    上传一张图片，返回可访问地址
    - 登录用户
    - 只接受 png / jpg / webp / gif，且做文件头校验
    - MinIO 可用时进对象存储，否则落到 runtime/uploads/ 并返回 /media/...

注意:
    1. 之前写手账界面的"图片记录"一直在调这个地址，但后端没有对应路由，
       所以上传永远失败——这里补上，画布才能真的导入照片。
    2. 只返回 URL，不写业务表；引用关系由手账的 canvas / images 字段负责。
"""

from ninja import File, Router
from ninja.files import UploadedFile

from apps.core.auth import login_required
from services import file_service

router = Router()


@router.post("/image", summary="上传图片")
@login_required
def upload_image(request, image: UploadedFile = File(...)):
    """上传一张图片（png/jpg/webp/gif），返回站内可访问地址。"""
    url = file_service.save_upload(image, namespace="journals", owner=request.auth)
    return {"success": True, "url": url}
