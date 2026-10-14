# `STRATA_KQ_SPLIT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

SYCL 版の grouped expert カーネルで、対象の量子化形式に対する複数 entry の dot product カーネルを選びます。有効時は、1行の重みを複数 entry 分の活性値に使う multi-entry 経路を使います。無効時は entry ごとの lane カーネルを使います。設定を読む実装は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` にあり、CUDA/HIP の同名カーネルではありません。

## 値と判定

`std::getenv()` の結果と、その先頭文字だけで判定します。文字列全体の parse や数値変換はしません。

| 値 | 動作 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（設定値は存在するが、先頭文字は `0` ではない） |
| 先頭文字が `0` の文字列（例: `0`, `0abc`） | 無効 |
| それ以外の設定値（例: `1`, `true`, `false`, `abc`） | 有効 |

判定結果はグローバル変数 `g_kq_split` の初期化時に一度読み取られます。プロセス実行中に環境を書き換えても再評価されません。`native_expert_set_kq_split(bool)` は同じ変数を変更しますが、調査対象ソース内の呼び出しは `native_grouped_parity` の比較処理です。通常の実行経路からの呼び出しは見つかりませんでした。

## 有効になる条件

- Strata の SYCL ビルドで、`native_expert_grouped()` が使う grouped expert の lane カーネルに適用されます。`native_expert_grouped()` は gate/up と down の量子化形式に応じてカーネルを dispatch します。
- 分割カーネルが定義されている型に限られます。ソースの `KqSplit<TY>::has` が有効なのは Q4_K (type 12)、Q5_K (13)、Q6_K (14)、Q5_1 (7)、Q8_0 (8) です。それ以外はこの変数で切り替わりません。
- 対象型でも、1つの行で4 entry単位または2 entry単位にまとめられる分は multi-entry dot を使い、端数の entry は1つずつ処理します。無効時は対象型の multi-entry 経路を通さず、entry ごとの `row_dot_lanes()` に進みます。

## 実行時の詳細

有効時の `row_dot_ksplit()` は、各 lane が担当する重みブロックを一度 `load()` し、その重みデータをまとめた各 entry の活性値に `apply()` します。gate/up と down の launch wrapper は `g_kq_split` が false の場合に `KM=false` のカーネルを起動し、true の場合は通常の `KM=true` カーネルを起動します。値によって変わるのはこのカーネル経路です。

環境変数に関するログ、警告、エラー出力はこの読み取り処理にはありません。`docs/DETAILS.md` と `docs/` の検索範囲では、この変数そのものの説明やこの切替による性能測定値は確認できません。したがって性能差は記載しません。

## 根拠

- 読み取りと既定値: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4328-4330`。
- 対象型と分割 dot の実装: 同ファイル `1754-1912`。
- entry を4個・2個にまとめ、残りを個別処理する箇所: 同ファイル `1969-1996`。
- gate/up と down の lane kernel に設定を適用する箇所: 同ファイル `4331-4339,4364-4371`。
- grouped expert の gate/up・down dispatch: 同ファイル `5282-5285,5360-5365,5459-5465`。
- `native_expert_set_kq_split()` とテスト側からの呼び出し: 同ファイル `4451-4455`、`sycl/src/kernels/native_grouped_parity.cpp:431-440`。
- `native_expert_grouped()` の実行呼び出し: `sycl/src/core/verify.cpp:1433`、`sycl/src/core/remote_experts.cpp:431`。
