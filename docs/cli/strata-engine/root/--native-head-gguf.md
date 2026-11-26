# `--native-head-gguf`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、トップレベル） |
| オプション | `--native-head-gguf PATH` |
| 別名 | なし |
| 値 | `output.weight` を含む GGUF ファイルのパス。分割 GGUF では shard 1（メタデータ shard）のパスを指定する |

## 役割

GGUF の `output.weight` をネイティブ head 実装で読み込み、通常の language-model head に代えて推論に使います。実験的な経路であり、`--stream-token` が必要です。`--native` も指定した場合、このオプションを省略すると `--native` と同じモデルの head を使います。

## 使い方

```sh
# native head を別の GGUF から読み込む（--pack には利用する expert pack を指定）
strata --pack /models/experts.pack --native-head-gguf /models/model-00001-of-00002.gguf --stream-token
```

## 値と既定値

- 値は parser が次の argv 要素からそのまま受け取ります。パスの存在や GGUF の内容は parser 時点では検証しません。値を省略すると `--native-head-gguf needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3847,3926-3928`）。
- 同じオプションを複数回指定した場合、`Options` の文字列を順に代入するため最後の値が残ります（`engine/src/program/generate.cpp:3926-3928`）。空文字列は空のまま格納され、後続の「未指定」扱いとなります。
- `--native` が指定され、head の値が空なら `--native` のパスが head の既定値になります。明示した非空値は `--native` と異なる GGUF を指しても受理され、後段でアーキテクチャ・テンソル形状が検証されます（`engine/src/program/generate.cpp:5160-5166,5309-5316`）。
- オプション自体にデフォルトのパスはありません。`--native` も本オプションも指定しない場合、ネイティブ head はロードされません。

## 実行時の動作

- `--native-head-gguf` のパスが `--native` と文字列として同じなら、`--native` 用に検出済みの shard 一覧を再利用します。それ以外は `strata::gguf_split_paths()` で指定パスから GGUF shard 一覧を得ます。ここでの shard 展開失敗はエラーを stderr に出し、終了コード 2 になります（`engine/src/program/generate.cpp:5309-5316`）。
- 指定先のメタデータからエンジン対応アーキテクチャを確認し、shard 群から `output.weight` を探します。テンソルは2次元で、ネイティブ MMVQ が対応する GGUF type、かつ実行モデルの埋め込み次元・語彙数と一致する形状でなければなりません。データ payload がテンソル範囲を満たすことも検証されます（`engine/src/core/native_head.cpp:105-123`）。対応 type の集合は `engine/src/kernels/cuda/native_mmvq.cu:3733-3737` に定義されています。
- 通常の単一 GPU 経路では native head を GPU にロードし、実行時は mixer の出力を native head に渡して logits を計算します。head がロードされていない場合は通常の `lm_head` が使われます（`engine/src/program/generate.cpp:8388-8400,10591-10596`）。層分割時は最後の GPU stage にロードします（`engine/src/program/generate.cpp:7775-7782`）。
- `--keep-canonical` を指定しない場合、canonical 重みのロード対象から `output.weight` を除外します。指定時は canonical head も保持します（`engine/src/program/generate.cpp:5804-5815`）。
- 開始時に stderr へ、ロードした head の GGUF 型名、バイト数、ロード所要時間を出力します（`engine/src/program/generate.cpp:8391-8400`）。

## 適用条件と副作用

- `--stream-token` が必要です。native head の値が空でないのに `--stream-token` が無効なら、`--native-head-gguf requires --stream-token` を stderr に出し、終了コード 2 で終了します。`--native` は `--stream-token` を有効にするため、この条件を満たします（`engine/src/program/generate.cpp:5160-5165,5378-5382`）。
- 読み込む `output.weight` はネイティブ MMVQ 対応型で、実行モデルと同じ canonical dimensions が必要です。未対応型・テンソル欠落・shape 不一致・payload 切れなどは native head loader のエラーになります。通常の単一 GPU 経路ではエラーを stderr に出し、終了コード 1 で終了します（`engine/src/core/native_head.cpp:108-123`; 呼出し側 `engine/src/program/generate.cpp:8391-8397`）。
- head の重みと作業用領域を GPU 側に確保し、GGUF のテンソルデータを転送します。VRAM 不足などロード時の失敗も開始を中止します（`engine/src/core/native_head.cpp:125-129`; 呼出し側 `engine/src/program/generate.cpp:8391-8397`）。層分割では最後の stage でのロード失敗がエラーとなります（`engine/src/program/generate.cpp:7775-7782`）。
- `strata-engine` には CUDA/HIP 系と SYCL 系の実装があります。SYCL 側にも同じ parser、stream-token 条件、native head の GGUF 検証とデバイス転送があります（`engine/sycl/src/program/generate.cpp:1965-1967,2592-2598,2723-2729,2776-2779`; `engine/sycl/src/core/native_head.cpp:32-50,52-97`）。この調査ではビルド済み実行ファイルを使った backend 別の実行確認はしていません。

## 根拠

- `engine/src/program/generate.cpp:806-810` — head パスと shard 一覧の状態。
- `engine/src/program/generate.cpp:1262` — help に記載された値と `--stream-token` 条件。
- `engine/src/program/generate.cpp:3842-3847,3926-3928` — parser、値の取得、値省略時のエラー。
- `engine/src/program/generate.cpp:5160-5166,5309-5316,5378-5382` — `--native` との既定値連携、shard 展開、stream-token の必須条件。
- `engine/src/core/native_head.cpp:98-123` — architecture、`output.weight`、対応型・shape・payload の検証。
- `engine/src/program/generate.cpp:5804-5815,7775-7782,8388-8400,10591-10596` — canonical head の扱い、層分割および単一 GPU でのロード、推論時の使用。
- `engine/src/kernels/cuda/native_mmvq.cu:3733-3755` — 対応型と重み byte 数の計算。
- `engine/sycl/src/program/generate.cpp:1965-1967,2723-2729,2776-2779,4575-4587`; `engine/sycl/src/core/native_head.cpp:32-50,52-97` — SYCL 系の parser、条件、loader。
