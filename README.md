# Windows 11 真正可用的 HDR 校准软件
![screenshot](https://github.com/forbxy/rwhc/blob/master/app.png)

## 使用方法

1. **获取项目代码**  
   下载或 clone 本项目，并进入项目根目录。

2. **安装 Python**  
   在 Windows 上安装 Python（任选其一）：
   - Microsoft Store
   - 官方网站：<https://www.python.org/downloads/windows/>

3. **安装依赖**  
   在项目根目录下执行：

   ```bash
   pip install -r requirements.txt
   ```

4. **运行程序**

   ```bash
   python app.py
   ```

## 使用说明补充

1. **使用爱色丽校色仪和罗技鼠标**  
   先在设备管理器中将鼠标的驱动更换为 Windows 默认驱动，然后在“服务”中停止 `Logitech LampArray Service`。

2. **使用 Datacolor Spyder 校色仪**  
   先安装 Argyll 驱动程序，然后在设备管理器中找到 Spyder 设备（位于“通用串行总线控制器”下）：
   - 右键设备选择“更新驱动”
   - 选择“浏览我的电脑以查找驱动程序”
   - 选择“让我从计算机的可用驱动程序列表中选取”
   - 从列表中选择 Argyll 驱动

3. **灰阶采样数**  
   10bit HDR 有 1024 级灰阶（R=G=B，范围 0–1023）。程序会在 1024 级灰阶中等距离采集指定数量的灰阶点，并对未测量的灰阶进行插值。  
   采集数量越多，PQ 曲线校准越精准(可能)，但耗时越长。

4. **色彩采样集**  
   程序会在所选色域内生成一个测试集，根据测试集预期 XYZ 与实测 XYZ 进行拟合得到矩阵。  
   - 如果你的屏幕在打开 HDR 后桌面色彩很鲜艳，推荐选择 **sRGB**  
   - 如果颜色偏暗淡，选择 **sRGB + DisplayP3** 通常更好

5. **明亮模式**  
   对生成的 LUT 进行整体提升，适合在强环境光下观看电影。

6. **预览校准结果**  
   当执行了校准后，矩阵和 LUT 会存储在程序中。勾选“预览校准结果”会生成临时 ICC 文件并加载到选中的屏幕，取消勾选则自动移除。  
   未执行校准时，加载的是理想 HDR ICC（BT.2020 色域，10000 nit，无需矩阵和 LUT 校准）。

7. **校准**  
   生成矩阵和 LUT。

8. **测量色准**  
   测量屏幕的色准（若选中“预览校准结果”，会将当前矩阵和 LUT 临时加载到屏幕上再测量）。  
   没有深入验证这个功能的准确性

9. **保存**  
   将矩阵和 LUT 保存为 ICC 配置文件。

## 集成的外部工具

- **色彩生成器**  
  dogegen  
  <https://github.com/ledoge/dogegen>

- **校色设备驱动 / 测量工具**  
  ArgyllCMS `spotread`  
  <https://www.argyllcms.com/>  
  因为displaycal也是使用同的底层，因此驱动问题也可以参考displaycal文档

## 色度计校准说明

色度计需要对应的校准文件，具体可参考：

- ArgyllCMS 文档：<https://www.argyllcms.com/doc/oeminst.html>  
- DisplayCAL 相关教程与文档

## 关于本项目的代码

本项目中有相当一部分代码由 ChatGPT 生成和协助完善。  
如对实现方式有不同的想法，建议先尝试与 ChatGPT 5.1 讨论、验证。

目前项目代码并不完善，后续也**可能不会继续维护**。  
如果有人能将项目中的 **MHC2 校色流程** 移植到 DisplayCAL，那将是非常理想的方案。