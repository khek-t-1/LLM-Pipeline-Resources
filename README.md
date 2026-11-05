# LLM Pipeline Resources

A standalone collection of LLM datasets, source repositories, research papers, and helper scripts, distributed as a reconstructed ZIP through GitHub Releases.

## Download

**Release:** [v1.0 — LLM Pipeline Resources Full Standalone Bundle](https://github.com/khek-t-1/LLM-Pipeline-Resources/releases/tag/v1.0)

| Item | Value |
|---|---|
| Original archive | `llm-resources-full.zip` |
| Archive size | 14,095,115,088 bytes (14.095 GB / 13.127 GiB) |
| Files inside archive | 79,465 |
| Uncompressed payload | 14,068,125,258 bytes |
| Release format | 27 binary parts, 512 MiB each except the final part |
| Gofile mirror | https://gofile.io/d/IQ22UNfo |

The Gofile mirror is temporary; the GitHub Release is the recommended long-term download route.

## Contents

| Area | Files | Approximate payload |
|---|---:|---:|
| `llm-resources/datasets` | 84 | 11.16 GB |
| `llm-resources/repos` | 79,367 | 2.87 GB |
| `llm-resources/papers` | 8 | 41.9 MB |
| Scripts and manifests | 6 | Small |

Dataset groups include FineWeb, FineWeb-Edu, FineWeb-2, PleIAs Common Corpus, AllenAI Dolma3 Pool, Dolci-Instruct-SFT, Tulu-3 SFT Mixture, and NVIDIA Nemotron SFT Agentic Finance.

Repository categories include `open`, `giants`, `learn`, `serving`, `finetune`, and `eval`.

The release asset `ZIP_CONTENTS.csv` lists all 79,465 archived files with sizes and CRC-32 values.

## Join the release parts

Download all 27 parts and `SHA256SUMS.txt` into one directory, then run:

```bash
sha256sum -c SHA256SUMS.txt
cat llm-resources-full.zip.*.part > llm-resources-full.zip
unzip -t llm-resources-full.zip
unzip llm-resources-full.zip
```

The archive extracts into one top-level `llm-resources/` directory. See [`JOIN.md`](JOIN.md) for Windows instructions.

## Repository files

- `docs/RELEASE_PLAN.md` — packaging and upload design
- `docs/ARCHIVE_SUMMARY.json` — remotely inspected ZIP summary
- `JOIN.md` — reconstruction instructions
- `scripts/stream_release.py` — resumable Gofile → GitHub streaming uploader

## License and provenance notice

This bundle aggregates third-party datasets, repositories, and papers. Each upstream item remains subject to its own license and terms. This repository's packaging and scripts do not relicense the bundled content. Review the upstream project/dataset licenses before redistribution or commercial use.
