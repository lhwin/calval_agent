"""
数据质量诊断模块

功能：
1. 检查 NC/H5 文件完整性
2. 评估数据覆盖度（时间、空间）
3. 标记可疑数据（质量指标超标）
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import netCDF4 as nc
import h5py
import warnings


class DataHealthChecker:
    """数据健康检查器"""
    
    def __init__(self):
        self.warnings = []
        self.errors = []
    
    def check_nc_integrity(self, nc_path: str) -> Dict[str, Any]:
        """检查 NC 文件完整性"""
        result = {
            "path": nc_path,
            "valid": True,
            "errors": [],
            "warnings": [],
            "metadata": {}
        }
        
        try:
            dataset = nc.Dataset(nc_path, 'r')
            
            # 检查文件大小（判断是否截断）
            file_size = Path(nc_path).stat().st_size
            if file_size < 1e6:  # < 1MB
                result["warnings"].append(f"文件大小过小：{file_size / 1024:.1f} KB")
            
            # 检查必需变量
            required_vars = ['latitude', 'longitude', 'time']
            missing_vars = [v for v in required_vars if v not in dataset.variables]
            if missing_vars:
                result["errors"].append(f"缺少必需变量：{missing_vars}")
                result["valid"] = False
            
            # 检查数据量
            if 'latitude' in dataset.variables:
                n_points = len(dataset.variables['latitude'])
                result["metadata"]["n_points"] = n_points
                if n_points < 10:
                    result["warnings"].append(f"数据点过少：{n_points}")
            
            # 检查时间范围
            if 'time' in dataset.variables:
                time_var = dataset.variables['time']
                result["metadata"]["time_range"] = {
                    "start": float(time_var[0]) if len(time_var) > 0 else None,
                    "end": float(time_var[-1]) if len(time_var) > 0 else None
                }
            
            dataset.close()
            
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"无法打开文件：{str(e)[:200]}")
        
        return result
    
    def check_h5_integrity(self, h5_path: str) -> Dict[str, Any]:
        """检查 H5 文件完整性"""
        result = {
            "path": h5_path,
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            with h5py.File(h5_path, 'r') as f:
                # 检查关键数据集
                required_keys = ['/XCross', '/YCross', '/Time']
                missing = [k for k in required_keys if k not in f]
                if missing:
                    result["warnings"].append(f"可能缺少关键数据集：{missing}")
                
                # 检查文件大小
                file_size = Path(h5_path).stat().st_size
                if file_size < 1e6:
                    result["warnings"].append(f"文件大小过小：{file_size / 1024:.1f} KB")
        
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"H5 读取失败：{str(e)[:200]}")
        
        return result
    
    def assess_coverage(
        self, 
        datasets: List[Dict[str, Any]],
        required_dates: Optional[tuple] = None,
        required_lat_range: tuple = (-60, 60)
    ) -> Dict[str, Any]:
        """评估数据覆盖度"""
        assessment = {
            "total_files": len(datasets),
            "valid_files": 0,
            "coverage_score": 0.0,
            "issues": []
        }
        
        if not datasets:
            assessment["issues"].append("没有可用数据")
            return assessment
        
        valid_count = 0
        total_points = 0
        
        for ds in datasets:
            # 检查基本有效性
            path = ds.get("path")
            if not path or not Path(path).exists():
                assessment["issues"].append(f"文件不存在：{path}")
                continue
            
            # NC 文件检查
            if path.endswith('.nc'):
                health = self.check_nc_integrity(path)
                if health["valid"]:
                    valid_count += 1
                    total_points += health["metadata"].get("n_points", 0)
            
            # H5 文件检查
            elif path.endswith('.h5'):
                health = self.check_h5_integrity(path)
                if health["valid"]:
                    valid_count += 1
        
        assessment["valid_files"] = valid_count
        assessment["coverage_score"] = valid_count / len(datasets) if datasets else 0.0
        assessment["total_points"] = total_points
        
        # 判断覆盖度等级
        if assessment["coverage_score"] < 0.3:
            assessment["level"] = "critical"
            assessment["issues"].append("数据覆盖率过低 (<30%)")
        elif assessment["coverage_score"] < 0.7:
            assessment["level"] = "warning"
            assessment["issues"].append("数据覆盖率不足 (30%-70%)")
        else:
            assessment["level"] = "good"
        
        return assessment
    
    def check_quality_metrics(
        self,
        nc_path: str,
        thresholds: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """检查质量指标（SWH、风速等）"""
        if thresholds is None:
            thresholds = {
                "swh_max": 15.0,  # 米
                "wind_speed_max": 40.0,  # m/s
                "lat_min": -60,
                "lat_max": 60
            }
        
        report = {
            "path": nc_path,
            "passed": True,
            "violations": []
        }
        
        try:
            dataset = nc.Dataset(nc_path, 'r')
            
            # 检查 SWH
            if 'swh' in dataset.variables or 'sig0' in dataset.variables:
                var_name = 'swh' if 'swh' in dataset.variables else 'sig0'
                data = dataset.variables[var_name][:]
                mask = ~((data is None) | (data.mask if hasattr(data, 'mask') else False))
                valid_data = data[mask] if mask.any() else data
                
                if len(valid_data) > 0:
                    max_val = float(valid_data.max())
                    threshold = thresholds.get("swh_max", 15.0)
                    if max_val > threshold:
                        report["violations"].append(
                            f"{var_name} 最大值 {max_val:.2f} 超过阈值 {threshold}"
                        )
                        report["passed"] = False
            
            # 检查纬度范围
            if 'latitude' in dataset.variables:
                lats = dataset.variables['latitude'][:]
                min_lat, max_lat = float(lats.min()), float(lats.max())
                if min_lat < thresholds["lat_min"] or max_lat > thresholds["lat_max"]:
                    report["violations"].append(
                        f"纬度范围 [{min_lat:.1f}, {max_lat:.1f}] 超出 [{thresholds['lat_min']}, {thresholds['lat_max']}]"
                    )
            
            dataset.close()
            
        except Exception as e:
            report["passed"] = False
            report["violations"].append(f"无法读取质量指标：{str(e)[:200]}")
        
        return report


def quick_scan(base_dir: str, file_patterns: List[str] = None) -> Dict[str, Any]:
    """快速扫描目录中的数据健康状况"""
    from pathlib import Path
    
    checker = DataHealthChecker()
    
    if file_patterns is None:
        file_patterns = ["*.nc", "*.h5"]
    
    all_files = []
    for pattern in file_patterns:
        all_files.extend(list(Path(base_dir).rglob(pattern)))
    
    results = {
        "total_files": len(all_files),
        "healthy": 0,
        "degraded": 0,
        "corrupted": 0,
        "details": []
    }
    
    for f in all_files[:20]:  # 限制扫描数量
        file_result = {
            "name": f.name,
            "size_mb": f.stat().st_size / 1e6,
            "health": "unknown"
        }
        
        if f.suffix == '.nc':
            health = checker.check_nc_integrity(str(f))
            file_result["health"] = "healthy" if health["valid"] else "corrupted"
        elif f.suffix == '.h5':
            health = checker.check_h5_integrity(str(f))
            file_result["health"] = "healthy" if health["valid"] else "corrupted"
        
        if file_result["health"] == "healthy":
            results["healthy"] += 1
        elif file_result["health"] == "corrupted":
            results["corrupted"] += 1
        else:
            results["degraded"] += 1
        
        results["details"].append(file_result)
    
    return results


if __name__ == "__main__":
    # 测试
    import sys
    
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
        result = quick_scan(base_dir)
        print(f"扫描目录：{base_dir}")
        print(f"总文件数：{result['total_files']}")
        print(f"健康：{result['healthy']}, 降级：{result['degraded']}, 损坏：{result['corrupted']}")
        print("\n详细信息:")
        for d in result["details"]:
            print(f"  - {d['name']} ({d['size_mb']:.1f} MB) [{d['health']}]")
    else:
        print("用法：python data_health_check.py <directory>")
