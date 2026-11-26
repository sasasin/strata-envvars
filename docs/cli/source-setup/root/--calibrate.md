# `--calibrate`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.sh` / `START-HERE.bat`（`terminal/setup.py`） |
| オプション | `--calibrate` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる（`terminal/setup.py:11553-11554`）。 |

## 役割

既にインストール済みの対応モデルを、この PC のハードウェアで測定し、設定を調整してからモデルを起動する。`--no-start` を併用すれば測定・保存後に起動しない。調整対象の設定は PCIe 転送比率、投機デコードの下限、CPU worker 数、適応型 expert tier などで、layer split がある場合は prompt chunk 数も測定する（`terminal/setup.py:8217-8226`、`terminal/tools/calibrate.py:327-423`）。

## 使い方

Strata の source checkout のルートで実行する。

```sh
./setup.sh --calibrate
./setup.sh --calibrate --family qwen --no-start
```

Windows では `START-HERE.bat --calibrate` を使う。`--model` または `--family` を省略すると対象モデルから選択する。モデルを指定した場合はそのモデル、family を指定した場合はその family が対象となる。両方を指定した場合は両方に一致する config が選ばれる（`terminal/setup.py:7835-7847`、`terminal/setup.py:11740-11758`）。

## 値と既定値

値を受け取らず、既定値は無効（未指定）である。`argparse` の `store_true` で定義されているため、引数値や空値を付ける形式ではない（`terminal/setup.py:11553-11554`）。

## 実行時の動作

通常はインストール済み config を対象に較正を実行する。モデル/family の指定がない場合、`OWN_PATH_FAMILIES`、`HY4_FAMILIES`、`INKLING_FAMILIES` に属する config は対象から除外される。指定がある場合も同じ family 群は除外される（`terminal/setup.py:7835-7847`）。複数候補が残ると一覧を表示し、どれを測るか尋ねる（`terminal/setup.py:11416`、`terminal/setup.py:11748-11753`）。

較正はモデルをロードして複数の設定候補を測定する。PCIe 比率と draft floor は各候補を3巡して比較し、候補が既定値を上回る場合は既定値と候補を交互に再測定する。CPU worker 数と expert tier は候補ごとにエンジンを再起動して比較する。layer split がある場合は prompt chunk も測定し、HIP では `STRATA_SH_STREAM` の値も比較する（`terminal/tools/calibrate.py:56-72`、`terminal/tools/calibrate.py:327-423`、`terminal/tools/calibrate.py:431-458`）。通常の候補は既定より `MIN_GAIN`（3%）を超えて優位な場合に採用する。prompt chunk はさらに3回の確認すべてで既定を上回る必要がある（`terminal/tools/calibrate.py:154-190`、`terminal/tools/calibrate.py:193-199`）。設定ごとの適用値は `calibrate.apply()` が作り、以前の較正値が今回選ばれなかった場合も製品既定に戻す（`terminal/tools/calibrate.py:526-536`）。

成功すると測定値を run config の `args`（HIP で選ばれた環境変数は `env`）に反映して書き換え、GPU/CPU/RAM とモデル条件などから作る hardware key に対応する較正記録を settings ファイルへ保存する。次回の更新・再セットアップで再利用される（`terminal/setup.py:8186-8197`、`terminal/setup.py:8217-8255`）。設定ファイルは一時ファイルへ書いてから置換する（`terminal/setup.py:7531-7537`）。較正後は通常モデルを起動し、`--no-start` 指定時は起動せず終了する（`terminal/setup.py:11754-11759`）。

## 適用条件と副作用

- `--setup` または `--check` と併用した場合、または未インストール状態では、このオプションは較正を行わず警告を出す。併用された他の操作は通常の処理に進む（`terminal/setup.py:11730-11734`）。
- Apple Silicon で通常の Metal setup 経路に入る場合、委譲先 parser は `--calibrate` を受け取らず、未知引数として「not used on a Mac」と警告して処理を続ける。したがってこの経路では較正されない（`terminal/setup.py:11434-11437`、`engine/metal/setup_mac.py:375-405`）。
- 条件に合うインストール済み config がない場合は、インストール済みモデル名を表示して終了コード1で失敗する（`terminal/setup.py:11740-11745`、`terminal/setup.py:1049-1056`）。
- HIP かつ Windows で KV streaming (`--kv-resident`) を使う場合は、既知のエンジン失敗条件を避けるため `STRATA_SH_STREAM` の比較をスキップする（`terminal/tools/calibrate.py:431-440`）。
- 測定中はモデルエンジンを複数回起動し、PC の計算資源を使用する。所要時間はソースの案内で概ね15〜30分（低速 GPU ではさらに長い）（`terminal/setup.py:11553-11554`、`terminal/setup.py:8223-8226`）。
- 設定保存先の run config と settings ファイルを更新する。較正結果の settings 保存に失敗した場合は警告を出すが、`save_settings()` はその `OSError` を捕捉する（`terminal/setup.py:7531-7537`、`terminal/setup.py:7299-7307`）。

## 出力とエラー

測定中は「Loading the model for the measurements ...」や設定ごとの tok/s を標準出力へ表示し、完了時に採用した値または既定値が最速だった旨を表示する（`terminal/tools/calibrate.py:327-339`、`terminal/tools/calibrate.py:484-505`、`terminal/setup.py:8248-8255`、`terminal/setup.py:997-999`）。`--output jsonl` を併用する場合、人向け出力は標準エラーへ送られ、イベント JSON は標準出力に残る（`terminal/setup.py:961-980`）。測定全体で例外が発生すると警告とログのエラー行を表示し、今回の較正結果を run config に書かずに戻る。その後、`--no-start` がなければ既存 run config の設定でモデルを起動する（ソースの警告文は「default settings」と表現するが、この失敗分岐は既存 config を書き換えない）（`terminal/setup.py:8231-8238`、`terminal/setup.py:11754-11759`）。個別候補の起動・測定失敗は候補を落とし、既に得た結果を保持して続行する（`terminal/tools/calibrate.py:470-505`）。

## 根拠

- parser と型: `terminal/setup.py:11553-11554`
- 対象 config の選択・非対応 family の除外: `terminal/setup.py:7835-7847`
- 較正の適用条件、モデル選択、失敗時の終了・起動: `terminal/setup.py:11730-11759`
- 測定候補、3巡 sweep、比較条件、HIP 分岐: `terminal/tools/calibrate.py:56-72`、`terminal/tools/calibrate.py:327-458`
- 候補ごとの起動・測定失敗処理: `terminal/tools/calibrate.py:470-505`
- run config と per-PC settings への反映: `terminal/setup.py:8186-8197`、`terminal/setup.py:8217-8255`
