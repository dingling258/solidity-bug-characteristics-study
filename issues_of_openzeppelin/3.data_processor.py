import pandas as pd
import os
import chardet
import io
import csv
from openpyxl import load_workbook


class DataProcessor:
    def __init__(self):
        self.input_files = []
        self.combined_df = None

    def add_input_file(self, file_path, source_label=None):
        """添加输入文件到处理列表"""
        self.input_files.append((file_path, source_label or os.path.basename(file_path).split('.')[0]))

    def detect_file_type(self, file_path):
        """检测文件类型"""
        with open(file_path, 'rb') as f:
            header = f.read(4)

        # Excel文件的标志
        if header.startswith(b'PK'):
            return 'xlsx'
        # CSV文件可能的起始
        elif any(header.startswith(x) for x in [b',', b';', b'\t', b'"', b"'"]):
            return 'csv'
        else:
            # 尝试更详细的检测
            with open(file_path, 'rb') as f:
                content = f.read(500)
                if b'docProps' in content and b'xl/' in content:
                    return 'xlsx'
                elif all(0x20 <= byte <= 0x7E or byte in [0x0A, 0x0D, 0x09] for byte in content):
                    return 'csv'  # 可能是ASCII文本
                else:
                    return 'unknown'

    def read_excel_file(self, file_path):
        """读取Excel文件"""
        try:
            print(f"尝试使用pandas读取Excel文件 {file_path}")
            df = pd.read_excel(file_path)
            return df
        except Exception as e:
            print(f"pandas读取Excel失败: {e}")

            try:
                print(f"尝试使用openpyxl读取Excel文件 {file_path}")
                # 使用openpyxl更灵活地读取
                wb = load_workbook(file_path)
                sheet = wb.active

                data = []
                for row in sheet.rows:
                    data.append([cell.value for cell in row])

                if not data:
                    print(f"Excel文件 {file_path} 没有数据")
                    return None

                headers = data[0]
                rows = data[1:]

                result_data = {header: [] for header in headers if header is not None}
                for row in rows:
                    for i, value in enumerate(row):
                        if i < len(headers) and headers[i] is not None:
                            result_data[headers[i]].append(value)

                return pd.DataFrame(result_data)
            except Exception as e2:
                print(f"openpyxl读取Excel失败: {e2}")
                return None

    def read_csv_file(self, file_path):
        """读取CSV文件"""
        try:
            # 检测编码
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'latin1'

            # 尝试不同的分隔符
            for sep in [',', ';', '\t', '|']:
                try:
                    df = pd.read_csv(file_path, sep=sep, encoding=encoding)
                    if len(df.columns) > 1:
                        return df
                except:
                    continue

            # 所有标准尝试失败，试试更灵活的方法
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()

            # 尝试手动分析
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(content[:1024])
                reader = csv.reader(io.StringIO(content), dialect)
                rows = list(reader)

                if not rows:
                    return None

                headers = rows[0]
                data = {header: [] for header in headers}

                for row in rows[1:]:
                    for i, value in enumerate(row):
                        if i < len(headers):
                            data[headers[i]].append(value)

                return pd.DataFrame(data)
            except:
                return None
        except Exception as e:
            print(f"读取CSV文件失败: {e}")
            return None

    def read_input_file(self, file_path):
        """智能读取输入文件，自动判断文件类型"""
        if not os.path.exists(file_path):
            print(f"文件 {file_path} 不存在")
            return None

        print(f"\n处理文件: {file_path}")
        file_type = self.detect_file_type(file_path)
        print(f"检测到文件类型: {file_type}")

        if file_type == 'xlsx':
            return self.read_excel_file(file_path)
        elif file_type == 'csv':
            return self.read_csv_file(file_path)
        else:
            print(f"未知文件类型，尝试作为Excel和CSV都处理")
            df = self.read_excel_file(file_path)
            if df is None:
                df = self.read_csv_file(file_path)
            return df

    def merge_datasets(self):
        """合并所有输入数据集"""
        dataframes = []

        for file_path, source_label in self.input_files:
            df = self.read_input_file(file_path)

            if df is not None and not df.empty:
                # 确保存在必需的列
                if 'number' not in df.columns or 'title' not in df.columns:
                    print(f"警告: 文件 {file_path} 缺少必需的列 (number, title)")

                    # 尝试查找可能的替代列名
                    possible_number_cols = ['number', 'num', 'id', 'issue', 'issue_id', '#']
                    possible_title_cols = ['title', 'name', 'description', 'summary', 'subject']

                    # 尝试映射列
                    number_col = None
                    for col in possible_number_cols:
                        if col in df.columns:
                            number_col = col
                            break

                    title_col = None
                    for col in possible_title_cols:
                        if col in df.columns:
                            title_col = col
                            break

                    # 重命名或创建必要的列
                    if number_col and number_col != 'number':
                        df['number'] = df[number_col]
                    elif 'number' not in df.columns:
                        df['number'] = range(1, len(df) + 1)

                    if title_col and title_col != 'title':
                        df['title'] = df[title_col]
                    elif 'title' not in df.columns:
                        df['title'] = f"Unknown title from {source_label}"

                # 添加来源标记
                df['source'] = source_label
                dataframes.append(df)
                print(f"成功读取 {file_path}，包含 {len(df)} 行数据")
            else:
                print(f"错误: 无法读取文件 {file_path} 或文件为空")

        if not dataframes:
            # 如果没有有效数据，创建一个示例数据集
            print("没有有效的输入文件，创建示例数据集...")
            sample_data = {
                'number': [1, 2, 3],
                'title': ['示例问题1', '示例问题2', '示例问题3'],
                'source': ['sample', 'sample', 'sample']
            }
            self.combined_df = pd.DataFrame(sample_data)
        else:
            # 合并有效的数据集
            self.combined_df = pd.concat(dataframes, ignore_index=True)

            # 去除重复
            self.combined_df = self.combined_df.drop_duplicates(subset=['number'])

            # 按issue编号排序
            try:
                self.combined_df['number'] = pd.to_numeric(self.combined_df['number'], errors='coerce')
                self.combined_df = self.combined_df.sort_values('number', ascending=False)
            except Exception as e:
                print(f"排序时出错: {e}")

        return self.combined_df

    def enhance_features(self):
        """从标题中提取特征"""
        if self.combined_df is None:
            raise ValueError("请先合并数据集。")

        # 确保title列是字符串类型
        self.combined_df['title'] = self.combined_df['title'].astype(str)

        # 标题转小写
        self.combined_df['title_lower'] = self.combined_df['title'].str.lower()

        # 提取合约名称特征
        contract_patterns = ['ERC20', 'ERC721', 'ERC1155', 'SafeMath', 'AccessControl',
                             'Governor', 'Ownable', 'Proxy', 'TimeLock', 'Merkle']
        for pattern in contract_patterns:
            self.combined_df[f'has_{pattern.lower()}'] = self.combined_df['title_lower'].str.contains(
                pattern.lower(), regex=False)

        # 提取操作类型特征
        operation_patterns = ['transfer', 'approve', 'mint', 'burn', 'initialize', 'deploy',
                              'upgrade', 'delegatecall', 'verify', 'validate']
        for pattern in operation_patterns:
            self.combined_df[f'op_{pattern}'] = self.combined_df['title_lower'].str.contains(
                pattern, regex=False)

        return self.combined_df

    def save_processed_data(self, output_file="processed_issues.csv"):
        """保存处理过的数据"""
        if self.combined_df is None:
            raise ValueError("没有数据可保存。")

        try:
            self.combined_df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"处理后的数据已保存至 {output_file}")
        except Exception as e:
            print(f"保存数据时出错: {e}")
            # 尝试降级保存（只保存最重要的列）
            try:
                essential_cols = ['number', 'title', 'source', 'title_lower']
                cols_to_save = [col for col in essential_cols if col in self.combined_df.columns]
                self.combined_df[cols_to_save].to_csv(output_file, index=False, encoding='utf-8')
                print(f"已保存简化版数据至 {output_file}")
            except Exception as e2:
                print(f"保存简化版数据时也出错: {e2}")
                return None

        return output_file

    def print_file_info(self, file_path):
        """打印文件的基本信息，用于调试"""
        if not os.path.exists(file_path):
            print(f"文件 {file_path} 不存在")
            return

        try:
            print(f"\n===== 文件 {file_path} 信息 =====")
            print(f"文件大小: {os.path.getsize(file_path)} 字节")

            # 尝试读取前几行
            with open(file_path, 'rb') as f:
                content = f.read(500)  # 读取前500字节

            print(f"文件前500字节的十六进制表示:")
            for i in range(0, len(content), 16):
                chunk = content[i:i + 16]
                hex_repr = ' '.join(f'{b:02x}' for b in chunk)
                ascii_repr = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                print(f"{i:04x}: {hex_repr.ljust(48)} | {ascii_repr}")

            print("============================\n")
        except Exception as e:
            print(f"获取文件信息时出错: {e}")

    def process_pipeline(self, output_file="processed_issues.csv"):
        """执行完整的数据处理流水线"""
        # 打印每个输入文件的信息
        for file_path, _ in self.input_files:
            self.print_file_info(file_path)

        # 合并数据集
        self.merge_datasets()

        # 增强特征
        try:
            self.enhance_features()
        except Exception as e:
            print(f"增强特征时出错: {e}")

        # 保存处理后的数据
        return self.save_processed_data(output_file)


# 如果作为独立脚本运行
if __name__ == "__main__":
    processor = DataProcessor()

    # 添加所有输入文件
    processor.add_input_file("fix_issues.csv", "fix")
    processor.add_input_file("bug_issues.csv", "bug")
    processor.add_input_file("problem_issues.csv", "problem")

    # 执行处理流水线
    processed_file = processor.process_pipeline()

    if processed_file:
        print(f"数据预处理完成，结果保存在 {processed_file}")
    else:
        print("数据预处理失败")