from abc import ABC, abstractmethod
from pathlib import Path


class BaseBrandCrawler(ABC):
    brand_id: str
    brand_name: str
    source_site: str

    @abstractmethod
    def crawl(self, url: str | None = None, headless: bool = True) -> list[dict]:
        """표준 CSV 컬럼 형식의 상품 목록 반환"""

    def output_dir(self, project_root: Path) -> Path:
        return project_root / "data" / "output" / self.brand_id

    def default_output_path(self, project_root: Path) -> Path:
        return self.output_dir(project_root) / f"{self.brand_id}_products.csv"
