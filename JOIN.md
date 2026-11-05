# Joining `llm-resources-full.zip` release parts

Download all 27 files, from `llm-resources-full.zip.00.part` through `llm-resources-full.zip.26.part`, into the same directory. Also download `SHA256SUMS.txt` for verification.

## Linux / macOS / WSL / Colab

```bash
# Verify downloaded parts first:
sha256sum -c SHA256SUMS.txt

# Join in numeric order:
cat llm-resources-full.zip.*.part > llm-resources-full.zip

# Test the reconstructed archive:
unzip -t llm-resources-full.zip

# Extract:
unzip llm-resources-full.zip
```

The archive contains one top-level directory: `llm-resources/`.

## Windows PowerShell

```powershell
$parts = Get-ChildItem "llm-resources-full.zip.*.part" | Sort-Object Name
$output = [System.IO.File]::Create("llm-resources-full.zip")
foreach ($part in $parts) {
    $bytes = [System.IO.File]::ReadAllBytes($part.FullName)
    $output.Write($bytes, 0, $bytes.Length)
}
$output.Close()
```

For large files, using WSL and the `cat` command above is recommended.

After joining, the expected archive size is **14,095,115,088 bytes**. The full archive SHA-256 will be recorded in `MANIFEST.csv` after streaming is complete.
