from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Optional
import xml.etree.ElementTree as ET
import time

from appium import webdriver
from appium.options.android import UiAutomator2Options
from omegaconf import OmegaConf


class ScreenExecutor:
	"""
	Capture current screen state (XML + screenshot) from an Appium driver.

	- Uses SHA1 hash of the XML content as the file id
	- Saves to the provided output directory
	- Returns raw XML and saved file paths
	"""

	def __init__(self, driver, output_dir: str = "assets/Screen") -> None:
		self.driver = driver
		self.output_dir = Path(output_dir)
		self.output_dir.mkdir(parents=True, exist_ok=True)

	@classmethod
	def from_configs(
		cls,
		app_tag: str,
		app_yaml: Optional[str] = None,
		env_yaml: Optional[str] = None,
		server_url: str = "http://localhost:4723",
		output_dir: str = "assets/Screen",
		connect_wait_seconds: int = 15,
	) -> "ScreenExecutor":
		"""
		基于 config 目录中的 YAML 配置初始化 Appium driver 并创建 ScreenExecutor。

		Args:
			app_tag: app.yaml 中的应用标识
			app_yaml: 应用配置文件路径（默认自动在模块所在的 config/ 下查找，找不到则回退到 ref/ITeM/config/）
			env_yaml: 环境配置文件路径（默认自动在模块所在的 config/ 下查找，找不到则回退到 ref/ITeM/config/）
			server_url: Appium 服务器 URL
			output_dir: 截图与 XML 输出目录
			connect_wait_seconds: 连接后等待秒数，保证会话稳定
		"""
		app_yaml_path = _resolve_config_path(app_yaml, "app.yaml")
		env_yaml_path = _resolve_config_path(env_yaml, "env.yaml")

		app_config = OmegaConf.load(str(app_yaml_path))[app_tag]
		env_config = OmegaConf.load(str(env_yaml_path))["Appium"]
		desired_caps = _generate_desired_caps(app_config, env_config)

		driver = webdriver.Remote(server_url, options=UiAutomator2Options().load_capabilities(desired_caps))
		if connect_wait_seconds > 0:
			time.sleep(connect_wait_seconds)

		return cls(driver=driver, output_dir=output_dir)

	def parse_current_screen(self) -> Dict[str, str]:
		"""
		获取当前界面的 XML 与截图，并以哈希命名保存到指定文件夹。

		Returns:
			{
			  "xml": XML 字符串,
			  "xml_path": 保存的 XML 文件路径,
			  "screenshot_path": 保存的 PNG 文件路径,
			  "hash": 基于 XML 的 sha1 哈希
			}
		"""
		# 参考 test_executor 的做法：从 driver 获取 page_source，并保存截图
		xml_str = str(self.driver.page_source)

		# 使用 XML 内容生成稳定的哈希作为文件名
		sha1 = hashlib.sha1(xml_str.encode("utf-8")).hexdigest()
		xml_path = self.output_dir / f"{sha1}.xml"
		png_path = self.output_dir / f"{sha1}.png"

		# 写入 XML（优先用 ElementTree，失败则写入原始文本）
		try:
			root = ET.fromstring(xml_str)
			tree = ET.ElementTree(root)
			tree.write(xml_path, encoding="utf-8")
		except Exception:
			xml_path.write_text(xml_str, encoding="utf-8")

		# 保存截图到 PNG
		self.driver.get_screenshot_as_file(str(png_path))

		return {
			"xml": xml_str,
			"xml_path": str(xml_path),
			"screenshot_path": str(png_path),
			"hash": sha1,
		}


# 兼容命名：如需要使用 Executor 名称，可直接引用
Executor = ScreenExecutor


def _resolve_config_path(provided: Optional[str], default_name: str) -> Path:
	"""解析配置文件路径：
	1) 若提供了绝对或相对路径，则使用该路径
	2) 否则优先使用模块所在目录下的 config/<name>
	3) 若不存在则回退到工作空间的 ref/ITeM/config/<name>
	"""
	if provided:
		p = Path(provided)
		if p.exists():
			return p
	# Module-local config directory
	module_dir = Path(__file__).resolve().parent
	local_cfg = module_dir / "config" / default_name
	if local_cfg.exists():
		return local_cfg
	# Fallback to ref/ITeM/config
	workspace_ref = Path.cwd() / "ref" / "ITeM" / "config" / default_name
	return workspace_ref


def _generate_desired_caps(app_config, env_config) -> Dict[str, object]:
	"""根据 test_executor 的实现生成 desired capabilities。"""
	desired_caps = {
		"appium-version": env_config["appium-version"],
		"platformName": env_config["platformName"],
		"platformVersion": env_config["platformVersion"],
		"deviceName": env_config["deviceName"],
		"automationName": env_config["automationName"],
		"newCommandTimeout": env_config["newCommandTimeout"],
		"appPackage": app_config["appPackage"],
		"appActivity": app_config["appActivity"],
	}
	if "noReset" not in app_config:
		desired_caps["autoGrantPermissions"] = env_config["autoGrantPermissions"]
	else:
		desired_caps["noReset"] = app_config["noReset"]
	return desired_caps

