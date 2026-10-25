# `--expert-vram`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 専用経路、または `strata-q36` |
| オプション | `--expert-vram GiB` |
| 別名 | なし |
| 値 | `std::atof` で変換される数値。GiB 単位 |

## 役割

Qwen3.6 の routed expert を VRAM に配置する際の予算を指定します。負値（省略時を含む）では、その時点の空き VRAM から既定 reserve を差し引く自動予算を使い、0 以上では指定 GiB を予算にします。予算に収まらない場合、CPU expert pool がある build では expert をホストメモリにも置く hybrid 配置に切り替わります。

このオプションは通常の `strata-engine/root/` parser ではなく Qwen3.6 専用 parser の option です。`strata` は `--model` または `--native` が指す GGUF の architecture が Qwen3.6 family の場合に専用実装へ振り分けます。

## 使い方

```sh
strata --model /path/to/qwen3.6.gguf --serve --expert-vram 20
```

自動予算を明示する場合は負値を指定します。省略時も同じ自動モードです。

```sh
strata-q36 --model /path/to/qwen3.6.gguf --serve --expert-vram -1
```

## 値と既定値

- 省略時の内部値は `-1.0` です。`--expert-vram -1` など負値は自動予算になります。
- `0` 以上は GiB で指定した明示予算です。たとえば `20` は `20 × 2^30` bytes に換算されます。0 は「予算なし」相当で、expert の全 VRAM 配置条件を満たしません。
- 値は `std::atof` で変換され、整数・小数の厳密な文法検証や有限値・正値の検証はありません。数値として読めない文字列は通常 `0` に変換されます。また `20xyz` のような数値で始まる文字列は先頭の数値部分が変換されます。
- 値が必要なのに後続引数がない場合は `strata-q36: --expert-vram needs a value` を stderr に出して終了コード `2` で終了します。
- 同じオプションを複数回指定すると、引数走査で後の値が前の値を上書きします。`--expert-vram=20` 形式の parser 分岐はありません。`--serve` より前など通常の不明 option として扱われる位置では usage を出して終了コード `2`、`--serve` の後では server mode の不明 option 処理により警告して無視される場合があります。

## 実行時の動作

1. Qwen3.6 parser は値を `double` に変換して保持し、モデル読み込みと engine buffer 初期化の後に `place_experts` へ渡します。
2. 自動モードでは `cudaMemGetInfo` の空き VRAMから 768 MiB を差し引いた量を予算とします。配置時に packed Q8_0 decode copy を解放できる条件も調べ、条件を満たして `STRATA_Q36_KEEP_PACKED` が未設定なら copy を解放して再計測します。
3. 明示モードでは予算を指定 GiB から換算します。この場合、配置関数内の通常の 768 MiB 自動 reserve 差し引き、packed copy の自動解放、後述の MTP 専用配置判定は使われません。ただし全 expert を VRAM に置く分岐には、予算内であることに加えて実際の空き VRAMに 256 MiB の余裕があることも必要です。
4. 予算に収まらず hybrid 配置になった場合、`--expert-slots` が正値ならその値（expert 数を上限）を各 layer の GPU slot 数に使い、非正値なら残りの予算から slot 数を算出します。`--expert-slots` が正値のときは、予算が大きくても全 VRAM 配置分岐を使いません。
5. `--chunk` / `--prefill` を省略または `auto` にした場合の chunk 判定にも使われます。`--expert-slots` が非正値なら、負の `--expert-vram` は空き量と buffer 見積もりを使って fit を判定し、0 以上なら routed expert 量と指定 GiB を比較します。明示予算では自動予算専用の大きな chunk 候補選択を行いません。`STRATA_Q36_CHUNK` が設定されていると、この自動判定結果は環境変数の値（256〜4096 に clamp）で置き換わります。

## 適用条件と相互作用

- 適用対象は Qwen3.6 専用実装です。独立実行ファイル `strata-q36` と、architecture 判定後に専用実装へ転送される `strata --model` / `--native` の双方で処理されます。他 family ではこの専用 parser の意味は適用されません。
- 自動モードで MTP block があり、通常配置が収まらない場合、main layer experts を全て VRAM に置き、MTP の expert だけ hybrid 配置する判定を行うことがあります。明示した `--expert-vram` はこの例外を無効にし、指定予算に基づく通常の配置判定になります。`STRATA_Q36_NO_MTP_CPU` が設定されている場合も MTP 専用 CPU 配置を抑止します。
- `STRATA_Q36_KEEP_PACKED` が設定されている場合、自動モードでも packed Q8_0 copy の解放を抑止します。`STRATA_Q36_NO_MTP_CPU` と併せて、これらの環境変数はこの option の配置分岐に関係します。
- hybrid 配置は全 expert blob をホストメモリに構築し、GPU slot、CPU pool、必要に応じて prompt 用 staging buffer を確保します。main layer が hybrid なら graph を無効化します。したがって予算設定は VRAM の使用だけでなく、GPU/CPU 間の実行経路や prompt chunk の選択にも影響します。
- CMake の `STRATA_NATIVE_EXPERTS=OFF` build では Qwen3.6 の CPU pool がなく、hybrid 経路を利用できません。全 routed experts が VRAM に収まらないと配置失敗になります。build 条件・Release 配布物の組み合わせは今回確認していません。

## 出力とエラー

- packed copy を解放した場合は、その容量と「全 expert を VRAM に置くために解放した」旨を stderr に表示します。
- 全 expert を VRAM に配置できた場合は、使用量と所要時間を stderr に表示します。hybrid の場合は GPU slot 数、ホストメモリの量・pinned/pageable の別、CPU pool、staging 容量などを表示します。
- CPU pool を含まない build で全 expert が収まらない場合、`the routed experts (...) do not fit in VRAM, and this build has no CPU expert pool` を stderr に出し、呼び出し側は終了コード `1` で終了します。
- hybrid 用 buffer/slot に空き VRAMが足りない場合は必要量と空き量を含むエラーを出し、終了コード `1` で終了します。メッセージは `--batch` / `--max-context` の縮小を案内し、明示 slot 指定時は `--expert-slots` の縮小も案内します。

## 根拠

- `src/program/generate.cpp:2393-2407` — `--model` / `--native` の GGUF architecture を確認し、Qwen3.6 family を専用実装へ振り分ける処理。
- `src/qwen35/q36_engine.cu:3735-3745,3778-3781` — option の初期値、値欠落時の終了、`std::atof` による parser 定義と関連 slot option。
- `src/qwen35/q36_engine.cu:3817-3865` — engine 初期化後の `--chunk auto` 判定、`STRATA_Q36_CHUNK` による上書き、配置関数の呼び出し。
- `src/qwen35/q36_engine.cu:2792-2813` — routed expert の容量計算、空き VRAM計測、既定 reserve と明示予算の算出。
- `src/qwen35/q36_engine.cu:2814-2864` — packed copy の解放条件、MTP-only 配置条件とログ。
- `src/qwen35/q36_engine.cu:2865-2886` — 全 VRAM 配置条件、および CPU pool がない build の失敗経路。
- `src/qwen35/q36_engine.cu:2888-2918,2920-3008` — hybrid slot 数・buffer 要求量の判定、失敗経路、ホストメモリと GPU/CPU 配置。
- `CMakeLists.txt:128,785-788` — `STRATA_NATIVE_EXPERTS` の build option と、Qwen3.6 CPU pool compile definition の条件。

今回の確認は指定 commit のソースと strata-envvars 側の CLI 索引・調査規約に限定しています。同一 revision の既存 CLI help、build 生成物、Release archive は確認していません。
