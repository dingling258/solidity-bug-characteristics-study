import openpyxl
import pandas as pd

def analyze_keyword(df, keyword):
    """分析特定关键词在标题中的出现情况"""
    # 只在标题中搜索关键词
    mask = df['title'].str.lower().str.contains(keyword.lower(), na=False)
    matching_issues = df[mask]

    print(f"\n以 '{keyword}' 为关键词的 issues ({len(matching_issues)}个):")
    for _, row in matching_issues.iterrows():
        print(f"#{row['number']}: {row['title']}")

    return matching_issues[['number', 'title']]  # 只返回需要的列


def main():
    # 读取CSV文件
    df = pd.read_csv('openzeppelin_issues.csv')

    # 分析每个关键词
    keywords = ['fix', 'bug', 'problem']
    results = {}

    # 创建一个字典来存储每个关键词的结果
    all_results = {}

    for keyword in keywords:
        matching_df = analyze_keyword(df, keyword)
        all_results[f'{keyword}_issues'] = matching_df

        # 打印总结
        print(f"\n以 '{keyword}' 为关键词的 issues 总数: {len(matching_df)}")

    # 将结果保存到一个Excel文件中，每个关键词一个sheet
    with pd.ExcelWriter('keyword_analysis_results.xlsx') as writer:
        for keyword, result_df in all_results.items():
            result_df.to_excel(writer, sheet_name=keyword, index=False)

    print("\n分析结果已保存到 'keyword_analysis_results.xlsx'")


if __name__ == "__main__":
    main()