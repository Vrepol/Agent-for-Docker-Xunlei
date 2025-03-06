# Agent-for-Docker-Xunlei
Docker迅雷的下载助手，解决批量磁力链接下载与批量电视剧重命名与移动
## 功能特性
- **磁力链接批量下载**：
  - 无需迅雷会员即可批量下载磁力。
- **文件批量移动**：
  - 由于多条磁力链接（一般为电视剧下载），会创建多个文件夹，每个文件夹下为一集，人工移动文件费时费力，因此开发该功能。
  - 匹配相同关键词的文件夹，并将其文件夹下的文件移动到指定文件夹下（若不存在，自动创建）
- **批量重命名**：
  - 使用正则表达式，一键修改文件名称，例如：行s走rS02E03 ,..., 行s走rS05E04 ---> 行尸走肉 - S02E03 ,..., 行尸走肉 - S05E04。

## 使用方法

### 环境准备
1. **安装 ffmpeg**  
   请先下载并安装 [FFmpeg](https://ffmpeg.org/download.html)。

2. **克隆仓库**  
   使用以下命令将仓库克隆到本地：
   ```bash
   https://github.com/Vrepol/Video-image-photo-converter-.git
   ```
   
3.**安装依赖**
  确保已安装 Python 3.x，然后运行以下命令安装项目依赖：
    ```
    pip install -r requirements.txt
    ```
   
4.**运行**
  运行以下命令启动 GUI 界面：
    ```
    python gui_converter.py
    ```


**界面截图**
以下是工具的界面示例：

<img src="img/屏幕截图1.png" alt="界面截图1" width="600"> <img src="img/屏幕截图2.png" alt="界面截图2" width="600"> <img src="img/屏幕截图3.png" alt="界面截图3" width="600"><img src="img/屏幕截图4.png" alt="界面截图4" width="600">
