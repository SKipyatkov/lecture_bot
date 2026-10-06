#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
dest="$root/models/faster-whisper-small"
mkdir -p "$dest"

base=https://huggingface.co/Systran/faster-whisper-small/resolve/main

fetch() {
    name=$1
    if [ -s "$dest/$name" ]; then
        echo "already present: $name"
        return
    fi
    echo "downloading $name"
    curl -fL --retry 3 --retry-delay 2 -A "lecture-bot" -o "$dest/$name.partial" "$base/$name"
    mv "$dest/$name.partial" "$dest/$name"
}

fetch config.json
fetch tokenizer.json
fetch vocabulary.txt
fetch model.bin
echo "whisper model ready in $dest"
