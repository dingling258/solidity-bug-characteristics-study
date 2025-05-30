import pandas as pd
import json
import os


class IssueClassifier:
    def __init__(self):
        # 非Bug相关关键词
        self.non_bug_keywords = {
            'documentation': ['typo', 'docs', 'documentation', 'comment', 'grammar', 'spelling',
                              'wording', 'readme', 'link', 'broken link', 'formatting'],
            'style': ['style', 'lint', 'format', 'indentation', 'spacing', 'whitespace'],
            'testing': ['test', 'coverage', 'mock', 'assertion', 'flaky test'],
            'build': ['build', 'script', 'ci', 'npm', 'package', 'dependency', 'hardhat', 'travis']
        }

        # Bug相关关键词，按严重程度分类
        self.bug_keywords = {
            'critical': ['security', 'vulnerability', 'exploit', 'attack', 'critical',
                         'unauthorized', 'hijack', 'compromise'],
            'high': ['bug', 'issue', 'overflow', 'underflow', 'reentrancy', 'access control',
                     'validation'],
            'medium': ['fix', 'problem', 'error', 'incorrect', 'malfunction', 'unsafe'],
            'low': ['enhance', 'improve', 'optimize', 'refactor']
        }

        # DASP分类关键词
        self.dasp_keywords = {
            '重入攻击': ['reentrancy', 'reenter', 'recursive call', 'call after transfer',
                         'callback', 'external call'],
            '访问控制问题': ['access', 'permission', 'authorization', 'owner', 'admin', 'authorize',
                             'ownable', 'privilege', 'role', 'rights', 'authentication'],
            '算术问题': ['overflow', 'underflow', 'arithmetic', 'math', 'calculation', 'div', 'mul',
                         'add', 'sub', 'safe math', 'precision', 'rounding', 'decimal'],
            '未检查的返回值': ['return value', 'unchecked', 'revert', 'result', 'response',
                               'callback', 'success', 'failure'],
            '拒绝服务': ['DOS', 'gas limit', 'out of gas', 'block gas limit', 'memory',
                         'loop', 'array', 'storage', 'consumption'],
            '错误的构造器命名': ['constructor', 'initialize', 'init', 'creation',
                                 'instantiation', 'setup'],
            '操纵区块时间戳': ['timestamp', 'time', 'block.timestamp', 'now', 'date',
                               'deadline', 'timeout'],
            '短地址攻击': ['short address', 'address validation', 'address length',
                           'byte length', 'padding'],
            '未知函数调用': ['delegatecall', 'delegate', 'proxy', 'callcode', 'unknown call',
                             'dynamic call', 'external call', 'indirect call'],
            '默认可见性': ['visibility', 'public', 'private', 'internal', 'external', 'scope',
                           'access modifier']
        }

    def classify_bug_related(self, title, source):
        """判断issue是否与bug相关"""
        title_lower = title.lower()

        # 已知bug标记的直接判定为bug相关
        if source == 'bug':
            return True

        # 检查非bug关键词
        non_bug_match = False
        for category, keywords in self.non_bug_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                non_bug_match = True
                break

        # 检查bug关键词，同时考虑严重性
        bug_match = False
        severity = 'none'
        for level, keywords in self.bug_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                bug_match = True
                severity = level
                break

        # 特殊处理"fix"关键词的含糊案例
        if 'fix' in title_lower and not bug_match and not non_bug_match:
            if any(pattern in title_lower for pattern in ['typo', 'comment', 'doc', 'test', 'format']):
                return False
            elif any(pattern in title_lower for pattern in ['erc', 'token', 'transfer', 'access', 'ownable']):
                return True
            else:
                return True

        # 分析判断结果优先级
        if bug_match and (severity in ['critical', 'high'] or 'security' in title_lower):
            return True
        elif bug_match and not non_bug_match:
            return True
        elif bug_match and non_bug_match:
            if 'doc' in title_lower and not any(
                    word in title_lower for word in ['security', 'vulnerability', 'attack']):
                return False
            else:
                return True
        else:
            return False

    def classify_dasp_category(self, title, is_bug_related):
        """对bug相关的issue进行DASP分类"""
        if not is_bug_related:
            return "非Bug相关", 0

        title_lower = title.lower()

        # 直接关键词匹配
        matches = {}
        for category, keywords in self.dasp_keywords.items():
            matches[category] = sum(1 for keyword in keywords if keyword in title_lower)

        # 找出匹配最多的类别
        if any(matches.values()):
            best_category = max(matches.items(), key=lambda x: x[1])
            return best_category[0], best_category[1]

        # 基于上下文的智能匹配
        if any(word in title_lower for word in ['burn', 'mint', 'transfer', 'balance']):
            return "算术问题", 1
        elif any(word in title_lower for word in ['owner', 'admin', 'role', 'access']):
            return "访问控制问题", 1
        elif any(word in title_lower for word in ['proxy', 'delegate', 'upgrade']):
            return "未知函数调用", 1
        elif any(word in title_lower for word in ['gas', 'memory', 'storage']):
            return "拒绝服务", 1

        # 如果没有匹配，标记为未分类
        return "未分类", 0

    def enhance_confidence(self, row):
        """增强分类置信度评估"""
        category = row['dasp_category']
        confidence = row['confidence']
        title = row['title_lower']

        # 检查是否有明确问题描述
        if 'bug' in title or 'fix' in title:
            confidence += 0.5

        # 在标题中明确提到某个合约名称增加置信度
        for contract in ['erc20', 'erc721', 'erc1155', 'safemath']:
            if contract in title:
                confidence += 0.5
                break

        # 类别特定增强
        if category == '重入攻击' and any(w in title for w in ['callback', 'external call']):
            confidence += 1
        elif category == '算术问题' and any(w in title for w in ['overflow', 'safemath', 'calculation']):
            confidence += 1
        elif category == '访问控制问题' and any(w in title for w in ['admin', 'owner', 'authorize']):
            confidence += 1

        return confidence

    def classify_issues(self, df):
        """对所有issues进行分类"""
        # 添加分类列
        df['is_bug_related'] = df.apply(lambda row: self.classify_bug_related(
            row['title'], row.get('source', '')), axis=1)

        # 只对bug相关的进行DASP分类
        dasp_results = df.apply(
            lambda row: self.classify_dasp_category(row['title'], row['is_bug_related']),
            axis=1
        )
        df['dasp_category'] = [result[0] for result in dasp_results]
        df['confidence'] = [result[1] for result in dasp_results]

        # 增强置信度评估
        df['confidence'] = df.apply(self.enhance_confidence, axis=1)

        return df

    def save_classification(self, df, output_file="classified_issues.csv"):
        """保存分类结果"""
        df.to_csv(output_file, index=False)
        print(f"分类结果已保存至 {output_file}")
        return output_file

    def classify_pipeline(self, input_file, output_file="classified_issues.csv"):
        """执行完整的分类流水线"""
        if not os.path.exists(input_file):
            raise ValueError(f"输入文件 {input_file} 不存在")

        # 读取输入数据
        df = pd.read_csv(input_file)

        # 执行分类
        classified_df = self.classify_issues(df)

        # 保存结果
        return self.save_classification(classified_df, output_file)


# 如果作为独立脚本运行
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "processed_issues.csv"

    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        output_file = "classified_issues.csv"

    classifier = IssueClassifier()
    result_file = classifier.classify_pipeline(input_file, output_file)

    print(f"分类完成，结果保存在 {result_file}")