# Philippine AI Governance Corpus

<div id="overview">
    <img alt="Repo Forks" src="https://img.shields.io/github/forks/ramennaut/aigov-corpus?style=for-the-badge&labelColor=2A2A2A&color=7CD995">
    <img alt="Repo Stars" src="https://img.shields.io/github/stars/ramennaut/aigov-corpus?style=for-the-badge&labelColor=2A2A2A&color=7CD995">
    <img alt="Repo License" src="https://img.shields.io/github/license/ramennaut/aigov-corpus?style=for-the-badge&labelColor=2A2A2A&color=7CD995">
</div>

## What is this dataset?

The Philippine AI Governance Corpus is a collection of Philippine legislative documents that directly and substantively address artificial intelligence or closely related digital automation issues.

At this stage, the corpus includes house bills and resolutions from the 15th, 16th, 17th, 18th, 19th, and 20th Congress of the House of Representatives of the Philippines, filtered for AI relevance.

Each document is stored as:

- a machine-readable Markdown file
- an original PDF copy
- a `metadata.json` file describing the document

## How do I get it?

You can access the data by cloning the repository:

```bash
git clone https://github.com/<your-username>/<your-repo>.git
```

Or downloading it as a ZIP file from the GitHub.

If there are GitHub releases or dataset snapshots in the future, they can be listed here.

## What are its sources?
All underlying documents are sourced from official public records, primarily the House of Representatives of the Philippines website. Document text and some metadata fields are copied or derived from these official sources. Other metadata fields (e.g., AI-related classification) may be produced by scripts and/or language models.