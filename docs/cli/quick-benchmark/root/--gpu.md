# `--gpu`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh`（Linux）/ `BENCH.bat`（Windows）、または `python tools/strata_bench.py` |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU 番号。server の `--gpu` として渡され、単一 GPU またはカンマ区切りの複数番号を指定する |

## 役割

quick benchmark が新しく起動する Strata server に GPU 選択を渡します。benchmark の計測処理自体を GPU に移す指定ではなく、推論 server の使用 GPU を選ぶ指定です。server の説明では番号は `nvidia-smi` の番号に従い、複数番号は layer split 用です（`tools/strata_bench.py:937`、`serve/server.py:8173-8174`）。

## 使い方

```sh
./bench.sh --gpu 0
```

Windows では `BENCH.bat --gpu 0`、直接実行する場合は `python tools/strata_bench.py --gpu 0` とします。wrapper は引数をそのまま Python script に渡します（`bench.sh:6-10`、`BENCH.bat:8-16`）。

複数 GPU の例は `python tools/strata_bench.py --gpu 0,2` です。これは起動する server に対し、その番号を複数指定します（`serve/server.py:8173-8174`）。

## 値と既定値

値を取る文字列オプションで、quick benchmark parser は型変換・選択肢・範囲検査を定義していません。省略時の値は `None` です（`tools/strata_bench.py:932-948`）。

benchmark が起動する server には、値が空文字でない場合だけ `--gpu <値>` を追加します。空文字を渡した場合は server に渡されません（`tools/strata_bench.py:701-705`）。server parser も独自の型変換を指定せず文字列で受け取り、値全体が数字なら整数、それ以外なら文字列として config の `gpu` に設定します（`serve/server.py:8173-8174`、`serve/server.py:8286-8287`）。server 側では単一番号またはカンマ区切りの GPU 番号を処理します（`serve/server.py:2913-2927`）。

quick benchmark 自身は GPU 番号の有効範囲を検査しません。無効な番号・形式を指定した場合の最終的な扱いは server / engine の処理に依存し、この文書の quick-benchmark parser からは特定できません。

## 実行時の動作

`--url` を指定せず server を起動する経路では、benchmark は `serve/server.py --engine strata --config … --port …` を子プロセスとして起動し、`--gpu` が指定されていればその後ろに値を付けて渡します。server は受け取った値で config の `gpu` を上書きし、GPU 選択に使います（`tools/strata_bench.py:688-705`、`tools/strata_bench.py:957-979`、`tools/strata_bench.py:983-1000`、`serve/server.py:8286-8287`、`serve/server.py:2913-2927`）。

`--url` を指定して既存 server を使う経路では server を起動しないため、この値は server に転送されません。その一方で、計測前後のマシン情報収集にも値が渡され、ローカル GPU の選択とレポート情報の判定に使われます（`tools/strata_bench.py:975-979`、`tools/strata_bench.py:983-1008`、`tools/strata_bench.py:579-598`、`tools/strata_bench.py:601-619`）。そのため、既存 server の実際の GPU 設定を変える効果はありません。

未指定時は config の `gpu`、さらにそれがなければ config の engine 引数に含まれる `--gpu` をレポート用の選択情報として調べます。選択番号がローカル GPU 一覧の範囲外なら、その番号に対応する GPU が選べず、一覧全体へフォールバックします（`tools/strata_bench.py:579-598`、`tools/strata_bench.py:608-619`）。server 側では保存 config の `gpu_roles` も GPU 順序に関係し、CLI から渡した `gpu` が設定されるとその番号が `gpu_roles` の順序より優先されます（`serve/server.py:8286-8287`、`serve/server.py:2913-2920`）。

## 適用条件と副作用

server を新規起動する経路にのみ GPU 実行設定として適用されます。server 起動時には指定 GPU でモデルをロードして benchmark の HTTP リクエストを処理します。benchmark が自分で起動した server は終了時に停止します（`tools/strata_bench.py:994-999`、`tools/strata_bench.py:1035-1037`、`tools/strata_bench.py:723-731`）。

計測結果の GPU 名・VRAM 等の識別にも選択値が使われます。server 側から報告された GPU 名がローカル NVIDIA 一覧と一致しない場合は、server の GPU 名を採用し、ローカル CUDA 情報を外します（`tools/strata_bench.py:608-637`）。

## 出力とエラー

このオプション固有の quick-benchmark parser エラーや警告は定義されていません。server を起動できない場合は server のログ末尾を stderr に表示して終了コード `1`、指定 URL の server が応答しない場合や設定ファイルがない場合などは stderr に理由を表示して終了コード `2` になります（`tools/strata_bench.py:969-972`、`tools/strata_bench.py:983-999`）。

## 根拠

- quick benchmark の parser と値: `tools/strata_bench.py:932-948`
- server 起動引数への転送: `tools/strata_bench.py:688-705`、起動条件: `tools/strata_bench.py:975-1000`
- 既存 server 経路とレポート用 GPU 選択: `tools/strata_bench.py:579-619`
- server parser と config 上書き: `serve/server.py:8173-8174`、`serve/server.py:8286-8287`
- server の GPU config 解釈: `serve/server.py:2913-2927`
- wrapper の委譲: `bench.sh:6-10`、`BENCH.bat:8-16`
