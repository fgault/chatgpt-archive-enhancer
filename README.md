# ChatGPT Archive Enhancer

A small, local-first utility for making OpenAI/ChatGPT data exports easier to browse and preserve.

**Your conversations never leave your computer.** The program works entirely on ZIP files you download from ChatGPT. It needs no OpenAI password, API key, browser cookies, or network connection.

## What it does

- Adds a searchable conversation sidebar to `chat.html`
- Sorts conversations newest-first
- Shows **Started** and **Last updated** timestamps in Pacific Time
- Adds **Export this thread to PDF** to every conversation (using your browser's print/PDF dialog)
- Creates a **true delta** between two exports: conversations that are new **or changed** since the older snapshot
- Carries forward assets referenced by delta conversations
- Rebuilds and integrity-checks the output ZIP

## Requirements

Python 3.9+; no third-party packages.

## Enhance a complete export

```bash
python3 chatgpt_archive_enhancer.py \
  --enhance ChatGPT-export.zip \
  --output ChatGPT-enhanced.zip
```

## Create a true delta

```bash
python3 chatgpt_archive_enhancer.py \
  --old ChatGPT-export-Aug08.zip \
  --new ChatGPT-export-Aug15.zip \
  --output ChatGPT-delta-Aug08-to-Aug15.zip
```

A true delta includes both newly created conversations and older conversations that were continued or otherwise changed.

Example:

```text
Aug 8:   A B C D
Aug 15:  A B C D E F
```

If conversation **B** was continued after Aug 8, the delta contains **B, E, F**.

## Export one thread to PDF

Open the generated `chat.html`, find a conversation, and click **Export this thread to PDF**. Only that thread is presented to the browser's print dialog. On macOS, choose **PDF → Save as PDF** (or the browser's Save to PDF destination).

## Privacy

This tool deliberately has no networking code. Your ChatGPT export may contain highly personal information; keep the original and processed ZIPs somewhere you trust and do not commit them to GitHub.

## Compatibility

This initial release targets the ChatGPT data-export structure observed in August 2026. OpenAI may change the export schema; please open an issue if a newer export no longer works.

## License

MIT. See [LICENSE](LICENSE).
