import os
import logging
import concurrent.futures
from typing import Dict, Any, Optional, List
from collections import Counter
from ultralytics import YOLO

logger = logging.getLogger(__name__)

class ImageProcessor:
    """处理图像、检测物种的核心类"""

    def __init__(self, model_path: str):
        """初始化图像处理器"""
        self.model = self._load_model(model_path)

    def _load_model(self, model_path: str) -> Optional[YOLO]:
        """加载YOLO模型"""
        try:
            logger.info(f"正在加载模型: {model_path}")
            return YOLO(model_path)
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return None

    def detect_species(self, img_path: str, use_fp16: bool = False, iou: float = 0.3,
                       conf: float = 0.25, augment: bool = True,
                       agnostic_nms: bool = True, timeout: float = 10.0) -> Dict[str, Any]:
        """检测图像中的物种"""
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            if not cuda_available:
                use_fp16 = False
        except ImportError:
            use_fp16 = False
        except Exception:
            use_fp16 = False

        species_names = ""
        species_counts = ""
        n = 0
        detect_results = None
        min_confidence = None

        if not self.model:
            return {
                '物种名称': species_names,
                '物种数量': species_counts,
                'detect_results': detect_results,
                '最低置信度': min_confidence
            }

        def run_detection():
            nonlocal species_names, species_counts, n, detect_results, min_confidence
            try:
                results = self.model(
                    img_path,
                    augment=augment,
                    agnostic_nms=agnostic_nms,
                    imgsz=1024,
                    half=use_fp16,
                    iou=iou,
                    conf=conf
                )
                detect_results = results

                for r in results:
                    data_list = r.boxes.cls.tolist()
                    counts = Counter(data_list)
                    species_dict = r.names
                    confidences = r.boxes.conf.tolist()

                    if confidences:
                        current_min_confidence = min(confidences)
                        if min_confidence is None or current_min_confidence < min_confidence:
                            min_confidence = "%.3f" % current_min_confidence

                    for element, count in counts.items():
                        n += 1
                        species_name = species_dict[int(element)]
                        if n == 1:
                            species_names += species_name
                            species_counts += str(count)
                        else:
                            species_names += f",{species_name}"
                            species_counts += f",{count}"
                return True
            except Exception as e:
                logger.error(f"物种检测失败: {e}")
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_detection)
            try:
                success = future.result(timeout=timeout)
                if not success:
                    raise Exception("检测过程出错")
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"物种检测超时（>{timeout}秒）")

        return {
            '物种名称': species_names,
            '物种数量': species_counts,
            'detect_results': detect_results,
            '最低置信度': min_confidence
        }

    def save_detection_result(self, results: Any, image_name: str, save_path: str) -> None:
        """保存探测结果图片"""
        if not results:
            return

        try:
            result_path = os.path.join(save_path, "result")
            os.makedirs(result_path, exist_ok=True)

            for c, h in enumerate(results):
                species_name = self._get_first_detected_species(results)
                result_file = os.path.join(result_path, f"{image_name}_result_{species_name}.jpg")
                h.save(filename=result_file)
        except Exception as e:
            logger.error(f"保存检测结果图片失败: {e}")

    def _get_first_detected_species(self, results: Any) -> str:
        """从检测结果中获取第一个物种的名称"""
        try:
            for r in results:
                if r.boxes and len(r.boxes.cls) > 0:
                    return r.names[int(r.boxes.cls[0].item())]
        except Exception as e:
            logger.error(f"获取物种名称失败: {e}")
        return "unknown"

    # V V V V V V V V V V V V V V V V V V V V
    # MODIFICATION: Accept dynamic temp_photo_dir
    # V V V V V V V V V V V V V V V V V V V V
    def save_detection_temp(self, results: Any, image_name: str, temp_photo_dir: str) -> str:
        """保存探测结果图片到指定的临时目录"""
        if not results or not temp_photo_dir:
            return ""

        try:
            os.makedirs(temp_photo_dir, exist_ok=True)
            result_file = os.path.join(temp_photo_dir, image_name)
            for h in results:
                from PIL import Image
                result_img = h.plot()
                result_img = Image.fromarray(result_img[..., ::-1])
                compressed_img, quality = self._compress_image_for_temp(result_img)
                compressed_img.save(result_file, "JPEG", quality=quality)
                return result_file
        except Exception as e:
            logger.error(f"保存临时检测结果图片失败: {e}")
            return ""

    def save_detection_info_json(self, results, image_name: str, species_info: dict, temp_photo_dir: str) -> str:
        """保存探测结果信息到指定的临时目录"""
        if not results or not temp_photo_dir:
            return ""

        try:
            import json
            os.makedirs(temp_photo_dir, exist_ok=True)
            data_to_save = {
                "物种名称": species_info.get('物种名称', ''),
                "物种数量": species_info.get('物种数量', ''),
                "最低置信度": species_info.get('最低置信度', ''),
                "检测时间": species_info.get('检测时间', '')
            }
            boxes_info = []
            for r in results:
                for i, box in enumerate(r.boxes):
                    cls_id = int(box.cls.item())
                    species_name = r.names[cls_id]
                    confidence = float(box.conf.item())
                    bbox = [float(x) for x in box.xyxy.tolist()[0]]
                    box_info = {"物种": species_name, "置信度": confidence, "边界框": bbox}
                    boxes_info.append(box_info)
            data_to_save["检测框"] = boxes_info
            
            base_name, _ = os.path.splitext(image_name)
            json_path = os.path.join(temp_photo_dir, f"{base_name}.json")

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)

            return json_path
        except Exception as e:
            logger.error(f"保存检测结果JSON失败: {e}")
            return ""
    # ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^ ^

    def load_model(self, model_path: str) -> None:
        """加载新的模型"""
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.model_path = model_path
            logger.info(f"模型已加载: {model_path}")

        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            raise Exception(f"加载模型失败: {e}")

    def _compress_image_for_temp(self, img, max_width=1280, quality=85):
        """压缩图像以节省临时存储空间"""
        try:
            from PIL import Image
            import numpy as np

            if isinstance(img, np.ndarray):
                img = Image.fromarray(img)

            width, height = img.size
            if width > max_width:
                ratio = max_width / width
                new_height = int(height * ratio)
                img = img.resize((max_width, new_height), Image.LANCZOS)

            return img, quality
        except Exception as e:
            logger.error(f"压缩图像失败: {e}")
            return img, 95