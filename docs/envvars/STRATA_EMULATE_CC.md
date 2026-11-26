# `STRATA_EMULATE_CC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU の compute capability と shared-memory 上限を、Strata のホスト側判定に限って別世代の値として扱うテスト用変数です。実際の GPU 属性やコンパイル済みデバイスコードは書き換えません。`strata generate` は表示上の capability に模擬値を使い、CUDA/SYCL のカーネル選択・機能判定や NVIDIA 向け既定値選択にも helper 経由でその値を使います（`engine/include/strata/core/emulate.hpp:58-92`、`engine/src/program/generate.cpp:8566-8571`、`engine/sycl/src/program/generate.cpp:4672-4683`、`engine/src/core/nv_defaults.cpp:21-40`）。

## 値と判定

`emulated_cc()` は初回呼び出し時に `std::getenv` で読み、設定があれば `std::atoi` で整数に変換します。結果が `75` 以上 `120` 未満なら採用し、それ以外は無効値として `0`（エミュレーションなし）にします。コメントは `75|80|86|89` を例示しますが、実装にこの4値だけの許可リストはありません（`engine/include/strata/core/emulate.hpp:58-65`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `emulated_cc()` を呼ぶビルド経路 | `0`（実機の属性を使う） | `atoi` の結果が 75–119。例: `75`, `80`, `89`, `119`, `75tail`, `+75`, 前置空白つき `75` | 空文字、空白だけ、`0`, `0anything`, `true`, `false`, 数字で始まらない文字列、`74`, `120`, 負数。変換結果が範囲外なら `0` |

`atoi` は文字列全体の妥当性検査をしないため、先頭の空白と符号の後にある数字列を変換し、数字以降の文字を無視します。大文字小文字の区別や `true`/`false` の解釈はありません。空文字や数値に変換できない文字列は `0` になります。整数型の範囲を超える文字列については安全な値域検査を実装していません（`engine/include/strata/core/emulate.hpp:61-64`）。

## 有効になる条件

- 値が有効範囲にあり、実行経路が `strata::emulated_cc()`、`cc_of()`、`cc_major_of()`、`cc_minor_of()`、または `smem_optin_of()` を呼ぶことが必要です。これらは `engine/include/strata/core/emulate.hpp:58-92` にあります。
- CUDA エンジンでは、GPU capability を使う NVIDIA 既定値選択や CUDA カーネル判定で使われます。たとえば Turing 向け QSA 判定は capability 75 と `STRATA_QSA_WARP=1` または `attn` の組み合わせを参照します（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2492-2507`）。この追加条件がない経路でも、同 helper を使う capability 判定は模擬値を受け取ります。
- SYCL エンジンでは、起動時の capability 表示、QSA の世代判定、共有メモリ上限判定で同じ helper が使われます（`engine/sycl/src/program/generate.cpp:4672-4683`、`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1938`、`engine/sycl/src/kernels/cuda/qsa.dp.cpp:1015-1028`）。
- コードがその世代向けにビルドされていることや、実 GPU がそのカーネルを実行できることまでは保証しません。たとえば QSA の cluster kernel は capability 判定に加えて PTX/binary version が 90 以上であることも確認し、条件を満たさないと選びません（`engine/src/kernels/cuda/qsa_select.cu:2488-2505`）。
- `engine/metal/src/engine/stubs.cpp` と `stubs_0145.cpp` にはヘッダーの include がありますが、この変数名または上記 helper の呼び出しは見つかりません。CPU-only 経路にもこの変数を読む呼び出しは確認できません（同じ checkout の `rg` 全参照調査）。

## 実行時の詳細

有効な整数 `v` は、能力値 helper では `cc_of()` の戻り値をそのまま `v` にし、major/minor helper ではそれぞれ `v / 10` と `v % 10` に分けます。shared-memory の opt-in 上限 helper は `75` を `65536` bytes、`80` を `166912` bytesとして返し、それ以外の有効値では実機値を最大 `101376` bytes に制限して返します（`engine/include/strata/core/emulate.hpp:67-92`）。これにより、たとえば fused prefill の setup 判定は模擬上限を超える候補を不採用にします（`engine/src/prefill/moe_fused_iq.cu:2748-2761`）。

値は `emulated_cc()` 内の関数ローカル `static const int` に初回呼び出し時に保存されます。したがってプロセス起動後に環境を書き換えても、いったん評価された後の値は変わりません。別の Strata プロセスではそれぞれ初回評価時の環境を読みます。Strata がこの変数を子プロセスへ設定・転送する処理は確認できません（`engine/include/strata/core/emulate.hpp:59-65`）。CLI 引数や別環境変数による一般的な上書き処理もありません。各機能固有の条件（例: QSA の `STRATA_QSA_WARP`）はその判定に限って作用します。`cc_of()` ではこの変数が優先され、未設定・無効値の場合に限り、Linux の CUDA 13 Volta compatibility proxy による実機 7.5 から 7.0 への remap が適用されます（`engine/include/strata/core/emulate.hpp:67-82`）。

## ログと測定値

`strata generate` は CUDA 経路で `GPU <番号>: <名前>, compute capability <major>.<minor> (STRATA_EMULATE_CC: a test mode, the card is emulated)` を stderr に出します。SYCL 経路も同じ注記を付けます。未設定または無効値ではエミュレーション注記を付けません（`engine/src/program/generate.cpp:8566-8571`、`engine/sycl/src/program/generate.cpp:4672-4683`）。

QSA の shared-memory 要求が helper の上限を超えると、CUDA は `qsa: qsa_attend: max_ids ... needs ... B of shared, over the ... B limit` を stderr に出して `exit(1)` します。SYCL 側も同様の理由を出して `exit(1)` します（`engine/src/kernels/cuda/qsa.cu:673-687`、`engine/sycl/src/kernels/cuda/qsa.dp.cpp:1015-1028`）。この変数自体に関する性能測定値は Strata の資料で確認できませんでした。

## 根拠

- `engine/include/strata/core/emulate.hpp:58-92` — 読み取り、変換、範囲、capability と shared-memory helper。
- `engine/include/strata/core/emulate.hpp:18-56,67-82` — Linux CUDA 13 Volta compatibility proxy の検出と、エミュレーションとの優先順位。
- `engine/src/program/generate.cpp:8566-8571`、`engine/sycl/src/program/generate.cpp:4672-4683` — 起動時表示。
- `engine/src/core/nv_defaults.cpp:21-40` — NVIDIA 既定値の capability 判定。
- `engine/src/kernels/cuda/qsa_prompt_attn.cu:2492-2507`、`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1938` — CUDA/SYCL の世代判定利用例。
- `engine/src/kernels/cuda/qsa.cu:673-687`、`engine/sycl/src/kernels/cuda/qsa.dp.cpp:1015-1028` — shared-memory 判定と失敗経路。
- `engine/src/kernels/cuda/qsa_select.cu:2488-2505` — capability に加えコンパイル済みデバイスコードを確認する例。
