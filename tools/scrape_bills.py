import json
import cloudscraper
from pathlib import Path
from typing import Optional, List, Dict, Any

CONGRESS_ID = 20
CONGRESS_MAP = {
    20: "twentieth",
    19: "nineteenth",
    18: "eighteenth",
    17: "seventeenth",
    16: "sixteenth",
    15: "fifteenth",
    14: "fourteenth",
    13: "thirteenth",
}

BASE_URL = "https://senate.gov.ph/legacy/api/v1/lis"
PDF_BASE_URL = "https://senate.gov.ph/legacy/lis_bills"
DATA_DIR = Path(__file__).parent.parent / "data" / "ph-senate"


class SenateScraper:
    def __init__(
        self, congress_id: int = CONGRESS_ID, data_dir: Path = DATA_DIR
    ) -> None:
        self.congress_id = congress_id
        self.congress_name = CONGRESS_MAP.get(congress_id, "twentieth")
        self.congress_label = f"{congress_id}th"
        self.scraper = cloudscraper.create_scraper()
        self.data_dir = data_dir

    def get_bills(
        self, page: int = 1, per_page: int = 50, bill_type: str = "SBN"
    ) -> Optional[Dict[str, Any]]:
        url = (
            f"{BASE_URL}/documents_v2?"
            f"document_type=bills&"
            f"congress={self.congress_id}th Congress&"
            f"type={bill_type}&"
            f"sort_by=no&sort_order=desc&"
            f"page={page}&per_page={per_page}"
        )

        try:
            response = self.scraper.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"error fetching bills: {response.status_code}")
                return None
        except Exception as e:
            print(f"network error fetching bills: {e}")
            return None

    def get_bill_comprehensive(self, bill_id: str) -> Optional[Dict[str, Any]]:
        url = f"{BASE_URL}/bills/{bill_id}/comprehensive?congress={self.congress_name}"

        try:
            response = self.scraper.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(
                    f"error fetching comprehensive data for bill {bill_id}: {response.status_code}"
                )
                return None
        except Exception as e:
            print(f"network error fetching comprehensive data: {e}")
            return None

    def get_pdf_url(self, file_path: str) -> str:
        return f"{PDF_BASE_URL}/{file_path}"

    def extract_docs(self, comp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        documents = []
        if comp_data and comp_data.get("data", {}).get("documents"):
            for doc in comp_data["data"]["documents"]:
                documents.append(
                    {
                        "description": doc.get("description"),
                        "pdf_url": self.get_pdf_url(doc.get("file_path")),
                        "file_path": doc.get("file_path"),
                        "file_size": doc.get("file_size"),
                        "upload_date": doc.get("upload_date"),
                    }
                )
        return documents

    def get_bill_dir(self, bill_number: str) -> Path:
        bill_dir = self.data_dir / self.congress_label / bill_number
        bill_dir.mkdir(parents=True, exist_ok=True)
        return bill_dir

    def save_metadata(self, bill_dir: Path, data: Dict[str, Any]) -> None:
        json_path = bill_dir / "metadata.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  metadata saved: {json_path.name}")

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

    def prepare_metadata(
        self,
        bill: Dict[str, Any],
        comp_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        metadata = {
            "bill_info": {
                "id": bill.get("id"),
                "number": bill.get("no"),
                "title": bill.get("title"),
                "long_title": bill.get("longTitle"),
                "author": bill.get("author"),
                "co_author": bill.get("coAuthor"),
                "date_filed": bill.get("dateFiled"),
                "status": bill.get("legislativeStatus"),
                "status_date": bill.get("legislativeStatusDate"),
                "primary_committee": bill.get("primaryCommittee"),
                "subjects": bill.get("subjects", []),
            },
            "comprehensive_data": comp_data.get("data") if comp_data else None,
            "documents": documents,
        }
        return metadata

    def print_bill(self, item: Dict[str, Any], documents: List[Dict[str, Any]]) -> None:
        print(f"\nBill: {item.get('no')} - {item.get('title')}")
        print(f"Status: {item.get('legislativeStatus')}")
        print(f"Filed: {item.get('dateFiled')}")
        print(f"Author: {item.get('author', 'N/A')}")

        if documents:
            print("Documents:")
            for doc in documents:
                print(f"  - {doc['description']}: {doc['pdf_url']}")

    def scrape_and_save(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        bills_data = self.get_bills()
        if not bills_data or not bills_data.get("data"):
            print("no bills data received")
            return []

        bills = bills_data.get("data")[:limit] if limit else bills_data.get("data")
        results = []

        for idx, bill in enumerate(bills, 1):
            bill_number = bill.get("no")
            print(f"\n{'=' * 80}")
            print(f"Processing {idx}/{len(bills)}: {bill_number}")
            print("=" * 80)

            comp_data = self.get_bill_comprehensive(bill["id"])
            documents = self.extract_docs(comp_data) if comp_data else []

            self.print_bill(bill, documents)

            bill_dir = self.get_bill_dir(bill_number)
            print(f"Storage: {bill_dir}")

            metadata = self.prepare_metadata(bill, comp_data, documents)
            self.save_metadata(bill_dir, metadata)

            if documents:
                print("Downloading pdfs:")
                for doc in documents:
                    self.download_pdf(bill_dir, bill_number, doc["pdf_url"])

            result = {
                "bill_number": bill_number,
                "bill_dir": bill_dir,
                "bill": bill,
                "comprehensive": comp_data,
                "documents": documents,
            }
            results.append(result)

        return results


if __name__ == "__main__":
    scraper = SenateScraper(congress_id=CONGRESS_ID)
    results = scraper.scrape_and_save(limit=20)
    print(f"\n{'=' * 80}")
    print(f"Successfully processed {len(results)} bills")
    print(f"Data saved to: {DATA_DIR / scraper.congress_label}")
