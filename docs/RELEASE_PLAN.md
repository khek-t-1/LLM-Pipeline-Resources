# LLM Pipeline Resources — GitHub Release Plan

## Source

- Gofile: https://gofile.io/d/IQ22UNfo
- Remote file: `llm-resources-full.zip`
- Exact archive size: **14,095,115,088 bytes** (**14.095 GB / 13.127 GiB**)
- Gofile MD5: `7fbd96c0a166300db65dfccc850c30ab`
- Archive entries inspected remotely: **79,465 files**
- Uncompressed payload: **14,068,125,258 bytes**

## Archive contents

| Area | Files | Approx. payload |
|---|---:|---:|
| `llm-resources/datasets` | 84 | 11.16 GB |
| `llm-resources/repos` | 79,367 | 2.87 GB |
| `llm-resources/papers` | 8 | 41.9 MB |
| Scripts and manifests | 6 | Small |

Largest dataset groups include FineWeb, FineWeb-Edu, FineWeb-2, PleIAs Common Corpus, AllenAI Dolma3 Pool, Dolci-Instruct-SFT, Tulu-3 SFT Mixture, and NVIDIA Nemotron SFT Agentic Finance.

The repository section includes categories such as `open`, `giants`, `learn`, `serving`, `finetune`, and `eval`.

## Recommended release format

Use **512 MiB binary parts**:

- **27 parts**: `llm-resources-full.zip.00.part` through `llm-resources-full.zip.26.part`
- Parts 00–25: **536,870,912 bytes each**
- Part 26: **136,471,376 bytes**
- Additional assets: `SHA256SUMS.txt`, `MANIFEST.csv`, `JOIN.md`, and `ZIP_CONTENTS.csv`
- Expected total: **31 uploaded assets**

A 24 MiB split would produce **561 parts**, which would make the release unnecessarily difficult to manage. Each 512 MiB part remains comfortably below GitHub's 2 GiB per-asset limit.

## Upload method

To avoid holding both the 14.1 GB source ZIP and another 14.1 GB of parts locally:

1. Open the Gofile file as an HTTP range/stream source.
2. Read one 512 MiB part at a time.
3. Compute its SHA-256.
4. Upload that part to the GitHub Release.
5. Verify GitHub's returned asset size and delete the temporary local part.
6. Continue with the next part; record progress so interrupted uploads can resume.
7. Upload checksums, manifest, join instructions, and the remote ZIP contents listing last.

This requires only about 512 MiB temporary storage at a time, rather than approximately 28 GB.

## Proposed release metadata

- **Tag:** `v1.0`
- **Title:** `LLM Pipeline Resources — Full Standalone Bundle (14.1 GB)`
- **Repository:** pending — user will provide the new repository URL.

## Integrity

The remote ZIP central directory was read successfully and all 79,465 entries were enumerated. A detailed file listing is saved locally as `zip_contents.csv` and will be uploaded as `ZIP_CONTENTS.csv`.

Before final publication, each uploaded part will be checked against its expected byte size, and a SHA-256 manifest will be supplied for downloaded-part verification.
