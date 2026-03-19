import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()


class BillMarkdownExtractor:
    def __init__(
        self, data_dir: Optional[Path] = None, api_key: Optional[str] = None
    ) -> None:
        self.data_dir = data_dir or (
            Path(__file__).parent.parent / "data" / "ph-senate"
        )
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY environment variable not set")
        self.client = Mistral(api_key=self.api_key)

    def extract_text_from_pdf(self, pdf_path: Path) -> Optional[str]:
        try:
            with open(pdf_path, "rb") as f:
                response = self.client.files.upload(
                    file={
                        "file_name": pdf_path.name,
                        "content": f,
                        "content_type": "application/pdf",
                    },
                    purpose="ocr",
                )

            ocr_response = self.client.ocr.process(
                model="mistral-ocr-latest",
                document={"type": "file", "file_id": response.id},
            )

            if (
                not ocr_response
                or not hasattr(ocr_response, "pages")
                or not ocr_response.pages
            ):
                print(f"  unexpected response format: {ocr_response}")
                return None

            return (
                "\n\n".join(
                    [
                        page.markdown
                        for page in ocr_response.pages
                        if hasattr(page, "markdown")
                    ]
                )
                or None
            )
        except Exception as e:
            print(f"  error extracting text: {e}")
            return None

    def process_bill(self, congress_label: str, bill_number: str) -> bool:
        bill_dir = self.data_dir / congress_label / bill_number

        metadata_path = bill_dir / "metadata.json"
        if not metadata_path.exists():
            print(f"metadata.json not found for {bill_number}")
            return False

        pdf_path = bill_dir / f"{bill_number}.pdf"
        if not pdf_path.exists():
            print(f"pdf not found for {bill_number}")
            return False

        print(f"Extracting text from {pdf_path.name}...")
        text = self.extract_text_from_pdf(pdf_path)
        if not text:
            return False

        md_path = bill_dir / f"{bill_number}.md"
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"  markdown saved: {md_path.name}")
            return True
        except Exception as e:
            print(f"error saving markdown: {e}")
            return False

    def process_congress(self, congress_label: str) -> None:
        congress_dir = self.data_dir / congress_label
        if not congress_dir.exists():
            print(f"congress directory not found: {congress_dir}")
            return

        bill_dirs = [d for d in congress_dir.iterdir() if d.is_dir()]
        if not bill_dirs:
            print(f"No bill directories found in {congress_label}")
            return

        print(f"Found {len(bill_dirs)} bills in {congress_label}")

        for idx, bill_dir in enumerate(bill_dirs, 1):
            bill_number = bill_dir.name
            print(f"\n{'=' * 80}")
            print(f"Processing {idx}/{len(bill_dirs)}: {bill_number}")
            print("=" * 80)
            self.process_bill(congress_label, bill_number)


if __name__ == "__main__":
    extractor = BillMarkdownExtractor()
    extractor.process_congress("20th")
