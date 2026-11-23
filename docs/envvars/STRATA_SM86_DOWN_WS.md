# `STRATA_SM86_DOWN_WS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP 用の `engine/src/kernels/cuda/iq_kernels.cu` にある grouped expert down projection で、特定の IQ4_NL / Q2_0 レイアウトに専用カーネルを使うかを選ぶ開発・調整用スイッチです。通常は既定値 `0` で無効です。値 `1` または `6` は両形式、`5` は Q2_0 のみを専用経路へ送ります。対象外のレイアウトや条件では、この関数は `false` を返し、呼び出し元が通常の down カーネル選択へ進みます（`engine/src/kernels/cuda/iq_kernels.cu:4496-4509,4524-4538,7351-7409`）。

専用経路は IQ4_NL では `sm86_down_iq4nl_clean_kernel`、Q2_0 では `expdec_down_kernel<42,2>` を起動します。コード上、GPU の compute capability を問い合わせて `sm_86` か判定する処理はこの dispatch にはありません。名前およびコメントは sm_86 向けとしていますが、コードから確認できる実行条件は以下の値・レイアウト・カーネル状態です（同 `:3016-3025,4496-4509,4524-4538`）。

## 値と判定

`env_int_or` は `std::getenv` で読み、未設定または空文字なら既定値を返し、それ以外は `std::atoi` の結果を返します。その後 `sm86_down_ws_mode` が `1`、`5`、`6` 以外をすべて `0` にします。`atoi` は文字列全体の厳密な検証ではなく、先頭から整数として読める部分を変換するため、例えば `5x` は `5`、`0anything` や `true` は `0` になります。数値として読めない場合も `0` です。空白や符号の扱いは `atoi` に委ねられ、Strata 側の追加検証・clamp はありません。`atoi` で `int` の範囲を超える入力の結果は規定されないため、受理値として扱えません（同 `:4356-4359,4499-4505`）。

| 条件 | unset | 有効になる値 | 無効になる値の例 |
|---|---|---|---|
| `sm86_down_ws_mode` の初回評価 | `0`（無効） | `1`, `5`, `6` | 空文字、`0`, `2`, `4`, `-1`, `true`, `0anything` |

モードと形式の対応は次のとおりです（同 `:4496-4504,4527-4537`）。

| モード | IQ4_NL (`d_type == 20`) | Q2_0 (`d_type == 42`) |
|---|---|---|
| `1` または `6` | 専用 IQ4_NL カーネル | `expdec_down_kernel<42,2>` |
| `5` | 通常経路へ fallback | `expdec_down_kernel<42,2>` |

## 有効になる条件

- 対象コードが含まれる GPU engine の CUDA/HIP `.cu` build 経路で実行されること。Strata の engine build は CUDA と HIP の経路を持ちます（`engine/CMakeLists.txt:91-104,233-241`）。
- grouped expert down projection が実行されること。呼び出し元は gate/up と SwiGLU の処理後に `sm86_down_ws` を呼び、成功時は通常 down dispatch を飛ばします（`engine/src/kernels/cuda/iq_kernels.cu:7339-7354`）。
- `STRATA_OLD_IQ_MMVQ` が有効でなく、`STRATA_NO_SUB16_GU` も有効でないこと。どちらかが有効なら専用経路は使われません。これらは同 translation unit の初期化時に `env_on` で読み取られます（同 `:3689-3695,4527-4529`）。
- レイアウトが `d_type` 20 (IQ4_NL) または 42 (Q2_0)、`n_ff == 32 * ED_HB`（`ED_HB` は 20 なので `n_ff == 640`）、`n_embd > 0`、`had_block == 0` であること。Q2_0 ではさらに `n_embd` が偶数であること、両形式とも `d_row` が IQ4_NL で 360、Q2_0 で 180 であることが必要です（同 `:2662,4506-4509`）。
- mode `5` では IQ4_NL は専用経路を使わず fallback します（同 `:4527-4529`）。

この dispatch にモデルの種類名、CLI 引数、設定ファイルを読む処理はありません。環境変数をプロセス起動後に変更しても、専用モードの初回評価後は関数内 `static const int mode` のキャッシュが使われます（同 `:4499-4505`）。別の CLI / 設定層が実行環境へ値を渡すかどうかは、この実装箇所からは確認できません。

## 実行時の詳細

呼び出し時にモードを取得し、無効モード、旧 IQ kernel の選択、`STRATA_NO_SUB16_GU`、対象外レイアウトを検査します。適用時は一つの down dtype につき初回だけ stderr にログを出し、IQ4_NL は block row 32、Q2_0 は block row 64 の grid で専用 kernel を起動します。成功を返した呼び出し元は `check("native_expert_grouped/down sm86_ws")` を通って通常 down dispatch を終了します（同 `:4510-4522,4524-4538,7351-7354`）。

モードは専用関数が初めて呼ばれた時に読み取ってプロセス内に保存されます。`STRATA_OLD_IQ_MMVQ` と `STRATA_NO_SUB16_GU` は別の `env_on` 呼び出しで translation unit の初期化時に読み取られます。`env_on` は未設定・空文字・先頭文字 `0` を無効、それ以外の非空文字列を有効とします（同 `:3689-3695,4499-4505`）。

## ログと測定値

専用経路を選んだ dtype ごとに初回だけ、次の形式を stderr に出します。`<device>`、`<type>`、`<kernel>`、`<mode>`、`<rb>`、grid 値などは実行時の値です。CUDA stream capture 中には末尾に `, captured into a graph` が付きます（同 `:4510-4522`）。

```text
strata sm86-down-ws: CUDA<device> down type <type>: <kernel> (mode=<mode> rb=<rb>), grid <x> x <y> (cap <groups>)
```

起動後の `check` は `cudaGetLastError()` を確認し、失敗時には `<呼び出し箇所>: <CUDA error text>` を stderr に出して `exit(1)` します（同 `:47-50,7351-7354`）。この変数について実測性能値は Strata の docs 内で確認できませんでした（同名の文書参照は `docs/SETTINGS.md:312` の索引行のみ）。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:4356-4359,4499-4505` — helper の変換、既定値、許可モード、初回評価キャッシュ。
- `engine/src/kernels/cuda/iq_kernels.cu:4506-4538` — layout 条件、mode `5` の除外、カーネル選択と launch。
- `engine/src/kernels/cuda/iq_kernels.cu:3689-3695,4527-4529` — `env_on` の値判定と他の環境変数による無効化。
- `engine/src/kernels/cuda/iq_kernels.cu:7339-7354,47-50` — 呼び出し元、通常経路への fallback、launch error の確認。
- `engine/CMakeLists.txt:91-104,233-241` — CUDA / HIP build 経路。
