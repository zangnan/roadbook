"""缩略图生成模块"""
import os
import base64
import io
from PIL import Image
from config import THUMBNAIL_SIZE


def apply_exif_orientation(img, exif=None):
    """根据 EXIF Orientation 标签旋转图像

    Args:
        img: PIL Image 对象
        exif: 可选，EXIF 数据字典。如果为 None，从 img.getexif() 获取

    Returns:
        PIL.Image: 已应用旋转的图像
    """
    if exif is None:
        try:
            exif = img.getexif()
        except Exception:
            return img

    orientation = exif.get(0x0112)  # EXIF Tag for Orientation
    if not orientation or orientation == 1:
        return img

    # Orientation 值对应的旋转操作
    rotations = {
        2: Image.FLIP_LEFT_RIGHT,
        3: Image.ROTATE_180,
        4: Image.FLIP_TOP_BOTTOM,
        5: Image.TRANSPOSE,
        6: Image.ROTATE_270,
        7: Image.TRANSVERSE,
        8: Image.ROTATE_90,
    }

    if orientation in rotations:
        img = img.transpose(rotations[orientation])

    return img


def generate_thumbnail(image_path, size=None):
    """生成缩略图

    Args:
        image_path: 图片路径
        size: 元组 (width, height)，默认使用 config 中的 THUMBNAIL_SIZE

    Returns:
        PIL.Image: 缩略图对象
    """
    if size is None:
        size = THUMBNAIL_SIZE

    try:
        img = Image.open(image_path)
        img = apply_exif_orientation(img)
        img.thumbnail(size, Image.Resampling.BILINEAR)
        return img
    except Exception as e:
        print(f"生成缩略图失败 {image_path}: {e}")
        return None


def image_to_base64(image_path, size=None):
    """图片转 Base64

    Args:
        image_path: 图片路径
        size: 缩略图大小，如果为 None 则返回原图

    Returns:
        str: Base64 编码字符串（不含 data:image/jpeg;base64, 前缀）
    """
    try:
        img = Image.open(image_path)

        # 如果指定了 size，则生成缩略图
        if size is not None:
            img.thumbnail(size, Image.Resampling.BILINEAR)

        # 转换为 RGB 模式（确保 JPEG 可以编码）
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        img_bytes = buffer.getvalue()

        return base64.b64encode(img_bytes).decode('utf-8')
    except Exception as e:
        print(f"Base64 转换失败 {image_path}: {e}")
        return None


def original_to_base64(image_path):
    """获取原图 Base64（不缩放，保持原始尺寸）

    Args:
        image_path: 图片路径

    Returns:
        str: Base64 编码字符串（不含 data:image/jpeg;base64, 前缀）
    """
    return image_to_base64(image_path, size=None)


def save_thumbnail(image_path, output_path, size=None):
    """保存缩略图到文件

    Args:
        image_path: 源图片路径
        output_path: 输出文件完整路径
        size: 缩略图大小，默认使用 config 中的 THUMBNAIL_SIZE

    Returns:
        str: 保存的文件路径，失败返回 None
    """
    if size is None:
        size = THUMBNAIL_SIZE

    try:
        img = Image.open(image_path)
        img = apply_exif_orientation(img)
        img.thumbnail(size, Image.Resampling.BILINEAR)

        # 转换为 RGB 模式（确保 JPEG 可以编码）
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存为 JPEG
        img.save(output_path, format='JPEG', quality=85)
        return output_path
    except Exception as e:
        print(f"保存缩略图失败 {image_path} -> {output_path}: {e}")
        return None


def save_original(image_path, output_path, quality=None):
    """保存原图到文件（保持原始尺寸，仅格式转换和压缩）

    Args:
        image_path: 源图片路径
        output_path: 输出文件完整路径
        quality: 压缩质量 (1-100)，默认从配置读取

    Returns:
        str: 保存的文件路径，失败返回 None
    """
    from config import ORIGINAL_IMAGE_QUALITY
    if quality is None:
        quality = ORIGINAL_IMAGE_QUALITY

    try:
        img = Image.open(image_path)
        img = apply_exif_orientation(img)

        # 转换为 RGB 模式（确保 JPEG 可以编码）
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存为 JPEG（使用压缩质量）
        img.save(output_path, format='JPEG', quality=quality)
        return output_path
    except Exception as e:
        print(f"保存原图失败 {image_path} -> {output_path}: {e}")
        return None
