# `STRATA_TOPK_SAMPLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA の QSA block top-k のうち、条件を満たす prompt / prefill 経路で one-read sample kernel を選ぶスイッチ。通常の wide top-k が複数回 scores を読む箇所を、sample kernel で候補を選び、その後 `block_topk_wide_kernel<true>` で sample 失敗 query だけを再処理する構成にする。既定では Turing 系（sm_75 で `STRATA_SM75_PERF=1`、または Volta sm_70 の既定スイッチ群が有効な場合）で選択可能になる。`STRATA_TOPK_SAMPLE=1` はこの GPU 世代判定を上書きするが、呼び出し側の active-block 条件は上書きしない。コードコメントは選択結果の ID は従来 kernel と同じとしているが、この調査では実行比較をしていない。実装は `engine/src/kernels/cuda/qsa_select.cu` の `topk_sample_on()` と `qsa_block_topk()`。

## 値と判定

`topk_sample_on()` 内の `static const int env` が `std::getenv` の戻り値を一度だけ読み、値が存在すれば `std::atoi(v) != 0` を 1、ゼロを 0 に変換する。未設定なら -1 を保存し、その場合だけデバイス既定判定へ進む。空文字も設定済みとして `atoi("") == 0` となる。文字列全体の妥当性検査はなく、先頭の整数部分を `atoi` が変換するため、たとえば `1tail` は有効、`0tail`・`true`・空文字は無効、先頭の空白の後の `1` は有効。負の非ゼロ値も有効。数値の範囲制限や無効文字列の警告はない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| 変数が明示設定済み | デバイス既定に委譲 | `1`, `-1`, `1tail`, ` 1` | `0`, `0tail`, `true`, 空文字 |
| 未設定時の CUDA デバイス既定 | sm_75 で `STRATA_SM75_PERF` が非ゼロ、または sm_70 で `STRATA_SM70_PERF` が未設定/先頭が `0` 以外かつ `STRATA_DEFAULTS` が `026` でない場合に有効 | 既定条件成立時 | それ以外は無効 |

CUDA sm_70 の engine 起動時には `nv_default_env()` が `STRATA_TOPK_SAMPLE=1` を既定候補に含める。`apply_nv_defaults()` は既に環境変数が存在する場合、値が空や `0` でもその値を保つ。sm_70 の既定候補群は `STRATA_SM70_PERF=0` または `STRATA_DEFAULTS=026` で無効になる。従って通常の engine 起動では、この既定注入により明示設定なしでも `topk_sample_on()` は明示値 `1` として扱う。候補を一つでも設定した起動では `stderr` に既定スイッチ一覧の案内が出るが、一覧に `STRATA_TOPK_SAMPLE` が含まれていればその名前が出る。根拠: `engine/src/core/nv_defaults.cpp:137-163`, `engine/src/core/nv_defaults.cpp:222-255`, `engine/src/program/generate.cpp:4430-4449`。

## 有効になる条件

- one-read kernel は `qsa_select.cu` の `#if !defined(__HIPCC__)` 範囲内にあり、HIP/AMD 実装からは呼び出されない（`engine/src/kernels/cuda/qsa_select.cu:2800-2814,2995-3014,3092-3098`）。`docs/SETTINGS.md` の候補表は NVIDIA と AMD の両方を記載しているが、このスイッチを読む実装と one-read kernel は CUDA 側だけにある。
- `qsa_block_topk()` が `nq > 0` であること。CUDA では `STRATA_TOPK_CAPACITY_GUARD` が設定されておらず、`active_blocks > 0 && active_blocks <= max_blocks` で、さらに Turing (sm_75)、または有効な Volta sm_70 であるか、テスト用 `STRATA_TOPK_ACTIVE_ANY=1` が必要（`engine/src/kernels/cuda/qsa_select.cu:3016-3021,3047-3057`）。
- 通常の QSA dispatch が wide kernel 分岐へ進み、`counted` が真、`nq <= 4096`、`reach > 28672` であることが必要。`reach` は counted 時に active block 数（上限 `max_blocks`）である（`engine/src/kernels/cuda/qsa_select.cu:3058-3059,3091-3098`; 上限は同ファイル `:857`）。
- `STRATA_TOPK_OLD` が設定されていれば参照 kernel に戻るためこの分岐に達しない。`STRATA_TOPK_STREAM` が未設定または先頭文字が `0` 以外で、かつ counted 時に `reach > 22528` の場合も wide 分岐に入るが、`reach > fit` ならこの条件に関係なく wide 分岐に進む。`STRATA_TOPK_CAPACITY_GUARD` が設定されている場合は counted にならず one-read 条件を満たさない（`engine/src/kernels/cuda/qsa_select.cu:3019-3021,3082-3098`）。
- `STRATA_TOPK_SAMPLE=1` は非 Turing CUDA カードでも `topk_sample_on()` の世代既定を上書きするが、それだけでは counted 条件を満たさず、通常の Ampere/Blackwell 等で機能を強制するものではない。`STRATA_TOPK_ACTIVE_ANY=1` はコードコメント上テスト向けの別スイッチで、任意カードで counted dispatch を許す（同ファイル `:3051-3056`）。
- `STRATA_QSA_CLUSTER` が既定の有効状態で、cluster kernel の呼び出しが成功すると `qsa_block_topk()` は先に return するため、後段の one-read 分岐を通らない（同ファイル `:3022-3030`）。

## 実行時の詳細

`topk_sample_on()` の環境値は、関数が初めて呼ばれた時に `static` 初期化される。プロセス中の環境変更は再評価されない。未設定時に使う CUDA device の可否は `ok[64]` に device ごとに cache される。デバイス取得に失敗するか ID が 0..63 の範囲外なら `false` を返す（`engine/src/kernels/cuda/qsa_select.cu:3000-3013`）。sm_75 の既定は `STRATA_SM75_PERF` を `atoi` で読み、非ゼロなら有効。sm_70 の既定は `STRATA_SM70_PERF` の未設定または先頭が `0` 以外、かつ `STRATA_DEFAULTS` が文字列として `026` と一致しない場合に有効（同ファイル `:2155-2161`; `engine/include/strata/core/sm75_series.hpp:24-37`）。

有効時は各 query に `block_topk_sample_kernel` を起動し、続けて `block_topk_wide_kernel<true>` を起動する。sample kernel は score block を一定 stride でサンプルして bound を作り、その後全 block を読み候補を集める。候補が `TS_CAP` を超えるか候補 cell 数が選択幅に満たない query は失敗フラグを立て、後続 wide kernel がその query だけを処理する。成功した query は後続 wide kernel がスキップする。stride は 32 から始まり、block 数に応じて最大 128 まで倍増する（`engine/src/kernels/cuda/qsa_select.cu:2800-2814,2836-2866,2892-2912,2960-2994`; fallback guard は同ファイル `:860-864`）。

対象関数は kernel launch 後 `cudaGetLastError()` を確認し、エラー時は `stderr` に `qsa_block_topk: <CUDA error>` を出して `exit(1)` する。通常時や sample fallback 時の専用ログはない（`engine/src/kernels/cuda/qsa_select.cu:3093-3105`）。SM70 の起動時既定値適用では、スイッチ候補が適用されたとき `strata: sm_70 (Volta): ... speed switches on by default ...` 形式の案内が `stderr` に出る（`engine/src/core/nv_defaults.cpp:240-255`）。

## 根拠

- 読み取り・値判定・世代既定: `engine/src/kernels/cuda/qsa_select.cu:2997-3013,2155-2161`; `engine/include/strata/core/sm75_series.hpp:24-37`
- dispatch と kernel 選択: `engine/src/kernels/cuda/qsa_select.cu:3016-3059,3082-3105`
- sample 候補抽出、fallback、stride: `engine/src/kernels/cuda/qsa_select.cu:2800-2814,2836-2866,2892-2912,2960-2994,860-864`
- sm_70 既定値と明示値の優先: `engine/src/core/nv_defaults.cpp:137-163,222-255`; 呼び出し: `engine/src/program/generate.cpp:4430-4449`
- 資料照合: `docs/DETAILS.md:1336-1346,1478-1488` は sm_75 スイッチ系列と sm_70 既定値表に記載。`docs/SETTINGS.md:479` は NVIDIA と AMD の候補とする一方、実装の one-read 分岐は CUDA のみ。
