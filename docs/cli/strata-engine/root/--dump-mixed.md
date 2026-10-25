# `--dump-mixed`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root 引数） |
| オプション | `--dump-mixed` |
| 別名 | なし |
| 値 | 出力先ファイルパス（`PATH`） |

## 役割

モデルの生成処理が終わった後、LM head に渡す `mixed` ベクトルを取り出して保存します。ソースコメントでは `bb.mixed` を head 入力と説明し、head の計算を調べる用途を示しています。出力は位置ごとの履歴ではなく、終了時点のベクトル1個です。

## 使い方

```sh
strata --pack MODEL.gguf --ple-gguf PLE.gguf --tokens 1,2,3 --max-new 1 --dump-mixed /tmp/last-mixed.f32
```

`MODEL.gguf`、`PLE.gguf`、token ID は実行環境に合う値へ置き換えてください。既存ファイルを指定すると `wb` モードで開くため内容を切り詰めて上書きします。

## 値と既定値

- `PATH` は `--dump-mixed` の直後の argv 要素をそのまま受け取ります。専用の形式・範囲検証はありません。値を省略すると `--dump-mixed needs a value` を stderr に出して終了コード 2 で終わります。
- 未指定時の値は空文字列で、dump は行いません。明示した値が空文字列の場合も、保存先が空のままなので dump は行いません。
- 同じオプションを複数回指定すると、parser の代入により最後の値が使われます。

## 実行時の動作

通常の engine parser は `--dump-mixed` の次の引数を `Options::dump_mixed` に設定します。生成処理の終端で値が空でなければ、`ss.block.mixed` から `g.n_embd` 個の float をホストメモリへコピーし、保存先を `wb` で開いて `sizeof(float) * g.n_embd` バイトを書きます。ファイルにはヘッダーを付けず、ネイティブ float の配列だけを出力します。成功時はパス、`n_embd`、RMS、平均絶対値を stdout に表示します。

保存は各 token の head 計算直後ではなく、通常の生成ループが完了した後に一度行われます。そのため複数 token を生成しても、出力ファイルは最後の処理状態のベクトル一つです。

## 適用条件と副作用

- これは `src/program/generate.cpp` の通常 engine parser が処理するオプションです。Qwen3.6 family に振り分けられた場合は `src/qwen35/q36_engine.cu` の別 parser が argv を処理します。同 parser は `--dump-mixed` を定義していません。非 serve 実行では未知 option として usage を表示し終了コード 2、serve 実行では未知の `--` option として警告を出し、次の非 option 値があればそれも読み飛ばします。
- 出力先が既存ファイルなら切り詰めて上書きし、なければ新規作成します。親ディレクトリは作成しません。
- GPU からの読み戻しとファイル書き込みを伴います。出力のために推論途中で停止する処理ではありません。

## 出力とエラー

- `cudaMemcpy` による読み戻しが失敗すると `strata generate: reading mixed back failed` を stderr に出し、終了コード 1 になります。
- `fopen` に失敗すると `strata generate: cannot write PATH` を stderr に出し、終了コード 1 になります。
- `fwrite` と `fclose` の戻り値は確認されていません。したがって、ディスク容量不足などで書き込みが完了しない場合に、この箇所がエラー終了を検出する保証はソース上確認できません。

## 根拠

- `src/program/generate.cpp:489-492` — `dump_mixed` の option state と、head 入力 `bb.mixed` に関するコメント。
- `src/program/generate.cpp:971` — help 表示上の値と説明（`PATH`、post-attention residual、`n_embd`・f32）。
- `src/program/generate.cpp:2418-2421,2468-2470` — 値の必須処理と parser 代入。
- `src/program/generate.cpp:7000-7003,15975-15985` — head が `ss.block.mixed` を使う実行経路。
- `src/program/generate.cpp:16880-16897` — 生成後の読み戻し、ファイル open/write、成功時表示。
- `src/qwen35/q36_engine.cu:3742-3795` — family 専用 parser、serve の未知 option 処理、非 serve の未知 option エラー。
