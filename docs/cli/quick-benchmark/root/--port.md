# `--port`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（委譲先: `python tools/strata_bench.py`） |
| オプション | `--port` |
| 別名 | なし |
| 値 | 整数。quick benchmark 側ではポート範囲の検証なし |

## 役割

quick benchmark が既存のモデル設定から Strata サーバーを起動するときに、接続先のポートを指定します。サーバーがすでに動いていて検出された場合はそれを再利用し、`--url` を指定した場合は URL の接続先を使います。

## 使い方

```sh
./bench.sh --port 8081
```

またはセットアップ済みの Windows 環境で:

```bat
BENCH.bat --port 8081
```

ラッパーは引数を `tools/strata_bench.py` に渡します（`bench.sh:6-10`、`BENCH.bat:8-16`）。

## 値と既定値

- `argparse` の `type=int` で整数に変換します。値を省略すると quick benchmark 側の値は `None` です（`tools/strata_bench.py:932-948`）。整数でない値は `argparse` が拒否し、通常の usage エラーで終了します。
- `--url` を指定せず起動先を選ぶ場合、ポートは `--port` の値、設定 JSON の `port`、設定に値がなければ `8080` の順で決まります（`tools/strata_bench.py:957-979`）。
- 明示した `--port 0` は `a.port or ...` の評価で偽と扱われ、設定 JSON の `port`（なければ `8080`）に置き換わります。したがって quick benchmark から OS の空きポート自動割当を要求する用途には使えません（`tools/strata_bench.py:978-979`）。
- quick benchmark 自身には `1..65535` などの範囲検証がありません。負数などの整数も parser を通りますが、実際に bind できるかはサーバー起動時に決まります（`tools/strata_bench.py:936`、`serve/server.py:8156`、`serve/server.py:7718-7723`）。

## 実行時の動作

- `--url` が指定されていれば、末尾の `/` を取り除いた URL を接続先に使い、`--port` の値は使用しません（`tools/strata_bench.py:975-979`）。この経路では既存サーバーの `/health` を確認し、Strata サーバーでなければ「No Strata server answers」として終了コード `2` になります（`tools/strata_bench.py:983-987`）。
- URL を指定しない場合、選ばれた port と設定の host から接続 URL を作ります。host が省略されると `127.0.0.1`、ワイルドカード `0.0.0.0` / `::` は疎通確認用に loopback アドレスへ置き換えられます（`tools/strata_bench.py:922-929`）。
- その URL に Strata の `/health` 応答があれば既存サーバーを利用し、新しいサーバーは起動しません。Strata ではない応答がポート上にある場合は、`--port N` を変えるよう stderr に表示し、終了コード `2` で終了します（`tools/strata_bench.py:983-991`）。
- 接続先に Strata がいなければ、ベンチマークは `serve/server.py --engine strata --config ... --port N` を子プロセスとして起動します（`tools/strata_bench.py:688-705`）。そのサーバーは指定 host/port で HTTP listener を作成します（`serve/server.py:7718-7723`）。

## 適用条件と副作用

- `--port` はサーバーを新規起動する経路に適用されます。`--url` 指定時は無視され、Strata サーバーがすでに選択ポートで稼働している場合もそのサーバーを再利用します（`tools/strata_bench.py:975-995`）。
- Strata サーバーとして識別されず、かつ指定ポートの `/health` が JSON を返す場合は、ベンチマークは別ポートを指定するよう案内します（`tools/strata_bench.py:983-991`）。
- 起動したサーバーの stdout/stderr は一時ディレクトリ内のログへまとめられます。起動後、指定時間内に ready にならない場合はログ末尾を stderr に出して終了コード `1`、ベンチマーク終了時には自分で起動したサーバーを停止します（`tools/strata_bench.py:704-705`、`tools/strata_bench.py:708-720`、`tools/strata_bench.py:992-999`、`tools/strata_bench.py:1035-1037`）。
- 実際の bind が失敗した場合、サーバーは「ポート使用中」や OS の理由を含む listen エラーを作ります（`serve/server.py:144-160`）。このサーバーログはベンチマーク起動ログに書かれ、ready 待ちの失敗経路でログ末尾が表示されます（`tools/strata_bench.py:704-705`、`tools/strata_bench.py:996-999`）。

## 出力とエラー

- 起動経路では選択した設定名とポートを標準出力に表示してからサーバーを開始します（`tools/strata_bench.py:992-995`）。
- ポート上に Strata 以外の HTTP health 応答がある場合は stderr に案内を出して終了コード `2`、サーバーが ready にならない場合はログ末尾を stderr に出して終了コード `1` です（`tools/strata_bench.py:989-999`）。
- このオプション専用の数値範囲エラーや、ポートを結果 JSON のパラメータとして保存する処理は確認できません。結果の `params` には `started_server` などが記録されますが、port は含まれていません（`tools/strata_bench.py:1011-1016`）。

## 根拠

- quick benchmark の parser と起動 URL の選択: `tools/strata_bench.py:932-979`
- 既存サーバーの判定、port 競合、子プロセス起動、ready 待ちと終了処理: `tools/strata_bench.py:983-999`、`tools/strata_bench.py:1035-1037`
- `bench.sh` / `BENCH.bat` からの引数委譲: `bench.sh:6-10`、`BENCH.bat:8-16`
- 委譲先サーバーの `--port` parser、bind、listen エラー: `serve/server.py:144-160`、`serve/server.py:7718-7723`、`serve/server.py:8156`
- 索引上の所属とリンク: `docs/cli/README.md:1522-1545`

この調査では同一 revision の quick benchmark を起動していません。無効な整数以外の境界値について、実際の OS・ポート状態ごとの bind 結果は確認していません。
