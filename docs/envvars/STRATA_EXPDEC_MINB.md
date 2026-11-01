# `STRATA_EXPDEC_MINB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

CUDA の EXPDEC gate/up カーネルで、`__launch_bounds__(256, MINB)` の `MINB` を 2 または 4 のどちらでインスタンス化するか選びます。コードのコメントでは 2 は最大 128 registers、4 は最大 64 registers に対応する設定です。環境変数がコンパイル済みカーネルの launch bounds を実行時に書き換えるのではなく、Strata は起動時に読んだ値を二択に正規化し、そのテンプレート引数でカーネルを起動します（`src/kernels/cuda/iq_kernels.cu:2447-2450,2562-2568,4108-4118`）。

この変数だけでは EXPDEC は有効になりません。EXPDEC の有効化には別の `STRATA_EXPDEC` が必要です。未設定時の `STRATA_EXPDEC_MINB` の既定値は、ソースの `#define STRATA_EXPDEC_MINB 4` です（`src/kernels/cuda/iq_kernels.cu:2447-2450,4060-4065`）。

## 値と判定

`env_int_or()` は環境変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` に渡します。parse エラーを報告したり、値を 2/4 に限定して拒否したりはしません。読み取った整数は後段で `>= 4` なら 4、それ未満なら 2 に正規化されます（`src/kernels/cuda/iq_kernels.cu:4056-4058,4065,4111-4118`）。

| 環境値 | `atoi` の結果 | gate/up 用 `MINB` |
|---|---:|---:|
| 未設定、空文字 | 既定値（通常は 4） | 既定値が 4 以上なら 4、未満なら 2 |
| `4` 以上の整数（例: `4`, `8`） | 4 以上 | 4 |
| 4 未満の整数（例: `3`, `2`, `1`, `0`, `-1`） | 4 未満 | 2 |
| 数字で始まらない文字列（例: `abc`） | 0 | 2 |
| 数字の後ろに文字が続く文字列（例: `4xyz`） | 数字部分 | 先頭の数値が 4 以上なら 4、それ以外は 2 |

したがって通常の既定 macro 値 4 のビルドでは、未設定と空文字は 4、`abc` は parse 失敗として拒否されるのではなく 2 の選択になります。`atoi` のため、先頭空白や符号を含む文字列も C の整数変換規則に従います。値の範囲 clamp や範囲エラーのログはありません。

## 有効になる条件

- この読み取りは `src/kernels/cuda/iq_kernels.cu` にある CUDA 実装です。HIP/SYCL 実装や GPU driver がこの環境変数を読む箇所は確認できません。
- EXPDEC の gate/up 経路が実行され、`STRATA_EXPDEC` が有効で、旧カーネル設定 `g_old_kernels` が無効である必要があります。そうでなければ `expdec_gu()` は `false` を返し、呼び出し元は既定 gate/up kernel を選びます（`src/kernels/cuda/iq_kernels.cu:4151-4165,6410-6415`）。
- gate/up の形式は `gu_type` が 16, 17, 18, 21, 22 のいずれか、`n_embd == 2560`、`n_ff` が 64 の倍数かつ正である必要があります。未対応 layout では既定 kernel に戻ります（`src/kernels/cuda/iq_kernels.cu:4077-4079,4155-4157`）。
- `STRATA_EXPDEC_MINB` は down kernel の `MINB` を実行時に変えません。`expdec_down_kernel` は `STRATA_EXPDEC_MINB` macro を直接 `__launch_bounds__` に使い、実行時の `g_expdec_minb` は gate/up テンプレート選択だけで参照されます（`src/kernels/cuda/iq_kernels.cu:2747-2748,4111-4118`）。
- 既定の EXPDEC gate/up kernel 経路で対応する専用 CLI 引数は見つかりません。公開 API `native_expert_set_expdec_params()` は正の `gu_min_blocks_per_sm` で値を上書きできます。リポジトリ内では `expdec_bench` がこの setter を呼びますが、通常の engine 呼び出し箇所は見つかりませんでした（`include/strata/kernels/iq_kernels.hpp:119-131`, `src/kernels/cuda/iq_kernels.cu:6218-6226`, `src/kernels/expdec_bench.cpp:105-106`）。

## 実行時の詳細

`g_expdec_minb` は CUDA translation unit のグローバル初期化で `env_int_or("STRATA_EXPDEC_MINB", STRATA_EXPDEC_MINB)` により初期化されます。リクエストごとに環境を読み直す処理はありません。公開 setter により後から変更された場合はその値が使われますが、gate/up kernel 起動時に再度 `>= 4 ? 4 : 2` として二択化されます（`src/kernels/cuda/iq_kernels.cu:4056-4065,4111-4118,6218-6222`）。ヘッダーも各 knob を起動時に環境から読むと記載しています（`include/strata/kernels/iq_kernels.hpp:119-123`）。

有効な EXPDEC gate/up layout に到達すると、初回の role/type について stderr に `strata expdec: CUDA%d gate/up type %d: expdec_gu_kernel R %d MINB %d, ...` を出し、選ばれた 2/4 がログに現れます。未対応 layout では `... not covered: the default kernel runs` と出ます。どちらも EXPDEC が無効、または旧カーネル設定で早期 return する経路では、この関数からは出ません（`src/kernels/cuda/iq_kernels.cu:4120-4147,4155-4157`）。環境値自体の parse エラー、終了、警告経路は実装されていません。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:771`。
- 全参照を `rg -n --hidden --glob '!.git/**' 'STRATA_EXPDEC_MINB'` で確認。実際の環境読み取りは `src/kernels/cuda/iq_kernels.cu:4065` のみ。ほかの参照は macro 定義・kernel annotation・コメントです。
- 変換 helper と実行時値: `src/kernels/cuda/iq_kernels.cu:4056-4058,4060-4065`。
- gate/up kernel のテンプレート選択と bounds: `src/kernels/cuda/iq_kernels.cu:2562-2568,4108-4118`。
- 有効化条件・layout fallback・ログ: `src/kernels/cuda/iq_kernels.cu:4077-4079,4120-4147,4151-4165`。
- down kernel は実行時値を参照しない: `src/kernels/cuda/iq_kernels.cu:2747-2748`。
- API による上書き: `include/strata/kernels/iq_kernels.hpp:119-131`, `src/kernels/cuda/iq_kernels.cu:6218-6226`; bench の setter 呼び出し: `src/kernels/expdec_bench.cpp:105-106`。
- 補助資料 `docs/EXPERTDEC.md:28-29,40-42` は gate/up の 2/4 設定と起動時読み取りを説明しています。効果と適用範囲の記述は上記の現行実装を根拠にしました。
