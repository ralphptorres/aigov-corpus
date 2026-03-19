import os
import json
import shutil
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import requests

load_dotenv()

SYSTEM_PROMPT = """You classify bills and resolutions as AI-related or not.

A measure is AI-related if it DIRECTLY and SUBSTANTIVELY addresses any of the following:

1. Artificial intelligence (AI), machine learning (ML), deep learning, algorithmic systems, automated decision systems, predictive models, autonomous systems, or robotics; OR
2. Governance, regulation, promotion, restriction, safety, security, risk management, or standards for AI/ML or algorithmic systems; OR
3. Programs, incentives, protections, or obligations that explicitly involve AI technologies, AI-enabled tools, intelligent automation, or algorithm-driven systems; OR
4. Critical digital or data-driven decision systems where AI/ML/algorithms are explicitly described as essential or required components.

If AI is only mentioned incidentally, metaphorically, or in a non-substantive way, classify as NO.

If unsure, default to NO.

Respond with only "YES" or "NO"."""


class BillClassifier:
    def __init__(
        self,
        data_dir: Optional[Path] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> None:
        self.data_dir = data_dir or (Path(__file__).parent.parent / "data" / "ph-senate")
        self.api_url = api_url or os.getenv("LLM_API_URL", "https://openrouter.ai/api/v1/chat/completions")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "google/gemini-2.0-flash-lite-001")
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY environment variable not set")

    def classify_bill(self, bill_text: str) -> Optional[str]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/aigov-corpus",
                "X-Title": "AI Gov Corpus"
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": bill_text}
                    ],
                    "temperature": 0
                },
                timeout=30
            )
            response.raise_for_status()
            classification = response.json()["choices"][0]["message"]["content"].strip().upper()
            return classification if classification in ("YES", "NO") else None
        except requests.exceptions.HTTPError as e:
            print(f"  error classifying bill (HTTP {e.response.status_code}): {e.response.text}")
            return None
        except Exception as e:
            print(f"  error classifying bill: {e}")
            return None

    def process_bill(self, congress_label: str, bill_number: str) -> bool:
        bill_dir = self.data_dir / congress_label / bill_number
        metadata_path = bill_dir / "metadata.json"

        if not metadata_path.exists():
            print(f"metadata.json not found for {bill_number}")
            return False

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"error loading metadata: {e}")
            return False

        bill_info = metadata.get("bill_info", {})
        title = bill_info.get("title", "")
        long_title = bill_info.get("long_title", "")
        subjects = ", ".join(bill_info.get("subjects", []))
        bill_text = f"Title: {title}\n\nLong Title: {long_title}\n\nSubjects: {subjects}"
        
        classification = self.classify_bill(bill_text)
        if not classification:
            return False

        metadata["ai_related"] = classification == "YES"
        
        try:
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            print(f"  classified as AI-related: {metadata['ai_related']}")
            
            if not metadata["ai_related"]:
                self._move_to_review(congress_label, bill_dir)
            return True
        except Exception as e:
            print(f"error saving classification: {e}")
            return False

    def _move_to_review(self, congress_label: str, bill_dir: Path) -> None:
        try:
            review_dir = self.data_dir / congress_label / "_classify_manually"
            review_dir.mkdir(parents=True, exist_ok=True)
            target_dir = review_dir / bill_dir.name
            
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.move(str(bill_dir), str(target_dir))
            print(f"  moved to: {target_dir.relative_to(self.data_dir)}")
        except Exception as e:
            print(f"error moving bill: {e}")

    def process_congress(self, congress_label: str) -> None:
        congress_dir = self.data_dir / congress_label
        if not congress_dir.exists():
            print(f"congress directory not found: {congress_dir}")
            return

        bill_dirs = [d for d in congress_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
        if not bill_dirs:
            print(f"No bill directories found in {congress_label}")
            return

        print(f"Found {len(bill_dirs)} bills in {congress_label}")
        print(f"Using model: {self.model}")

        for idx, bill_dir in enumerate(bill_dirs, 1):
            bill_number = bill_dir.name
            print(f"\n{'=' * 80}")
            print(f"Classifying {idx}/{len(bill_dirs)}: {bill_number}")
            print("=" * 80)
            self.process_bill(congress_label, bill_number)


if __name__ == "__main__":
    classifier = BillClassifier()
    classifier.process_congress("20th")
