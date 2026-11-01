# `DS4_ZC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 DSv4.1 の decode で、CPU lane にある MXFP4 expert の行列を GPU から直接参照する経路を有効にします。対象 expert の3行列を Metal の no-copy buffer として map できれば、CPU lane で処理せず通常の GPU expert と同じ GEMV 経路へ載せます。コードコメントは、この経路が CPU lane より速くなかった測定結果にも触れていますが、測定条件や数値は示していません（`src/dsv41/ds4_model.cu:4470-4475`）。

## 値と判定

`std::getenv("DS4_ZC") != nullptr` だけで判定します。未設定なら無効、何らかの値が設定されていれば有効です。空文字、`0`、`false` も設定済みなので有効になります。数値変換、文字列比較、範囲検査、無効値時の fallback 値はありません（`src/dsv41/ds4_model.cu:4473-4475`）。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 有効 |
| `1`、`0`、`false`、その他の文字列 | すべて有効 |

CLI 引数や別環境変数による `DS4_ZC` の上書き・優先順位はありません。`DS4_ZC_MAX` は Metal の map 数上限を扱う別変数で、`DS4_ZC` の有効判定ではありません（`metal/src/mtl_rt.mm:422-445`）。

## 有効になる条件

- `STRATA_METAL` でコンパイルされた DSv4.1 実装でのみ、この環境変数を読む分岐と呼び出しがあります（`src/dsv41/ds4_model.cu:4470-4475,10491-10495`）。CUDA/HIP の分岐では `zc_try()` が呼ばれず、この変数はこの経路に影響しません。
- ルーティングで選ばれた expert が既に VRAM slot にある場合は通常の GPU 経路を使うため、`zc_try()` は不要です。slot にない expert でも、token 数 `T` が1でなければ試行しません（`src/dsv41/ds4_model.cu:10488-10496`）。
- `zc_try()` 内で `DS4_ZC` が有効で、layer の形式が MXFP4、`l.nm == 1`、`l.vm` が空でない場合にだけ map を試します。いずれかを満たさなければ `false` を返し、CPU lane に残ります（`src/dsv41/ds4_model.cu:4473-4476,10491-10522`）。
- 3行列のいずれかで `metal_host::zc_map()` が 0 を返した場合も試行は失敗し、expert は CPU lane で処理されます（`src/dsv41/ds4_model.cu:4477-4491,10509-10522`）。Metal の map 実装は map 数上限に達した場合や no-copy buffer を作れない場合に 0 を返します（`metal/src/mtl_rt.mm:422-445`）。

## 実行時の詳細

`on` は `zc_try()` 内の `static const bool` です。したがって環境値は、プロセスで初めてこの関数に到達したときに読み取られ、その後の変更は反映されません。実際には Metal 経路で `T == 1` かつ VRAM slot にないルーティング済み expert があるときに初めて関数へ到達します（`src/dsv41/ds4_model.cu:4473-4475,10488-10495`）。

map 成功時は expert の各行列について `x3::Mat::raw` に map 先アドレスを設定し、GPU 側の expert 一覧に加えて `mv_n()` で計算します。map 失敗時や条件不一致時には CPU lane 用の `Ent` に入り、`cpu_experts()` が処理します（`src/dsv41/ds4_model.cu:4477-4491,10496-10522,10530-10552,10555-10565`）。この分岐自体には有効化・失敗を知らせる専用ログや終了処理はありません。後続の計算関数が失敗した場合は通常の `false` エラー経路を返します（`src/dsv41/ds4_model.cu:10530-10552`）。

## 根拠

- `src/dsv41/ds4_model.cu:4470-4493` — Metal 限定の `zc_try()`、設定有無判定、対象形式・layer 条件、行列 map。
- `src/dsv41/ds4_model.cu:10488-10522,10530-10565` — decode の呼び出し条件、GPU expert と CPU lane への振り分け、実行経路。
- `metal/src/engine/ds4_finish.cpp:595-599`, `metal/src/mtl_rt.mm:422-445` — Strata の Metal map 呼び出しと失敗時の 0 返却。
