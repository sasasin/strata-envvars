# `STRATA_MMVQ_IL_SM80`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の interleaved small-batch matvec (`native_mmvq_il`) が compute capability 8.0（sm_80）で使う、アーキテクチャ別の行数テーブルを選ぶ既定値スイッチです。無効にすると sm_80 専用の `kIlRows_80` / `kIlRows58_80` / `kIl1Rows_80` を選ばず、通常の共有テーブル（または該当テーブルなし）に戻ります。この切り替えは行列演算の kernel 選択・rows-per-warp を変えます。Strata の資料は出力 bit は同じで速度だけが変わると説明しています。

## 値と判定

`sm80_default_on()` は文字列全体を parse せず、先頭文字だけを調べます。`STRATA_MMVQ_IL_SM80` は sm_80 のデバイス能力を初めて解決するときに評価されます。

| 値 | 判定 |
|---|---|
| 未設定 | `STRATA_DEFAULTS=026` が有効なら OFF、それ以外は ON |
| 先頭文字が `1` | ON。`1`, `10`, `1anything` など |
| 先頭文字が `0` | OFF。`0`, `0anything` など |
| 空文字 | `STRATA_DEFAULTS=026` が有効なら OFF、それ以外は ON |
| その他（例: `true`, `false`, 空白で始まる値） | 未設定と同じく、`STRATA_DEFAULTS=026` が有効なら OFF、それ以外は ON |

`STRATA_DEFAULTS` は値全体が `026`、`0.2.6`、`v0.2.6` のいずれかと完全一致する場合だけ有効です。対象変数の先頭 `1` または `0` は、この master switch より優先されます。たとえば `STRATA_DEFAULTS=026` と `STRATA_MMVQ_IL_SM80=1` の組み合わせなら ON です。

## 有効になる条件

- 対象の環境変数による選択変更は、CUDA 実装で現在のデバイスが compute capability 8.0 の場合だけです。ほかの compute capability の `cc` はこの分岐を通りません。
- HIP ビルドは interleaved 実装を持たず、`native_mmvq_il_supported()` は常に false を返し、呼び出しは `native_mmvq()` に fallback します。そのため、この変数で HIP の動作は変わりません。
- CUDA でも interleaved 経路の利用には `g_multi_exact`、対応 arch、1〜8 列、対応量子化 type（IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K）、および該当 shape の非ゼロ rows 選択が必要です。上位 caller では `STRATA_MMVQ_IL` が明示的に先頭 `0` でないことも条件です。条件が合わない場合は通常の `native_mmvq()` が使われます。
- `STRATA_MMVQ_IL_ROWS` に該当 type・列数の行設定がある場合、それがアーキテクチャ別テーブルより先に使われます。そのため、この変数で sm_80 の固有表を OFF にしても、同じ shape に対する明示的な rows override は残ります。
- sm_80 固有表でも shape ごとに値が 0 のセルは interleaved kernel を使わず、通常 kernel に fallback します。5〜8 列には `STRATA_MMVQ_IL_WIDE`、1 列には `STRATA_MMVQ_IL_T1`、Q3_K には `STRATA_MMVQ_IL_Q3K` による別条件もあります。

## 実行時の詳細

`il_cc()` は現在の CUDA device ordinal ごとに compute capability を `static` 配列へ保存します。能力値が 80 のときだけ `STRATA_MMVQ_IL_SM80` と `qwen_defaults_026()` を `sm80_default_on()` に渡し、OFF 判定なら保存値を 81 に置き換えます。後段の表検索では cc 81 は sm_80 固有表に一致しないため、2〜4 列は共有表、5〜8 列は専用表なし、1 列は専用表なしとなります。ON の場合は cc 80 の固有表が検索対象になります。

`il_cc()` の値は device ordinal ごとに一度保存されるため、対象環境変数の判定も各 device の能力解決時です。`STRATA_DEFAULTS` 自体は `qwen_defaults_026()` の function-local `static` に一度保存されます。初回評価後にプロセス環境を書き換えても、既に保存された cc や master switch の判定には反映されません。

表から選ばれた rows が非ゼロなら `native_mmvq_il()` が該当 kernel を launch し、0 またはほかの条件不成立なら `native_mmvq()` に委譲します。この変数について専用の警告・状態ログ・終了経路は見つかりませんでした。CUDA device 属性の取得に失敗した場合は `il_cc()` が 0 を返し、利用可能な専用表が選ばれない方向に進みます。

## 根拠

- 候補名の実際の読み取りと sm_80 判定: `src/kernels/cuda/native_mmvq.cu:3863-3883`。リポジトリ全体の完全一致検索では、候補名の `getenv()` はここだけです。ほかの出現はコメントや文書です。
- 先頭文字による値判定: `include/strata/core/sm120_series.hpp:87-93`。
- `STRATA_DEFAULTS` の完全一致判定と static cache: `include/strata/core/defaults_026.hpp:21-29`。
- 共有表・architecture 表の選択、行数 0 の扱い、列数・量子化 type の条件: `src/kernels/cuda/native_mmvq.cu:3608-3613,3829-3860`。
- CUDA interleaved 経路の利用条件と通常 kernel への fallback: `src/kernels/cuda/native_mmvq.cu:3930-3957`。HIP stub: `src/kernels/cuda/native_mmvq.cu:3960-3976`。
- engine 側の `STRATA_MMVQ_IL` 判定と通常経路への分岐例: `src/core/verify.cpp:173-175,1495-1517,1791-1798,2452-2463`。
- ソース内コメントは sm_80 専用表を CMP 170HX で測定し bitwise equality を確認したと記しています（`src/kernels/cuda/native_mmvq.cu:3681-3689`）。`docs/DETAILS.md:1524-1533` は同じ CMP 170HX（GA100、70 SMs）での測定として decode +2.7〜+3.2% と記載します。これは文書に記された当該カードでの値で、他の sm_80 GPU の速度を保証しません。設計資料 `docs/MMVQ_IL_TABLE.md:3-21` も sm_80 ではこの変数または `STRATA_DEFAULTS=026` で共有表へ戻ると説明しています。
