"""
Image Inventory Tool for Qlik-to-Power BI Migration

Extracts and catalogs embedded images from Qlik apps.
Produces inventory for manual Power BI image asset management.
"""

import json
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
from zipfile import ZipFile
import base64


@dataclass
class ImageAsset:
    """Metadata for an embedded image."""
    image_id: str  # Unique identifier (SHA256 hash)
    original_name: str
    file_size_bytes: int
    image_type: str  # png, jpg, gif, bmp, svg, etc.
    dimensions: Optional[str] = None  # WxH if parseable
    used_in_sheets: List[str] = field(default_factory=list)
    used_in_visuals: List[str] = field(default_factory=list)
    embedded_in_qvf: bool = True
    sha256_hash: str = ""
    base64_preview: Optional[str] = None  # First 100KB as base64
    
    def to_dict(self) -> Dict:
        return {
            "image_id": self.image_id,
            "original_name": self.original_name,
            "file_size_bytes": self.file_size_bytes,
            "file_size_mb": round(self.file_size_bytes / (1024 * 1024), 2),
            "image_type": self.image_type,
            "dimensions": self.dimensions,
            "used_in_sheets": self.used_in_sheets,
            "used_in_visuals": self.used_in_visuals,
            "embedded_in_qvf": self.embedded_in_qvf,
            "sha256_hash": self.sha256_hash,
            "preview_available": self.base64_preview is not None
        }


@dataclass
class ImageInventory:
    """Complete image inventory for a Qlik app."""
    app_id: str
    app_path: str
    total_images: int
    total_image_size_bytes: int
    images: List[ImageAsset] = field(default_factory=list)
    duplicate_images: List[Dict] = field(default_factory=list)  # Groups of duplicate hashes
    
    def to_dict(self) -> Dict:
        return {
            "app_id": self.app_id,
            "app_path": self.app_path,
            "total_images": self.total_images,
            "total_image_size_mb": round(self.total_image_size_bytes / (1024 * 1024), 2),
            "images": [img.to_dict() for img in self.images],
            "duplicate_images": self.duplicate_images
        }


class ImageInventoryBuilder:
    """Extracts and catalogs images from Qlik apps."""
    
    # Supported image formats
    SUPPORTED_FORMATS = {
        b'\x89PNG': 'png',
        b'\xFF\xD8\xFF': 'jpg',
        b'GIF8': 'gif',
        b'BM': 'bmp',
        b'<svg': 'svg',
        b'\x00\x00\x01\x00': 'ico',
    }
    
    def __init__(self):
        """Initialize image inventory builder."""
        self.logger = logging.getLogger(__name__)
    
    def build_inventory(self, qvf_path: str, app_id: Optional[str] = None) -> ImageInventory:
        """
        Extract image inventory from QVF file.
        
        Args:
            qvf_path: Path to QVF file
            app_id: Optional app identifier (defaults to filename)
        
        Returns:
            ImageInventory with all embedded images
        """
        qvf_path = Path(qvf_path)
        app_id = app_id or qvf_path.stem
        
        images: List[ImageAsset] = []
        total_size = 0
        image_hashes: Dict[str, List[str]] = {}  # hash -> [image_ids]
        
        try:
            with ZipFile(qvf_path, 'r') as qvf:
                # Extract all potential image files
                for file_info in qvf.filelist:
                    if self._is_image_file(file_info.filename):
                        with qvf.open(file_info) as f:
                            image_data = f.read()
                        
                        asset = self._create_image_asset(
                            image_data,
                            file_info.filename
                        )
                        
                        images.append(asset)
                        total_size += asset.file_size_bytes
                        
                        # Track duplicates by hash
                        if asset.sha256_hash not in image_hashes:
                            image_hashes[asset.sha256_hash] = []
                        image_hashes[asset.sha256_hash].append(asset.image_id)
                
                # Find usage information from manifest
                self._extract_usage_information(qvf, images)
        
        except Exception as e:
            self.logger.error(f"Error building image inventory for {qvf_path}: {e}")
        
        # Identify duplicate images
        duplicates = self._identify_duplicates(image_hashes, images)
        
        inventory = ImageInventory(
            app_id=app_id,
            app_path=str(qvf_path),
            total_images=len(images),
            total_image_size_bytes=total_size,
            images=images,
            duplicate_images=duplicates
        )
        
        self.logger.info(
            f"Inventory for {app_id}: {len(images)} images, "
            f"{round(total_size / (1024 * 1024), 2)}MB total"
        )
        
        return inventory
    
    def _is_image_file(self, filename: str) -> bool:
        """Check if file is likely an image based on extension."""
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.ico', '.webp'}
        return Path(filename).suffix.lower() in image_extensions
    
    def _create_image_asset(self, image_data: bytes, filename: str) -> ImageAsset:
        """Create ImageAsset from image data."""
        image_hash = hashlib.sha256(image_data).hexdigest()
        image_type = self._detect_image_type(image_data)
        
        # Create preview (first 100KB)
        preview_size = min(102400, len(image_data))
        base64_preview = base64.b64encode(image_data[:preview_size]).decode('utf-8')
        
        asset = ImageAsset(
            image_id=image_hash[:16],  # First 16 chars of hash
            original_name=Path(filename).name,
            file_size_bytes=len(image_data),
            image_type=image_type,
            sha256_hash=image_hash,
            base64_preview=base64_preview if len(image_data) > 100 else None
        )
        
        return asset
    
    def _detect_image_type(self, data: bytes) -> str:
        """Detect image type from file signature."""
        for signature, img_type in self.SUPPORTED_FORMATS.items():
            if data.startswith(signature):
                return img_type
        return "unknown"
    
    def _extract_usage_information(self, qvf: ZipFile, images: List[ImageAsset]) -> None:
        """Try to extract usage information from QVF manifest."""
        try:
            # Look for manifest.json or similar metadata
            manifest_names = ["manifest.json", "workbook.json"]
            manifest_data = None
            
            for name in manifest_names:
                if name in qvf.namelist():
                    with qvf.open(name) as f:
                        manifest_data = json.load(f)
                    break
            
            if manifest_data:
                # Look for image references in sheets/visuals
                sheets = manifest_data.get("sheets", [])
                for sheet in sheets:
                    sheet_name = sheet.get("name", "Unknown")
                    visuals = sheet.get("visuals", [])
                    for visual in visuals:
                        visual_name = visual.get("name", "Unknown")
                        # Check if visual references image
                        if "image" in visual or "backgroundImage" in visual:
                            # Try to match to our extracted images
                            for image in images:
                                if image.original_name in str(visual):
                                    image.used_in_sheets.append(sheet_name)
                                    image.used_in_visuals.append(visual_name)
        
        except Exception as e:
            self.logger.debug(f"Could not extract usage info: {e}")
    
    def _identify_duplicates(
        self,
        image_hashes: Dict[str, List[str]],
        images: List[ImageAsset]
    ) -> List[Dict]:
        """Identify duplicate images by hash."""
        duplicates = []
        images_by_id = {img.image_id: img for img in images}
        
        for hash_val, image_ids in image_hashes.items():
            if len(image_ids) > 1:
                duplicate_group = {
                    "hash": hash_val,
                    "count": len(image_ids),
                    "size_bytes": images_by_id[image_ids[0]].file_size_bytes,
                    "image_ids": image_ids,
                    "filenames": [images_by_id[iid].original_name for iid in image_ids],
                    "potential_savings_bytes": (len(image_ids) - 1) * images_by_id[image_ids[0]].file_size_bytes
                }
                duplicates.append(duplicate_group)
                self.logger.info(
                    f"Found {len(image_ids)} duplicate images: {duplicate_group['filenames']}"
                )
        
        return duplicates


class ImageInventoryReporter:
    """Generates reports from image inventories."""
    
    def __init__(self):
        """Initialize reporter."""
        self.logger = logging.getLogger(__name__)
    
    def generate_summary(self, inventories: List[ImageInventory]) -> Dict:
        """Generate portfolio-level summary."""
        total_images = sum(inv.total_images for inv in inventories)
        total_size = sum(inv.total_image_size_bytes for inv in inventories)
        total_duplicates = sum(len(inv.duplicate_images) for inv in inventories)
        
        duplicate_savings = sum(
            dup["potential_savings_bytes"]
            for inv in inventories
            for dup in inv.duplicate_images
        )
        
        return {
            "total_apps": len(inventories),
            "total_images": total_images,
            "total_image_size_mb": round(total_size / (1024 * 1024), 2),
            "total_duplicate_groups": total_duplicates,
            "potential_savings_mb": round(duplicate_savings / (1024 * 1024), 2),
            "apps_with_large_images": len([
                inv for inv in inventories
                if inv.total_image_size_bytes > 100 * 1024 * 1024  # >100MB
            ]),
            "image_types_found": list(set(
                img.image_type
                for inv in inventories
                for img in inv.images
            ))
        }
    
    def save_inventory(self, inventory: ImageInventory, output_path: str) -> None:
        """Save inventory to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(inventory.to_dict(), f, indent=2)
        
        self.logger.info(f"Saved inventory to {output_path}")
    
    def generate_html_report(
        self,
        inventory: ImageInventory,
        output_path: str
    ) -> None:
        """Generate HTML report with image previews."""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Image Inventory Report - {inventory.app_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
                .image-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }}
                .image-card {{ border: 1px solid #ddd; padding: 10px; border-radius: 5px; }}
                .image-card img {{ max-width: 100%; height: auto; }}
                .duplicate-warning {{ color: #d32f2f; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Image Inventory Report</h1>
            <div class="summary">
                <p><strong>App:</strong> {inventory.app_id}</p>
                <p><strong>Total Images:</strong> {inventory.total_images}</p>
                <p><strong>Total Size:</strong> {round(inventory.total_image_size_bytes / (1024 * 1024), 2)} MB</p>
                <p><strong>Duplicate Groups:</strong> {len(inventory.duplicate_images)}</p>
            </div>
            <h2>Images</h2>
            <div class="image-grid">
        """
        
        for img in inventory.images:
            if img.base64_preview:
                html_content += f"""
                <div class="image-card">
                    <img src="data:image/{img.image_type};base64,{img.base64_preview[:500]}..." alt="{img.original_name}">
                    <p><strong>{img.original_name}</strong></p>
                    <p>Size: {round(img.file_size_bytes / 1024, 1)} KB</p>
                </div>
                """
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        output_path = Path(output_path)
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        self.logger.info(f"Saved HTML report to {output_path}")


# Example usage
if __name__ == "__main__":
    builder = ImageInventoryBuilder()
    
    # Build inventory for sample app
    inventory = builder.build_inventory("examples/qlik/sample_sales.qvf")
    
    # Save inventory
    reporter = ImageInventoryReporter()
    reporter.save_inventory(
        inventory,
        "output/sample_sales_image_inventory.json"
    )
    
    print(json.dumps(inventory.to_dict(), indent=2))
