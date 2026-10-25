# `STRATA_PIPED_DECODE_MAX_MS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

層分割した GPU 上で `--batch-groups` によるパイプライン実行を行うとき、分割された prompt 読み込みの合間にバッチスロットが decode する時間の上限（ミリ秒）を指定します。読み込み片の所要時間に `STRATA_BATCH_DECODE_SHARE` を掛けた時間を基本予算とし、この変数が正の値ならその予算を上から制限します。読み込み片ごとに適用され、連続する読み込みの先行 decode 予算にも使われます。

## 値と判定

値は `std::getenv` で取得し、`std::atof` で変換した後、`std::max(0.0, value)` で負値を 0 にします。文字列全体の妥当性検証やエラー報告はありません。`atof` が数値として変換できない値（空文字を含む）は 0 となり、数値の後ろにある非数値部分は変換を妨げません。

| 入力 | `pr_cap` の値 | 効果 |
|---|---:|---|
| 未設定 | 0 ms | 上限を設けない |
| `0`、負値、空文字、数値に変換できない文字列 | 0 ms | 上限を設けない |
| 正の数値 | その数値（ms） | decode 予算をその値以下にする |

通常の片間 decode 予算では、上限は `STRATA_PIPED_DECODE_MIN_MS` による下限より先に適用されます。したがって、下限が上限より大きい場合は最終予算が上限を超え、下限が優先されます。直前に分割読み込みがない場合の最初の先行 decode は別計算で、上限が正ならその値をそのまま予算にします（この初回先行予算では下限を適用しません）。上限が 0 の場合は `max(下限, 200 ms)` です。

## 有効になる条件

環境変数を読み取るコード自体はバッチ読み込み処理にありますが、値が decode 予算へ反映されるのは、次の条件を満たす場合です。

- `--batch` が有効である。
- `--batch-groups` が 1 より大きく、層分割の stage がある（`piped` が true）。
- `STRATA_PIPED_READ_PIECE` が正の値であり、読み込みを複数片に分ける（`pr_on` が true）。
- その時点でバッチが稼働中である。稼働していなければ片のログを出して次の読み込み片へ進み、スロットの decode 予算を使いません。

`STRATA_PIPED_READ_PIECE` が未設定・0 以下なら読み込みはこの方式で分割されず、この上限は使われません。`--batch-groups 1` や層分割のない経路でも適用されません。

## 実行時の詳細

`STRATA_PIPED_DECODE_MAX_MS` は `generate.cpp` 内の関数ローカル `static const double` として初回評価時に一度読み取られます。その後プロセス内で環境を変更しても再評価されません。読み込み片の時間を `piece_ms`、`STRATA_BATCH_DECODE_SHARE` を `share`、本変数を `cap_ms`、`STRATA_PIPED_DECODE_MIN_MS` を `floor_ms` とすると、予算は次の順に計算されます。

1. `max(0, share) * max(0, piece_ms)` を求める。
2. `cap_ms > 0` なら、その値と `cap_ms` の小さい方にする。
3. `max(0, floor_ms)` 以上にする。

この予算の時間だけ `pump(true)` でパイプラインのスロットを進め、その後 `pipe_drain()` で処理中の stage を完了させてから次の prompt 読み込み片へ進みます。decode が失敗した場合は読み込み処理も失敗し、`a pipelined batch window failed` をエラーとして返します。

片の間にバッチが稼働していると、stderr に `strata batch: piped read ... then the slots decoded ...` の形式で読み込んだ token 数と decode 行数・時間を出します。`docs/BATCHING.md` は、この方式を長い読み込み中のスロット停止を減らすための選択肢として説明しています。

## 根拠

- `src/program/generate.cpp:11092-11095` — `piped` の成立条件（batch、複数 group、層分割 stage）。
- `src/program/generate.cpp:12739-12747` — `STRATA_BATCH_DECODE_SHARE` の既定値と読み込み時の static cache。
- `src/program/generate.cpp:13117-13138` — 分割読み込み opt-in と本変数の取得・変換、`pr_on` の条件。
- `src/program/generate.cpp:13140-13158,13164-13179,13181-13225` — decode 予算の適用、pump/drain、連続読み込み時の先行予算とログ。
- `include/strata/program/batch_read.hpp:69-76` — 予算の上限・下限の計算。
- `docs/BATCHING.md:287-315` — 機能の説明と運用上の位置づけ。記載された測定値は特定構成のものであり、本調査では再測定していません。
