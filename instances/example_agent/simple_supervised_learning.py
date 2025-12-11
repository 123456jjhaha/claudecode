"""
监督学习核心概念演示
用简单的数学例子理解监督学习的工作原理
"""

import numpy as np

def simple_supervised_learning_example():
    """
    简单的监督学习例子：学习加法关系
    """
    print("=" * 50)
    print("监督学习核心概念演示")
    print("=" * 50)

    # 1. 训练数据 (已知输入和正确输出)
    print("\n1. 训练数据 (有标签的数据):")
    training_data = [
        ([2, 3], 5),    # 2 + 3 = 5
        ([4, 1], 5),    # 4 + 1 = 5
        ([7, 2], 9),    # 7 + 2 = 9
        ([1, 8], 9),    # 1 + 8 = 9
        ([5, 5], 10),   # 5 + 5 = 10
        ([3, 6], 9),    # 3 + 6 = 9
        ([8, 1], 9),    # 8 + 1 = 9
        ([6, 4], 10)    # 6 + 4 = 10
    ]

    for i, (inputs, target) in enumerate(training_data):
        print(f"   样本 {i+1}: 输入 {inputs} → 目标输出 {target}")

    # 2. "学习"过程 - 寻找模式
    print("\n2. 学习过程:")
    print("   观察模式：所有样本中，目标输出 = 第一个数 + 第二个数")
    print("   发现规律：输出 = 输入[0] + 输入[1]")

    # 3. 定义模型函数
    def learned_model(inputs):
        """学习到的加法模型"""
        return inputs[0] + inputs[1]

    print("\n3. 模型函数:")
    print("   def learned_model(inputs):")
    print("       return inputs[0] + inputs[1]")

    # 4. 验证模型在训练数据上的表现
    print("\n4. 模型验证:")
    for i, (inputs, target) in enumerate(training_data):
        prediction = learned_model(inputs)
        correct = "✓" if prediction == target else "✗"
        print(f"   样本 {i+1}: {inputs} → 预测 {prediction} (目标 {target}) {correct}")

    # 5. 预测新数据
    print("\n5. 预测新数据:")
    test_cases = [
        [10, 15],   # 预期: 25
        [3, 7],     # 预期: 10
        [12, 8],    # 预期: 20
        [0, 5]      # 预期: 5
    ]

    for test_input in test_cases:
        prediction = learned_model(test_input)
        print(f"   输入 {test_input} → 预测输出 {prediction}")

def supervised_learning_components():
    """
    说明监督学习的关键组成部分
    """
    print("\n" + "=" * 50)
    print("监督学习的关键组成部分")
    print("=" * 50)

    components = [
        ("1. 训练数据", "包含输入特征和对应正确标签的数据集"),
        ("2. 特征 (Features)", "用来做预测的输入变量"),
        ("3. 标签 (Labels)", "要预测的目标变量"),
        ("4. 模型", "学习特征和标签之间关系的数学函数"),
        ("5. 损失函数", "衡量模型预测与实际标签差异的函数"),
        ("6. 学习算法", "通过最小化损失函数来调整模型参数的方法"),
        ("7. 验证", "评估模型在未见数据上表现的过程")
    ]

    for name, description in components:
        print(f"\n{name}:")
        print(f"   {description}")

def real_world_applications():
    """
    列出监督学习的真实应用场景
    """
    print("\n" + "=" * 50)
    print("监督学习的真实应用场景")
    print("=" * 50)

    applications = {
        "分类问题": [
            "垃圾邮件检测 → 是/否垃圾邮件",
            "图像识别 → 猫/狗/鸟/汽车",
            "医疗诊断 → 患病/健康",
            "信用评分 → 高风险/低风险"
        ],
        "回归问题": [
            "房价预测 → 具体房价数值",
            "股票预测 → 未来价格",
            "销售额预测 → 具体销售额",
            "温度预测 → 具体温度值"
        ]
    }

    for category, examples in applications.items():
        print(f"\n{category}:")
        for example in examples:
            print(f"   • {example}")

if __name__ == "__main__":
    simple_supervised_learning_example()
    supervised_learning_components()
    real_world_applications()

    print("\n" + "=" * 50)
    print("总结")
    print("=" * 50)
    print("监督学习的核心思想：")
    print("1. 从有标签的数据中学习模式")
    print("2. 建立输入特征与输出标签之间的映射关系")
    print("3. 用学习到的模型对新的、未见的数据进行预测")
    print("4. 关键是要有高质量的标注数据作为学习基础")