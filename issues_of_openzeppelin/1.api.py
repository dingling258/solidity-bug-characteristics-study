import requests
import pandas as pd
from datetime import datetime
import time

# GitHub API配置
BASE_URL = "https://api.github.com"
REPO = "OpenZeppelin/openzeppelin-contracts"
TOKEN = "YOUR_GITHUB_TOKEN"

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# 基础查询参数
params = {
    "state": "all",  # 获取所有状态的issue
    "per_page": 100  # 每页最大条数
}


def test_api_connection():
    """测试API连接和令牌有效性"""
    test_response = requests.get(f"{BASE_URL}/rate_limit", headers=headers)
    if test_response.status_code == 200:
        print("API连接成功!")
        rate_limit = test_response.json()
        print(f"API调用限制信息：")
        print(f"核心API剩余请求数: {rate_limit['resources']['core']['remaining']}")
        print(f"搜索API剩余请求数: {rate_limit['resources']['search']['remaining']}")
        return True
    else:
        print(f"API连接失败! 状态码: {test_response.status_code}")
        print(f"错误信息: {test_response.text}")
        return False


def fetch_issues(page=1):
    """获取单页issues"""
    url = f"{BASE_URL}/repos/{REPO}/issues"
    params["page"] = page
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"获取第{page}页失败! 状态码: {response.status_code}")
        return []


def get_first_page_issues():
    """获取第一页issues并打印基本信息"""
    issues = fetch_issues(page=1)
    print(f"\n成功获取第一页issues，共{len(issues)}条")

    if issues:
        print("\n前5个issues的标题：")
        for issue in issues[:5]:
            print(f"#{issue['number']}: {issue['title']}")


if __name__ == "__main__":
    # 先测试API连接
    if test_api_connection():
        # 如果连接成功，获取第一页数据
        get_first_page_issues()


        def fetch_all_issues():
            """获取所有issues"""
            all_issues = []
            page = 1
            while True:
                print(f"正在获取第{page}页...")
                issues = fetch_issues(page)

                if not issues:
                    break

                all_issues.extend(issues)
                page += 1

                # 简单的进度显示
                print(f"已获取{len(all_issues)}条issues")

                # 检查是否还有下一页
                if len(issues) < 100:  # 如果返回的数据少于每页最大数，说明是最后一页
                    break

                # 避免触发GitHub API限制
                time.sleep(1)

            return all_issues


        def process_issues(issues):
            """处理和分析issues数据"""
            processed_data = []

            for issue in issues:
                # 提取关键信息
                issue_data = {
                    'number': issue['number'],
                    'title': issue['title'],
                    'state': issue['state'],
                    'created_at': issue['created_at'],
                    'closed_at': issue.get('closed_at'),
                    'labels': [label['name'] for label in issue['labels']],
                    'is_pull_request': 'pull_request' in issue,
                    'body': issue.get('body', '')
                }

                # 检查是否包含bug/fix相关关键词
                keywords = ['bug', 'fix', 'error', 'issue', 'vulnerability', 'security']
                issue_data['is_bug_related'] = any(
                    keyword in issue['title'].lower() or
                    (issue['body'] and keyword in issue['body'].lower())
                    for keyword in keywords
                )

                processed_data.append(issue_data)

            return pd.DataFrame(processed_data)


        def analyze_data(df):
            """分析处理后的数据"""
            print("\n数据分析结果:")
            print(f"总issues数量: {len(df)}")
            print(f"bug相关issues数量: {df['is_bug_related'].sum()}")
            print(f"开放状态的issues数量: {len(df[df['state'] == 'open'])}")

            print("\n标签统计:")
            all_labels = [label for labels in df['labels'] for label in labels]
            label_counts = pd.Series(all_labels).value_counts()
            print(label_counts.head())

            return df


        if __name__ == "__main__":
            # 测试API连接
            if test_api_connection():
                # 获取所有issues
                print("\n开始获取所有issues...")
                all_issues = fetch_all_issues()

                # 处理数据
                print("\n处理数据...")
                df = process_issues(all_issues)

                # 分析数据
                df = analyze_data(df)

                # 保存数据
                print("\n保存数据到CSV文件...")
                df.to_csv('openzeppelin_issues.csv', index=False)
                print("数据已保存到 openzeppelin_issues.csv")