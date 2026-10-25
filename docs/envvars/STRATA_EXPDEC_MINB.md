# `STRATA_EXPDEC_MINB`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数は対象外。

## 役割

CUDA の EXPDEC gate/up カーネルで、`__launch_bounds__(256, MINB)` の `MINB` を 2 または4から選びます。4 の場合はカーネルのコンパイル時条件が「SM あたり4ブロックを最低限確保」で、2 の場合は2ブロックです。環境変数の整数値そのものがカーネルへ渡るのではなく、4以上かどうかで二択に変換されます。

## 値と判定

共通 helper `env_int_or()` は、変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を使います。`STRATA_EXPDEC_MINB` の既定値は、ソースで別途定義されていなければ compile-time macro `STRATA_EXPDEC_MINB` の4です（`#ifndef` 定義）。その後、gate/up の起動時に `g_expdec_minb >= 4` なら4、そうでなければ2として扱います。

| 環境値 | `atoi` の結果 | gate/up 用 `MINB` |
|---|---:|---:|
| 未設定、空文字 | compile-time 既定値（通常4） | 通常4 |
| `4`、`5` など4以上の整数 | 4以上 | 4 |
| `2`、`3`、`1`、`0`、負値 | 4未満 | 2 |
| 数字で始まる文字列（例: `4tail`, `2tail`） | 数字の先頭部分 | それぞれ4、2 |
| 数字として読めない非空文字列 | 0 | 2 |

`atoi` による変換なので、全体の書式検証や末尾文字の拒否は行いません。先頭空白や符号を含む整数は `atoi` の規則で変換されます。整数変換の範囲外の入力について、コードは別途エラー処理をしていません。

## 有効になる条件

- この実装は `src/kernels/cuda/iq_kernels.cu` の EXPDEC gate/up 経路です。通常の engine 経路では `STRATA_EXPDEC` が未設定・空でなく、先頭文字が `0` 以外の場合に EXPDEC が有効になります（`false` も有効扱いです）。
- `STRATA_EXPDEC` が有効でも、旧 multi kernels が選択されている場合や、gate/up の量子化形式・形状が対象外の場合、EXPDEC gate/up カーネルは使われず、この値も効きません。対象形式は type 16/17/18/21/22、形状条件は `n_embd == 2560`、`n_ff > 0` かつ64の倍数です。
- ここで説明する環境変数は gate/up のカーネル選択だけに使います。down カーネル宣言にも同じ名前の compile-time macro が使われますが、その起動条件はビルド時に固定され、環境変数で切り替わりません。
- `native_expert_set_expdec_params()` は正の `gu_min_blocks_per_sm` を渡すと実行時値を上書きします。調査対象ソースでこの関数を呼ぶのは EXPDEC ベンチ用コードであり、通常の engine の呼び出し経路ではありません。

## 実行時の詳細

値は `iq_kernels.cu` のグローバル変数初期化時に一度読み取られます。従って、起動後にプロセス環境を書き換えても再読込されません。EXPDEC gate/up を起動するとき、実装は `g_expdec_minb >= 4` を判定し、テンプレート引数4または2のカーネルを選びます。値は `native_expert_expdec_params()` でも二択に丸めた形で返されます。

EXPDEC が対象形式で使われたとき、最初の該当する role/format について stderr に `strata expdec: ... MINB 4 ...` または `MINB 2` を含む行が出ます。EXPDEC の詳細資料は gate/up の既定を4、2を代替値として説明しています。資料記載の EXPDEC 性能測定は最適化全体の測定であり、`MINB` 単独の効果を示す値ではありません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:2353-2356`: compile-time macro の既定値4。
- `src/kernels/cuda/iq_kernels.cu:3933-3943`: `env_int_or()` の空値・未設定 fallback と `atoi`、環境値の読み取りおよび既定値。
- `src/kernels/cuda/iq_kernels.cu:3273-3276,3940`: EXPDEC を有効にする別環境変数 `STRATA_EXPDEC` の判定。
- `src/kernels/cuda/iq_kernels.cu:3955-3958,3976-3996`: 対象レイアウト条件と、4以上を4、それ以外を2に変換して gate/up カーネルを起動する処理。
- `src/kernels/cuda/iq_kernels.cu:4015-4019`: 有効時の stderr ログ。
- `src/kernels/cuda/iq_kernels.cu:2654`: down カーネルにおける compile-time macro の使用。
- `src/kernels/cuda/iq_kernels.cu:5022-5026,5032-5037`: EXPDEC パラメータ API による上書きと読み出し時の二択化。
- `src/kernels/expdec_bench.cpp:105-106`: 調査対象ソースで確認できるパラメータ setter の呼び出し。
- `docs/EXPERTDEC.md:1-3,23-29,36-40`: EXPDEC の適用範囲、設定値の説明とログ例。
- `docs/DETAILS.md:2512`: EXPDEC 全体の性能表。`STRATA_EXPDEC_MINB` 単独の測定ではない。
