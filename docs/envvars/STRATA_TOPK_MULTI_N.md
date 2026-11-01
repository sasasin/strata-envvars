# `STRATA_TOPK_MULTI_N`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

multi-CTA top-k カーネルを実行するとき、1 query あたりに使う CTA 数を指定します。正の数値に変換される値は固定数として使われ、カーネルの上限 32 に制限されます。unset または正数に変換できない値は、`max_blocks` から計算する既定数を使います。この変数はカーネルの選択スイッチではありません。

コメントでは「tests」用とされていますが、読み取りと利用は CUDA カーネル実装にあり、条件を満たす通常の呼び出しにも作用します。別の診断実行ファイル `qsa_select_long_parity` は値を表示しますが、その表示はカーネル設定の判定ではありません。

## 値と判定

`qsa_block_topk_multi()` 内の関数ローカル `static const int` が、最初の呼び出し時に `std::getenv()` と `std::atoi()` で一度読みます。`atoi` の変換結果が正の場合だけ指定数を採用します。

| 値 | 結果 |
|---|---|
| 未設定 | `n_env = 0`。容量から既定数を計算 |
| 空文字 | `atoi("")` は 0。容量から既定数を計算 |
| 正の整数（例 `3`） | 1 query あたり指定数の CTA。32 を超える値は 32 に制限 |
| 0、負数 | 容量から既定数を計算 |
| 数字で始まらない文字列 | `atoi` の結果は 0 となり、容量から既定数を計算 |
| 数字の後ろに文字が続く値（例 `3x`） | `atoi` が先頭の整数部分を変換するため、3 CTA |

空白や符号などの解釈も `atoi` に委ねられ、文字列全体の妥当性検査やエラー報告はありません。指定値を使わない場合、`n = ceil(max_blocks / 2048)` を計算し、最終的に 1〜32 に clamp します。したがって自動計算値も `max_blocks` の範囲に応じて上下限に制限されます。

## 有効になる条件

次の条件を満たして `qsa_block_topk_long()` が multi-CTA 経路を選んだ場合にだけ、この値が CTA 数に反映されます。

- CUDA で `STRATA_EXPERIMENTAL_SM60` を有効にしてビルドされている。HIP と通常ビルドでは multi-CTA 実装がなく、top-k は通常経路へ進みます。
- 呼び出し元が long-select 経路を使う。Verifier では `STRATA_SELECT_LONG=1` が必要で、さらに選択対象の window が `STRATA_SELECT_LONG_AT`（既定 65,536 cells）の閾値以上である必要があります。multi-CTA scratch がないビルドでは `STRATA_SELECT_LONG` 自体が無効になります。
- `nq > 0`、multi-CTA scratch が渡され、`STRATA_TOPK_OLD` が設定されておらず、active count がなく、`nq <= 16`、shape の `idx_block` がカーネル定数 `R` と一致し、capacity が選択幅以上であること。
- `STRATA_TOPK_MULTI` が有効であること。値が設定されていれば `atoi` が 0 以外なら有効、未設定または空文字なら compute capability 6.x で既定有効です。それ以外の GPU では明示的に有効化しない限りこの multi-CTA 経路に進みません。`STRATA_TOPK_MULTI=0` なら本変数による CTA 数指定も使われません。

これらを満たさない呼び出しでは `STRATA_TOPK_MULTI_N` の値は top-k の経路や CTA 数を変えません。

## 実行時の詳細

値は `qsa_block_topk_multi()` の最初の呼び出し時に static cache され、同じプロセスで後から環境を変更しても再評価されません。正の値から CTA grid の x 次元を作り、query 数を y 次元にして、multi-CTA top-k の histogram、count、emit カーネル群を起動します。値が unset または正数でなければ、容量由来の CTA 数で同じカーネル群を起動します。

カーネル起動直後の `cudaGetLastError()` が失敗した場合は stderr に `qsa_block_topk multi: <CUDA error text>` を出して `exit(1)` します。この環境変数の値自体に対する警告やログはありません。`qsa_select_long_parity` は実行時に値を stdout へ表示し、未設定時は `(per capacity)` と表示します。CMake の `qsa_select_long_parity_n3` は診断ケースとして `STRATA_TOPK_MULTI_N=3` を渡します。

## 根拠

- `src/kernels/cuda/qsa_select.cu:3031-3072` — multi-CTA top-k のビルド条件、`STRATA_TOPK_MULTI` の既定判定、対象変数の読み取り・数値変換・既定計算・clamp・カーネル起動・失敗時の終了。
- `src/kernels/cuda/qsa_select.cu:1676-1683,3077-3101` — CTA 上限 32、scratch の有無、および long top-k の選択条件と通常経路への fallback。
- `src/core/verify.cpp:176-200,966-967,1775-1786,3076-3078` — `STRATA_SELECT_LONG` の値判定と build 不適合時の警告、scratch 確保、decode window から long/通常 select を選ぶ箇所。
- `CMakeLists.txt:236-284,539-550` — experimental CUDA build の compile macro と、診断用 parity ケースが値 3 を渡す設定。
- `src/kernels/qsa_select_long_parity.cpp:177-191` — parity プログラムの build 判定と、対象変数の診断表示。
- `include/strata/kernels/qsa_select.hpp:81-95` と `docs/OLDER_GPUS.md:178-185` — long-select の文書上の説明。後者の測定は `STRATA_SELECT_LONG` と `STRATA_TOPK_MULTI` / `STRATA_SCORES_DX` の組み合わせについてであり、`STRATA_TOPK_MULTI_N` 単独の性能測定ではありません。
