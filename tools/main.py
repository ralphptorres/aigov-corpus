import sys
from pathlib import Path
from scrape_bills import BillScraper
from fetch_content import BillContentDownloader
from classify_bills import BillClassifier
from extract_content import BillMarkdownExtractor
from segment_content import BillContentProcessor

DATA_DIR = Path(__file__).parent.parent / "data" / "ph-senate"

def scrape(congress_id=20, limit=None):
    scraper = BillScraper(congress_id=congress_id, data_dir=DATA_DIR)
    return scraper.scrape_and_save(limit=limit)

def download(congress_id=20):
    congress_label = f"{congress_id}th"
    downloader = BillContentDownloader(data_dir=DATA_DIR)
    downloader.process_congress(congress_label)

def classify(congress_id=20):
    congress_label = f"{congress_id}th"
    classifier = BillClassifier(data_dir=DATA_DIR)
    classifier.process_congress(congress_label)

def extract(congress_id=20):
    congress_label = f"{congress_id}th"
    extractor = BillMarkdownExtractor(data_dir=DATA_DIR)
    extractor.process_congress(congress_label)

def segment(congress_id=20):
    congress_label = f"{congress_id}th"
    processor = BillContentProcessor(data_dir=DATA_DIR)
    processor.process_congress(congress_label)

def main():
    congress_id = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    print(f"Scraping Congress {congress_id}...")
    scrape(congress_id, limit)
    
    print(f"\nDownloading content for Congress {congress_id}...")
    download(congress_id)
    
    print(f"\nClassifying bills for Congress {congress_id}...")
    classify(congress_id)
    
    print(f"\nExtracting markdown for Congress {congress_id}...")
    extract(congress_id)
    
    print(f"\nSegmenting content for Congress {congress_id}...")
    segment(congress_id)
    
    print("\nDone")

if __name__ == "__main__":
    main()
