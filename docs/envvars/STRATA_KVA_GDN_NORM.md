# `STRATA_KVA_GDN_NORM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

KVA の既定の state-only 経路で GDN 層を処理するとき、出力正規化まで含む通常の GDN recurrence を実行する A/B 対照用のスイッチです。未設定または `atoi` の結果が 0 なら、出力正規化を行わない state-only recurrence を使います。いずれの場合も state-only KVA 層では GDN の出力投影、残差への書き戻し、MoE half は実行しません。そのためこの変数は KVA 自体を有効にする設定ではありません。

## 値と判定

値は `std::getenv()` で読み、`std::atoi(v) != 0` で判定します。文字列全体の検証や無効値の警告はありません。

| 値 | 判定 | 例 |
|---|---|---|
| 未設定 | 無効 | `getenv()` が null |
| 空文字 | 無効 | `atoi("")` は 0 |
| `atoi` が 0 を返す文字列 | 無効 | `0`, `0tail`, `true`, `false`, 数字で始まらない文字列 |
| `atoi` が 0 以外を返す文字列 | 有効 | `1`, `-1`, `+2`, `1tail`, `1.5` |

`atoi` は十進整数として読み、先頭の空白と符号を許し、数値の後ろに続く非数字部分を判定に含めません。従って `1tail` は有効ですが `true` は無効です。コードは境界値の clamp や範囲検査をしません。`int` で表せない数値文字列については `atoi` の結果を保証できません。CLI 引数・設定ファイル・別環境変数との優先順位、無効値からの fallback もありません。この変数を読むのは `prefill.cpp` のこの経路だけで、KVA の他設定とは別に評価されます。

## 有効になる条件

値が非ゼロでも、次のすべてが揃う場合だけ分岐に影響します。

- CUDA または HIP の state-only prefill 経路である。KVA backend 定義では CUDA/HIP は対応、Metal は非対応です。
- `STRATA_KVA` により KVA が有効で、その prefill が KVA の近似経路を実際に通る。
- 対象の late layer が GDN 層であり、その層が KVA 対象に選ばれている。
- `STRATA_KVA_SKIP=moe` の moe-only skip ではない。moe-only 経路は GDN 出力まで通常どおり実行するため、この変数は分岐に使われません。

KVA が無効、read が KVA 条件を満たさない、対象層が QSA、または moe-only skip の場合、この値はその実行の GDN 計算を変えません。KVA の条件には cold read、全 trunk、画像・DFlash2 taps がないこと、十分な prompt 長、モデル形状等があります（`include/strata/prefill/kva.hpp:104-133`）。

## 実行時の詳細

`Prefill::run_impl()` 内の GDN 処理が初めてこの分岐に到達したとき、関数内 `static const bool` の初期化で環境を読み、その値をプロセス内で再利用します。初期化後に環境を変更しても再評価されません。KVA 設定そのものも `kva_config()` が `static const` に一度 cache しますが、本変数はその設定 parser には含まれず、GDN 分岐で別に cache されます。

KVA state-only の GDN 層では、どちらの値でも QKV projection、alpha/beta projection、畳み込み、state 更新は行い、層出力から先は消費者がないため層の残差/MoE 処理を飛ばします。値による違いは以下です。

- **未設定または 0**: gate projection を省略し、`gdn_recurrence_state_only()` を呼びます。この関数は recurrence state を更新しますが、出力正規化は行わず、`z` と `gamma` を読みません。
- **非ゼロ**: gate projection を行い、通常の `gdn_recurrence()` を呼びます。これは `z` と `ssm_norm.weight` を使う出力正規化を含みますが、後続の GDN 出力投影は依然として省略されます。実装コメントでは state-only 経路との A/B control とされています。

HIP では fused conv+recurrence は `!kva_state_only` の場合に限り試みられます。従って state-only KVA ではこの変数が 0 でも非ゼロでも fused 経路に入らず、別々の conv と recurrence を実行します。通常 recurrence / state-only recurrence の選択箇所には、この変数専用のログや無効値エラーはありません。実行時には KVA の適用・不適用と近似位置数の一般ログが出ますが、そのログは本変数の判定値を表示しません。周辺の projection 等が失敗した場合は通常の prefill 失敗経路へ戻ります。

## 根拠

- 候補名の全参照は `docs/KVA.md:122`（設定表）、`src/prefill/prefill.cpp:3805-3809`（コメントと唯一の環境読み取り）にあります。`std::getenv` の結果を使う本番読み取りは後者のみです。
- KVA 設定の cache と KVA 経路の条件: `include/strata/prefill/kva.hpp:43-49,104-133,191-195`; `src/prefill/prefill.cpp:2947-2965,3619-3629`。
- GDN の gate projection、recurrence の選択、HIP fused path 条件、state-only 後の早期終了: `src/prefill/prefill.cpp:3792-3815,3817-3841`。
- state-only recurrence が `z` / `gamma` を使わないこと、および通常 recurrence の正規化付き実装呼び出し: `src/prefill/kernels.cu:3078-3106`。
- KVA の適用ログ: `src/prefill/prefill.cpp:5820-5842`; KVA が無効な場合の理由ログ: `src/prefill/prefill.cpp:5844-5856`。
- Strata の設定表は既定 off、非ゼロ設定で full GDN recurrence を維持する A/B control と記載しています（`docs/KVA.md:122`）。上記の効果と条件は当該 commit の実装分岐に基づきます。
