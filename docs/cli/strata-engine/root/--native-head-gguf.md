# `--native-head-gguf`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--native-head-gguf PATH` |
| 別名 | なし |
| 値 | 出力 head の `output.weight` を含む GGUF ファイルのパス |
| 既定値 | 空（`--native` 使用時は `--native` の GGUF shard 群に補完） |

## 役割

GGUF の `output.weight` をネイティブ head として GPU にロードし、通常の `lm_head` の代わりに logits を計算します。ヘルプは native Q5_K head と説明していますが、実装は `native_mmvq_supported` が対応する型を受け付けます。したがって Q5_K に限定した parser validation ではありません（`src/program/generate.cpp:860`、`src/core/native_head.cpp:41-46`）。

## 使い方

```sh
strata generate --pack ./model.pack --tokens "1,2,3" \
  --stream-token --native-head-gguf ./model-00001-of-00002.gguf
```

`--native-head-gguf` は `--stream-token` と併用する必要があります。`--native MODEL.gguf` を指定する構成では、head のパスを省略すると `--native` の shard 群が使用されます（`src/program/generate.cpp:3263-3268, 3453-3456`）。

## 値と既定値

- parser は次の argv 要素を文字列として受け取り、パスの存在や形式は parser 時点では検査しません。値が欠けている場合は `<option> needs a value` を stderr に出し、終了コード2で終了します（`src/program/generate.cpp:2418-2421, 2501`）。
- 繰り返し指定は同じ文字列変数への代入なので最後の値が残ります（`src/program/generate.cpp:2501`）。
- 空文字列は「未指定」として扱われます。`--native` が空でなければその値を head の入力に補完します（`src/program/generate.cpp:3268`）。
- パスが `--native` の値と同一なら既に解決した `--native` shard 群を再利用し、それ以外は `strata::gguf_split_paths` で指定パスの shard 群を解決します（`src/program/generate.cpp:3394-3400`）。

## 実行時の動作

指定した GGUF 群の architecture metadata がエンジン対応かを確認し、`output.weight` を探します。tensor は2次元で、形状がモデルの `[n_embd, n_vocab]` と一致し、ネイティブ MMVQ が扱える型である必要があります。payload の範囲も検査されます（`src/core/native_head.cpp:34-52`）。

検証後、head の重みと Q8_1 scratch buffer を CUDA device memory に確保し、head の tensor を host から device にコピーします。native head を使う場合、canonical weight table から `output.weight` を読み飛ばします（`src/core/native_head.cpp:54-78`、`src/program/generate.cpp:3783`）。通常の単一 GPU 経路ではロード完了を stderr に表示し、head の実行は `lm_head_mix` に続けて `NativeHead::run` を呼び出します（`src/program/generate.cpp:5554-5564, 6999-7003`）。

`--native` プリセットは `--stream-token` を有効にし、head パスが空ならプリセットと同じ GGUF shard 群を設定します（`src/program/generate.cpp:3263-3268`）。明示指定した head は `--stream-token` が無効なら拒否されます（`src/program/generate.cpp:3453-3456`）。`--layer-split` の経路では最終 stage の head に指定 shard 群をロードします（`src/program/generate.cpp:5556` のコメントおよび stage head load 処理）。

## 適用条件と副作用

- `--stream-token` が必要です。これは session stream 上で token 処理を実行する実験経路です（`src/program/generate.cpp:438, 860, 7024`）。
- 単一 GPU の経路では native head の重みと scratch が CUDA VRAM を消費します。VRAM 確保に失敗した場合、確保済み buffer を解放してロード失敗になります（`src/core/native_head.cpp:54-66`）。
- `--native` と別の head ファイルを指定した場合、同じモデルであることを照合する処理は確認できません。実装が確認するのは architecture、`output.weight` の形状・型、payload 範囲です（`src/core/native_head.cpp:34-52`）。
- 公式 Release artifact と同一 revision のビルド済み `--help` はこの調査では確認していません。ソース内 usage と parser を照合しました。

## 出力とエラー

- `--native-head-gguf` に値がない場合は parser が stderr にエラーを出し、終了コード2です（`src/program/generate.cpp:2418-2421`）。
- 指定した shard 群を解決できない場合は `strata generate: --native-head-gguf <path>: <理由>` を stderr に出し、終了コード2で終了します（`src/program/generate.cpp:3394-3400`）。
- `--stream-token` がない場合は `--native-head-gguf requires --stream-token` を stderr に出し、終了コード2です（`src/program/generate.cpp:3453-3456`）。
- architecture、tensor、形状、型、payload の検証または CUDA 確保・転送に失敗すると、呼び出し元が `strata generate: <理由>` と VRAM 空き情報を stderr に出して終了コード1を返します（`src/core/native_head.cpp:38-66, 80-82`、`src/program/generate.cpp:5558-5560`）。

## 根拠

- `src/program/generate.cpp:468-472, 860` — option の値保持、shard 群の前提、usage。
- `src/program/generate.cpp:2418-2421, 2501, 3263-3268, 3394-3400, 3453-3456` — parser、既定補完、入力 shard 解決、stream-token 要件。
- `src/core/native_head.cpp:28-83` — 寸法・architecture・tensor・payload 検証、CUDA load と失敗処理。
- `src/program/generate.cpp:3783, 5554-5564, 6999-7003` — canonical head の除外、head のロードと推論時の使用。
