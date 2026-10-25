# `STRATA_EXPDEC_DOWN`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有コードであり、外部ライブラリの環境変数動作は含めない。

## 役割

`native_expert_grouped` の down projection に EXPDEC カーネルを使うことを許可する。既定値は `0` で、EXPDEC が有効な場合も通常は gate/up projection だけが EXPDEC 対象になる。この変数単独では EXPDEC 全体を有効にしない。全体の有効化には `STRATA_EXPDEC` が必要である。

## 値と判定

値は `env_int_or("STRATA_EXPDEC_DOWN", 0)` で読み、設定されていて空でなければ `std::atoi` の結果を保存する。

| 環境変数の状態・値 | 保存値 | この変数による許可 |
|---|---:|---|
| 未設定 | `0` | しない |
| 空文字 | `0`（既定値） | しない |
| 整数として `0` になる文字列（例 `0`, `abc`, `0tail`） | `0` | しない |
| 整数として 0 以外になる文字列（例 `1`, `-1`, `2`, `1tail`, ` 1`) | 非ゼロ | 許可 |

全体の文字列検証はせず、整数変換で先頭にある整数部分を使うため、`1tail` のような後続文字は判定に使われない。`atoi` のため無効文字列は 0 として扱われ、数値としての範囲エラーも別途検出されない。`expdec_down_ok()` は保存値を真偽値として扱うので、`1` だけでなく任意の非ゼロ値が許可条件を満たす。

## 有効になる条件

環境値が非ゼロでも、実際に down 用 EXPDEC カーネルが選ばれるには次の条件が必要である。

- EXPDEC 全体が有効である（`STRATA_EXPDEC` の判定が有効）。
- `STRATA_OLD_IQ_MMVQ` による旧カーネル選択が無効である。
- down のレイアウトが対応する型・形状である。Q2_0 (`d_type == 42`)、または IQ4_NL (`d_type == 20`) かつ `STRATA_EXPDEC_D20` が非ゼロで、さらに `n_ff == 640`、`n_embd > 0`、`n_embd` が 128 の倍数である。型番号と形式の対応、および EXPDEC の対応形式は `docs/EXPERTDEC.md:16-17` に記載されている。

対応する型でも上記の形状条件を満たさなければ、down は通常カーネルに戻る。`d_type == 20` は別変数 `STRATA_EXPDEC_D20` も必要とする。対象のソースは CUDA 実装 (`src/kernels/cuda/iq_kernels.cu`) である。

## 実行時の詳細

`STRATA_EXPDEC_DOWN` は CUDA ソース内のグローバル変数初期化で読み込まれるため、プロセス起動時の環境が使われる。実行中にプロセス環境を変更してもこの値は再読込されない。内部 API `native_expert_set_expdec_params()` は `p.down >= 0` の場合に値を上書きできるが、通常の実行コード内でこの setter を呼び出す箇所は確認できず、リポジトリ内の呼び出しはベンチマーク用コードに限られる。

grouped expert の down 処理で EXPDEC モードと型・形状を確認し、条件に合えば `expdec_down_kernel` を起動する。条件に合わない場合は呼び出し元が既定 down kernel を起動する。EXPDEC が有効な処理で未対応の型に初めて到達すると、stderr に `strata expdec: CUDA%d down type %d (n_embd %lld, n_ff %lld) not covered: the default kernel runs` と出る。対象カーネルを使う最初の到達時には `strata expdec: CUDA%d down type %d: expdec_down_kernel ...` の設定情報が stderr に出る。これらの通知は型と採用／不採用ごとに一度だけである。EXPDEC 全体が無効、または旧カーネル選択中は、この down EXPDEC 判定・通知の経路に入らない。

## 根拠

- 値変換と既定値: `src/kernels/cuda/iq_kernels.cu:3934-3937,3948`。
- EXPDEC 全体および旧カーネルとの条件、down の型・形状判定: `src/kernels/cuda/iq_kernels.cu:3959-3961,4063-4069`。
- 対応型での起動と既定カーネルへの fallback: `src/kernels/cuda/iq_kernels.cu:5262-5269`。
- 一度だけの通知とログ文言: `src/kernels/cuda/iq_kernels.cu:4001-4025`。
- setter による上書きとパラメータ返却: `src/kernels/cuda/iq_kernels.cu:5022-5042`。リポジトリでの setter 利用箇所: `src/kernels/expdec_bench.cpp`。
- 役割・性能上の注記: `docs/EXPERTDEC.md:16-17,31-34,89-100` は、Q2_0 down での EXPDEC を既定 OFF とし、記載の RTX 2080 Ti を含む engine 測定では約 10% 遅かったと説明している。これは同資料の条件での測定値であり、別環境の性能を示すものではない。
