import pandas as pd
import requests
import time
import os
import re  # 添加这一行
from datetime import datetime

# GitHub API相关参数
REPO_OWNER = 'Uniswap'
REPO_NAME = 'v2-core'
GITHUB_TOKEN = 'YOUR_GITHUB_TOKEN'  # 如果有的话，可以提高API限制

# 输出路径
OUTPUT_DIR = 'D:\\paper\\issues_of_uniswap_v2'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'uniswap_v2_core_merged_prs.xlsx')


def fetch_merged_prs(owner, repo, token=None):
    """使用GitHub API获取所有已合并的PR"""
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

        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            print(f"API请求失败: {response.status_code} - {response.text}")
            break

        prs = response.json()
        if not prs:
            break

        # 过滤出已合并的PR
        merged_prs = [pr for pr in prs if pr.get('merged_at')]
        all_prs.extend(merged_prs)

        page += 1

        # 如果获取的PR数量小于每页数量，说明已经到最后一页
        if len(prs) < per_page:
            break

        # 避免触发GitHub API速率限制
        time.sleep(1)

    print(f"共获取到 {len(all_prs)} 个已合并的PR")
    return all_prs


def extract_pr_data(prs):
    """从PR数据中提取我们需要的信息"""
    pr_data = []

    for pr in prs:
        # 获取PR的额外信息（特别是PR内容）
        pr_detail_url = pr['url']
        headers = {}
        if GITHUB_TOKEN:
            headers['Authorization'] = f'token {GITHUB_TOKEN}'

        detail_response = requests.get(pr_detail_url, headers=headers)
        if detail_response.status_code == 200:
            pr_detail = detail_response.json()
        else:
            print(f"获取PR#{pr['number']}详情失败")
            pr_detail = {}

        # 避免触发GitHub API速率限制
        time.sleep(1)

        # 提取PR的基本信息
        pr_info = {
            'number': pr['number'],
            'title': pr['title'],
            'state': pr['state'],
            'created_at': pr['created_at'],
            'merged_at': pr['merged_at'],
            'body': pr_detail.get('body', ''),
            'labels': ', '.join([label['name'] for label in pr.get('labels', [])]),
            'additions': pr_detail.get('additions', 0),
            'deletions': pr_detail.get('deletions', 0),
            'changed_files': pr_detail.get('changed_files', 0),
            'author': pr['user']['login'],
            'html_url': pr['html_url']
        }

        pr_data.append(pr_info)

    # 创建DataFrame
    df = pd.DataFrame(pr_data)
    return df


def calculate_bug_fix_confidence(row):
    """计算PR是否为bug修复的置信度"""
    confidence = 0

    # 安全获取字段值，处理可能的NaN值
    title = str(row.get('title', '')) if pd.notna(row.get('title', '')) else ""
    body = str(row.get('body', '')) if pd.notna(row.get('body', '')) else ""

    # 转小写
    title = title.lower()
    body = body.lower()

    # 高置信度关键词（标题中）
    high_keywords_title = ['fix', 'bug', 'issue', 'error', 'crash', 'incorrect',
                           'wrong', 'vulnerability', 'exploit', 'security', 'problem',
                           'resolve', 'patch']

    # 中置信度关键词（标题中）
    medium_keywords_title = ['update', 'improve', 'adjust', 'address', 'correct',
                             'handle', 'prevent', 'validate']

    # 高置信度关键词（正文中）
    high_keywords_body = ['fixes #', 'closes #', 'resolves #', 'bugfix', 'fixed a bug',
                          'edge case', 'race condition', 'overflow', 'underflow',
                          'security vulnerability', 'incorrect calculation']

    # 降低置信度的词
    negative_keywords = ['feature', 'enhancement', 'add', 'implement', 'introduce',
                         'support', 'documentation', 'docs', 'refactor', 'cleanup',
                         'style', 'formatting', 'typo']

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

    # 评估代码更改范围
    changes = row.get('additions', 0) + row.get('deletions', 0)
    if changes < 10:  # 小改动更可能是简单修复
        confidence += 10
    elif changes > 100:  # 大改动更可能是特性或重构
        confidence -= 10

    # 评估更改的文件数量
    changed_files = row.get('changed_files', 0)
    if changed_files == 1:  # 单文件更改更可能是简单修复
        confidence += 5
    elif changed_files > 5:  # 多文件更改更可能是特性或重构
        confidence -= 5

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
    print(f"开始获取和分析Uniswap/v2-core已合并的PR...")

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