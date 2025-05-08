"""
图像处理模块 - 负责物种识别和图像处理功能
"""

import os
import logging
from typing import Dict, Any, Optional, List
from collections import Counter
from ultralytics import YOLO

logger = logging.getLogger(__name__)

class ImageProcessor:
    """处理图像、检测物种的核心类"""

    def __init__(self, model_path: str):
        """初始化图像处理器

        Args:
            model_path: YOLO模型文件路径
        """
        self.model = self._load_model(model_path)

    def _load_model(self, model_path: str) -> Optional[YOLO]:
        """加载YOLO模型

        Args:
            model_path: 模型文件路径

        Returns:
            加载的YOLO模型或None（如果加载失败）
        """
        try:
            logger.info(f"正在加载模型: {model_path}")
            return YOLO(model_path)
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return None

    def _process_images_thread(self, file_path: str, save_path: str,
                               save_detect_image: bool, output_excel: bool,
                               copy_img: bool, use_fp16: bool, resume_from: int = 0) -> None:
        """图像处理线程

        Args:
            file_path: 源文件路径
            save_path: 保存路径
            save_detect_image: 是否保存探测图片
            output_excel: 是否输出Excel表格
            copy_img: 是否按物种分类复制图片
            use_fp16: 是否使用FP16加速推理
            resume_from: 从第几张图片开始处理，用于继续上次未完成的处理
        """
        # 强制检查CUDA是否可用，并在不可用时禁用FP16
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            if not cuda_available:
                use_fp16 = False  # 如果CUDA不可用，强制禁用FP16
        except ImportError:
            use_fp16 = False  # 如果无法导入torch，强制禁用FP16
        except Exception:
            use_fp16 = False  # 任何其他异常也禁用FP16

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

        # 定义执行检测的函数
        def run_detection():
            nonlocal species_names, species_counts, n, detect_results, min_confidence
            try:
                # 使用参数进行检测
                results = self.model(
                    img_path,
                    augment=augment,
                    agnostic_nms=agnostic_nms,
                    imgsz=1024,
                    half=use_fp16,  # 这里使用可能已被调整的use_fp16值
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

        # 使用线程池执行带有超时的检测
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_detection)
            try:
                # 等待执行完成，有超时限制
                success = future.result(timeout=timeout)
                if not success:
                    raise Exception("检测过程出错")
            except concurrent.futures.TimeoutError:
                # 超时处理
                raise TimeoutError(f"物种检测超时（>{timeout}秒）")

        return {
            '物种名称': species_names,
            '物种数量': species_counts,
            'detect_results': detect_results,
            '最低置信度': min_confidence
        }

    def save_detection_result(self, results: Any, image_name: str, save_path: str) -> None:
        """保存探测结果图片

        Args:
            results: YOLO检测结果
            image_name: 原始图片名称
            save_path: 保存路径
        """
        if not results:
            return

        try:
            # 创建结果保存目录
            result_path = os.path.join(save_path, "result")
            os.makedirs(result_path, exist_ok=True)

            for c, h in enumerate(results):
                # 获取第一个检测到的物种名称
                species_name = self._get_first_detected_species(results)
                result_file = os.path.join(result_path, f"{image_name}_result_{species_name}.jpg")
                h.save(filename=result_file)
        except Exception as e:
            logger.error(f"保存检测结果图片失败: {e}")

    def _get_first_detected_species(self, results: Any) -> str:
        """从检测结果中获取第一个物种的名称

        Args:
            results: YOLO检测结果

        Returns:
            物种名称或空字符串
        """
        try:
            for r in results:
                if r.boxes and len(r.boxes.cls) > 0:
                    return r.names[int(r.boxes.cls[0].item())]
        except Exception as e:
            logger.error(f"获取物种名称失败: {e}")
        return "unknown"