# `--chunk`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 専用 parser（または `strata-q36`） |
| オプション | `--chunk` |
| 別名 | `--prefill` |
| 値 | prompt を処理する token 数。整数として `0..4096`。`0` と `auto` は自動選択。 |

## 役割

Qwen3.6 engine が prompt を一度に処理する最大 token 数を指定します。長い prompt はこのサイズ以下の単位に分けて処理します。これは通常の `strata` engine parser にある `--prefill` とは別の Qwen3.6 専用 parser の設定です。

## 使い方

```sh
strata --native /models/qwen36.gguf --tokens 1,2,3 --chunk 512
strata-q36 --model /models/qwen36.gguf --serve --prefill auto
```

`strata` は `--native` または `--model` が指す GGUF の architecture が `qwen35moe` の場合、引数全体を Qwen3.6 engine に渡します。独立 executable `strata-q36` も同じ parser を呼びます（根拠: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5`）。

## 値と既定値

- 未指定時の内部値は `0` で、自動選択になります。`--chunk auto` / `--prefill auto` も `0` に変換されます（`src/qwen35/q36_engine.cu:3735-3741,3756-3758`）。
- 数値指定は `std::atoi` で変換され、負数または `4096` を超える値は `strata-q36: bad --chunk / --max-context` を stderr に出して終了コード 2 になります。値を伴わない指定は `needs a value` を出して終了コード 2 です（同 `:3742-3747,3757,3807-3808`）。
- 数字以外を含む文字列は厳密な数値 validation を受けません。`atoi` の変換結果が 0 なら自動選択に進みます。option を複数回指定した場合、parser は後の値で上書きします（同 `:3742-3747,3757`）。
- Engine 初期化時の実効 buffer 高さは `max(指定値, kVerify)` です。従って小さい正数も受理されますが、指定値そのものより大きな値で初期化される場合があります（同 `:1339-1346`）。

## 実行時の動作

正の明示値は自動選択を通らず、その値を engine 初期化へ渡します。自動選択では現在の GPU 空き容量、expert 重みの総量、`--expert-slots`、`--expert-vram` を使って値を決めます。基本値は、expert 全体と約 1.1 GiB の余裕が収まる場合 512、そうでない場合は空き VRAM に応じて 512 / 1024 / 2048 です。expert 全体が収まる条件では、単一 slot なら 1024 / 2048 / 4096 も追加の推定メモリー条件を満たす範囲で選ばれ、複数 slot では最大 1024 です（`src/qwen35/q36_engine.cu:3817-3857`）。

自動選択のときだけ、環境変数 `STRATA_Q36_CHUNK` があれば値を `256..4096` に clamp して自動選択結果を上書きします。明示的な正数指定はこの環境変数の影響を受けません（同 `:3819,3858`）。

実際の prompt 処理は `tmax` 件ずつループし、各分割の forward 処理を完了してから次へ進みます。最後の分割は残り token 数に縮みます（同 `:2431-2433,2463-2491`）。serve mode でも prompt はこの分割単位で処理されます。`--batch` で複数 session を使う場合、各 session の prompt cache と chunk 用 buffer のための VRAM も必要になり、初期化時に slot 数・context に対する空き容量を検査します（同 `:1450-1469`）。

## 適用条件と副作用

- この parser は Qwen3.6 (`qwen35moe`) の family switch 先、および `strata-q36` で使われます。通常の engine parser は異なる処理経路であり、この文書の auto 規則を適用しません（`src/program/generate.cpp:2393-2407`）。
- `--chunk` は engine 内の activation、expert routing、attention 等の作業 buffer の行数にも使われるため、大きな値は GPU memory 使用量を増やします（`src/qwen35/q36_engine.cu:1339-1360`）。prompt の chunk ごとに処理が同期され、serve の他 slot は chunk 境界で進行できる設計です（同 `:2463-2489`、serve protocol の説明 `:3174-3195`）。
- 自動選択または初期化では GPU memory 情報の取得と device buffer の確保が行われます。chunk 設定によってファイルを書き出す処理は確認できません。明示値で VRAM に収まらない場合の具体的な allocator error 文言は backend に依存するため、ここでは固定の文言や終了コードを断定しません。

## 出力とエラー

- 無効な範囲、または `--chunk` / `--prefill` の値欠落は parser が stderr に診断を出し、終了コード 2 を返します（`src/qwen35/q36_engine.cu:3744-3747,3807-3808`）。
- 自動選択時に `STRATA_Q36_PLACE_DEBUG` が設定されていると、free VRAM、expert 容量、選択 chunk を stderr に表示します。初期化後は context、実効 prompt chunk、残り VRAM を stderr に表示します（同 `:3858-3862,1505-1509`）。
- GPU buffer 確保を含む初期化・model load の失敗は engine の CUDA/HIP error 経路または load 診断を経由します。model load 失敗は終了コード 1 です（同 `:3810-3816`）。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3808` — parser、alias、値変換、既定値、範囲検査、エラー。
- `src/qwen35/q36_engine.cu:3817-3863` — VRAM 条件による auto 選択、`STRATA_Q36_CHUNK` の適用、engine 初期化への引き渡し。
- `src/qwen35/q36_engine.cu:1339-1360,1450-1469,1505-1509` — chunk に応じた buffer/session 初期化、VRAM 条件、診断出力。
- `src/qwen35/q36_engine.cu:2431-2491` — prompt を chunk 単位で forward する処理。
- `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5` — `strata` からの family dispatch と独立 executable の入口。
- `CMakeLists.txt:771-792` — Qwen3.6 reference executable と `strata-q36` の build 定義。Release 配布物の有無はこの調査では確認していません。
