# `STRATA_P4_TIMING`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

layer-split の grouped batch pipeline における host 側の時間配分を計測し、集計を stderr に出す診断用スイッチです。window の launch-to-done、launch cycle、done 後の gap、stage の busy share、launch cost、pump の tick cost、最終 stage の verdict work、in-flight group 数、stage が group 待ちで idle か前段待ちで starved かを集計します。モデル計算や pipeline のスケジューリングを切り替える設定ではありません。実装は `include/strata/program/pipe_probe.hpp` の `PipeProbe` で、`src/program/generate.cpp` の piped batch loop から使われます。

## 値と判定

| 環境変数の状態 | `timing_` | 判定 |
|---|---:|---|
| 未設定 | false | 計測しない |
| 空文字を含む、何らかの値が設定済み | true | 計測する |

実装は `std::getenv("STRATA_P4_TIMING") != nullptr` だけを判定し、内容を parse しません。したがって `1` だけでなく `0`、`false`、任意の文字列、空文字も有効です。数値変換、範囲、無効値 fallback はありません。CLI 引数や他の環境変数による上書きもありません。`STRATA_P4_TRACE` は別の計測出力を制御し、`PipeProbe::on()` を通じて時計読み取りなどの共通 hook を有効にしますが、`timing_` の真偽や timing 集計出力を変更しません。

## 有効になる条件

- 実際に集計されるのは `--batch` が正数、`--batch-groups` が 1 より大きく、layer split の stage 数が 1 以上である grouped pipeline 経路です。コード上の条件は `piped = o.batch > 0 && o.batch_groups > 1 && n_pipe > 1` です。
- `PipeProbe` 自体はこの batch loop の共通セットアップで生成されますが、計測 hook を呼ぶ `pump()` は piped 経路で使われます。`--batch-groups 1` や layer split なしでは、この grouped pipeline の timing 集計は行われません。
- OS や GPU backend、build macro による `STRATA_P4_TIMING` 固有の値判定分岐はありません。`strata` 実行ファイルに `src/program/generate.cpp` が組み込まれています。
- `STRATA_P4_TRACE` が設定されていれば trace file が開けなくても timing の値判定自体は独立しています。trace が開けない場合に出る警告は `STRATA_P4_TRACE` の処理であり、この変数による警告ではありません。

## 実行時の詳細

`PipeProbe` のコンストラクターで環境を一度読み `timing_` に保持します。プロセス内で後から環境を変更しても、既に生成された probe には反映されません。設定値は batch loop 内の `PipeProbe` インスタンスごとに読み取られます（static cache ではありません）。起動時に設定した値は通常のプロセス環境として engine に渡される必要がありますが、Strata ソース内にこの変数を子プロセスへ個別転送する処理はありません。

`timing_` が true のとき、pump ごとに active stage と in-flight group を数え、stage の空き状態を記録します。window の完了・launch、poll、最終 stage の verdict work も集計します。各 group が完了し batch が idle になると、通常の `strata batch (pipelined, ...)` summary に続けて `strata p4:` で始まる集計行を stderr に出し、カウンターを reset します。出力は集計値であり GPU kernel occupancy の計測とは記述されていません。

この変数について、Strata 固有のエラー・警告・終了経路はありません。pipeline の `batch_poll` 失敗などは通常経路の `ERR ...` 処理です。`docs/BATCHING.md` は grouped pipeline の動作を説明していますが、この変数の計測値や性能向上を記載していないため、ここでは性能効果を主張しません。

## 根拠

- 値の取得と判定、`on()` / `timing()`、clock hook、計測 counters、stderr 出力と reset: `include/strata/program/pipe_probe.hpp:24-48,50-68,70-128`。
- executable の構成: `CMakeLists.txt:868-871`。
- grouped pipeline の条件、probe 生成、pump 内計測: `src/program/generate.cpp:13012-13016,13245-13263`。
- group の進行と完了時 summary / `p4.flush()` の呼び出し: `src/program/generate.cpp:13271-13288,13459-13485`。
- CLI の `--batch` / `--batch-groups` と layer-split pipeline の説明: `docs/BATCHING.md:90-97`。
- ソース全体検索では、実装上の `std::getenv` 読み取りは `include/strata/program/pipe_probe.hpp:33` の一箇所です。その他は説明コメント、CPU-only test、または `tools/par/variants/cnt_2g.txt` の計測用 variant 指定であり、追加の本番読み取り箇所ではありません。
