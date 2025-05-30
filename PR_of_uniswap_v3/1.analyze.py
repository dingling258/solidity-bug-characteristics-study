import pandas as pd
import requests
import time
import os
import re
import json
from datetime import datetime

# GitHub API相关参数
REPO_OWNER = 'Uniswap'
REPO_NAME = 'v3-core'
GITHUB_TOKEN = 'YOUR_GITHUB_TOKEN'

# 输出路径
OUTPUT_DIR = 'D:\\paper\\issues_of_uniswap_v3'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'uniswap_v3_core_merged_prs.xlsx')
CACHE_FILE = os.path.join(OUTPUT_DIR, 'pr_cache.json')  # 添加缓存文件

# 请求重试配置
MAX_RETRIES = 5
RETRY_DELAY = 3  # 秒


def fetch_merged_prs(owner, repo, token=None):
    """使用GitHub API获取所有已合并的PR"""
    # 首先检查是否有缓存
    if os.path.exists(CACHE_FILE):
        print(f"找到缓存文件，正在加载...")
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                all_prs = json.load(f)
            print(f"成功从缓存加载 {len(all_prs)} 个PR")
            return all_prs
        except Exception as e:
            print(f"加载缓存失败: {e}")

    all_prs = []
    page = 1
    per_page = 100

    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'

    while True:
        print(f"获取第{page}页PR...")
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        params = {
            'state': 'closed',
            'per_page': per_page,
            'page': page
        }

        # 添加重试逻辑
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()  # 抛出异常，如果请求失败
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                    print(f"等待 {RETRY_DELAY} 秒后重试...")
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"请求失败，已达到最大重试次数: {e}")
                    # 保存已获取的PRs
                    if all_prs:
                        print(f"保存已获取的 {len(all_prs)} 个PR到缓存...")
                        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                            json.dump(all_prs, f, ensure_ascii=False, indent=2)
                    return all_prs

        if response.status_code != 200:
            print(f"API请求失败: {response.status_code} - {response.text}")
            break

        prs = response.json()
        if not prs:
            break

        # 过滤出已合并的PR (在这个阶段只获取基本信息)
        for pr in prs:
            if pr.get('merged_at'):
                # 只保留必要的字段，减少内存占用
                simplified_pr = {
                    'number': pr['number'],
                    'title': pr['title'],
                    'url': pr['url'],
                    'html_url': pr['html_url'],
                    'state': pr['state'],
                    'created_at': pr['created_at'],
                    'merged_at': pr['merged_at'],
                    'user': {'login': pr['user']['login']},
                    'labels': pr.get('labels', [])
                }
                all_prs.append(simplified_pr)

        page += 1

        # 如果获取的PR数量小于每页数量，说明已经到最后一页
        if len(prs) < per_page:
            break

        # 避免触发GitHub API速率限制
        time.sleep(1)

    print(f"共获取到 {len(all_prs)} 个已合并的PR")

    # 保存到缓存文件
    print("保存PR数据到缓存文件...")
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_prs, f, ensure_ascii=False, indent=2)

    return all_prs


def extract_pr_data(prs):
    """从PR数据中提取我们需要的信息，批量获取PR详情"""
    # 先把基础数据整理出来
    pr_data = []
    for pr in prs:
        pr_info = {
            'number': pr['number'],
            'title': pr['title'],
            'state': pr['state'],
            'created_at': pr['created_at'],
            'merged_at': pr['merged_at'],
            'body': '',  # 稍后填充
            'labels': ', '.join([label['name'] for label in pr.get('labels', [])]),
            'additions': 0,  # 稍后填充
            'deletions': 0,  # 稍后填充
            'changed_files': 0,  # 稍后填充
            'author': pr['user']['login'],
            'html_url': pr['html_url']
        }
        pr_data.append(pr_info)

    # 创建DataFrame
    df = pd.DataFrame(pr_data)

    # 如果数据量太大，可以跳过详细信息获取
    if len(prs) > 300:
        print(f"PR数量过多 ({len(prs)}), 跳过获取详细信息...")
        print("将只基于标题和标签进行分析.")
        return df

    # 添加详细信息获取的设置选项
    fetch_details = input("是否获取PR的详细信息？这将耗费更多时间 (y/n, 默认n): ").strip().lower()
    if fetch_details != 'y':
        print("跳过获取PR详细信息，将只基于基本信息进行分析...")
        return df

    # 批量获取PR详情
    print("\n开始获取PR详细信息...")

    # 对所有PR进行分批处理
    batch_size = 10  # 每次处理10个PR
    num_batches = (len(prs) + batch_size - 1) // batch_size

    for batch_idx in range(num_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(prs))

        print(f"\n处理批次 {batch_idx + 1}/{num_batches} (PR {start_idx + 1}-{end_idx}/{len(prs)})...")

        # 处理当前批次
        for i in range(start_idx, end_idx):
            pr = prs[i]
            pr_number = pr['number']

            print(f"  获取PR #{pr_number} 详情...")

            # 获取PR详情
            headers = {}
            if GITHUB_TOKEN:
                headers['Authorization'] = f'token {GITHUB_TOKEN}'

            # 添加重试逻辑
            detail_url = pr['url']
            for attempt in range(MAX_RETRIES):
                try:
                    detail_response = requests.get(detail_url, headers=headers, timeout=30)
                    detail_response.raise_for_status()
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        print(f"  获取详情失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                        print(f"  等待 {RETRY_DELAY} 秒后重试...")
                        time.sleep(RETRY_DELAY)
                    else:
                        print(f"  获取详情失败，已达到最大重试次数: {e}")
                        continue

            if detail_response.status_code != 200:
                print(f"  获取PR#{pr_number}详情失败: {detail_response.status_code}")
                continue

            pr_detail = detail_response.json()

            # 更新DataFrame中的值
            idx = df['number'] == pr_number
            df.loc[idx, 'body'] = pr_detail.get('body', '')
            df.loc[idx, 'additions'] = pr_detail.get('additions', 0)
            df.loc[idx, 'deletions'] = pr_detail.get('deletions', 0)
            df.loc[idx, 'changed_files'] = pr_detail.get('changed_files', 0)

            # 避免触发GitHub API速率限制
            time.sleep(1)

        # 每批次结束后保存一次，防止中途出错
        print("  保存当前进度...")
        with pd.ExcelWriter(OUTPUT_FILE.replace('.xlsx', '_progress.xlsx')) as writer:
            df.to_excel(writer, index=False)

        # 批次间休息，避免过于频繁的请求
        if batch_idx < num_batches - 1:
            print(f"批次完成，休息5秒...")
            time.sleep(5)

    return df


def calculate_bug_fix_confidence(row):
    """计算PR是否为bug修复的置信度"""
    confidence = 0

    # 安全获取字段值，处理可能的NaN值
    title = str(row.get('title', '')) if pd.notna(row.get('title', '')) else ""
    body = str(row.get('body', '')) if pd.notna(row.get('body', '')) else ""
    labels = str(row.get('labels', '')) if pd.notna(row.get('labels', '')) else ""

    # 转小写
    title = title.lower()
    body = body.lower()
    labels = labels.lower()

    # v3特有的关键词
    v3_keywords = ['v3', 'v3-core', 'pool', 'tick', 'sqrt price', 'fee tier',
                   'concentrated liquidity', 'range', 'position', 'oracle',
                   'swap', 'mint', 'burn', 'flash']

    # 高置信度关键词（标题中）
    high_keywords_title = ['fix', 'bug', 'issue', 'error', 'crash', 'incorrect',
                           'wrong', 'vulnerability', 'exploit', 'security', 'problem',
                           'resolve', 'patch', 'overflow', 'underflow']

    # 中置信度关键词（标题中）
    medium_keywords_title = ['update', 'improve', 'adjust', 'address', 'correct',
                             'handle', 'prevent', 'validate', 'edge case']

    # 高置信度关键词（正文中）
    high_keywords_body = ['fixes #', 'closes #', 'resolves #', 'bugfix', 'fixed a bug',
                          'edge case', 'race condition', 'overflow', 'underflow',
                          'security vulnerability', 'incorrect calculation',
                          'off-by-one', 'rounding error']

    # 降低置信度的词
    negative_keywords = ['feature', 'enhancement', 'add', 'implement', 'introduce',
                         'support', 'documentation', 'docs', 'refactor', 'cleanup',
                         'style', 'formatting', 'typo', 'test']

    # 标签中的关键词
    high_confidence_labels = ['bug', 'fix', 'security', 'vulnerability']
    medium_confidence_labels = ['enhancement', 'improvement']
    low_confidence_labels = ['documentation', 'refactor', 'style', 'test']

    # 检查标签
    for label in high_confidence_labels:
        if label in labels:
            confidence += 25
            break

    for label in medium_confidence_labels:
        if label in labels:
            confidence += 10
            break

    for label in low_confidence_labels:
        if label in labels:
            confidence -= 15
            break

    # 检查标题中的高置信度关键词
    for keyword in high_keywords_title:
        if keyword in title:
            confidence += 20
            break  # 找到一个就足够

    # 检查标题中的中置信度关键词
    for keyword in medium_keywords_title:
        if keyword in title:
            confidence += 10
            break  # 找到一个就足够

    # 检查正文中的高置信度关键词
    for keyword in high_keywords_body:
        if keyword in body:
            confidence += 15
            break  # 找到一个就足够

    # 检查正文中是否引用了issue编号
    issue_refs = []
    issue_patterns = [
        r'(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#(\d+)',
        r'(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+\w+/\w+#(\d+)'
    ]
    for pattern in issue_patterns:
        matches = re.findall(pattern, body, re.IGNORECASE)
        issue_refs.extend(matches)

    if issue_refs:
        confidence += 25

    # 检查降低置信度的词
    for keyword in negative_keywords:
        if keyword in title.lower():
            confidence -= 15
            break  # 找到一个就足够

    # 评估代码更改范围（只有当有详细信息时才评估）
    if pd.notna(row.get('additions', 0)) and pd.notna(row.get('deletions', 0)):
        changes = row.get('additions', 0) + row.get('deletions', 0)
        if changes < 10:  # 小改动更可能是简单修复
            confidence += 10
        elif changes > 100:  # 大改动更可能是特性或重构
            confidence -= 10

    # 评估更改的文件数量（只有当有详细信息时才评估）
    if pd.notna(row.get('changed_files', 0)):
        changed_files = row.get('changed_files', 0)
        if changed_files == 1:  # 单文件更改更可能是简单修复
            confidence += 5
        elif changed_files > 5:  # 多文件更改更可能是特性或重构
            confidence -= 5

    # v3特有的加分
    for keyword in v3_keywords:
        if keyword in title or keyword in body:
            confidence += 2  # 每个v3相关的关键词稍微增加一点置信度
            break  # 只加一次

    # 合约改动相关关键词
    contract_keywords = ['contract', 'solidity', 'function', 'variable', 'struct',
                         'library', 'interface', 'inheritance', 'gas', 'optimiz']

    for keyword in contract_keywords:
        if keyword in title or keyword in body:
            confidence += 2  # 每个合约相关的关键词稍微增加一点置信度
            break  # 只加一次

    # 确保置信度在0-100之间
    confidence = max(0, min(confidence, 100))

    return confidence


def analyze_prs(df):
    """分析PR数据，计算bug修复置信度"""
    # 计算置信度
    print("\n计算bug修复置信度...")
    df['bug_fix_confidence'] = df.apply(calculate_bug_fix_confidence, axis=1)

    # 根据置信度分类
    df['confidence_level'] = pd.cut(
        df['bug_fix_confidence'],
        bins=[0, 30, 60, 100],
        labels=['低', '中', '高']
    )

    # 统计各置信度级别的数量
    confidence_counts = df['confidence_level'].value_counts().sort_index()
    print("\n按置信度分类的PR数量:")
    for level, count in confidence_counts.items():
        print(f"  {level}置信度: {count}个")

    return df


def save_results(df):
    """保存分析结果到Excel文件"""
    # 按置信度降序排序
    df_sorted = df.sort_values('bug_fix_confidence', ascending=False)

    # 保存到Excel
    with pd.ExcelWriter(OUTPUT_FILE) as writer:
        # 所有PR的摘要
        df_sorted.to_excel(writer, sheet_name='所有已合并PR', index=False)

        # 高置信度的PR
        high_conf = df_sorted[df_sorted['confidence_level'] == '高']
        if len(high_conf) > 0:
            high_conf.to_excel(writer, sheet_name='高置信度-可能的bug修复', index=False)

        # 中置信度的PR
        medium_conf = df_sorted[df_sorted['confidence_level'] == '中']
        if len(medium_conf) > 0:
            medium_conf.to_excel(writer, sheet_name='中置信度', index=False)

    print(f"\n分析结果已保存到: {OUTPUT_FILE}")

    # 打印高置信度PR的摘要
    if len(high_conf) > 0:
        print("\n高置信度的潜在bug修复PR (前10个):")
        for i, (_, row) in enumerate(high_conf.iterrows()):
            if i < 10:  # 只显示前10个
                print(f"#{row['number']}: {row['title']} [置信度: {row['bug_fix_confidence']:.0f}]")
        if len(high_conf) > 10:
            print(f"... 以及其他 {len(high_conf) - 10} 个高置信度PR (详见Excel文件)")

    return OUTPUT_FILE


def main():
    print(f"开始获取和分析Uniswap/v3-core已合并的PR...")

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 获取已合并的PR
    prs = fetch_merged_prs(REPO_OWNER, REPO_NAME, GITHUB_TOKEN)

    if not prs:
        print("未获取到任何PR，程序终止")
        return

    # 提取PR数据
    df = extract_pr_data(prs)

    # 分析PR
    df = analyze_prs(df)

    # 保存结果
    output_file = save_results(df)

    print(f"\n分析完成！高置信度和中置信度的PR已准备好进行人工审核")
    print(f"请查看 {output_file} 获取完整结果")


if __name__ == "__main__":
    main()