# TODO: went thru heavy debugging - pls refactor
 
import os
import json
import re
import time
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import requests
import tomli
import tomli_w

load_dotenv()

SEGMENTATION_PROMPT = """Analyze this bill's markdown content and identify logical segments.

Segments should be meaningful groups of content that belong together, not necessarily following section headings.
Consider the bill's structure, themes, and natural groupings of related concepts.

For each segment, provide:
1. A unique kebab-case segment ID (e.g., "intro-meta", "exec-summary", "labor-intent", "prohibitions")
2. The line number where the segment starts (1-indexed)

Return ONLY a JSON array of objects with this structure:
[
  {"segment_id": "intro-meta", "start_line": 1},
  {"segment_id": "definitions", "start_line": 15},
  {"segment_id": "labor-intent", "start_line": 45}
]

Do not include any other text or explanation."""

SUMMARY_PROMPT = """Determine if this bill segment is substantive and useful (contains important information about the bill's purpose, mechanics, impact, or governance).

If the segment is substantive: Return ONLY a 1-2 sentence summary focusing on key purpose and content. Do not include "YES" or any prefix.
If the segment is NOT substantive: Return ONLY the word "SKIP"

Examples:
Good: "Establishes penalties for violations including fines up to $50,000 and imprisonment."
Bad: "YES - Establishes penalties for violations..."
Bad: "Yes, this segment establishes penalties..."
"""

TAGS_PROMPT = """Generate 3-5 relevant tags for this bill segment. Tags should be kebab-case and descriptive.
Return only a JSON array of strings like: ["tag1", "tag2", "tag3"]"""


class BillContentProcessor:
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

    def call_llm(self, prompt: str, description: str = "LLM call") -> Optional[str]:
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
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"].strip()
            return result
        except requests.exceptions.Timeout as e:
            print(f"  Error: LLM timeout after 30s")
            return None
        except requests.exceptions.HTTPError as e:
            print(f"  Error: LLM HTTP {e.response.status_code}")
            return None
        except Exception as e:
            print(f"  Error: {type(e).__name__}: {e}")
            return None

    def segment_content(self, content: str) -> Optional[list]:
        """Call LLM to identify segment boundaries, returns list of dicts with segment_id and start_line."""
        lines = content.splitlines()
        line_count = len(lines)
        
        # Add numbered lines to help LLM identify correct line numbers
        numbered_content = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
        
        prompt = f"""{SEGMENTATION_PROMPT}

IMPORTANT: This content has {line_count} lines total. Line numbers must be between 1 and {line_count}.

Bill content with line numbers:
{numbered_content}"""
        
        response = self.call_llm(prompt, "Segmentation")
        
        if not response:
            return None
        
        # Clean up response
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        try:
            segments = json.loads(response)
            # Validate and filter out invalid line numbers
            valid_segments = []
            for seg in segments:
                if 1 <= seg['start_line'] <= line_count:
                    valid_segments.append(seg)
                else:
                    print(f"  Warning: Ignoring segment '{seg['segment_id']}' with invalid line {seg['start_line']} (max: {line_count})")
            return valid_segments
        except json.JSONDecodeError as e:
            print(f"  Error: Failed to parse segmentation JSON: {e}")
            return None

    def insert_segment_markers(self, content: str, segments: list) -> str:
        """Insert segment markers into the markdown content at specified line numbers."""
        lines = content.splitlines(keepends=True)
        
        # Sort segments by start_line in reverse order so we can insert from bottom to top
        # This way line numbers don't shift as we insert
        sorted_segments = sorted(segments, key=lambda s: s['start_line'], reverse=True)
        
        for seg in sorted_segments:
            seg_id = seg['segment_id']
            start_line = seg['start_line']
            
            # Convert to 0-indexed
            line_idx = start_line - 1
            
            # Insert marker before the line
            marker = f"{{{seg_id}}}\n"
            lines.insert(line_idx, marker)
        
        return ''.join(lines)

    def extract_segments(self, content: str) -> dict:
        pattern = r"\{([\w-]+)\}"
        segments = {}
        
        parts = re.split(pattern, content)
        for i in range(1, len(parts), 2):
            seg_id = parts[i]
            seg_content = parts[i + 1] if i + 1 < len(parts) else ""
            segments[seg_id] = seg_content.strip()
        
        return segments

    def summarize_segment(self, segment_text: str) -> Optional[str]:
        prompt = f"{SUMMARY_PROMPT}\n\nSegment:\n{segment_text}"
        response = self.call_llm(prompt, "Summarization")
        
        if not response:
            return None
        
        # Clean up common prefixes that LLMs might add
        response = response.strip()
        
        # Remove "YES" or "Yes" prefixes with various separators
        if response.upper().startswith("YES"):
            # Handle "YES - ", "Yes: ", "YES, ", etc.
            for separator in [" - ", ": ", ", ", " "]:
                if response.upper().startswith("YES" + separator.upper()):
                    response = response[len("YES" + separator):].strip()
                    break
        
        return response

    def tag_segment(self, segment_text: str) -> Optional[list]:
        prompt = f"{TAGS_PROMPT}\n\nSegment:\n{segment_text}"
        response = self.call_llm(prompt, "Tagging")
        
        if not response:
            return []
        
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        
        try:
            tags = json.loads(response)
            return tags
        except json.JSONDecodeError as e:
            print(f"  Error parsing tags JSON: {e}")
            return []

    def process_bill(self, congress_label: str, bill_number: str) -> bool:
        bill_dir = self.data_dir / congress_label / bill_number
        md_path = bill_dir / f"{bill_number}.md"
        md_backup_path = bill_dir / f"{bill_number}.md.bak"
        toml_path = bill_dir / f"{bill_number}.toml"
        
        if not md_path.exists():
            print(f"  Markdown file not found")
            return False

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"  Error reading markdown: {e}")
            return False

        try:
            with open(md_backup_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"  Error creating backup: {e}")
            return False

        print(f"  Segmenting content...")
        segment_list = self.segment_content(content)
        if not segment_list:
            print(f"  Segmentation failed")
            return False

        segmented_content = self.insert_segment_markers(content, segment_list)

        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(segmented_content)
        except Exception as e:
            print(f"  Error writing segmented markdown: {e}")
            return False

        segments = self.extract_segments(segmented_content)
        if not segments:
            print(f"  No segments found")
            return False

        # Initialize or load existing TOML data
        if toml_path.exists():
            try:
                with open(toml_path, "rb") as f:
                    segments_toml = tomli.load(f)
            except Exception as e:
                segments_toml = {}
        else:
            segments_toml = {}

        print(f"  Processing {len(segments)} segments...")
        processed_count = 0
        
        if "segments" not in segments_toml:
            segments_toml["segments"] = {}

        for idx, (seg_id, segment_text) in enumerate(segments.items(), 1):
            # First check if segment is substantive
            summary = self.summarize_segment(segment_text)
            
            if not summary:
                continue
            
            if summary.strip().upper() == "SKIP":
                print(f"  - {seg_id}: skipped (not substantive)")
                continue
            
            # Only generate tags if segment is substantive
            tags = self.tag_segment(segment_text)
            
            if not tags:
                continue
            
            segments_toml["segments"][seg_id] = {
                "summary": summary,
                "tags": tags
            }
            processed_count += 1
            print(f"  - {seg_id}: ✓")
            
            # Write incrementally after each segment
            try:
                with open(toml_path, "wb") as f:
                    tomli_w.dump(segments_toml, f)
            except Exception as e:
                print(f"  Error writing TOML: {e}")

        if processed_count == 0:
            print(f"  No segments processed")
            return False

        print(f"  Saved {processed_count} segments")
        return True

    def process_congress(self, congress_label: str) -> None:
        congress_dir = self.data_dir / congress_label
        
        if not congress_dir.exists():
            print(f"Congress directory not found: {congress_dir}")
            return

        bill_dirs = [d for d in congress_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
        if not bill_dirs:
            print(f"No bill directories found in {congress_label}")
            return

        print(f"Found {len(bill_dirs)} bills in {congress_label}")
        print(f"Model: {self.model}\n")

        for idx, bill_dir in enumerate(bill_dirs, 1):
            bill_number = bill_dir.name
            print(f"[{idx}/{len(bill_dirs)}] {bill_number}")
            
            start_time = time.time()
            success = self.process_bill(congress_label, bill_number)
            elapsed = time.time() - start_time
            
            status = "✓" if success else "✗"
            print(f"  {status} Completed in {elapsed:.1f}s\n")


if __name__ == "__main__":
    try:
        processor = BillContentProcessor()
        processor.process_congress("20th")
    except Exception as e:
        print(f"Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
