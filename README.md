# Agent-for-Docker-Xunlei

Docker迅雷的下载助手，解决批量磁力链接下载与批量电视剧重命名与移动。由于每个磁力文件名称的不确定性，该项目需要人工介入，保证省去重复人工劳动。

## 功能特性

- **磁力链接批量下载**：
  - 无需迅雷会员即可批量下载磁力。
- **文件批量移动**：
  - 由于多条磁力链接（一般为电视剧下载），会创建多个文件夹，每个文件夹下为一集，人工移动文件费时费力，因此开发该功能。
  - 匹配相同关键词的文件夹，并将其文件夹下的文件移动到指定文件夹下（若不存在，自动创建）。
- **批量重命名**：
  - 使用正则表达式，一键修改文件名称，例如：`行s走rS02E03 ,..., 行s走rS05E04` → `行尸走肉 - S02E03 ,..., 行尸走肉 - S05E04`。

## 使用方法

### 环境准备

#### 1. 安装依赖

确保已安装 Python 3.x，然后运行以下命令安装项目依赖：
```bash
pip install -r requirements.txt
```
或
```bash
pip install -r gradio selenium
```

#### 2. 运行

运行以下命令启动 GUI 界面：
```bash
python app.py
```

#### 3. 进入 Gradio

访问：
```bash
127.0.0.1:7861
```
或
```bash
192.168.*.*:7861
```

#### 4. 选择 TAB

主要探讨批量处理部分：
---

![界面截图2](img/屏幕截图2.png)

1. **根目录**：根目录为迅雷下载目录，点击预览子文件夹来展示目录下的文件夹以便挑选关键词。
2. **文件夹关键词**：该变量用于匹配文件夹名称，相当于选择特定文件夹进行操作（无正则表达式）。
3. **目标文件夹**：指定文件夹，将需要移动的文件移动到该文件夹（若不存在则自动创建）。

---

![界面截图3](img/屏幕截图3.png)

### 批量重命名

填完上述三个变量后，点击执行移动并确认无误后，关闭预览模式，实际执行移动。


移动完成后需要填写 **重命名前缀** 与 **自定义正则式**。

#### 例如：

现有 `行s走rS02E03`、`行s走rS02E04`，
- **重命名前缀** 填写为 `行尸走肉 - S`
- **自定义正则式** 填写为 `S(\\d+E\\d+)`

即可重命名为：
```bash
行尸走肉 - S02E03
行尸走肉 - S02E04
```

1. **重命名前缀**：期望的文件夹名称，例如 `行s走r` → `行尸走肉`。
2. **自定义正则式**：匹配括号内的正则表达式并返回匹配值。

填完上述两个变量后，点击执行重命名并确认无误后，关闭预览模式，实际执行重命名。

---
### 删除空文件夹

![界面截图4](img/屏幕截图4.png)


最后，删除迅雷下载目录的空文件夹（自动匹配之前的关键词），同样需要关闭预览模式进行实际删除。

## 界面截图

以下是工具的界面示例：

![界面截图1](img/屏幕截图1.png)
