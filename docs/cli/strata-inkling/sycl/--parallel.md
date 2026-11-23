# `--parallel`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--parallel` |
| 別名 | `-p` |
| 値 | 整数として `std::atoi` で読む slot 数。runner 側で有効値を1〜64に制限する |

## 役割

SYCL runner が保持する実行 slot 数を指定します。slot ごとの KV・ShortConv 履歴・DSpark 状態などの領域を確保するため、値を増やすと主にデバイスメモリ使用量が増えます。この値だけで入力や生成を複数 slot に自動分配する処理はありません。通常の greedy decode と benchmark は slot 0 を使い、複数 slot を実際に使う測定経路は `--par-sweep` です。

## 使い方

```sh
# 既定の greedy decode 経路を初期化し、最大4 slot 分の runner 領域を確保する
strata-inkling-sycl --model ./model.strata --parallel 4

# 固定された slot 数の組を使う並列性 sweep を実行する（--parallel の値は slot 数を決めない）
strata-inkling-sycl --model ./model.strata --parallel 4 --par-sweep
```

## 値と既定値

- 省略時は `1`。`--parallel N` と `-p N` は同じ変数に値を代入し、両方を複数回指定した場合は後に解析された値が残ります（`engine/src/inkling2/sycl/ink_sy_main.cpp:104,112-128`）。
- 値は `std::atoi` で変換され、明示的な parse error や正数チェックはありません。空値や整数として読めない値は `atoi` により `0` となり、runner の slot 数は最小値 `1` になります。負数も同様に `1` へ補正されます（`engine/src/inkling2/sycl/ink_sy_main.cpp:114,127,198`、`engine/src/inkling2/sycl/ink_sy_runner.h:223-228`）。
- 65以上の値は `InkSyRunner::init` で最大 `64` に制限されます。したがって実際に確保される slot 数は1〜64です（`engine/src/inkling2/sycl/ink_sy_main.cpp:198-201`、`engine/src/inkling2/sycl/ink_sy_runner.h:223-228`）。
- `--par-sweep` を同時指定すると、初期 slot 数は `--parallel` の値ではなく常に64になります（`engine/src/inkling2/sycl/ink_sy_main.cpp:198-201`）。

## 実行時の動作

モデル読み込み後、通常経路では `max(1, parallel)` を runner の slot 数に渡します。runner はこれを1〜64に clamp し、slot 数に応じた KV cache、ShortConv 履歴、slot 管理領域を確保します。DSpark が有効かつモデルに DSpark がある場合は、DSpark context KV と slot 状態も slot 数および context 長に応じて確保します（`engine/src/inkling2/sycl/ink_sy_main.cpp:183,198-204`、`engine/src/inkling2/sycl/ink_sy_runner.h:223-259,262-266,313-317`）。

通常の `--bench` は `run_greedy_decode` を呼び、同関数は slot 0 のみを使います（`engine/src/inkling2/sycl/ink_sy_main.cpp:31-42,257-265`）。一方、`--par-sweep` は slot 数を `1, 4, 8, 32, 64` と変えて各ケースを測定します。このモードは runner を64 slotで初期化し、`--parallel` による slot 数指定を上書きします（`engine/src/inkling2/sycl/ink_sy_main.cpp:198-201,267-285`）。

`--info` は model probe の後、runner 初期化より前に終了するため、このモードでは `--parallel` の値は使われません（`engine/src/inkling2/sycl/ink_sy_main.cpp:173-180`）。

## 適用条件と副作用

- `--model` が必要です。モデル指定がない場合は usage を stderr に出して終了コード1となり、runner は初期化されません（`engine/src/inkling2/sycl/ink_sy_main.cpp:166-169`）。
- slot 数を増やすと slot ごとのデバイス領域が増えます。特に KV 領域は各 visit について `max_slots × stride × n_kv × head_dim` 要素で確保され、DSpark の context KV は `max_slots × max_ctx × 1024` 要素で確保されます（`engine/src/inkling2/sycl/ink_sy_runner.h:240-259,313-317`）。
- `--ctx` / `--max-context` が指定された場合、DSpark context KV の確保量にも影響します。runner 内では context 長の最小値が256です（`engine/src/inkling2/sycl/ink_sy_main.cpp:126`、`engine/src/inkling2/sycl/ink_sy_runner.h:227,313-315`）。
- 成功すると stderr に `[ink_sycl] runner ready: slots=...` を含む初期化情報が出ます（`engine/src/inkling2/sycl/ink_sy_runner.h:328-335`）。
- 通常の device allocation が失敗した場合、共通 `dalloc` は `exit_device_error` に「out of device memory」を渡します。SYCL の peer GPU1 scratch allocation 失敗は `runner.init` が false を返し、呼び出し側が `[ERROR] runner init: ...` を stderr に出して終了コード1にします（`engine/src/inkling2/sycl/ink_sy_common.h:228-238`、`engine/src/inkling2/sycl/ink_sy_runner.h:287-299`、`engine/src/inkling2/sycl/ink_sy_main.cpp:200-204`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:104,112-128` — 既定値、`--parallel` と `-p` の解析、`atoi` による変換。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-204` — model 必須条件、`--info` の早期終了、slot 数と batch 容量の設定、runner 初期化失敗時の出力。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:31-42,257-285` — 通常 decode の slot 0 使用と `--par-sweep` の固定 slot 数。
- `engine/src/inkling2/sycl/ink_sy_runner.h:223-259,262-266,313-335` — slot 数の clamp、slot/context に連動する確保領域、初期化ログ。
- `engine/src/inkling2/sycl/ink_sy_common.h:228-238` — device allocation の失敗経路。
