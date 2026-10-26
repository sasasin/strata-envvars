# `DS4_AHEAD_EXTRA`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 の非同期 decode で使う router lookahead のうち、直後の layer について先読みする expert 数を調整します。通常の top-k 数 `k_exp` にこの値を足し、次 layer の routing 候補を何個予測するか決めます。予測は CPU lane の expert 読み出しを先に要求するためのもので、実際の routing 結果や expert の計算対象は変えません。

## 値と判定

値は `std::getenv()` で取得し、設定されていれば `std::atoi()` で整数に変換します。未設定は `0` です。空文字や数値で始まらない文字列も `atoi` の結果は `0` になります。先頭の空白と符号は変換対象になり、数値の後ろに文字があっても数値部分を読みます（例: `"  -2tail"` は `-2`）。文字列全体の検証はしません。

| `DS4_AHEAD_EXTRA` | 直後の layer で予測する個数 `m` |
|---|---|
| 未設定、空文字、数値として読めない値 | `k_exp` を 1〜16 に収めた数 |
| 正の整数 | `k_exp + 値` を 1〜16 に収めた数。最大 16 個まで予測 |
| 負の整数 | `k_exp + 値` を 1〜16 に収めた数。少なくとも 1 個は予測 |

実装式は `max(1, min(16, next_layer.k_exp + ahead_extra))` です。`kAhead1` は 16 です。したがって値を大きくしても予測数は 16 を超えず、負値でも lookahead 自体は無効になりません。2 layer 先の予測数はこの変数を使わず、別の固定式で決まります。

## 有効になる条件

- DSV4.1 の非同期 decode 経路で、`ahead_mode > 0` の場合にだけ lookahead の予測と先読みが行われます。`DS4_AHEAD` は未設定時 `1`、設定時は `atoi` の値です。通常は `DS4_AHEAD=0` で lookahead が止まり、正の値で有効になります。
- ただし RAM store の初期化が成立した場合、`DS4_AHEAD` が未設定ならコードが `ahead_mode` を `0` に変更します。store を使う場合に lookahead を有効にするには `DS4_AHEAD` を明示し、その値が正である必要があります。
- 次 layer が存在し、同じ device と MTP/non-MTP 区分に属し、MXFP4 形式で、gate weights があり、expert 数が 1024 以下で、slot 配列が揃い、その layer に file read 対象の expert が少なくとも一つある場合にだけ、その layer の予測を作ります。対象条件を満たさない layer では `DS4_AHEAD_EXTRA` の値は使われません。
- 2 layer 先の予測では `min(8, k_exp)` 個を使うため、この変数は直後の layer の予測幅だけに作用します。

## 実行時の詳細

値は `Model::Impl` のメンバー初期化時に読み込まれます。実行中にプロセス環境を書き換えても、このモデルインスタンスで再読込されません。

各 layer の非同期 routing で、GPU は現在 layer の FFN 入力に次 layer の gate weights を適用し、`k_exp + DS4_AHEAD_EXTRA` を clamp した数の候補を予測して request に格納します。CPU lane が request を処理すると、予測された expert のうち file read 対象のものを先読みします。RAM store がある経路では `store->prefetch()` に渡します。この関数は未キャッシュ・未処理の expert の読み込みを開始し、その要求は未 pin のため使用前に破棄される場合があります。それ以外の経路では expert の3つの MXFP4 データ範囲を background prefetch thread に渡します。lookahead の統計は stderr に `lookahead: ...` で出力されますが、`DS4_AHEAD_EXTRA` 専用のログはありません。

関連資料 `docs/DETAILS.md` と `docs/DEEPSEEK41.md` には、この変数の説明や測定条件を確認できませんでした。性能向上の値は記載していません。

## 根拠

- `src/dsv41/ds4_model.cu:988-1000`: lookahead の説明、`DS4_AHEAD` と `DS4_AHEAD_EXTRA` の既定値、メンバー値の読み取り。
- `src/dsv41/ds4_model.cu:2785-2793`: lookahead 用配列と prefetch thread の初期化条件。
- `src/dsv41/ds4_model.cu:4633-4636,4710-4718`: RAM store の初期化条件と、store 使用時に `DS4_AHEAD` 未設定なら lookahead を無効にする処理。
- `src/dsv41/ds4_model.cu:6394-6409`: 先読み可能な次 layer と file read expert の条件。
- `src/dsv41/ds4_model.cu:6411-6446`: 予測の受け取り、対象 expert の選別、prefetch 要求の発行。
- `src/dsv41/ds4_store.hpp:212-218`: RAM store が推測先読みを開始し、未 pin の要求を扱う実装。
- `src/dsv41/ds4_model.cu:9051-9072`: 非同期 routing 中の予測処理、個数の計算、実際の routing request への格納。
- `src/dsv41/ds4_kernels.cuh:18-19,216-240`: expert 数上限 `kPicks` と lookahead 配列の容量 `kAhead1=16`。
- `src/dsv41/ds4_main.cpp:1483-1501`: stderr に出る lookahead 統計。
