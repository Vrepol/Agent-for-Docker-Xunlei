#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import time
import gradio as gr

# ====== 以下是 Selenium 及其依赖 ======
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


# ---------------------- (1) 批量磁力下载逻辑 ----------------------
def start_download(magnet_input,server_addr):
    """
    从单个文本框中接收多条磁力链接（每行一条），
    然后逐个在 Selenium 中执行下载。
    """
    # 按行拆分用户粘贴的磁力链接，并去掉空白行
    magnet_links = [line.strip() for line in magnet_input.split("\n") if line.strip()]
    # 初始化浏览器（若在树莓派Docker环境，可用 Chromium + chromedriver for ARM）
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 无头模式，可根据需要注释
    chrome_options.add_argument("--no-sandbox")  # 关键
    chrome_options.add_argument("--disable-dev-shm-usage")  # 关键
    prefs = {"profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.managed_default_content_settings.fonts": 2}
    service = Service("/usr/bin/chromedriver")
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    driver = webdriver.Chrome(options=chrome_options,service=service)
    for link in magnet_links:
        # 访问你的下载服务器页面
        driver.get(server_addr)
        driver.implicitly_wait(2)

        # 点击“新建任务”
        new_task_btn = driver.find_element(By.CSS_SELECTOR, ".create__task")
        new_task_btn.click()

        # 显式等待弹窗出现
        wait = WebDriverWait(driver, 2)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".nas-task-dialog")))

        # 找到输入框，输入磁力链接
        input_box = driver.find_element(By.CSS_SELECTOR, ".el-textarea__inner")
        input_box.send_keys(link)

        # 找到确认按钮
        confirm_btn = driver.find_element(By.CSS_SELECTOR, ".el-dialog__footer .el-button.el-button--primary.task-parse-btn")
        confirm_btn.click()

        # 等一下解析完（这里简单等待 1 秒，可根据页面加载情况调整）
        time.sleep(1)

        # 点击下载按钮
        download_btn = driver.find_element(By.CSS_SELECTOR, ".result-nas-task-dialog_footer .el-button.el-button--primary.task-parse-btn")
        download_btn.click()

        # 等待一些时间，或在此处做更多校验
        time.sleep(1)
    driver.quit()

    return f"已处理 {len(magnet_links)} 条磁力链接！"


# ---------------------- (2) 文件处理工具逻辑 ----------------------
def move_files_with_keyword_in_subfolder(
    root_folder: str,
    keyword: str,
    target_folder: str,
    create_if_not_exists: bool = True,
    recursive: bool = False,
    preview: bool = True
) -> str:
    """
    在 root_folder 下查找所有子文件夹(或子孙文件夹)：
      - 若文件夹名称包含 keyword，则将其下所有文件移动到 target_folder。
      - 如果 preview=True，则仅打印操作，不执行移动。
    """
    logs = []

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
                os.chmod(dest_path, 0o777)
                os.chmod(target_folder, 0o777)
                logs.append(f"[移动成功] {file_path} -> {dest_path}")
            except Exception as e:
                logs.append(f"[移动失败] {file_path} -> {dest_path}, 原因: {e}")

    if recursive:
        for dirpath, _, filenames in os.walk(root_folder):
            folder_name = os.path.basename(dirpath)
            if keyword in folder_name:
                for file in filenames:
                    source_path = os.path.join(dirpath, file)
                    if os.path.isfile(source_path):
                        move_or_preview(source_path, target_folder)
    else:
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
    1. 如果 custom_pattern 非空，优先尝试匹配；
    2. 若匹配失败，再用后续默认规则；
    3. 如果全部都不匹配则跳过。
    """
    logs = []
    
    pattern_config = []
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

    pattern_config.extend(DEFAULT_PATTERN_CONFIG)

    if not os.path.isdir(folder_path):
        logs.append(f"错误：文件夹不存在或路径无效: {folder_path}")
        return "\n".join(logs)

    file_list = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    if not file_list:
        logs.append(f"文件夹 {folder_path} 下没有任何文件。")
        return "\n".join(logs)

    file_list.sort()

    rename_pairs = []
    for old_name in file_list:
        old_path = os.path.join(folder_path, old_name)
        _, ext = os.path.splitext(old_name)

        new_suffix = None
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

    if preview:
        logs.append("重命名预览:")
        for old_path, new_path in rename_pairs:
            logs.append(f"{os.path.basename(old_path)} -> {os.path.basename(new_path)}")
        logs.append("\n(预览模式，未执行实际重命名)")
    else:
        for old_path, new_path in rename_pairs:
            try:
                os.rename(old_path, new_path)
                logs.append(f"已重命名: {os.path.basename(old_path)} -> {os.path.basename(new_path)}")
            except Exception as e:
                logs.append(f"重命名失败: {os.path.basename(old_path)} -> {os.path.basename(new_path)}，错误原因: {e}")

    return "\n".join(logs)


def delete_empty_folders_with_keyword(
    root_folder: str,
    keyword: str,
    recursive: bool = False,
    preview: bool = True
) -> str:
    """
    在 root_folder 下查找所有“名称含 keyword”的子文件夹，若该文件夹为空则删除。
    """
    logs = []
    if not os.path.isdir(root_folder):
        logs.append(f"[ERROR] 无效的 root_folder: {root_folder}")
        return "\n".join(logs)

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
                        logs.append(f"[ERROR] 删除文件夹时出错: {folder_to_check}, 原因: {e}")
    else:
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
                    logs.append(f"[ERROR] 删除文件夹时出错: {folder_to_check}, 原因: {e}")

    return "\n".join(logs)


def preview_subfolders(root_folder: str) -> str:
    """
    列出 root_folder 下第一层子文件夹名称
    """
    logs = []
    if not os.path.isdir(root_folder):
        logs.append(f"[ERROR] 无效的根目录: {root_folder}")
        return "\n".join(logs)

    try:
        sub_dirs = [d for d in os.listdir(root_folder) if os.path.isdir(os.path.join(root_folder, d))]
        logs.append(f"根目录: {root_folder} 下的子文件夹如下：")
        if not sub_dirs:
            logs.append("（无子文件夹）")
        for d in sub_dirs:
            logs.append(f"- {d}")
    except Exception as e:
        logs.append(f"[ERROR] 无法访问目录: {root_folder}, 错误原因: {e}")
    return "\n".join(logs)


# ---------------------- (3) 构建 Gradio 多Tab界面并运行 ----------------------
def build_interface():
    with gr.Blocks() as demo:
        # ====== Tab 1: 批量下载 ======
        with gr.Tab("批量下载"):
            gr.Markdown("## 一次性粘贴多个磁力链接的示例")

            magnet_input = gr.Textbox(
                label="粘贴磁力链接（每行一个）",
                lines=8,
                placeholder="magnet:?xt=urn:btih:xxxx..."
            )
            server_addr = gr.Textbox(label="迅雷Docker地址", value="http://IP:Port", lines=1)
            output_box = gr.Textbox(label="执行结果", lines=2)

            download_button = gr.Button("开始下载")
            download_button.click(
                fn=start_download,
                inputs=[magnet_input,server_addr],
                outputs=output_box
            )

        # ====== Tab 2: 文件处理工具 ======
        with gr.Tab("文件处理工具"):
            gr.Markdown("## 文件处理工具：移动 / 重命名 / 删除空文件夹")

            # --- 1) 通用输入区域 ---
            with gr.Row():
                root_folder = gr.Textbox(
                    label="根目录 (root_folder)",
                    value="/DataBase/downloads"
                )
                keyword = gr.Textbox(label="文件夹名称关键字 (keyword)", value="Key", lines=1)
            target_folder = gr.Textbox(label="目标文件夹 (或重命名用)", value="/DataBase/电视剧/Name", lines=1)

            # --- 2) 子文件夹预览功能 ---
            preview_subfolders_btn = gr.Button("预览子文件夹")
            preview_subfolders_output = gr.Textbox(label="子文件夹列表", lines=6)

            def on_preview_subfolders_click(root_folder_value):
                return preview_subfolders(root_folder_value)

            preview_subfolders_btn.click(
                fn=on_preview_subfolders_click,
                inputs=[root_folder],
                outputs=preview_subfolders_output
            )

            # --- A) 按关键字移动文件 ---
            gr.Markdown("### A) 按关键字移动文件")
            with gr.Row():
                create_if_not_exists = gr.Checkbox(label="若目标文件夹不存在则创建", value=True)
                recursive_move = gr.Checkbox(label="递归子文件夹", value=False)
                preview_move = gr.Checkbox(label="预览模式 (只打印，不执行)", value=True)
            move_button = gr.Button("执行移动")
            move_output = gr.Textbox(label="移动操作日志", lines=8)

            def on_move_click(
                root_folder_value, keyword_value, target_folder_value,
                create_if_not_exists_value, recursive_value, preview_value
            ):
                return move_files_with_keyword_in_subfolder(
                    root_folder_value,
                    keyword_value,
                    target_folder_value,
                    create_if_not_exists_value,
                    recursive_value,
                    preview_value
                )

            move_button.click(
                fn=on_move_click,
                inputs=[
                    root_folder,
                    keyword,
                    target_folder,
                    create_if_not_exists,
                    recursive_move,
                    preview_move
                ],
                outputs=move_output
            )

            # --- B) 批量重命名 ---
            gr.Markdown("### B) 批量重命名")
            with gr.Row():
                rename_prefix = gr.Textbox(label="重命名前缀", value="Name - S0E", lines=1)
                custom_pattern = gr.Textbox(label="自定义正则(如 S(\\d+)E(\\d+))，需带捕获组 ( )", value="E(\\d+) ", lines=1)
                preview_rename = gr.Checkbox(label="预览模式(只打印，不执行)", value=True)
            rename_button = gr.Button("执行重命名")
            rename_output = gr.Textbox(label="重命名操作日志", lines=8)

            def on_rename_click(prefix_value, preview_value, pattern_value, target_folder_value):
                return rename_files(
                    folder_path=target_folder_value,
                    prefix=prefix_value,
                    preview=preview_value,
                    custom_pattern=pattern_value
                )

            rename_button.click(
                fn=on_rename_click,
                inputs=[rename_prefix, preview_rename, custom_pattern, target_folder],
                outputs=rename_output
            )

            # --- C) 删除空文件夹 ---
            gr.Markdown("### C) 删除空文件夹")
            with gr.Row():
                recursive_del = gr.Checkbox(label="递归子文件夹", value=False)
                preview_delete = gr.Checkbox(label="预览模式(只打印，不执行)", value=True)
            delete_button = gr.Button("执行删除")
            delete_output = gr.Textbox(label="删除操作日志", lines=8)

            def on_delete_click(folder_value, keyword_value, recursive_value, preview_value):
                return delete_empty_folders_with_keyword(
                    root_folder=folder_value,
                    keyword=keyword_value,
                    recursive=recursive_value,
                    preview=preview_value
                )

            delete_button.click(
                fn=on_delete_click,
                inputs=[root_folder, keyword, recursive_del, preview_delete],
                outputs=delete_output
            )

    return demo


def main():
    demo = build_interface()
    demo.launch(server_name="0.0.0.0", server_port=7861, show_error=True)


if __name__ == "__main__":
    main()
