"""
Configuration Manager for Cal/Val Agent.

Loads settings from YAML config files and provides defaults.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """Manage configuration from YAML files and defaults."""
    
    DEFAULTS = {
        "qc_thresholds": {
            "swh_max": 15.0,
            "wind_speed_range": [2.0, 40.0],
            "outlier_threshold_cm": 15.0,
            "match_time_hours": 2.0,
            "distance_to_coast_km": 50.0,
            "ocean_depth_m": 1000.0,
            "lat_range": [-60, 60],
            "lon_range": [-180, 180]
        },
        "fallback": {
            "strategies": [
                {"action": "relax_match_time", "value": 4.0},
                {"action": "reduce_coast_distance", "value": 30.0},
                {"action": "relax_outlier_threshold", "value": 20.0},
                {"action": "expand_date_range", "value": 7}
            ]
        }
    }
    
    def __init__(self, config_dir: str = "configs"):
        self.config_dir = Path(config_dir)
        self._settings: Dict[str, Any] = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load all YAML configuration files."""
        if not self.config_dir.exists():
            self._settings = self.DEFAULTS.copy()
            return
        
        settings = self.DEFAULTS.copy()
        
        # Load settings.yaml if exists
        settings_file = self.config_dir / "settings.yaml"
        if settings_file.exists():
            with open(settings_file, 'r', encoding='utf-8') as f:
                user_settings = yaml.safe_load(f) or {}
                self._deep_merge(settings, user_settings)
        
        # Load additional YAML configs
        for yaml_file in self.config_dir.glob("*.yaml"):
            if yaml_file.name != "settings.yaml":
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    section_name = yaml_file.stem
                    section_data = yaml.safe_load(f) or {}
                    settings[section_name] = section_data
        
        self._settings = settings
    
    def _deep_merge(self, base: dict, override: dict):
        """Deep merge two dicts."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation path."""
        keys = key.split(".")
        val = self._settings
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val
    
    def get_thresholds(self) -> Dict[str, Any]:
        """Get QC thresholds."""
        return self.get("qc_thresholds", self.DEFAULTS["qc_thresholds"])
    
    def get_fallback_strategies(self) -> list:
        """Get fallback strategies."""
        return self.get("fallback.strategies", self.DEFAULTS["fallback"]["strategies"])


# Global config instance
config_manager = None


def init_config(config_dir: str = "configs"):
    """Initialize global config manager."""
    global config_manager
    config_manager = ConfigManager(config_dir)


def get_config() -> ConfigManager:
    """Get the global config manager."""
    return config_manager


# Convenience functions
def get_thresholds() -> Dict[str, Any]:
    """Get QC thresholds."""
    return get_config().get_thresholds() if get_config() else {}


def get_fallback() -> list:
    """Get fallback strategies."""
    return get_config().get_fallback_strategies() if get_config() else []