# `STRATA_GDN_PIPELINE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GDN recurrence の列分割カーネルで、次 token の入力を先読みする software-pipelined 版を選ぶかを制御する。未設定時はパイプライン版が選ばれる。値を `0` として判定すると、fallback dispatch で `gdn_rec_cols_kernel` を使う。パイプライン版は `gdn_rec_cols_kernel` と同じ演算順序・bit pattern とソースコメントに記されている（測定値の記載ではない）。CUDA、HIP、SYCL の各 recurrence 実装に読み取り箇所がある。`engine/src/prefill/kernels.cu` の `gdn_recurrence_impl` と `engine/sycl/src/prefill/kernels.dp.cpp` の `gdn_recurrence_variant` が実際の選択を行う。 ( `engine/src/prefill/kernels.cu:700-703,3183-3189,3253-3277`; `engine/sycl/src/prefill/kernels.dp.cpp:876-885,2887-2952` )

## 値と判定

CUDA/HIP と SYCL の読み取りは同じ式で、`getenv` の結果を初回評価時に `static const bool` へ保存する。未設定（null）の場合だけ `true`。設定済みなら `std::atoi(v) != 0` であり、空文字や数値として先頭を変換できない文字列は 0 となる。文字列全体の妥当性、大文字小文字、真偽語は検査しない。先頭の空白と符号は `atoi` の変換規則に従う。値の範囲を Strata 側で検査・clamp するコードはない。

| 条件 | unset | パイプラインを選ぶ例 | 列カーネルを選ぶ例 |
|---|---|---|---|
| CUDA/HIP または SYCL の読み取りに到達 | `pipe=true` | `1`, `-1`, `2`, ` 1`, `1xyz` (`atoi` が非 0) | `0`, `00`, `0xyz`, `true`, 空文字, `xyz` (`atoi` が 0) |

( `engine/src/prefill/kernels.cu:3188`; `engine/sycl/src/prefill/kernels.dp.cpp:2888` )

## 有効になる条件

- 対応 backend の GDN recurrence がこの環境変数の読み取り箇所まで到達すること。未設定を含む最初の読み取り結果は関数内 `static` に保存される。
- CUDA の通常 dispatch では、別経路が先に選ばれないこと。`STRATA_GDN_TC` / `STRATA_GDN_CHUNKED` による適用可能な経路が成功すれば、その経路が優先され、fallback の pipeline/columns 選択には到達しない。fallback では `pipe=true` かつ `gdn_keyhead_ok()` なら key-head kernel、そうでなければ pipe kernel が選ばれる。`pipe=false` なら key-head 判定を通さず columns kernel を選ぶ。テスト用 probe が強制 path を指定した場合、その path が優先され、`STRATA_GDN_PIPELINE` は選択に関与しない。 ( `engine/src/prefill/kernels.cu:3211-3265` )
- HIP では `gdn_rec_wmma` が chunked 経路を実行して戻る場合、または診断用 variant が早期 return する場合には読み取り・選択に到達しない。それ以外の通常 fallback は `pipe` に応じて pipe / columns kernel を選ぶ。 ( `engine/src/prefill/kernels.cu:3088-3100,3101-3144,3270-3275` )
- SYCL では `STRATA_GDN_REC_HEADS` が設定されている場合、`T <= 0`、または `variant == 2` のとき読み取り前の分岐で通常 recurrence kernel を選ぶ。`variant == 6` の Xe 経路では読み取りは行われるが、その後 `xe` 分岐が優先するため、この変数は選択に影響しない。その他の経路では `pipe=true` が pipeline 分岐へ進み、`gdn_keyhead_ok()` なら key-head kernel、そうでなければ pipe kernel（SYCL の追加条件により paired/local variant を含む）を選ぶ。`pipe=false` は columns kernel を選ぶ。 ( `engine/sycl/src/prefill/kernels.dp.cpp:2864-2893,2909-2952` )
- この変数を読む箇所には CLI 引数や設定ファイルから値を上書きする処理がない。したがってこの分岐の値源はプロセス環境であり、プロセス内で後から環境を変更しても、関数内 static が初期化済みなら反映されない。

## 実行時の詳細

CUDA/HIP の `gdn_recurrence_impl` は一部の早期経路を除き、fallback dispatch 内で `pipe` を初期化し、同じ `state`, `h`, `gate`, `beta`, `y`, `T` を受ける二つの recurrence kernel のいずれかを launch する。通常の出力付き処理では、その後 `with_out` かつ選択 kernel が出力正規化を融合していない場合に `gdn_out_norm_kernel` も launch する。環境変数は token ごとや呼び出しごとに読み直さない。CUDA probe による強制選択はこの設定を迂回できる。 ( `engine/src/prefill/kernels.cu:3083-3087,3183-3189,3253-3279` )

SYCL でも初回到達時の値を static 保存し、pipeline 分岐か columns 分岐を選ぶ。どちらの分岐も recurrence kernel を投入し、通常経路では続けて出力正規化 kernel を投入する。SYCL の `STRATA_SYCL_GDN_PREFILL_REG_QK` は pipeline 分岐内の別最適化を選ぶが、`STRATA_GDN_PIPELINE` の値判定を置き換えない。 ( `engine/sycl/src/prefill/kernels.dp.cpp:2887-2952,2953-2970` )

## ログと測定値

本番 recurrence のこの分岐自体は値や選択 kernel のログを出さない。GDN harness は環境変数が設定済みの場合に限り `env STRATA_GDN_PIPELINE=<値>` を stdout に表示するが、これは harness の診断表示で、本番 engine のログではない。 ( `engine/src/prefill/gdn_harness.cu:448-452` )

## 根拠

- `engine/src/prefill/kernels.cu:700-703,3081-3087,3145-3164,3183-3189,3211-3279` — CUDA/HIP の候補 kernel、評価、dispatch と出力正規化。
- `engine/sycl/src/prefill/kernels.dp.cpp:876-885,2800-2815,2864-2893,2909-2970` — SYCL の評価、Xe / key-head / pipeline / columns dispatch。
- `engine/src/prefill/gdn_harness.cu:448-452` — harness の環境値表示。
- `docs/GDN_CONTRACT.md:62-72` — dispatch 説明との照合。これはソース実装の根拠ではなく、条件確認の補助として参照。
