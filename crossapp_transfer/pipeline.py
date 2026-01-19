
from crossapp_transfer.utils import (
    load_prototypes,
    log_prototype_execution,
    verify_prototype_execution,
    parse_current_screen,
    parse_screen_xml_to_capabilities,
)
from crossapp_transfer.executor import ScreenExecutor
def pipeline_main(prototype_path: str, driver=None, output_dir: str = "states"):
    """
    Pipeline 总流程：
    在新 App 中执行并验证 Prototype 中的功能
    """

    # -----------------------------
    # Step 1: 读取 Prototype.json
    # -----------------------------
    prototypes = load_prototypes(prototype_path)

    # -----------------------------
    # Step 2: 遍历每个 Prototype
    # -----------------------------
    for proto in prototypes:

        # 2a. 获取当前屏幕状态（XML/截图）
        # 优先通过 ScreenExecutor 获取 XML 与截图，并基于 XML 构建能力映射
        if driver is not None:
            executor = ScreenExecutor(driver, output_dir=output_dir)
            screen = executor.parse_current_screen()
            # screen: {"xml", "xml_path", "screenshot_path", "hash"}
            current_screen_state = parse_screen_xml_to_capabilities(screen["xml"])  # {capability: [node_keys]}
        else:
            # 兼容旧路径：无 driver 时回退到文件系统最近 XML
            current_screen_state = parse_current_screen()

        # # 2b. Guided Exploration Loop
        # guided_exploration(proto, current_screen_state)

        # # 2c. 验证功能是否完成（postcondition 检查）
        # verify_prototype_execution(proto)

        # # 可选：记录执行日志和屏幕反馈
        # log_prototype_execution(proto)
