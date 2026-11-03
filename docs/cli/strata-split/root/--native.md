# `strata-split` `--native`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の checkout は `main`、`origin/main` と一致し、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（`--serve` で起動する engine process） |
| オプション | `--native` |
| 別名 | なし |
| 値 | GGUF ファイルのパス。分割 GGUF の場合は先頭 shard のパス |

## 役割

分割 engine が推論に使う Qwen3.8-Flash-Next GGUF を指定します。値は起動時にモデル loader へ渡され、GGUF のメタデータ・tensor とモデル形状の検査、全カードへのモデル配置に使われます。ここでの `--native` は `strata-engine` の `--native` と異なり、sFNX のモデルファイルパスを指定する引数です（`src/split/tools/sfnx.cpp:65-84,1052-1059`）。

## 使い方

```sh
strata-split-2-sm86 --serve --native /models/flash-next-00001-of-00003.gguf --mtp /models/mtp --draft-vocab /models/draft_vocab_en.bin
```

実際の実行ファイル名は build / GPU 構成により異なります。`--native` は `--serve`、`--mtp` とともに必要です。Terminal が split engine を選ぶ場合、`strata_control/split_engine.py` が `--native` の値を `split_config()` の引数に設定します（同ファイル `:250-263`）。

## 値と既定値

値は必須です。既定値はなく、parser は直後の argv をそのままパス文字列として受け取ります。次の argv が無ければ `--native needs a value`、値が空文字列または未指定のままなら `--native and --mtp are required` で起動時検査に失敗します。同じ option を複数回指定した場合は parser が都度 `a.gguf` に代入するため、最後の値が残ります（`src/split/tools/sfnx.cpp:72-84,99-104`）。

## 実行時の動作

`main()` は保存されたパスを `fnx::Model` に渡し、model constructor が GGUF を開きます（`src/split/tools/sfnx.cpp:1050-1059`; `src/split/src/model.cpp:1253`）。ファイルは `O_RDONLY` で開かれて read-only mmap されます。パスが `名前-00001-of-00003.gguf` のような `-00001-of-00003.gguf` 形式に一致すると、同じ名前規則の shard 1 から shard 数までを連続して開きます。形式に一致しない名前は単一ファイルとして扱われます（`src/split/src/gguf.cpp:98-112,147-159`; 宣言は `src/split/src/gguf.hpp:50`）。

読み込んだモデルは GGUF の routed expert tensor 型とモデル形状の検査対象です。非対応の routed expert 型なら通常の layer split を使うようエラーになり、Flash-Next の metadata / tensor shape が期待値と異なる場合も拒否されます（`src/split/src/model.cpp:1246-1292`）。一部の混合量子化ファイルではロード時に dense / small tensor を Q8_0 または F32 へ変換し、変換件数を stderr に出します。routed expert tensor はこの変換対象から除外されています（`src/split/src/gguf.cpp:114-137`）。

## 適用条件と副作用

- `strata-split` は build されたカード数と可視カード数が一致する必要があり、異なる場合はモデルロードを拒否します（`src/split/src/model.cpp:1253-1265`）。
- 自動起動の可否は Terminal 側でも判定されます。`strata_control/split_engine.py:458-482` は `--native` の値をモデルスキャンに使い、読み取り不能なら split を選ばない理由として返します。起動後に engine が拒否・失敗した場合、server は通常の layer split に切り替える設計です（`docs/SPLIT_ENGINE.md:43-47`）。
- `--native` 自体がファイルを書き換える処理は確認できません。loader は入力を read-only で mmap しますが、混合量子化モデルでは変換 tensor のメモリ上の生成が発生します（`src/split/src/gguf.cpp:147-159,114-137`）。

## 出力とエラー

option の不足・必須引数不足など parser 段階のエラーは stderr に `sfnx: <理由>` を出し、終了コード 2 になります（`src/split/tools/sfnx.cpp:77-80,99-104,1040-1048`）。GGUF を開けない・mmap できない場合は理由を `ERR <理由>` と stderr の `sfnx: failed: <理由>` に出し、終了コード 1 で終了します。GGUF loader は `gguf: cannot open <path>` / `gguf: mmap failed for <path>` を例外にします（`src/split/src/gguf.cpp:147-159`; `src/split/tools/sfnx.cpp:1030-1035,1050-1062`）。起動時に未知の引数やモデル形式の問題が起きたときの経路と区別してください。

## 根拠

- Parser、必須条件、値の代入: `src/split/tools/sfnx.cpp:72-104`
- パスのモデル loader への受け渡し: `src/split/tools/sfnx.cpp:1050-1059`; `src/split/src/model.cpp:1253`
- shard の探索と read-only mmap: `src/split/src/gguf.cpp:98-112,147-159`; `src/split/src/gguf.hpp:50`
- routed expert 型・Flash-Next 形状の検証: `src/split/src/model.cpp:1246-1292`
- Terminal から渡されるパスと split engine の判定: `strata_control/split_engine.py:250-263,458-482`
- 起動失敗時の通常 engine への fallback: `docs/SPLIT_ENGINE.md:43-47`

調査範囲は上記 revision の Strata 所有ソースです。同一 revision のビルド済み split engine は起動しておらず、実 GPU 上のロード結果や個別の Release artifact は確認していません。
