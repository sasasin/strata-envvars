# `--prefill-chunk`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `maya-ds4`（DSv4.1 エンジン） |
| オプション | `--prefill-chunk` |
| 別名 | なし |
| 値 | 整数 `N`（tokens 単位）。parser は `atoi` で読み、負値を 0 に丸める |

## 役割

長い prompt を層ごとの chunk 単位で処理する経路における chunk の大きさを指定します。chunk 経路では各層を複数 token 分まとめて実行し、指定値が 0 の場合は 16 token の window 経路を使います。ただし、オプションは実際の chunk 経路を有効にするかどうかにも関わり、`--tp`、`--threads`、`DS4_WINDOWS` の条件が適用されます（`src/dsv41/ds4_main.cpp:1232`、`src/dsv41/ds4_model.cu:1917-1924`）。

## 使い方

```sh
maya-ds4 --pack /path/to/model/maya-ds4 --ids 1,2,3 --prefill-chunk 1024
```

`--pack` と `--ids` は同じ CLI の代表的な通常実行引数です（`src/dsv41/ds4_main.cpp:87-93`）。この例では prompt chunk の候補値として 1024 tokens を指定します。実際に chunk 経路へ進むかは下記の条件に従います。

## 値と既定値

- 値を省略すると parser が「値が必要」と stderr に出し、プロセスは終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1207`）。
- 整数は `std::atoi` で変換され、その結果を `max(0, 値)` に通します。従って負数は 0 になり、数値として読めない文字列も `atoi` の結果 0 として扱われます。厳密な数値形式や上限の parser validation はありません（`src/dsv41/ds4_main.cpp:1232`）。同じオプションを複数回指定した場合、parser は都度同じフィールドに代入するため後の指定が残ります（`src/dsv41/ds4_main.cpp:1200-1233`）。
- 未指定時の `Options::prefill_chunk` は `-1` です。これは自動選択用の sentinel で、モデル読み込み時に prompt 経路に応じた既定値へ置き換わります（`src/dsv41/ds4_model.hpp:54-57`、`src/dsv41/ds4_model.cu:1968-1969`）。`--tp 1 --threads off` の経路では 1024、`--tp`/`--threads` による並列 prompt 経路では、expert をファイルから読む場合 `kVlRows`、それ以外は 2048 が選ばれます。
- 指定値が正の場合、実効値は最大 `kMaxChunk` までに制限され、通常は 16 の倍数に切り下げられ、最小 256 になります。環境変数 `DS4_CHUNK` が設定されている場合は最小値が 16 に変わり、同変数の整数値がオプション由来の値を上書きします。0 はこの正値の正規化を通らず 0 のままです（`src/dsv41/ds4_model.cu:816`、`src/dsv41/ds4_model.cu:1969-1975`）。

## 実行時の動作

モデル読み込み時に chunk 経路を有効にするか決めます。`--tp` が 1 より大きい場合、または `--threads` が `off` 以外なら prompt 経路は chunk 対応になります。そうでない場合は、値が正、または未指定（`-1`）で、かつ `DS4_WINDOWS` が未設定の場合に chunk 対応になります。`--prefill-chunk 0` は既定の `--tp 2` などで chunk 経路自体を有効にする条件を取り消しませんが、実効 chunk を 0 にして window 処理へ進ませます。`--tp 1 --threads off` と `DS4_WINDOWS` の設定下では、正の値を指定しても chunk prompt 経路は有効になりません（`src/dsv41/ds4_model.cu:1917-1924`、`src/dsv41/ds4_model.cu:1968-1979`）。

prompt の `feed()` は、実効 chunk が正で入力 token 数が `chunk_min` 以上のときだけ chunk 経路の候補になります。初期 `chunk_min` は 512 ですが、GPU の層がすべて flow 経路になった場合、`DS4_CHUNK_MIN` が未設定なら 2 まで引き下げられることがあります。候補の後も `pick_path()` が window 経路を選ぶ場合があります。したがって値は一回の処理量を指定するもので、全 prompt が必ずその単位で処理される保証ではありません（`src/dsv41/ds4_model.cu:809-812`、`src/dsv41/ds4_model.cu:2707-2712`、`src/dsv41/ds4_model.cu:9056-9067`）。

## 適用条件と副作用

- chunk prompt 用の GPU・host buffer を確保します。確保に失敗すると、実装は chunk を段階的に小さくして再試行します。さらに確保できない場合は chunk prompt を無効にし、16 token window で処理する旨を stderr に出します（`src/dsv41/ds4_model.cu:2578-2592`）。
- chunk 用 buffer は decode 時にも VRAM を占有します。ソースコメントは、`kVlRows` 相当の大きな chunk が expert の VRAM 使用可能量を減らし得ると説明しています。値を大きくした場合の性能向上を一般化する測定根拠はこの調査では確認していません（`src/dsv41/ds4_model.cu:813-816`）。
- `DS4_CHUNK` と `DS4_CHUNK_MIN` は実効 chunk と開始閾値を変更し、`DS4_WINDOWS` は並列指定がない場合の chunk 経路有効化を抑止します（`src/dsv41/ds4_model.cu:1922-1924`、`src/dsv41/ds4_model.cu:1970-1972`、`src/dsv41/ds4_model.cu:2710-2712`）。これら環境変数の詳細仕様は本オプション文書の範囲外です。
- chunk の有効・無効はモデル読み込み時に確定し、prompt は `Model::feed()` / `feed_mark()` で選択された経路を使います（`src/dsv41/ds4_model.cu:9056-9083`）。

## 出力とエラー

- option 自体には独立した成功メッセージはありません。chunk prompt の buffer 確保失敗と小さい chunk での再試行、window 経路への fallback は stderr に出ます（`src/dsv41/ds4_model.cu:2580-2592`）。chunk が 0 の場合も window 経路を使う理由を stderr に説明します（`src/dsv41/ds4_model.cu:1977-1984`）。
- 引数値が欠けた場合は終了コード 2 です。未知のオプションも usage を stderr に表示して終了コード 2 になります（`src/dsv41/ds4_main.cpp:1202-1207`、`src/dsv41/ds4_main.cpp:1266-1272`）。数値以外の値は parser で拒否されず 0 扱いになります。
- `Model::load()` の失敗は `maya-ds4: <理由>` を stderr に出し、終了コード 1 で終了します。これはこのオプションだけに固有のエラーではありません（`src/dsv41/ds4_main.cpp:1289-1294`）。

## 根拠

- CLI usage と option parser: `src/dsv41/ds4_main.cpp:85-94`, `src/dsv41/ds4_main.cpp:1200-1207`, `src/dsv41/ds4_main.cpp:1232`。
- option の初期値と prompt feed の役割: `src/dsv41/ds4_model.hpp:54-57`, `src/dsv41/ds4_model.hpp:107-115`。
- 経路判定、既定 chunk、chunk 正規化: `src/dsv41/ds4_model.cu:1917-1924`, `src/dsv41/ds4_model.cu:1968-1984`。
- buffer 確保の fallback と feed 時の経路選択: `src/dsv41/ds4_model.cu:2578-2592`, `src/dsv41/ds4_model.cu:2707-2712`, `src/dsv41/ds4_model.cu:9056-9083`。
- CLI 索引では `strata-engine-dsv41` の root option として掲載されています: [`docs/cli/README.md`](../../README.md)（索引の `--prefill-chunk` 行）。

調査範囲: 指定 revision の checkout 上の parser とモデル実装を確認しました。CLI バイナリの `--help` は実行しておらず、別 platform/build variant と Release 配布物での挙動は確認していません。
