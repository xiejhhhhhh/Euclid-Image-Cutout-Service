#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
提供统一的配置加载和访问接口
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from string import Template


class Config:
    """统一配置管理类"""

    def __init__(self, config_dict: Dict[str, Any]):
        """
        初始化配置

        Args:
            config_dict: 配置字典
        """
        self._config = config_dict
        self._resolve_variables()

    @classmethod
    def from_yaml(cls, path: str) -> 'Config':
        """
        从YAML文件加载配置

        Args:
            path: YAML文件路径

        Returns:
            Config实例
        """
        path = Path(path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)

        return cls(config_dict)

    @classmethod
    def from_env(cls, prefix: str = "EUCLID_") -> 'Config':
        """
        从环境变量加载配置

        Args:
            prefix: 环境变量前缀

        Returns:
            Config实例
        """
        config_dict = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # 移除前缀并转换为小写
                config_key = key[len(prefix):].lower()
                config_dict[config_key] = value

        return cls(config_dict)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'Config':
        """
        加载配置（优先级：环境变量 > 指定文件 > 默认文件）

        Args:
            config_path: 配置文件路径（可选）

        Returns:
            Config实例
        """
        # 默认配置文件路径
        default_paths = [
            Path.cwd() / "config.yaml",
            Path.cwd() / "config.yml",
            Path.home() / ".euclid" / "config.yaml",
        ]

        # 从环境变量获取配置文件路径
        env_config_path = os.environ.get("EUCLID_CONFIG")
        if env_config_path:
            default_paths.insert(0, Path(env_config_path))

        # 如果指定了配置文件路径
        if config_path:
            default_paths.insert(0, Path(config_path))

        # 尝试加载配置文件
        for path in default_paths:
            if path.exists():
                return cls.from_yaml(str(path))

        raise FileNotFoundError(
            f"未找到配置文件。尝试的路径: {[str(p) for p in default_paths]}"
        )

    def _resolve_variables(self):
        """解析配置中的变量引用（如 ${data.root}）"""
        self._config = self._resolve_dict(self._config)

    def _resolve_dict(self, d: Dict) -> Dict:
        """递归解析字典中的变量"""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._resolve_dict(value)
            elif isinstance(value, list):
                result[key] = [self._resolve_value(v) for v in value]
            else:
                result[key] = self._resolve_value(value)
        return result

    def _resolve_value(self, value: Any) -> Any:
        """解析单个值中的变量"""
        if not isinstance(value, str):
            return value

        # 检查是否包含变量引用
        if '${' not in value:
            return value

        # 使用Template进行变量替换
        try:
            # 构建变量字典（扁平化配置）
            variables = self._flatten_config(self._config)
            template = Template(value)
            return template.safe_substitute(variables)
        except Exception:
            return value

    def _flatten_config(self, d: Dict, parent_key: str = '') -> Dict:
        """将嵌套字典扁平化为点号分隔的键"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_config(v, new_key).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项（支持点号路径）

        Args:
            key: 配置键（支持点号分隔，如 'data.root'）
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """
        设置配置项

        Args:
            key: 配置键（支持点号分隔）
            value: 配置值
        """
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def to_dict(self) -> Dict[str, Any]:
        """返回完整配置字典"""
        return self._config.copy()

    def __getitem__(self, key: str) -> Any:
        """支持字典式访问"""
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        """支持字典式设置"""
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """支持 in 操作符"""
        return self.get(key) is not None

    def __repr__(self) -> str:
        return f"Config({self._config})"


# 全局配置实例（延迟加载）
_global_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = Config.load()
    return _global_config


def set_config(config: Config):
    """设置全局配置实例"""
    global _global_config
    _global_config = config


def reload_config(config_path: Optional[str] = None):
    """重新加载配置"""
    global _global_config
    _global_config = Config.load(config_path)
    return _global_config
