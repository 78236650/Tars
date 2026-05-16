"""Python 插件动态加载器"""
import importlib.util
import sys
from pathlib import Path
from typing import Optional

from .base import BaseTool


def load_plugin_tool(entry_point: Path) -> Optional[BaseTool]:
    """从 Python 文件动态加载 BaseTool 子类实例"""
    if not entry_point.exists():
        return None

    module_name = f"tars_plugin_{entry_point.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(entry_point))
    if not spec or not spec.loader:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        del sys.modules[module_name]
        raise RuntimeError(f"加载插件失败 {entry_point}: {e}")

    # 查找所有 BaseTool 子类
    tools = []
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, BaseTool)
            and attr is not BaseTool
        ):
            try:
                tools.append(attr())
            except Exception as e:
                raise RuntimeError(f"实例化插件 {attr_name} 失败: {e}")

    if len(tools) == 1:
        return tools[0]
    elif len(tools) > 1:
        # 返回工具列表（调用者需要处理）
        return tools

    return None
