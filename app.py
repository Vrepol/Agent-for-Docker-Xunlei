#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import time
import gradio as gr
import paramiko  # pip install paramiko

# ================== 追加：selenium 相关 ==================
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# =============================================================================
# （A）Paramiko 相关的辅助函数: 远程 chmod
# =============================================================================
def remote_chmod_via_paramiko(
    host: str,
    port: int,
    username: str,
    password: str,
    target_path: str
) -> str:
    """
    通过 SSH 连接到远程主机, 对 target_path 执行: sudo chmod -R 777 target_path
    返回执行过程的日志。
    """
    logs = []
    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        logs.append(f"[INFO] 正在连接到远程主机 {host}:{port} ...")
        client.connect(hostname=host, port=port, username=username, password=password)

        chmod_cmd = f"sudo chmod -R 777 '{target_path}'"
        logs.append(f"[INFO] 执行命令: {chmod_cmd}")

        stdin, stdout, stderr = client.exec_command(chmod_cmd)
        
        # 若 sudo 需要再次输入密码，则可在此处写: 
        # stdin.write(password + "\n")
        # stdin.flush()

        # 读取执行结果
        out = stdout.read().decode('utf-8', 'ignore')
        err = stderr.read().decode('utf-8', 'ignore')

        if out.strip():
            logs.append("[STDOUT] " + out.strip())
        if err.strip():
            logs.append("[STDERR] " + err.strip())

        logs.append("[INFO] 远程 chmod 操作完成。")
    except Exception as e:
        logs.append(f"[ERROR] 在远程执行 chmod 时出错: {e}")
    finally:
        if client:
            client.close()
    
    return "\n".join(logs)

# =============================================================================
# （1）移动文件脚本
# =============================================================================
def move_files_with_keyword_in_subfolder(
    root_folder: str, 
    keyword: str, 
    target_folder: str, 
    create_if_not_exists: bool = True,
    recursive: bool = False,
    preview: bool = True
) -> str:
    """
    在 root_folder 下查找所有子文件夹(或子孙文件夹)。
    - 若文件夹名称包含 keyword，则将其下所有文件移动到 target_folder。
    - 支持预览模式(仅打印即将发生的操作，不执行)。
    返回执行/预览日志。
    """
    logs = []
    
    # 如果需要自动创建目标文件夹，但当前是 preview 模式，则先不创建
    if not preview and create_if_not_exists and not os.path.exists(target_folder):
        try:
            os.makedirs(target_folder)
            logs.append(f"[INFO] 已创建目标文件夹: {target_folder}")
        except Exception as e:
            logs.append(f"[ERROR] 无法创建目标文件夹: {target_folder}, 错误原因: {e}")
            return "\n".join(logs)

    def move_or_preview(file_path, dest_folder):
        filename = os.path.basename(file_path)
        dest_path = os.path.join(dest_folder, filename)
        if preview:
            logs.append(f"[预览] 将移动: {file_path} -> {dest_path}")
        else:
            try:
                shutil.move(file_path, dest_path)
                logs.append(f"[移动成功] {file_path} -> {dest_path}")
            except Exception as e:
                logs.append(f"[移动失败] {file_path} -> {dest_path}, 原因: {e}")

    if recursive:
        # 递归遍历
        for dirpath, _, filenames in os.walk(root_folder):
            folder_name = os.path.basename(dirpath)
            if keyword in folder_name:
                for file in filenames:
                    source_path = os.path.join(dirpath, file)
                    if os.path.isfile(source_path):
                        move_or_preview(source_path, target_folder)
    else:
        # 仅遍历第一层子文件夹
        try:
            sub_dirs = os.listdir(root_folder)
        except Exception as e:
            logs.append(f"[ERROR] 无法访问目录: {root_folder}, 错误原因: {e}")
            return "\n".join(logs)
        
        for name in sub_dirs:
            subfolder_path = os.path.join(root_folder, name)
            if os.path.isdir(subfolder_path) and (keyword in name):
                for file in os.listdir(subfolder_path):
                    source_path = os.path.join(subfolder_path, file)
                    if os.path.isfile(source_path):
                        move_or_preview(source_path, target_folder)

    return "\n".join(logs)

# =============================================================================
# （2）批量重命名脚本 (支持自定义正则)
# =============================================================================
# 这是原先的默认匹配规则，可根据需要随时扩展或修改
DEFAULT_PATTERN_CONFIG = [
    {
        "name": "提取 EP 后面的数字",
        "pattern": r"EP(\d+)",
        "rename_func": lambda m: m.group(1),  
    },
    {
        "name": "提取第一个数字串",
        "pattern": r"(\d+)",
        "rename_func": lambda m: m.group(1),
    },
]

def rename_files(
    folder_path: str, 
    prefix: str = "NewFile_",        
    preview: bool = True,
    custom_pattern: str = ""
) -> str:
    """
    在 folder_path 下批量重命名文件。
    
    1. 如果 custom_pattern 非空，先构造一个 "自定义规则" 放在最前面试图匹配；
    2. 若匹配失败，再用后续默认规则；
    3. 如果全部都不匹配则跳过。
    返回执行/预览日志。
    """
    logs = []
    
    # --- 构建最终的 pattern_config 列表 ---
    pattern_config = []
    
    # 如果用户填写了自定义正则，我们尝试将它加入到列表的最前面
    if custom_pattern.strip():
        try:
            re.compile(custom_pattern.strip())
            pattern_config.append({
                "name": "自定义规则",
                "pattern": custom_pattern.strip(),
                "rename_func": lambda m: m.group(1),
            })
        except re.error as e:
            logs.append(f"自定义正则无效: {custom_pattern}, 错误原因: {e}")
    
    # 然后再追加默认规则
    pattern_config.extend(DEFAULT_PATTERN_CONFIG)
    
    # --- 开始实际的文件遍历与重命名 ---
    if not os.path.isdir(folder_path):
        logs.append(f"错误：文件夹不存在或路径无效: {folder_path}")
        return "\n".join(logs)
    
    file_list = os.listdir(folder_path)
    file_list = [f for f in file_list if os.path.isfile(os.path.join(folder_path, f))]
    
    if not file_list:
        logs.append(f"文件夹 {folder_path} 下没有任何文件。")
        return "\n".join(logs)
    
    file_list.sort()  # 按名字排序

    rename_pairs = []
    for old_name in file_list:
        old_path = os.path.join(folder_path, old_name)
        _, ext = os.path.splitext(old_name)
        
        new_suffix = None
        
        # 尝试按顺序匹配
        for rule in pattern_config:
            match_obj = re.search(rule["pattern"], old_name)
            if match_obj:
                new_suffix = rule["rename_func"](match_obj)
                break
        
        if not new_suffix:
            logs.append(f"跳过：文件名不符合任何规则 -> {old_name}")
            continue
        
        new_name = f"{prefix}{new_suffix}{ext}"
        new_path = os.path.join(folder_path, new_name)
        rename_pairs.append((old_path, new_path))
    
    # --- 预览 or 执行 ---
    if preview:
        logs.append("重命名预览:")
        for old_path, new_path in rename_pairs:
            logs.append(f"{os.path.basename(old_path)} -> {os.path.basename(new_path)}")
        logs.append("\n当前是预览模式 (preview=True)，未执行实际重命名。")
    else:
        for old_path, new_path in rename_pairs:
            try:
                os.rename(old_path, new_path)
                logs.append(f"已重命名: {os.path.basename(old_path)} -> {os.path.basename(new_path)}")
            except Exception as e:
                logs.append(f"重命名失败: {os.path.basename(old_path)} -> {os.path.basename(new_path)}，错误原因: {e}")

    return "\n".join(logs)

# =============================================================================
# （3）辅助函数：读取目录结构并输出为文本
# =============================================================================
def read_subfolders_one_level(folder_path: str) -> str:
    """
    仅读取 folder_path 下的一层子目录（可根据需要展示文件或只展示文件夹）。
    """
    if not os.path.isdir(folder_path):
        return f"路径无效或不是文件夹: {folder_path}"
    
    try:
        items = os.listdir(folder_path)
    except Exception as e:
        return f"无法访问目录: {folder_path}, 错误原因: {e}"

    dirs = [item for item in items if os.path.isdir(os.path.join(folder_path, item))]
    lines = [f"{os.path.basename(folder_path)} 下的子文件夹："]
    for d in dirs:
        lines.append(f"- {d}")

    return "\n".join(lines)

# =============================================================================
# （4）删除空文件夹
# =============================================================================
def delete_empty_folders_with_keyword(
    root_folder: str, 
    keyword: str, 
    recursive: bool = False, 
    preview: bool = True
) -> str:
    """
    在 root_folder 下查找所有“名称含 keyword”的子文件夹，若该文件夹已为空(无任何文件/子文件夹)，则删除。
    - 支持递归(多级)和预览模式。
    - 返回操作日志。
    """
    logs = []
    
    if not os.path.isdir(root_folder):
        logs.append(f"[ERROR] 无效的 root_folder: {root_folder}")
        return "\n".join(logs)
    
    # 递归删除时，从里往外删，需要 topdown=False
    if recursive:
        for dirpath, dirnames, _ in os.walk(root_folder, topdown=False):
            for d in dirnames:
                if keyword in d:
                    folder_to_check = os.path.join(dirpath, d)
                    try:
                        if not os.listdir(folder_to_check):
                            if preview:
                                logs.append(f"[预览] 将删除空文件夹: {folder_to_check}")
                            else:
                                os.rmdir(folder_to_check)
                                logs.append(f"[删除成功] {folder_to_check}")
                        else:
                            logs.append(f"[跳过] 该文件夹不为空: {folder_to_check}")
                    except Exception as e:
                        logs.append(f"[ERROR] 检查/删除文件夹时出错: {folder_to_check}, 原因: {e}")
    else:
        # 仅遍历第一层子文件夹
        try:
            sub_dirs = os.listdir(root_folder)
        except Exception as e:
            logs.append(f"[ERROR] 无法访问目录: {root_folder}, 错误原因: {e}")
            return "\n".join(logs)
        
        for d in sub_dirs:
            folder_to_check = os.path.join(root_folder, d)
            if os.path.isdir(folder_to_check) and (keyword in d):
                try:
                    if not os.listdir(folder_to_check):
                        if preview:
                            logs.append(f"[预览] 将删除空文件夹: {folder_to_check}")
                        else:
                            os.rmdir(folder_to_check)
                            logs.append(f"[删除成功] {folder_to_check}")
                    else:
                        logs.append(f"[跳过] 该文件夹不为空: {folder_to_check}")
                except Exception as e:
                    logs.append(f"[ERROR] 检查/删除文件夹时出错: {folder_to_check}, 原因: {e}")

    return "\n".join(logs)

# =============================================================================
#  构建 Gradio 界面: 在这里我们把 “多磁力链接下载” + “文件处理” 放到不同的 Tab
#  并通过 build_interface(...) 接收 main() 传进来的配置
# =============================================================================
def build_interface(
    download_page_url: str,
    remote_path_choices: list,
    local_folder_choices: list
):
    """
    使用传入的配置，构建 Gradio 界面。
    """

    # 这里的 start_download 是个内嵌函数，能够使用外部的 download_page_url
    def start_download(magnet_input):
        """
        从单个文本框中接收多条磁力链接（每行一条），
        然后逐个在 Selenium 中执行下载。
        """
        magnet_links = [line.strip() for line in magnet_input.split("\n") if line.strip()]

        for link in magnet_links:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(download_page_url)  # 使用main里传进来的 URL
            driver.implicitly_wait(10)

            # 点击“新建任务”
            new_task_btn = driver.find_element(By.CSS_SELECTOR, ".create__task")
            new_task_btn.click()

            # 显式等待弹窗出现
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".nas-task-dialog")))

            # 找到输入框，输入磁力链接
            input_box = driver.find_element(By.CSS_SELECTOR, ".el-textarea__inner")
            input_box.send_keys(link)

            # 找到确认按钮
            confirm_btn = driver.find_element(By.CSS_SELECTOR, ".el-dialog__footer .el-button.el-button--primary.task-parse-btn")
            confirm_btn.click()

            time.sleep(2)  # 等待解析完成

            # 点击下载按钮
            download_btn = driver.find_element(By.CSS_SELECTOR, ".result-nas-task-dialog_footer .el-button.el-button--primary.task-parse-btn")
            download_btn.click()

            time.sleep(2)  # 等待一些时间，也可以根据需要做更多判断
            driver.quit()

        return f"已处理 {len(magnet_links)} 条磁力链接！"

    # 下面正式开始绘制 Gradio 的 Blocks
    with gr.Blocks() as demo:
        gr.Markdown("## 综合示例：多磁力链接下载 + 文件移动/重命名")

        with gr.Tabs():
            # =============== Tab 1: 多磁力链接下载 ===============
            with gr.Tab("多磁力链接下载"):
                gr.Markdown("### 通过 Selenium 执行下载任务")

                magnet_input = gr.Textbox(
                    label="粘贴磁力链接（每行一个）", 
                    lines=8, 
                    interactive=True
                )
                output_box = gr.Textbox(
                    label="执行结果", 
                    lines=2, 
                    interactive=False
                )
                download_button = gr.Button("开始下载")

                # 绑定点击事件
                download_button.click(
                    fn=start_download,
                    inputs=magnet_input,
                    outputs=output_box
                )

            # =============== Tab 2: 文件处理：移动 + 重命名 ===============
            with gr.Tab("文件处理：移动 + 重命名"):
                gr.Markdown("### 文件处理脚本：移动文件、批量重命名、删除空文件夹")

                # --- 远程SSH配置 & chmod ---
                with gr.Group():
                    gr.Markdown("#### 远程 SSH 配置 (Paramiko)")
                    with gr.Row():
                        host_input = gr.Textbox(
                            label="树莓派 / 服务器 IP", 
                            value="100.97.92.19", 
                            interactive=True
                        )
                        port_input = gr.Number(
                            label="SSH端口", 
                            value=22, 
                            interactive=True
                        )
                    username_input = gr.Textbox(
                        label="SSH 用户名", 
                        value="root",
                        interactive=True
                    )
                    password_input = gr.Textbox(
                        label="SSH 密码(若有)", 
                        type="password",
                        interactive=True
                    )
                    remote_chmod_path_input = gr.Dropdown(
                        label="远程目录(执行 sudo chmod -R 777 的路径)",
                        choices=remote_path_choices,  # 接收 main 中传进来的
                        value=remote_path_choices[0],  # 默认选第一个
                        interactive=True
                    )

                gr.Markdown("#### 查看本地(或共享)文件夹结构")
                folder_path_input = gr.Dropdown(
                    label="本地(或网络共享)文件夹路径",
                    choices=local_folder_choices,    # 接收 main 中传进来的
                    value=local_folder_choices[0],   # 默认值选第一个
                    interactive=True
                )
                read_tree_button = gr.Button("读取文件夹结构（先远程chmod）")
                tree_output = gr.Textbox(label="操作日志", lines=15)

                def on_read_tree(
                    host, port, username, password, remote_chmod_path,
                    local_folder
                ):
                    logs = []
                    # 1. 远程 chmod -R 777
                    chmod_log = remote_chmod_via_paramiko(
                        host=host,
                        port=int(port),
                        username=username,
                        password=password,
                        target_path=remote_chmod_path
                    )
                    logs.append(chmod_log)

                    # 2. 读取目录结构
                    local_tree = read_subfolders_one_level(local_folder)
                    logs.append("[INFO] 本地/共享 目录结构:\n" + local_tree)

                    return "\n\n".join(logs)

                read_tree_button.click(
                    fn=on_read_tree,
                    inputs=[
                        host_input, 
                        port_input, 
                        username_input, 
                        password_input, 
                        remote_chmod_path_input,
                        folder_path_input
                    ],
                    outputs=tree_output
                )

                with gr.Row():
                    # ------------------------- 左侧：移动文件 -------------------------
                    with gr.Column():
                        gr.Markdown("#### 第一步：按关键字移动文件")

                        root_folder = gr.Textbox(
                            label="根目录路径 (root_folder)",
                            value=local_folder_choices[0],  # 默认值
                            interactive=True
                        )
                        keyword = gr.Textbox(
                            label="文件夹名称关键字 (keyword)",
                            placeholder="例如：第一季",
                            interactive=True
                        )
                        target_folder = gr.Textbox(
                            label="目标文件夹(后续也会用于重命名)",
                            value=r"\\100.97.92.19\DataBase\电视剧",
                            interactive=True
                        )
                        create_if_not_exists = gr.Checkbox(
                            label="若目标文件夹不存在，是否自动创建？",
                            value=True,
                            interactive=True
                        )
                        recursive = gr.Checkbox(
                            label="是否递归到多级子文件夹？",
                            value=False,
                            interactive=True
                        )
                        preview_move = gr.Checkbox(
                            label="预览模式(只打印，不执行移动)",
                            value=True,
                            interactive=True
                        )

                        move_button = gr.Button("执行/预览移动操作")
                        move_output = gr.Textbox(label="移动操作日志", lines=10)

                        def on_move_click(
                            root_folder, keyword, target_folder, create_if_not_exists, recursive, preview
                        ):
                            return move_files_with_keyword_in_subfolder(
                                root_folder, keyword, target_folder, 
                                create_if_not_exists, recursive, preview
                            )

                        move_button.click(
                            fn=on_move_click,
                            inputs=[
                                root_folder, 
                                keyword, 
                                target_folder, 
                                create_if_not_exists, 
                                recursive, 
                                preview_move
                            ],
                            outputs=move_output
                        )

                    # ------------------------- 右侧：批量重命名 -------------------------
                    with gr.Column():
                        gr.Markdown("#### 第二步：批量重命名 (可自定义正则)")

                        rename_prefix = gr.Textbox(
                            label="重命名前缀 (prefix)",
                            placeholder="电视剧名称_",
                            interactive=True
                        )
                        custom_pattern_input = gr.Textbox(
                            label="自定义正则 (如 S(\\d+)E(\\d+)，并带括号捕获组)",
                            placeholder="示例：S(\\d+)E(\\d+)",
                            interactive=True
                        )
                        preview_rename = gr.Checkbox(
                            label="预览模式(只打印，不执行重命名)",
                            value=True,
                            interactive=True
                        )

                        rename_button = gr.Button("执行/预览重命名操作")
                        rename_output = gr.Textbox(label="重命名操作日志", lines=10)

                        def on_rename_click(folder_path, prefix, preview, custom_pattern):
                            return rename_files(
                                folder_path=folder_path,
                                prefix=prefix,
                                preview=preview,
                                custom_pattern=custom_pattern
                            )

                        rename_button.click(
                            fn=on_rename_click,
                            inputs=[target_folder, rename_prefix, preview_rename, custom_pattern_input],
                            outputs=rename_output
                        )

                gr.Markdown("#### 第三步：删除空文件夹 (名称含关键字)")
                preview_delete = gr.Checkbox(
                    label="预览模式(只打印，不执行删除)",
                    value=True,
                    interactive=True
                )
                delete_button = gr.Button("执行/预览删除空文件夹")
                delete_output = gr.Textbox(label="删除文件夹操作日志", lines=10)

                def on_delete_click(root_folder_value, keyword_value, recursive_value, preview_value):
                    return delete_empty_folders_with_keyword(
                        root_folder=root_folder_value,
                        keyword=keyword_value,
                        recursive=recursive_value,
                        preview=preview_value
                    )

                delete_button.click(
                    fn=on_delete_click,
                    inputs=[
                        root_folder,  # 直接复用上面填写的根目录
                        keyword,      # 同样复用关键字
                        recursive,    # 是否递归
                        preview_delete
                    ],
                    outputs=delete_output
                )

    return demo

# =============================================================================
# main(): 在这里统一定义“易变的 URL / 路径”，然后传给 build_interface
# =============================================================================
def main():
    # 1) 下载页面的 URL（Selenium 会用到）
    DOWNLOAD_PAGE_URL = "http://IP:2345"

    # 2) 可选的远程路径（chmod 目标），就是服务器的硬盘地址，可以修改地更细一点（比如/srv/Device/DataBase/Xunlei_download)，
    REMOTE_PATH_CHOICES = [
        "/srv/Device/DataBase",
        "/srv/Device/DataBase2"
    ]

    # 3) 本地或网络共享目录，通过什么地址可以访问到服务器迅雷下载地址
    LOCAL_FOLDER_CHOICES = [
        r"\\IP\DataBase\downloads",
        r"\\IP\DataBase2\downloads"
    ]

    # 构建 Gradio 界面，传入这些配置
    demo = build_interface(
        download_page_url=DOWNLOAD_PAGE_URL,
        remote_path_choices=REMOTE_PATH_CHOICES,
        local_folder_choices=LOCAL_FOLDER_CHOICES
    )

    # 启动服务
    demo.launch(server_name="0.0.0.0", server_port=7861)

if __name__ == "__main__":
    main()
