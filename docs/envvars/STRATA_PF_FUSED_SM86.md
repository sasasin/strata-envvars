# `STRATA_PF_FUSED_SM86`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

CUDA の fused prompt expert に使う「sm_86 class」既定ルールを無効にする診断スイッチです。未設定、または値の先頭文字が `0` 以外なら、compute capability 8.0 / 8.6 / 8.9 をこのクラスとして扱います。値の先頭が `0` ならクラス判定から外し、通常は該当する既定 fused 経路を MMQ に戻します。実装は CUDA の `dev_info()` と起動時の K-quant 既定経路表示判定にあります（`src/prefill/moe_fused_iq.cu:2422-2424`, `src/core/nv_defaults.cpp:142-146`）。

このクラス判定は、通常の CUDA fused default（`STRATA_PF_FUSED` 未設定時の対象 i-quant、既定 K-quant、Gyro-S の trellis kernels）やタイル選択ルールで使われます。既定 i-quant は 80 SM 以上で対象 gate/up 形式を取り、40–79 SM では `STRATA_PF_FUSED_SM40` の条件を満たす staged launch に限ります。K-quant と trellis にもそれぞれの形式・設定条件があります（`include/strata/prefill/fused_tile_rule.hpp:29-33,130-166`; `src/prefill/moe_fused_iq.cu:2495-2502,2966-2990`）。これは全 GPU の fused kernels を一括で切るスイッチではありません。たとえば `STRATA_PF_FUSED=0` は全 fused kernel を止め、`STRATA_PF_FUSED=1` は対象形式の opt-in 経路を選びます（同 `src/prefill/moe_fused_iq.cu:2901-2908,2976-2990`）。

## 値と判定

エンジン側の `dev_info()` は `std::getenv` の戻り値について `v != nullptr && v[0] == '0'` だけを判定します。文字列全体の比較、数値変換、空白除去、大文字小文字変換、範囲検査はありません（`src/prefill/moe_fused_iq.cu:2422-2424`）。起動時の `nv_kq_fused_here()` 側も同じ先頭文字判定を共通 helper `off()` で行います（`src/core/nv_defaults.cpp:14-18,142-146`）。

| 条件 | unset | 設定時にクラスが有効 | 設定時にクラスが無効 |
|---|---|---|---|
| CUDA | sm_86 class 判定を許可 | 先頭文字が `0` でない値（例: 空文字、`1`, `true`, `false`, ` 0`, `anything`）。文字列全体や数値としての妥当性は見ない | 先頭文字が `0` の値（例: `0`, `00`, `0anything`） |
| HIP / Metal | この変数を読まない | 該当なし | 該当なし |

具体的には、空文字は「設定済み」でも `v[0]` が `\0` なので無効化条件に一致せず、クラスを維持します。`false` や先頭に空白のある ` 0` もクラスを維持します。`0anything` は先頭が `0` のためクラスを無効にします。エンジン側では `sm86_off` が関数内 `static` として初回 `dev_info()` 呼び出し時に読み込まれ、その後はプロセス内で固定です。一方、`nv_kq_fused_here()` の helper は呼び出しごとに環境を読み直し、現状の呼び出し元は起動時の GPU 列挙です（`src/prefill/moe_fused_iq.cu:2379-2385,2422-2424`; `src/core/nv_defaults.cpp:14-18,142-146`; `src/program/generate.cpp:4208-4241`）。

## 有効になる条件

- **CUDA build のみ**です。`moe_fused_iq.cu` では HIP 分岐の対になる CUDA 側で読み取り、起動時 helper の呼び出しも HIP / Metal を除く CUDA 条件内にあります（`src/prefill/moe_fused_iq.cu:2390-2392,2416-2424`; `src/program/generate.cpp:4208-4241`）。
- クラスの対象は compute capability 8.0、8.6、8.9 です。8.7、9.0、10.x、12.x および 8.0 未満は、変数がクラスを許可していても含まれません（`include/strata/prefill/fused_tile_rule.hpp:29-33`）。
- CUDA の既定 i-quant 経路では、さらに `STRATA_PF_FUSED` が未設定（空文字も未設定扱い）であること、gate/up が既定対象形式であること、kernel setup が成功することが必要です。クラス内でも 80 SM 未満は staged gate/up と down 形式などの追加条件があります。40–79 SM の staged 既定は `STRATA_PF_FUSED_SM40` が先頭 `0` でない場合に限ります（`src/prefill/moe_fused_iq.cu:2901-2908,2976-2990`; `include/strata/prefill/fused_tile_rule.hpp:139-166`）。
- CUDA の既定 K-quant 経路は `STRATA_PF_FUSED=0` で止まり、`STRATA_PF_FUSED_KQ` に明示値があればその値で既定判定が分かれます。`STRATA_PF_FUSED_KQ=1` は対応 kernel が設定できた sm_80+ のカードを対象にし、`=0` は K-quant fused 経路を止めます。未設定時の既定は sm_86 class（または該当する sm_120 ルール）と SM 数・`STRATA_PF_FUSED_SM40` 条件に従います（`include/strata/prefill/fused_tile_rule.hpp:190-202`; `src/prefill/moe_fused_iq.cu:2461-2465,2954-2957`）。
- CUDA の Gyro-S trellis default も `d.s86` と 80 SM 以上を条件にします。`STRATA_PF_FUSED_TQ=1` は対応 trellis kernel が設定できる sm_80+ カードで opt-in し、`STRATA_PF_FUSED_TQ` の無効値は trellis 経路を選びません（`include/strata/prefill/fused_tq_default.hpp:4-10,23-31`; `src/prefill/moe_fused_iq.cu:2495-2502`）。
- 明示的な `STRATA_PF_FUSED=1` などの opt-in 経路は通常の「unset 時の sm_86 default」と別判定です。`STRATA_PF_FUSED_SM86=0` が全 fused kernel を遮断するとはコードから言えません。`STRATA_PF_FUSED=0` はこの変数の値にかかわらず fused 経路を止めます（`src/prefill/moe_fused_iq.cu:2901-2908,2976-2990`）。
- CLI 引数によるこの変数固有の上書きや、Strata の起動時既定値による自動設定は見つかりません。`STRATA_PF_FUSED_SM86` はユーザー環境から読み取られるだけです（読み取り箇所全件: `src/core/nv_defaults.cpp:14-18,142-146`; `src/prefill/moe_fused_iq.cu:2422-2424`）。

## 実行時の詳細

起動処理は CUDA GPU 群の compute capability を調べ、全可視カードが同一 capability の場合に既定環境設定を適用します。その後、K-quant default の有効判定で各可視カードについて `nv_kq_fused_here()` を呼び、この変数の先頭文字判定を行います。この判定値は K-quant expert を含む native layout の起動メッセージを選ぶために使われます（`src/program/generate.cpp:4208-4241,5064-5070`; `src/core/nv_defaults.cpp:99-123,142-146,178-190`）。

fused kernel 側では `dev_info()` が現在の CUDA device ごとに `DevInfo` を初期化し、`done` を立てた後はキャッシュを返します。`sm86_off` 自体も関数内 `static` なので、初回読み取り後にプロセス環境を変更しても fused kernel の class 判定には反映されません。`s86_class()` は capability 8.0 / 8.6 / 8.9 かつ `off` でないことを `d.s86` に保存します（`src/prefill/moe_fused_iq.cu:2379-2385,2417-2427`; `include/strata/prefill/fused_tile_rule.hpp:29-33`）。

`d.s86` は default format 判定に渡されます。該当ルールから外れたレイヤーはその fused default の対象にならず、通常の選択経路では MMQ 側に残ります。K-quant については fused kernel に入る際も `d.kq` などの kernel setup 状態が必要です（`src/prefill/moe_fused_iq.cu:2459-2465,2954-2957,2976-2990`）。

## ログと測定値

この変数単独の有効・無効ログやエラー出力はありません。K-quant が既定で設定され、モデルの native layout に K-quant expert が含まれる場合、起動時に stderr へ `nv_kq_default_line()` の文言が出ます。sm_86 class を無効にしたことで K-quant fused default 判定が偽になると、MMQ build では `strata: a model with K-quant experts (Unsloth UD-Q4/Q5/Q6_K_XL) reads its prompt on llama.cpp's MMQ kernels (STRATA_MMQ_KQ=0 or STRATA_NV_KQ_DEFAULT=0 turns it off)` の行が選ばれます。モデル形式や default 条件が満たされない場合、この行は出ません（`src/core/nv_defaults.cpp:153-165,178-190`; `src/program/generate.cpp:4240-4241,5064-5070`）。

`docs/DETAILS.md:1056,1319-1321` は fused prompt path と 12.0 の既定条件を説明していますが、この変数や sm_86 の既定条件は記載していません。そのため、変数固有の挙動は上記の Strata ソースだけを根拠にしています。ここでは新しい性能値や異なる環境への一般化は行いません。

## 根拠

- `src/core/nv_defaults.cpp:14-18,142-146` — 名前を引数で受ける共通 `off()` helper と、K-quant 起動時判定からの呼び出し。
- `src/prefill/moe_fused_iq.cu:2379-2385,2417-2427` — CUDA `DevInfo` 初期化、環境値の static cache、capability class の設定。
- `include/strata/prefill/fused_tile_rule.hpp:29-33,130-166,190-202` — 対象 compute capability と default / K-quant 判定への影響。
- `src/prefill/moe_fused_iq.cu:2495-2502,2891-2908,2954-2990` — trellis setup と native fused prefill の有効条件。
- `src/program/generate.cpp:4208-4241,5064-5070`; `src/core/nv_defaults.cpp:153-165,178-190` — 起動時の判定と K-quant 含有モデルでのログ。
- `docs/DETAILS.md:1056,1319-1321` — fused prompt の一般説明と 12.0 既定条件。対象変数の記載はない。
