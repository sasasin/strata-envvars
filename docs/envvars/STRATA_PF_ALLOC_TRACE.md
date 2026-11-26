# `STRATA_PF_ALLOC_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prompt 用 `Prefill` の初期化中に、GPU 空きメモリの変化と `Alloc::take` が要求した割り当て量を stderr に出す診断スイッチ。`pf_alloc_trace()` の結果はログと `cudaMemGetInfo` による計測の分岐にだけ使われ、バッファサイズや割り当て方を選ぶ条件には使われない。実装は `engine/src/prefill/prefill.cpp` の `pf_alloc_trace`、`pf_mark`、`Alloc::take` にある（`engine/src/prefill/prefill.cpp:1063-1116`）。

## 値と判定

`std::getenv` の戻り値が null でないことに加え、値の先頭文字が文字 `'1'` であることを判定する。文字列全体の数値変換・比較はしない（`engine/src/prefill/prefill.cpp:1065-1067`）。

| ビルド / 実行経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `Prefill::init` がこの実装を通る経路 | 無効 | `1`、`10`、`1anything`（先頭が `1`） | 空文字、`0`、`true`、` 1`、`True`（先頭が `1` でない） |

大文字小文字や数値としての妥当性は検査しない。先頭の空白は読み飛ばさない。設定有無だけを判定する方式ではないため、空文字は無効。コード上の既定値は無効である（同 `1065-1067`）。

## 有効になる条件

- `Prefill::init` が呼ばれること。通常の生成コードでは prompt path の初期化時に呼ばれ、複数 GPU の stage がある場合は各 stage でも呼ばれる（`engine/src/program/generate.cpp:13006-13029,13031-13041`）。
- この計測コードは `engine/src/prefill/prefill.cpp` にある。設定レジストリは当該読み取りを `cuda-hip` として登録している（`terminal/data/settings-register.json:29763-29776`）。Metal 分岐も `Prefill::init` の先頭にある読み取りと最初の `pf_mark` の後に現れるが、通常の CUDA/HIP 初期化処理とは異なり `window_ensure` へ早期 return する（`engine/src/prefill/prefill.cpp:2443-2454`）。
- 他の環境変数、CLI 引数、モデル形式による有効化条件はこのスイッチ自体にはない。環境変数が有効でも、`Prefill::init` を通らない実行では初期化ログは出ない。

## 実行時の詳細

値は `pf_alloc_trace()` 内の関数ローカル `static const bool` に保存される。最初の参照は `Prefill::init` の開始時であり、その後プロセス内で環境を変更しても判定は更新されない（`engine/src/prefill/prefill.cpp:1065-1067,2443-2448`）。

有効時、`pf_mark` は初期化の区切りで `cudaMemGetInfo` を呼び、空き量（整数 MiB）、前回マークからの減少量、呼び出し側から渡された要求量を出力する（`engine/src/prefill/prefill.cpp:1069-1081,2447-2448,2557,2595,2710,2737-2754`）。`Alloc::take` は借用領域からの切り出しではなく `cudaMalloc` を実行して成功した場合に限り、その直前・直後の空き量の差と要求 byte 数を加算する。従って借用領域からの切り出し、count-only の sizing、`Alloc` を介さない割り当て、失敗した `cudaMalloc` はこの集計に含まれない（同 `1083-1116`）。

carve が失敗すると通常の初期化失敗経路へ進み、空き量・確保済み量・失敗した buffer の要求量を含む `prefill: device buffers for a chunk of ... tokens do not fit (...)` をエラーにする。この場合、成功時の `Alloc takes: ...` 集計行は出ない。診断フラグによる割り当て方式の fallback や再試行はない（同 `2738-2752`）。

## ログと測定値

有効時の区切りログは stderr に次の形式で出る。`what` と数値部分は実行経路の値で置き換わる（`engine/src/prefill/prefill.cpp:1075-1080`）。

```text
prefill alloc trace: <区切り名> free <MiB> MiB, dropped <MiB> MiB, asked <MiB> MiB
```

初期化の carve 成功後には次の集計行も stderr に出る。`asked` と `bytes_needed` は MiB 単位にシフトして表示され、`free fell` は成功した `Alloc::take` 内の各割り当て前後で観測した空き量の差の合計である（同 `1109-1112,2748-2752`）。

```text
prefill alloc trace: Alloc takes: <個数> cudaMallocs, asked <MiB> MiB, free fell <MiB> MiB over them (bytes_needed counts <MiB> MiB for this chunk's own buffers; o.used <MiB> MiB)
```

Strata の説明資料にこの変数の測定値は見つからなかった。ソースコメントは `RESULTS-STRIX2.md` を参照しているが、ここでは測定値を記載しない（`engine/src/prefill/prefill.cpp:1063-1064`）。

## 根拠

- `engine/src/prefill/prefill.cpp:1063-1081` — 環境値の判定、cache、空きメモリ取得、マーク出力。
- `engine/src/prefill/prefill.cpp:1083-1116` — Alloc 経由で成功した `cudaMalloc` の計測範囲。
- `engine/src/prefill/prefill.cpp:2443-2454,2737-2755` — 初期化での読み取り・ログ・失敗時と成功時の分岐。
- `engine/src/program/generate.cpp:13006-13041` — prompt path 初期化からの呼び出し。
- `terminal/data/settings-register.json:29763-29776` — settings register 上の backend・読み取り情報（補助情報。実動作の根拠は上記ソース）。
