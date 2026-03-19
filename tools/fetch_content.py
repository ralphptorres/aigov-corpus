import json
import cloudscraper
from pathlib import Path
from typing import Optional, Dict, Any


class BillContentDownloader:
    def __init__(self, data_dir: Path = None) -> None:
        self.scraper = cloudscraper.create_scraper()
        self.data_dir = data_dir or (Path(__file__).parent.parent / "data" / "ph-senate")

    def load_metadata(self, metadata_path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"error loading metadata from {metadata_path}: {e}")
            return None

    def download_pdf(self, bill_dir: Path, bill_number: str, pdf_url: str) -> bool:
        try:
            pdf_path = bill_dir / f"{bill_number}.pdf"

            if pdf_path.exists():
                print(f"  pdf already exists: {pdf_path.name}")
                return True

            response = self.scraper.get(pdf_url)
            if response.status_code == 200:
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                print(f"  pdf downloaded: {pdf_path.name}")
                return True
            else:
                print(f"  failed to download pdf: {response.status_code}")
                return False
        except Exception as e:
            print(f"  error downloading pdf: {e}")
            return False

    def process_bill(self, congress_label: str, bill_number: str) -> bool:
        bill_dir = self.data_dir / congress_label / bill_number
        metadata_path = bill_dir / "metadata.json"

        if not metadata_path.exists():
            print(f"metadata.json not found for {bill_number}")
            return False

        metadata = self.load_metadata(metadata_path)
        if not metadata:
            return False

        documents = metadata.get("documents", [])
        if not documents:
            print(f"no documents found in metadata for {bill_number}")
            return True

        print(f"\nDownloading PDFs for {bill_number}:")
        for doc in documents:
            pdf_url = doc.get("pdf_url")
            if pdf_url:
                self.download_pdf(bill_dir, bill_number, pdf_url)

        return True

    def process_congress(self, congress_label: str) -> None:
        congress_dir = self.data_dir / congress_label
        if not congress_dir.exists():
            print(f"congress directory not found: {congress_dir}")
            return

        bill_dirs = [d for d in congress_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
        print(f"Found {len(bill_dirs)} bills in {congress_label}")

        for idx, bill_dir in enumerate(bill_dirs, 1):
            bill_number = bill_dir.name
            print(f"\n{'=' * 80}")
            print(f"Processing {idx}/{len(bill_dirs)}: {bill_number}")
            print("=" * 80)
            self.process_bill(congress_label, bill_number)


if __name__ == "__main__":
    downloader = BillContentDownloader()
    downloader.process_congress("20th")
