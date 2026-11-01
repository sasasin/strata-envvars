# `STRATA_MMVQ_IL_PF`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の interleaved small-batch matvec (`native_mmvq_il`) で、hoisted-load カーネルの variant を選びます。`=1` は sm_80 用の測定済み variant/rows テーブルを参照し、`=2`〜`=6` は指定 variant を使います。変わるのはカーネル選択です。Strata の資料と実装コメントは各 variant の出力が通常カーネルと bitwise 同じとしていますが、ここでは実行時測定を行っていません。

## 値と判定

CUDA 実装は環境値を `std::atoi` で整数にし、結果をキャッシュします。文字列全体の検証はありません。空文字と数値に変換できない文字列は `0` になり、先頭の空白や符号、整数の後ろの文字列は `atoi` の変換規則に従います（例: `1abc` は `1`）。

| 環境値の `atoi` 結果 | 選択 |
|---|---|
| unset、空文字、`0`、`0abc`、数値に変換できない文字列 | `0`。通常の interleaved kernel。unset の既定も `0`。 |
| `1` | sm_80 テーブルから variant と rows を取得。対象外の GPU、型、列数、テーブルセルでは `0` 相当となり、通常の interleaved kernel。 |
| `2`〜`6` | 対応する hoisted-load variant を指定。ただし interleaved 経路が先に有効になり、型 trait が variant を持つ場合に限る。 |
| その他（負数を含む） | variant switch に該当せず、通常の interleaved kernel。 |

`2`〜`6` の対応は `2`: ring + exact integer、`3`: hoisted loads + exact integer、`4`: variant 3 の 5 blocks/SM 版、`5`: variant 4 の ring 版、`6`: hoisted loads（exact integer なし）です。環境値の判定自体は警告やエラーを出しません。根拠: `src/kernels/cuda/native_mmvq.cu:2004-2006,2207-2223,2224-2239`。

## 有効になる条件

この環境変数の読み取り・適用箇所は CUDA 側だけです。HIP 側は interleaved 経路を使わず、`native_mmvq_il` は通常の `native_mmvq` に転送し、variant 設定関数も空実装です（`src/kernels/cuda/native_mmvq.cu:3930-3958,3960-3976`）。この変数を読む Metal、SYCL、Python サーバー、CLI 起動処理は見つかりませんでした。

CUDA でも、次の条件が成立して `native_mmvq_il` の launch に到達した場合に限り、PF variant が選択されます。

- `STRATA_MMVQ_IL` が無効化していない。verify 側では未設定または先頭文字が `0` でない値が ON で、`0...` は OFF（`src/core/verify.cpp:169-175`）。
- `g_multi_exact` が有効で、GPU の compute capability が対応し、型が IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K のいずれかである。さらに `native_mmvq_il_supported` が選んだ rows が 0 でない。条件を満たさない呼び出しは verify 側またはカーネル API 側で通常の `native_mmvq` に進みます（`src/kernels/cuda/native_mmvq.cu:3929-3943`; 呼び出し側 `src/core/verify.cpp:1508-1517,1551-1560,1791-1798,2452-2464`）。
- `=1` の PF テーブルは compute capability 8.0、2〜8列だけを対象とし、現行表にある型は Q6_K のみです。sm_80 以外ではテーブル検索が 0 を返します。`STRATA_MMVQ_IL_SM80=0`（または `STRATA_DEFAULTS=026` による同等の既定切り替え）が sm_80 を共有テーブル扱いにすると、PF テーブルのキー 80 から外れるため `=1` は適用されません（`src/kernels/cuda/native_mmvq.cu:3681-3703,3877-3879,3884-3895`）。
- `=2`〜`=6` は compute capability 8.0 の PF テーブルを必要としませんが、上記の interleaved 対応・rows 条件は残ります。また各型の `HAS_PF` が false なら variant switch を通らず通常の interleaved kernel です（`src/kernels/cuda/native_mmvq.cu:1642,1710,1798,1895,1952,2224-2239`）。

したがって `=2`〜`=6` は、rows table が 0 のため interleaved 経路に入らない型・形状まで強制的に有効化するスイッチではありません。`=1` も全 GPU・全型で PF kernel を有効化する値ではありません。

## 実行時の詳細

PF 値は `il_pf_env()` が最初に呼ばれたときの `static const int` に保存されます。これは `native_mmvq_il` の呼び出し後、対応する `launch_il_rows` に到達して初めて評価されるため、プロセス起動時に必ず読むとは限りません。その後に環境を変更しても再評価されません。内部テスト・ベンチマーク用 API `native_mmvq_il_pf(int)` が `g_il_pf` を 0 以上に設定した場合は、環境値よりそちらを優先します。`mmvq_il_parity --pf ...` はこの API で上書きしますが、Strata の通常実行 CLI に `--pf` オプションはありません（`include/strata/kernels/native_mmvq.hpp:174-178`; `src/kernels/mmvq_il_parity.cpp:223-229,245-257,470-488`）。

`=1` は sm_80 の表から variant と rows を選びます。表のセルは `variant << 4 | rows` で、テーブルがないセルは 0 です。`=2`〜`=6` は PF variant を指定しますが、rows は通常の interleaved rows 選択を使います。variant を含む条件に該当しない場合、`launch_il_one` は `native_mmvq_il_kernel` を起動します（`src/kernels/cuda/native_mmvq.cu:2212-2239,2264-2274,3690-3703,3884-3895`）。

この環境変数を理由とする Strata のログ、警告、終了経路はありません。未対応経路は通常の matvec に fallback します。interleaved API で不正な列数なら `std::invalid_argument`、CUDA kernel の launch 検査失敗なら `launch_check()` のエラー経路がありますが、PF 値そのものの検証エラーではありません（`src/kernels/cuda/native_mmvq.cu:2252-2261,3936-3958`）。

## 資料との照合

`docs/MMVQ_IL_TABLE.md:40-53` は sm_80 のテーブルが Q6_K のみであること、unset/0 が通常 kernel、2〜6 が variant 固定であることを説明しています。`docs/DETAILS.md:1524-1533` は CMP 170HX (sm_80) での報告値として decode +1.4% を記載し、測定主体が変更作者で Strata 側では未測定と明記しています。この数値は資料記載の測定結果であり、この調査で再測定したものではありません。

資料の「2〜6 は everywhere」という表現は、カーネル variant 選択についての説明です。実装上は interleaved 経路が有効な型・形状が前提であり、この変数だけでその経路を有効化するわけではありません。

## 根拠

- 環境値の取得、`atoi`、キャッシュ、variant 分岐: `src/kernels/cuda/native_mmvq.cu:2207-2239`
- PF kernel variant 定義と `HAS_PF`: `src/kernels/cuda/native_mmvq.cu:1642-2006,2224-2239`
- PF テーブルと sm_80 条件: `src/kernels/cuda/native_mmvq.cu:3681-3703,3877-3895`
- interleaved 対応条件と fallback: `src/kernels/cuda/native_mmvq.cu:3929-3958,3960-3976`; `src/core/verify.cpp:1508-1517,1551-1560,1791-1798,2452-2464`
- テスト・ベンチマークからの override: `include/strata/kernels/native_mmvq.hpp:174-178`; `src/kernels/mmvq_il_parity.cpp:223-229,245-257,470-488`
- 設計・測定資料: `docs/MMVQ_IL_TABLE.md:40-53`; `docs/DETAILS.md:1524-1533`
