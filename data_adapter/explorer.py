"""
Data Explorer - Discover available datasets in GPF directory.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


class LocalDataExplorer:
    """Scan local GPF directory for match data files."""
    
    def __init__(self, base_path: str = "GPF"):
        self.base_path = Path(base_path)
    
    def discover_satellite_folders(
        self,
        sat_id: Optional[str] = None,
        date_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Scan base_path for satellite folders.

        Structure:
            base_path/
                S6A/
                    S6A_P4_2__LR_STD__NT_091_051_20230501T004921...nc
                JA3/
                    ...

        Each satellite folder = one dataset unit.
        """
        datasets = []
        if not self.base_path.exists():
            return datasets

        for folder in sorted(self.base_path.iterdir()):
            if not folder.is_dir():
                continue

            folder_name = folder.name
            # Filter by sat_id if given (exact or substring match)
            if sat_id and sat_id.upper() != folder_name.upper() and sat_id.upper() not in folder_name.upper():
                continue

            nc_files = []
            total_size = 0
            start_dates, end_dates = [], []

            for nc_file in sorted(folder.glob("*.nc")):
                filename = nc_file.name
                # 支持两种命名:
                #   S6A_P4_2__LR_STD__NT_091_051_20230501T004921_20230501T014534_F08.nc
                #   JA3_GPN_2PfP337_254_20230501_004359_20230501_014012.nc
                match = re.search(r"(\d{8})[_T]\d{6}[_T](\d{8})[_T]\d{6}", filename)
                if match:
                    f_start = match.group(1)
                    f_end = match.group(2)
                    start_dates.append(f_start)
                    end_dates.append(f_end)

                total_size += nc_file.stat().st_size
                nc_files.append({
                    "path": str(nc_file),
                    "filename": filename,
                    "size_bytes": nc_file.stat().st_size,
                })

            if not nc_files:
                continue

            start_date = min(start_dates) if start_dates else "00000000"
            end_date = max(end_dates) if end_dates else "99999999"

            if date_range and (end_date < date_range[0] or start_date > date_range[1]):
                continue

            datasets.append({
                "sat_id": folder_name.upper(),
                "path": str(folder),
                "folder_name": folder_name,
                "nc_files": nc_files,
                "nc_count": len(nc_files),
                "start_date": start_date,
                "end_date": end_date,
                "total_size_bytes": total_size,
            })

        return sorted(datasets, key=lambda x: x["start_date"])

    def find_match_files(
        self,
        sat_id: Optional[str] = None,
        aux_type: Optional[str] = None,
        date_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Legacy wrapper - returns satellite folders as datasets."""
        return self.discover_satellite_folders(sat_id=sat_id, date_range=date_range)

    def find_nc_files(
        self,
        sat_id: Optional[str] = None,
        aux_type: Optional[str] = None,
        date_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Find NetCDF files matching satellite and date range."""
        datasets = []
        
        for nc_file in self.base_path.rglob("*.nc"):
            filename = nc_file.name
            
            # Parse: S6A_P4_2__LR_STD__NT_091_051_20230501T004921_20230501T014534_F08.nc
            # Date format: YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS
            match = re.search(r"(\w+).*?(\d{8})T\d+_(\d{8})T", filename)
            if not match:
                continue
            
            file_sat = match.group(1)
            file_start_date = match.group(2)
            file_end_date = match.group(3)
            
            if sat_id and sat_id not in file_sat:
                continue
            # Check if any part of the date range overlaps
            if date_range:
                if file_end_date < date_range[0] or file_start_date > date_range[1]:
                    continue
            
            inferred_aux = aux_type if aux_type else None
            
            datasets.append({
                "path": str(nc_file),
                "filename": filename,
                "sat_id": file_sat,
                "aux_type": inferred_aux,
                "date": file_start_date,  # Use start date for sorting
                "date_range": (file_start_date, file_end_date),
                "size_bytes": nc_file.stat().st_size,
            })
        
        return sorted(datasets, key=lambda x: x["date"])

    def find_h5_files(self, base_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find HDF5 files for SIG0 cross validation."""
        datasets = []
        search_path = Path(base_dir) if base_dir else self.base_path
        
        for h5_file in search_path.rglob("*.h5"):
            filename = h5_file.name
            match = re.search(r"XOver_data.*?(\d{8})", filename)
            date_str = match.group(1) if match else "00000000"
            
            datasets.append({
                "path": str(h5_file),
                "filename": filename,
                "date": date_str,
                "size_bytes": h5_file.stat().st_size,
            })
        
        return sorted(datasets, key=lambda x: x["date"])

    def find_tide_data(self, base_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find tide station matching data (HY-2BGDR NC + WSTG TXT)."""
        datasets = []
        search_path = Path(base_dir) if base_dir else self.base_path
        
        nc_dir = search_path / "HY-2BGDR"
        wstg_dir = search_path / "WSTG"
        
        if not nc_dir.exists() or not wstg_dir.exists():
            return datasets
        
        nc_files = list(nc_dir.glob("*.nc"))
        txt_files = list(wstg_dir.rglob("*.txt"))
        
        if nc_files and txt_files:
            datasets.append({
                "path": str(nc_dir),
                "nc_count": len(nc_files),
                "txt_count": len(txt_files),
                "wstg_dir": str(wstg_dir),
                "mss_path": str(search_path / "DTU18MSS_1min.nc"),
                "fes2014_path": None,  # Will be set later
            })
        
        return datasets
