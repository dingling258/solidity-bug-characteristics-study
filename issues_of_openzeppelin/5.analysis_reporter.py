import pandas as pd
import json
import matplotlib.pyplot as plt
import os
import shutil
from datetime import datetime
import matplotlib as mpl
from matplotlib.font_manager import FontProperties
import time
import warnings
import numpy as np

# 忽略matplotlib的字体警告
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")


class AnalysisReporter:
    def __init__(self, classified_file=None):
        self.df = None
        if classified_file and os.path.exists(classified_file):
            self.df = pd.read_csv(classified_file)

        # 设置中文字体支持
        self.set_chinese_font()

        # 存储统计结果
        self.statistics = {}

    def set_chinese_font(self):
        """设置matplotlib支持中文显示"""
        # 方法1：指定特定的中文字体路径
        # Windows中文字体路径
        font_paths = [
            'C:/Windows/Fonts/simhei.ttf',  # 黑体
            'C:/Windows/Fonts/msyh.ttc',  # 微软雅黑
            'C:/Windows/Fonts/simsun.ttc',  # 宋体
            # macOS字体路径
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Light.ttc',
            # Linux字体路径
            '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
        ]

        # 尝试查找系统中存在的字体
        font_found = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                self.chinese_font = FontProperties(fname=font_path)
                mpl.rcParams['font.family'] = self.chinese_font.get_name()
                font_found = True
                break

        # 方法2：如果找不到特定路径的字体，尝试使用系统内置字体
        if not font_found:
            try:
                plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun',
                                                   'PingFang SC', 'Heiti SC', 'Source Han Sans CN',
                                                   'WenQuanYi Micro Hei', 'Droid Sans Fallback',
                                                   'Noto Sans CJK SC']
                plt.rcParams['axes.unicode_minus'] = False  # 解决负号'-'显示为方块的问题
                # 使用空的FontProperties对象，让matplotlib尝试使用上面设置的sans-serif字体
                self.chinese_font = FontProperties()
            except Exception as e:
                print(f"设置中文字体失败: {e}")
                self.chinese_font = None

    def load_data(self, file_path):
        """加载分类后的数据"""
        if not os.path.exists(file_path):
            raise ValueError(f"文件 {file_path} 不存在")

        self.df = pd.read_csv(file_path)
        return self.df

    def filter_text_issues(self):
        """过滤文本类issues，将其标记为非bug相关"""
        if self.df is None:
            raise ValueError("请先加载数据")

        # 确保有title_lower列，如果没有，则创建
        if 'title_lower' not in self.df.columns and 'title' in self.df.columns:
            self.df['title_lower'] = self.df['title'].str.lower()

        # 定义文本类关键词
        text_keywords = [
            'doc', 'documentation', 'typo', 'spelling', 'grammar',
            'comment', 'example', 'tutorial', 'readme', 'clarification',
            'explanation', 'wording', 'text', 'description', 'guide',
            'update readme', 'update docs', 'fix typo', 'improve docs'
        ]

        # 创建mask来识别文本类issues
        text_masks = []

        # 标题中的关键词
        title_mask = self.df['title_lower'].str.contains('|'.join(text_keywords), na=False, regex=True)
        text_masks.append(title_mask)

        # 如果有正文列
        if 'body' in self.df.columns:
            # 检查是否没有代码块同时包含文档关键词
            body_lower = self.df['body'].str.lower()
            body_mask = (
                    ~body_lower.str.contains('```', na=False, regex=False) &
                    body_lower.str.contains('|'.join(text_keywords), na=False, regex=True)
            )
            text_masks.append(body_mask)

        # 如果有标签列
        if 'labels' in self.df.columns:
            labels_lower = self.df['labels'].str.lower()
            labels_mask = labels_lower.str.contains('documentation|docs|typo|enhancement', na=False, regex=True)
            text_masks.append(labels_mask)

        # 合并所有mask
        combined_mask = pd.Series(False, index=self.df.index)
        for mask in text_masks:
            combined_mask = combined_mask | mask

        # 统计过滤前的bug相关issues数量
        before_count = self.df['is_bug_related'].sum()

        # 将识别出的文本类issues修改为非bug相关
        self.df.loc[combined_mask & self.df['is_bug_related'], 'is_bug_related'] = False

        # 统计过滤后的bug相关issues数量
        after_count = self.df['is_bug_related'].sum()
        filtered_count = before_count - after_count

        # 保存过滤信息
        self.filtered_text_count = filtered_count

        print(f"已将 {filtered_count} 个文本类issues从bug相关中过滤出去")

        # 保存过滤后的csv用于查看
        try:
            self.df.to_csv("filtered_issues.csv", index=False, encoding='utf-8')
            print("过滤后的数据已保存至 filtered_issues.csv")
        except Exception as e:
            print(f"保存过滤后数据时出错: {e}")

        return filtered_count

    def generate_low_confidence_report(self, threshold=1.5, output_file="low_confidence_issues.csv"):
        """生成需要人工审核的低置信度报告"""
        if self.df is None:
            raise ValueError("请先加载数据")

        # 提取置信度低的bug相关issue
        low_conf = self.df[(self.df['is_bug_related']) & (self.df['confidence'] <= threshold)].copy()

        # 添加人工审核列
        low_conf.loc[:, 'manual_review'] = ''
        low_conf.loc[:, 'correct_category'] = ''
        low_conf.loc[:, 'notes'] = ''

        # 保存为CSV
        try:
            low_conf.to_csv(output_file, index=False, encoding='utf-8')
            print(f"共有 {len(low_conf)} 个bug相关issue的分类置信度较低，已保存至 {output_file}")
        except Exception as e:
            print(f"保存低置信度报告时出错: {e}")
            # 尝试使用备用文件名
            backup_file = f"low_confidence_issues_backup.csv"
            try:
                low_conf.to_csv(backup_file, index=False, encoding='utf-8')
                print(f"已将低置信度报告保存至备用文件: {backup_file}")
            except Exception as e2:
                print(f"保存到备用文件也失败: {e2}")

        # 保存低置信度数量
        self.low_confidence_count = len(low_conf)
        return len(low_conf)

    def generate_statistics(self):
        """生成分类统计分析"""
        if self.df is None:
            raise ValueError("请先加载数据")

        # 基本统计
        total_issues = len(self.df)
        bug_related = self.df['is_bug_related'].sum()
        bug_percentage = (bug_related / total_issues) * 100 if total_issues > 0 else 0

        stats = {
            'total_issues': total_issues,
            'bug_related': int(bug_related),
            'bug_percentage': round(bug_percentage, 2)
        }

        # DASP类别分布
        if bug_related > 0:
            dasp_counts = self.df[self.df['is_bug_related']]['dasp_category'].value_counts()
            stats['dasp_distribution'] = dasp_counts.to_dict()
        else:
            stats['dasp_distribution'] = {}

        # 按合约类型分析
        contract_stats = {}
        contract_types = ['erc20', 'erc721', 'erc1155', 'safemath', 'accesscontrol',
                          'governor', 'ownable', 'proxy']

        for contract in contract_types:
            try:
                # 首先尝试使用特征列
                if f'has_{contract}' in self.df.columns:
                    contract_issues = self.df[self.df[f'has_{contract}']]
                else:
                    # 回退到标题搜索
                    contract_issues = self.df[self.df['title_lower'].str.contains(contract, na=False)]

                contract_bugs = contract_issues['is_bug_related'].sum()
                if len(contract_issues) > 0:
                    bug_rate = (contract_bugs / len(contract_issues)) * 100
                    contract_stats[contract.upper()] = {
                        'total': len(contract_issues),
                        'bugs': int(contract_bugs),
                        'percentage': round(bug_rate, 2)
                    }
            except Exception as e:
                print(f"分析 {contract} 时出错: {e}")

        stats['contract_analysis'] = contract_stats

        # 置信度统计
        if bug_related > 0:
            # 明确强制类型转换为float，避免潜在的NaN问题
            self.df['confidence'] = self.df['confidence'].astype(float)

            high_conf_count = int(self.df[(self.df['is_bug_related']) & (self.df['confidence'] > 2.0)].shape[0])
            med_conf_count = int(self.df[(self.df['is_bug_related']) &
                                         (self.df['confidence'] > 1.5) &
                                         (self.df['confidence'] <= 2.0)].shape[0])
            low_conf_count = int(self.df[(self.df['is_bug_related']) & (self.df['confidence'] <= 1.5)].shape[0])

            confidence_stats = {
                'high_confidence': high_conf_count,
                'medium_confidence': med_conf_count,
                'low_confidence': low_conf_count
            }
            stats['confidence_distribution'] = confidence_stats

            # 保存各置信度级别的数量以便后续使用
            self.high_confidence_count = high_conf_count
            self.medium_confidence_count = med_conf_count
            self.low_confidence_count = low_conf_count

        # 保存统计信息以供其他方法使用
        self.statistics = stats
        return stats

    def analyze_time_trends(self):
        """分析bug相关issue的时间趋势"""
        if self.df is None:
            raise ValueError("请先加载数据")

        try:
            # 尝试转换日期列（如果存在）
            if 'created_at' in self.df.columns:
                self.df['created_at'] = pd.to_datetime(self.df['created_at'])
                self.df['year_month'] = self.df['created_at'].dt.strftime('%Y-%m')

                # 按月统计
                monthly_counts = self.df.groupby('year_month').size()
                monthly_bugs = self.df[self.df['is_bug_related']].groupby('year_month').size()

                # 计算每月bug占比
                result = pd.DataFrame({
                    'total_issues': monthly_counts,
                    'bug_issues': monthly_bugs,
                    'percentage': (monthly_bugs / monthly_counts * 100).fillna(0)
                })

                # 保存趋势数据
                try:
                    result.to_csv("time_trends.csv", encoding='utf-8')
                    print("时间趋势分析已保存至 time_trends.csv")
                except Exception as e:
                    print(f"保存时间趋势数据时出错: {e}")

                return result.to_dict()
            else:
                return {"error": "没有找到创建日期列"}
        except Exception as e:
            print(f"时间趋势分析出错: {e}")
            return {"error": str(e)}

    def generate_visualizations(self, output_dir="visualizations"):
        """生成可视化图表"""
        if self.df is None:
            raise ValueError("请先加载数据")

        # 如果目录已存在，先删除
        if os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except Exception as e:
                print(f"删除可视化目录时出错: {e}")
                # 尝试创建备用目录
                output_dir = "visualizations_new"

        # 创建新的输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 图1: Bug vs 非Bug饼图
        try:
            # 直接计算Bug相关和非Bug相关数量
            bug_related_count = int(self.df['is_bug_related'].sum())
            non_bug_related_count = len(self.df) - bug_related_count

            # 创建数据和标签
            sizes = [bug_related_count, non_bug_related_count]
            labels = ['Bug相关', '非Bug相关']

            # 只在有数据时绘制
            if sum(sizes) > 0:
                plt.figure(figsize=(8, 6))
                plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
                plt.title('Bug相关 vs 非Bug相关 Issues', fontproperties=self.chinese_font)
                plt.axis('equal')  # 确保饼图是圆的
                plt.savefig(f"{output_dir}/bug_proportion.png")
                plt.close()
                print(f"Bug比例饼图已保存至 {output_dir}/bug_proportion.png")
            else:
                print("没有足够的数据生成Bug比例饼图")
        except Exception as e:
            print(f"生成Bug比例图表时出错: {e}")

        # 图2: DASP分类分布图
        try:
            if self.df['is_bug_related'].sum() > 0:
                dasp_counts = self.df[self.df['is_bug_related']]['dasp_category'].value_counts()

                # 将分类映射为中文名称
                chinese_categories = {
                    '未分类': '未分类',
                    'Access Control': '访问控制问题',
                    'Arithmetic': '算术问题',
                    'Reentrancy': '重入攻击',
                    'Unchecked Return Values': '未检查的返回值',
                    'Denial of Service': '拒绝服务',
                    'Bad Randomness': '随机数问题',
                    'Front Running': '抢先交易',
                    'Time Manipulation': '时间操纵',
                    'Short Address Attack': '短地址攻击',
                    'Race Conditions': '竞态条件',
                    'Default Visibility': '默认可见性',
                    'Other': '其他问题'
                }

                # 转换分类名称为中文
                chinese_dasp_counts = pd.Series(index=[chinese_categories.get(cat, cat) for cat in dasp_counts.index],
                                                data=dasp_counts.values)

                plt.figure(figsize=(12, 8))
                chinese_dasp_counts.plot(kind='bar')
                plt.title('DASP漏洞类别分布', fontproperties=self.chinese_font)
                plt.ylabel('Issue数量', fontproperties=self.chinese_font)
                plt.xlabel('漏洞类别', fontproperties=self.chinese_font)
                plt.xticks(rotation=45, ha='right', fontproperties=self.chinese_font)
                plt.tight_layout()
                plt.savefig(f"{output_dir}/dasp_distribution.png")
                plt.close()
                print(f"DASP分布图已保存至 {output_dir}/dasp_distribution.png")
        except Exception as e:
            print(f"生成DASP分布图表时出错: {e}")

        # 图3: 置信度分布饼图
        try:
            # 确保generate_statistics已运行
            if not hasattr(self, 'statistics') or not self.statistics:
                self.generate_statistics()

            if self.df['is_bug_related'].sum() > 0:
                # 使用已保存的置信度计数
                high_conf = self.high_confidence_count
                med_conf = self.medium_confidence_count
                low_conf = self.low_confidence_count

                # 打印调试信息
                print(f"置信度分布 - 高:{high_conf}, 中:{med_conf}, 低:{low_conf}")

                conf_sizes = [high_conf, med_conf, low_conf]
                conf_labels = ['高置信度', '中置信度', '低置信度']

                # 移除零值数据点
                non_zero_sizes = []
                non_zero_labels = []
                for i, size in enumerate(conf_sizes):
                    if size > 0:
                        non_zero_sizes.append(size)
                        non_zero_labels.append(conf_labels[i])

                if sum(non_zero_sizes) > 0:
                    plt.figure(figsize=(8, 6))
                    plt.pie(non_zero_sizes, labels=non_zero_labels, autopct='%1.1f%%', startangle=90)
                    plt.title('Bug相关Issues置信度分布', fontproperties=self.chinese_font)
                    plt.axis('equal')
                    plt.savefig(f"{output_dir}/confidence_distribution.png")
                    plt.close()
                    print(f"置信度分布图已保存至 {output_dir}/confidence_distribution.png")
        except Exception as e:
            print(f"生成置信度分布图表时出错: {e}")

        # 图4: 时间趋势图
        try:
            if 'created_at' in self.df.columns:
                self.df['created_at'] = pd.to_datetime(self.df['created_at'])
                self.df['year_month'] = self.df['created_at'].dt.strftime('%Y-%m')

                # 按月统计
                monthly_bugs = self.df[self.df['is_bug_related']].groupby('year_month').size()

                if not monthly_bugs.empty:
                    plt.figure(figsize=(14, 8))
                    monthly_bugs.plot(kind='line', marker='o')
                    plt.title('Bug相关Issues随时间变化趋势', fontproperties=self.chinese_font)
                    plt.ylabel('Bug相关Issue数量', fontproperties=self.chinese_font)
                    plt.xlabel('年-月', fontproperties=self.chinese_font)
                    plt.grid(True, linestyle='--', alpha=0.7)
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()
                    plt.savefig(f"{output_dir}/time_trend.png")
                    plt.close()
                    print(f"时间趋势图已保存至 {output_dir}/time_trend.png")
        except Exception as e:
            print(f"生成时间趋势图表时出错: {e}")

        print(f"可视化图表已保存至 {output_dir} 目录")

    def generate_final_report(self, output_file="classification_report.json"):
        """生成最终分析报告"""
        if self.df is None:
            raise ValueError("请先加载数据")

        # 获取统计信息（如果尚未生成）
        if not hasattr(self, 'statistics') or not self.statistics:
            statistics = self.generate_statistics()
        else:
            statistics = self.statistics

        # 提取各DASP类别的典型案例
        typical_cases = {}
        for category in set(self.df[self.df['is_bug_related']]['dasp_category']):
            if pd.notna(category) and category != "非Bug相关":  # 检查非空和非Bug相关
                # 获取置信度最高的案例
                category_issues = self.df[(self.df['is_bug_related']) & (self.df['dasp_category'] == category)]
                if not category_issues.empty:
                    top_case = category_issues.sort_values('confidence', ascending=False).iloc[0]
                    typical_cases[category] = {
                        'number': int(top_case['number']),
                        'title': top_case['title'],
                        'confidence': float(top_case['confidence'])
                    }

        # 时间趋势分析
        time_trends = self.analyze_time_trends()

        # 构建完整报告
        report = {
            'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'statistics': statistics,
            'typical_cases': typical_cases,
            'time_trends': time_trends
        }

        # 保存报告
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"最终分析报告已保存至 {output_file}")
        except Exception as e:
            print(f"保存分析报告时出错: {e}")
            # 尝试备用文件名
            try:
                backup_file = "classification_report_backup.json"
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                print(f"已将分析报告保存至备用文件: {backup_file}")
            except Exception as e2:
                print(f"保存到备用文件也失败: {e2}")

        # 确保我们有准确的置信度计数
        if not (hasattr(self, 'high_confidence_count') and
                hasattr(self, 'medium_confidence_count') and
                hasattr(self, 'low_confidence_count')):
            self.df['confidence'] = self.df['confidence'].astype(float)  # 确保类型
            self.high_confidence_count = int(
                self.df[(self.df['is_bug_related']) & (self.df['confidence'] > 2.0)].shape[0])
            self.medium_confidence_count = int(self.df[(self.df['is_bug_related']) &
                                                       (self.df['confidence'] > 1.5) &
                                                       (self.df['confidence'] <= 2.0)].shape[0])
            self.low_confidence_count = int(
                self.df[(self.df['is_bug_related']) & (self.df['confidence'] <= 1.5)].shape[0])

        # 输出高置信度的分类结果
        high_conf_bugs = self.df[(self.df['is_bug_related']) & (self.df['confidence'] > 2.0)]
        try:
            high_conf_bugs.to_csv("high_confidence_bugs.csv", index=False, encoding='utf-8')
            print(f"已将 {len(high_conf_bugs)} 个高置信度的bug相关issues保存至 high_confidence_bugs.csv")
        except Exception as e:
            print(f"保存高置信度bug数据时出错: {e}")

        # 输出中等置信度的分类结果
        med_conf_bugs = self.df[(self.df['is_bug_related']) &
                                (self.df['confidence'] > 1.5) &
                                (self.df['confidence'] <= 2.0)]
        try:
            med_conf_bugs.to_csv("medium_confidence_bugs.csv", index=False, encoding='utf-8')
            print(f"已将 {len(med_conf_bugs)} 个中等置信度的bug相关issues保存至 medium_confidence_bugs.csv")
        except Exception as e:
            print(f"保存中等置信度bug数据时出错: {e}")

        return report

    def analysis_pipeline(self, input_file="classified_issues.csv", report_file="classification_report.json"):
        """执行完整的分析流水线"""
        # 加载数据
        self.load_data(input_file)

        # 首先进行文本类issues过滤
        print("\n--- 步骤1: 过滤文本类issues ---")
        filtered_count = self.filter_text_issues()

        # 生成低置信度报告
        print("\n--- 步骤2: 生成低置信度报告 ---")
        self.generate_low_confidence_report()

        # 生成统计信息
        self.generate_statistics()

        # 生成可视化
        print("\n--- 步骤3: 生成数据可视化 ---")
        self.generate_visualizations()

        # 生成最终报告
        print("\n--- 步骤4: 生成最终分析报告 ---")
        report = self.generate_final_report(report_file)

        # 打印摘要
        print("\n=== 分析摘要 ===")
        print(f"总issues数: {self.statistics['total_issues']}")
        print(f"Bug相关issues数: {self.statistics['bug_related']} ({self.statistics['bug_percentage']}%)")

        # 使用正确的置信度计数
        print(f"高置信度issues: {self.high_confidence_count}")
        print(f"中置信度issues: {self.medium_confidence_count}")
        print(f"低置信度issues: {self.low_confidence_count}")
        print(f"已过滤文本类issues: {filtered_count}")

        return report


# 如果作为独立脚本运行
if __name__ == "__main__":
    import sys

    # 忽略matplotlib的字体警告
    warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "classified_issues.csv"

    reporter = AnalysisReporter()
    reporter.analysis_pipeline(input_file)

    print("\n分析报告生成完成")