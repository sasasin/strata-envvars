# `STRATA_DS4_A_MB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 専用実行ファイル `strata-dsv41` の chunked prompt path で、GPU ごとの attention slab の基準サイズ（Q buffer の MiB 数）を指定します。未設定なら統合 GPU は通常 32 MiB、離散 GPU は 8 MiB が基準です。値を設定すると GPU 種別にかかわらずその MiB 数が基準になります。これは slab の行数を直接指定する `DS4_ATTN_SLAB` とは単位も役割も異なります。

## 値と判定

読み取りは `std::atoi` による整数変換です。未設定だけが「自動基準」を表す 0 sentinel になります。設定時は変換結果を最低 1 にしてから `size_t` にします。

| 環境変数の状態・値 | `a_mb_env` | 基準サイズへの効果 |
|---|---:|---|
| 未設定 | 0 | `DS4_DEFAULTS=026` のとき 8 MiB。それ以外は統合 GPU 32 MiB、離散 GPU 8 MiB |
| 空文字、数値に変換できない文字列、`0`、負数 | 1 | 1 MiB。設定値として扱われる |
| 正の整数 | その整数 | その MiB 数。GPU 種別や `DS4_DEFAULTS=026` による基準値を置き換える |
| 数字で始まる文字列（例 `16MiB`、`12.5`） | `atoi` が読む先頭の整数（例 16、12） | その MiB 数。文字列全体の検証はしない |

空白と符号は `atoi` の規則に従います。`atoi` で `int` の範囲を超える文字列を渡した場合の結果は、この実装では範囲検証されず、移植可能な値として保証されません。

MiB 基準から行数 `c.A` を作る際は、各 GPU の attention head 幅 `HQ` で割り、64 行単位で切り下げ、最低 64 行にします。したがって基準 MiB 数はそのまま確保量を厳密に保証する値ではありません。`DS4_ATTN_SLAB` が有効な場合は、その後に slab 行数を別途選びます。

根拠: `src/dsv41/ds4_model.cu:3322-3332`, `src/dsv41/ds4_experts_rule.hpp:167-172`。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` でビルドされる `strata-dsv41` のコードです。この CMake オプションは既定 OFF で、同ターゲットに `src/dsv41/ds4_model.cu` が含まれます。既存の汎用 `strata` 実行ファイル全体に適用される設定ではありません（`CMakeLists.txt:906-920`）。
- モデル load 中に chunked prompt path が有効で `chunk > 0` の場合に slab バッファを確保します。`--prefill-chunk 0` は windowed path を選び、この環境変数による slab 設定を使いません。`--prefill-chunk N` は chunk サイズの指定であり、MiB 基準を上書きしません（`src/dsv41/ds4_model.cu:2224-2232,2293-2305,2945-2956`）。
- GPU ごとに `cudaGetDeviceProperties` の `integrated` を調べ、未設定時の既定基準を選びます。`STRATA_DS4_A_MB` が設定されている場合は、統合 GPU / 離散 GPU のどちらにも同じ MiB 値を使います（`src/dsv41/ds4_model.cu:3322-3332`）。
- `DS4_DEFAULTS=026` は未設定時の基準を 8 MiB にしますが、`STRATA_DS4_A_MB` の明示値には勝ちません。`DS4_DEFAULTS` は完全一致で `026` / `0.2.6` / `v0.2.6` のみを認識します（`src/dsv41/ds4_experts_rule.hpp:16-27,169-172`）。
- `DS4_ATTN_SLAB` が明示設定されていれば、MiB 基準から得た行数より後段で優先されます。未設定の場合は、統合 GPU または `STRATA_DS4_A_MB` 指定時に自動拡大を抑え、基準行数を使います。明示した `DS4_ATTN_SLAB` はこの抑制条件の対象外です（`src/dsv41/ds4_model.cu:3333-3354`）。

## 実行時の詳細

値は `alloc_chunks()` 内の関数ローカル `static const size_t` として読み込まれます。初回の slab 計算で一度だけ評価され、プロセス中の後続 GPU や Model load でも同じ値を使います。起動後の環境変更は反映されません。これは設定値の cache であり、プロセス起動時に必ず読むわけではなく、chunked prompt の slab 計算に到達した時点で初めて読みます（`src/dsv41/ds4_model.cu:3301-3303,3327-3332`）。

この値は `c.A` を介して `c.q`, `c.o`, `c.o16`, `c.oa`, `c.oa16` の GPU buffer サイズに使われます。大きな slab はこれらの確保量を増やします（`src/dsv41/ds4_model.cu:3379-3399`）。通常、基準 MiB 値自体を出すログはありません。自動行数拡大が行われた場合は `--verbose` 時に `ds4: attention slab ... (automatic: ...)` を stderr に出しますが、環境変数指定時は未設定時の自動拡大を抑えるため、このログ経路には入りません（`src/dsv41/ds4_model.cu:3355-3364`）。

確保失敗時にこの環境変数の値そのものを縮小する処理はありません。GPU buffer 確保失敗は `cudaMalloc ... failed` として記録されます。自動 slab 拡大が原因の再試行では基準 slab に戻す処理がありますが、この環境変数指定時は自動拡大扱いになりません。その後は prompt chunk を縮小し、最後は chunked path を止めて windowed prompt に fallback します。fallback 後もモデル load 自体が失敗する場合は `maya-ds4: <error>` を stderr に出して終了コード 1 になります（`src/dsv41/ds4_model.cu:1531-1537,2945-2999`; `src/dsv41/ds4_main.cpp:1402-1407`）。

## 根拠

- 候補名の全参照を Strata リポジトリで検索し、実読み取りは `src/dsv41/ds4_model.cu:3327-3330` の一か所と確認しました。他の候補名参照は実装コメントと `tests/dsv41/experts_rule_test.cpp:242-247` のテストです。
- 基準サイズ選択と行数換算: `src/dsv41/ds4_model.cu:3322-3332`; helper `src/dsv41/ds4_experts_rule.hpp:167-172`。
- 別環境変数との関係および適応行数: `src/dsv41/ds4_model.cu:3333-3364`; helper `src/dsv41/ds4_experts_rule.hpp:102-130`。
- ビルド対象と実行経路: `CMakeLists.txt:906-920`, `src/dsv41/ds4_main.cpp:1395-1410`。
- 確保と失敗時の処理: `src/dsv41/ds4_model.cu:1531-1549,2945-2999,3379-3400`。

