# `STRATA_PIPE_ADAPT_EVERY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

複数 GPU の layer split で `--serve` と `--batch-groups` 2以上を使うパイプライン経路において、適応 VRAM expert tier の swap round を何 group window ごとに開始するかを指定します。未設定時は、このパイプライン経路は独自の round を開始しません。正値を設定すると、指定数の group window が完了した後に新しい group の開始を止め、進行中の group を完了させてから一度 round を実行します。

この変数は適応 tier 自体を有効にしません。`--adapt-every` と `--adapt-swaps` が正で、モデル全体が VRAM 常駐ではないなど、Strata の既存適応 tier が利用可能なことが必要です。`--adapt-async 1` を使う場合、この変数による blocking round は行いません。

## 値と判定

値は `std::getenv()` で取得し、共通 helper が `std::atoi()` で変換します。変換結果が正の場合だけその整数を interval として使い、それ以外は無効（0）です。文字列全体の妥当性検査や警告はありません。

| 環境値 | 判定 |
| --- | --- |
| 未設定 | 0（無効） |
| 空文字 | `atoi` 結果 0（無効） |
| `0`、負数、数字で始まらない文字列 | 0 以下または 0（無効） |
| 正の整数文字列（例: `8`, `+8`, ` 8`) | その正の整数を group window interval にする |
| 数字の後ろに文字が続く文字列（例: `8x`) | `atoi` が先頭の整数を変換するため interval 8 |

範囲外の値を `int` に変換した場合の結果は、この実装で保証されません。値を読むときに CLI 引数や設定ファイルで上書きする処理はありません。`--adapt-every` は環境変数の値を置き換える指定ではなく、適応 tier が動作可能かを決める別の条件です。

## 有効になる条件

実際に round が開始されるには、すべての条件が揃う必要があります。

- serve の batch 経路が複数 GPU の layer split 上でパイプライン実行されること（`--batch` が正、`--batch-groups` が2以上、stage 数が1以上）。
- 変換後の interval が正であること。
- 適応 tier の usage table が存在すること。Strata は `--adapt-every > 0`、`--adapt-swaps > 0`、かつ全 expert が VRAM 常駐でない場合に usage table を作ります。
- `--adapt-async 1` が動作中でないこと。
- prompt read が slot と並行していないこと。
- 前の round の swap copy が pending でないこと。
- interval 以上の group window が前回の round 以後に完了していること。

prompt read 中は round を延期します。適応 tier が無効な場合、値が正でも round は実行されません。開始時の案内ログは `--serve`、`--batch > 0`、`--batch-groups > 1`、複数 GPU の条件で正値を検出したときに出ますが、適応 tier が無効なら `- but the adaptive tier is off` が付きます。

## 実行時の詳細

環境変数は Strata の起動処理で一度、適用条件付きの案内ログ用に読み、パイプライン loop の初期化時にもう一度読みます。helper は値を static cache しません。loop 内の値は request ごとではなく、そのパイプライン loop の間使われます。

完了した group window ごとに counter が増えます。round が due になると stage 0 に次の group を割り当てず、すでに in-flight の group を進めます。pipeline が空になった時点で `adapt()` を呼び、適応 tier の usage と residency をもとに候補 expert と退避 expert を選びます。差が `--adapt-min-gain` 未満の swap は除外され、round あたりの swap 数は `--adapt-swaps` で制限されます。copy の完了と residency table 更新を待ってから次の launch に進みます。round 後に interval counter の基準を更新し、次の周期を数えます。

観測できる出力:

- 起動時 stderr: `strata batch: STRATA_PIPE_ADAPT_EVERY=N: ...`。適応 tier が無効なら上記の補足が付きます。
- pipelined batch の stderr 集計: `adaptive tier (STRATA_PIPE_ADAPT_EVERY): ... rounds, ... experts swapped in, ... ms`。この集計は batch の処理区間が終了した時に出ます。
- adaptive refill が失敗すると stdout に `ERR an adaptive refill failed` を出して pipelined 処理が失敗し、serve loop は終了コード 1 を返します。

## 根拠

- 値変換: `include/strata/program/batch_groups.hpp:24-30`。周期成立条件: `include/strata/program/batch_groups.hpp:32-45`。
- 起動時の条件付き読み取りと案内ログ: `src/program/generate.cpp:9064-9071`。
- 適応 tier が有効な場合の usage table 作成: `src/program/generate.cpp:11181-11182`。
- パイプライン条件、2回目の読み取り、runtime の due 判定入力: `src/program/generate.cpp:13012-13016,13223-13243`。
- window の完了計数と due の間は stage 0 の新 group を止める処理: `src/program/generate.cpp:13332-13335,13338-13350`。
- pipeline drain 後の round、失敗出力、swap 適用、集計: `src/program/generate.cpp:13437-13448,13461-13471`。
- swap 選定と上限: `src/program/generate.cpp:11455-11481`。
- 既存資料の説明と測定条件: `docs/BATCHING.md:389-425`。2x RTX 5090、記載のモデル・設定・負荷に限定された rows/s 測定であり、ここでは再測定していません。
