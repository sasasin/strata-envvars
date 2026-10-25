# `--calibrate`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などから起動） |
| オプション | `--calibrate` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる |

## 役割

インストール済みモデルをこの PC で計測し、エンジン設定の候補を比較して実行設定へ保存します。通常は測定後にモデルも起動します。測定するのは PCIe 転送の割合、speculative draft の確度しきい値、CPU worker 数、複数 GPU の layer split がある場合の prompt chunk 数、expert tier の設定です。HIP backend では `STRATA_SH_STREAM` も比較します（`setup.py:6601-6610`、`tools/calibrate.py:3-29`、`tools/calibrate.py:320-329`、`tools/calibrate.py:364-455`）。

## 使い方

POSIX では Strata checkout で `./setup.sh --calibrate --no-start`、Windows では `START-HERE.bat --calibrate --no-start` を実行します。特定の導入済みモデルを選ぶときは `--model NAME`、または系列を選ぶときは `--family NAME` を併用できます。選択したモデルを測定後に起動する通常の例は `./setup.sh --calibrate` です。

## 値と既定値

`action="store_true"` のため値を付けません。既定値は未指定時の `False` です。値の範囲や数値 validation はありません（`setup.py:8515-8517`）。

`--model` または `--family` を同時に指定すると、その条件に合う導入済み設定だけを測定対象にします。両方を省略した場合は、導入済みのうち own-path family と multi-file family を除いた設定が対象です。これらの除外 family は selector 指定時にも候補になりません。候補が複数なら一覧を出して選択を促し、`--yes` のときは選択 prompt の既定値である先頭候補が使われます（`setup.py:6433-6444`、`setup.py:8656-8669`）。

## 実行時の動作

`--calibrate` は plain start 判定を外し、セットアップ処理側の経路へ進めます（`setup.py:8602-8609`）。導入済みモデルがあり、かつ `--setup` と `--check` が同時に指定されていない場合に、対象設定を選んで測定します。成功すると測定結果で run config の `args` を置換・更新し、HIP 測定で環境値が返れば `env` も更新します。さらに同じ校正結果を `settings.json` の `calibration` に hardware key ごとに保存します。key は GPU 名と VRAM、CPU、RAM、モデル、context、画像設定から作られます（`setup.py:6584-6598`、`setup.py:6601-6631`）。run config は一時ファイルに書いてから置換されます。設定ファイル保存に失敗した場合は警告を出します（`setup.py:6154-6159`、`setup.py:5922-5929`）。

校正は製品既定値を基準に測定し、明確な改善が出た値だけを採用します。`tools/calibrate.py` では採用閾値を `MIN_GAIN = 0.03` とし、worker 候補や adaptive expert tier、HIP stream などを比較します。測定結果が空の項目はエンジン既定値（または setup の `--spec-min-p 0.5`）に戻すため、以前の校正値がそのまま残る設計ではありません（`tools/calibrate.py:49-65`、`tools/calibrate.py:186-192`、`tools/calibrate.py:485-507`）。

測定に成功した場合、`--no-start` がなければ選んだモデルを起動します。通常起動と同じく、起動時に config が更新されることがあります（例: 最近使ったモデル記録）。セットアップ時に保存済み校正が一致すれば、新しい config にその値を適用します。Windows HIP は保存校正の再適用対象外です（`setup.py:6642-6655`、`setup.py:6737-6776`、`setup.py:9712-9729`）。

## 適用条件と副作用

- `--setup` または `--check` と同時なら、このオプションによる校正は実行せず警告します。まだモデルがない場合も「校正は何もしない」と警告し、既存モデルの準備後に再実行するよう案内します（`setup.py:8652-8655`）。
- selector で一致する導入済みモデルがなければ、導入済みモデル名を含むエラーを出して終了コード 1 で停止します（`setup.py:8656-8661`、`setup.py:825-830`）。
- `--no-start` は測定後のモデル起動を抑止します。校正に失敗した場合も `--no-start` ならモデルを起動しません（`setup.py:8670-8676`）。
- 測定中はエンジンを起動し、複数の設定候補で生成速度を計測します。setup は所要時間を約 15–30 分（遅い GPU ではさらに長い）と案内し、その間 PC が使用中になると表示します（`setup.py:6608-6610`）。測定は実際のモデルと tokenizer を読み、prompt 生成を行うため、GPU/CPU/メモリとモデルファイルを使用します（`tools/calibrate.py:224-247`）。
- 初回モデル導入と同時に指定しても、その新規モデルの校正をこのフラグが実行するわけではありません。通常のセットアップ後に対話で校正を選べる経路が別にあり、`--yes` ではその対話を行わない実装です（`setup.py:9731-9737`）。

## 出力とエラー

進捗、候補ごとの測定速度、採用設定を標準出力向けの `say` / `ok` / `warn` 経由で表示します。測定処理が例外で失敗した場合は例外とエンジンログの理由を警告し、config と校正記録を更新せず既定設定を維持します。その後、`--no-start` がなければ既定設定のままモデルを起動し、校正失敗だけを理由に非ゼロ終了にはしません（`setup.py:6611-6639`、`setup.py:8670-8676`）。

## 根拠

- Parser と説明: `setup.py:8515-8517`
- 対象モデルの選定: `setup.py:6433-6444`、呼び出しと selector エラー・複数候補選択: `setup.py:8652-8676`
- 測定、config と hardware-key 別記録: `setup.py:6584-6639`
- 測定条件、比較、設定適用: `tools/calibrate.py:303-455`、`tools/calibrate.py:485-507`
- config の原子的置換と設定ファイル書き込み警告: `setup.py:5922-5929`、`setup.py:6154-6159`
- CLI 起動 wrapper の引数転送: `setup.sh:76`。Windows 入口は `START-HERE.bat:48-50` と `START-HERE.bat:53-56`。

調査範囲は上記 Strata checkout のソースです。同一 revision の `--help` は実行しておらず、Release 配布物との動作差は確認していません。
