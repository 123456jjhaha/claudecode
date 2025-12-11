"""
监督学习简单示例：房价预测
使用线性回归模型根据房屋面积预测房价
"""

import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

# 1. 准备训练数据
# 房屋面积(平方米) 和 对应价格(万元)
np.random.seed(42)
areas = np.array([50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160]).reshape(-1, 1)
prices = np.array([150, 180, 210, 240, 270, 300, 330, 360, 390, 420, 450, 480]) + np.random.normal(0, 10, 12)

print("训练数据：")
for i, (area, price) in enumerate(zip(areas.flatten(), prices)):
    print(f"房屋 {i+1}: 面积 = {area}m², 价格 = {price:.1f}万元")

# 2. 数据可视化
plt.figure(figsize=(10, 6))
plt.scatter(areas, prices, color='blue', alpha=0.7, label='训练数据')
plt.xlabel('房屋面积 (m²)')
plt.ylabel('房价 (万元)')
plt.title('房屋面积与房价关系图')
plt.grid(True, alpha=0.3)
plt.legend()

# 3. 创建并训练线性回归模型
model = LinearRegression()
model.fit(areas, prices)

# 4. 模型评估
train_score = model.score(areas, prices)
print(f"\n模型训练完成！")
print(f"模型得分 (R²): {train_score:.4f}")
print(f"回归系数 (每平方米价格): {model.coef_[0]:.2f}万元/m²")
print(f"截距 (基础价格): {model.intercept_:.2f}万元")

# 5. 绘制回归线
plt.plot(areas, model.predict(areas), color='red', linewidth=2, label='预测模型')
plt.legend()

# 6. 预测新数据
test_areas = np.array([65, 95, 125, 155]).reshape(-1, 1)
predicted_prices = model.predict(test_areas)

print(f"\n房价预测结果：")
for area, price in zip(test_areas.flatten(), predicted_prices):
    print(f"面积 {area}m² 的房屋预测价格: {price:.1f}万元")

# 7. 保存图表
plt.tight_layout()
plt.savefig('/root/myai/claude_agent_system/instances/example_agent/house_price_prediction.png', dpi=300, bbox_inches='tight')
print(f"\n预测图表已保存为 house_price_prediction.png")

plt.show()

# 8. 模型验证
print(f"\n模型验证：")
print(f"均方误差 (MSE): {mean_squared_error(prices, model.predict(areas)):.2f}")
print(f"决定系数 (R²): {r2_score(prices, model.predict(areas)):.4f}")

print(f"\n监督学习的关键要素：")
print(f"1. 标注数据：我们有已知的房屋面积和对应价格")
print(f"2. 特征 (Features): 房屋面积")
print(f"3. 标签 (Labels): 房屋价格")
print(f"4. 模型训练：使用已知数据学习面积与价格的关系")
print(f"5. 预测：用训练好的模型预测新房屋的价格")