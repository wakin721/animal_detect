"""
数据处理模块 - 负责数据处理和Excel导出
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from system.config import INDEPENDENT_DETECTION_THRESHOLD

logger = logging.getLogger(__name__)

class DataProcessor:
    """数据处理类，处理图像信息集合"""

    @staticmethod
    def calculate_working_days(image_info_list: List[Dict], earliest_date: Optional[datetime]) -> List[Dict]:
        """计算每张图片的工作天数

        Args:
            image_info_list: 图像信息列表
            earliest_date: 最早的拍摄日期

        Returns:
            更新后的图像信息列表
        """
        if not earliest_date:
            logger.warning("无法计算工作天数：未找到任何有效拍摄日期")
            return image_info_list

        for info in image_info_list:
            date_taken = info.get('拍摄日期对象')
            if date_taken:
                working_days = (date_taken.date() - earliest_date.date()).days + 1
                info['工作天数'] = working_days

        return image_info_list

    @staticmethod
    def process_independent_detection(image_info_list: List[Dict]) -> List[Dict]:
        """处理独立探测首只标记

        Args:
            image_info_list: 图像信息列表

        Returns:
            更新后的图像信息列表
        """
        # 按拍摄日期排序
        sorted_images = sorted(
            [img for img in image_info_list if img.get('拍摄日期对象')],
            key=lambda x: x['拍摄日期对象']
        )

        species_last_detected = {}  # 记录每个物种的最后探测时间

        for img_info in sorted_images:
            species_names = img_info['物种名称'].split(',')
            current_time = img_info.get('拍摄日期对象')

            if not current_time or not species_names or species_names == ['']:
                img_info['独立探测首只'] = ''
                continue

            is_independent = False

            for species in species_names:
                if species in species_last_detected:
                    # 检查时间差是否超过阈值
                    time_diff = (current_time - species_last_detected[species]).total_seconds()
                    if time_diff > INDEPENDENT_DETECTION_THRESHOLD:
                        is_independent = True
                else:
                    # 首次探测该物种
                    is_independent = True

                # 更新最后探测时间
                species_last_detected[species] = current_time

            img_info['独立探测首只'] = '是' if is_independent else ''

        return image_info_list

    @staticmethod
    def export_to_excel(image_info_list: List[Dict], output_path: str) -> bool:
        """将图像信息导出为Excel文件

        Args:
            image_info_list: 图像信息列表
            output_path: 输出文件路径

        Returns:
            是否成功导出
        """
        if not image_info_list:
            logger.warning("没有数据可导出到Excel")
            return False

        try:
            # 使用pandas创建DataFrame更高效
            df = pd.DataFrame(image_info_list)

            # 选择需要的列并按顺序排列
            columns = ['文件名', '格式', '拍摄日期', '拍摄时间', '工作天数',
                       '物种名称', '物种数量', '最低置信度', '独立探测首只']

            # 确保所有列都存在，不存在的列填充空值
            for col in columns:
                if col not in df.columns:
                    df[col] = ''

            # 只保留需要的列并排序
            df = df[columns]

            # 导出到Excel
            df.to_excel(output_path, sheet_name="物种检测信息", index=False)

            return True
        except Exception as e:
            logger.error(f"导出Excel失败: {e}")
            return False