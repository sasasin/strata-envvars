# `--gpu`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（内部で `terminal/tools/strata_bench.py` を実行） |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU 番号、または番号をカンマ区切りにした文字列。parser は文字列として受け取る |

## 役割

ベンチマークが Strata server を起動するときに、使用 GPU を server の `--gpu` に渡す。server 起動後に収集するマシン情報でもこの値を使い、レポート上で使用 GPU を識別する。ベンチマークがすでに動いている Strata server を利用する場合は server を変更せず、値はレポート用の GPU 選択情報として使われる。

## 使い方

```sh
# GPU 0 を指定して bench.sh から server を起動する
./tools/bench.sh --gpu 0

# server の layer split 用に GPU 0 と 2 を指定する
./tools/bench.sh --gpu 0,2

# 既存 server を測定する。この場合 --gpu は server の設定を変えず、レポートの GPU 選択情報に使われる
./tools/bench.sh --url http://127.0.0.1:8080 --gpu 0
```

## 値と既定値

`argparse` の登録に `type`、`choices`、既定値の指定がないため、値は任意の文字列として受け取られ、省略時は `None` になる（`terminal/tools/strata_bench.py:1079-1095`）。ベンチマーク起動時に値が空でなければ server の引数 `--gpu <値>` にそのまま追加する（同 `:812-829`）。

起動する server は `--gpu` 値が数字だけなら整数に変換し、それ以外は文字列のまま設定の `gpu` に代入する（`terminal/serve/server.py:9322-9323`）。server の GPU 一覧処理は単一値またはカンマ区切り値を整数化する（`terminal/serve/server_parts/engines.py:678-692`）。quick-benchmark 側には GPU 番号の範囲確認や独自のエラー文言はないため、無効な番号・書式に対する最終的な挙動はこのオプション文書の範囲では確定できない。

server の設定に `gpu_roles` がある場合、保存済み roles は `gpu` の一覧が roles と矛盾しない限り優先される。CLI で渡した GPU が roles の mirror と異なる一覧や Main の位置を作ると、roles は無視されて `gpu` の値が使われる（`terminal/strata_control/gpu_roles.py:421-440`）。

## 実行時の動作

- **quick-benchmark が server を起動する場合:** 指定値を `server.py --gpu` に転送する。server は CLI 値を設定ファイルの `gpu` より優先して設定に入れ、GPU 選択に利用する（`terminal/tools/strata_bench.py:812-829, 1135-1143`; `terminal/serve/server.py:9322-9323`）。server が既定で使用する GPU は、quick-benchmark 側で固定されず、設定や server の選択経路に委ねられる。
- **server がすでに起動している場合:** 起動処理自体を通らないため `--gpu` は server に渡されず、実行中の server の GPU を切り替えない。GPU 情報収集では `--gpu` が設定ファイルの `gpu` より先に選択情報として解析される（`terminal/tools/strata_bench.py:696-715, 1130-1149`）。
- GPU 情報収集用の解析はカンマ区切りの各要素を trim し、数字だけの要素を番号として採用する。そうして得た番号でローカル GPU 情報を選ぶが、番号に対応する情報が一つも得られない場合は既定の GPU 情報を残す（`terminal/tools/strata_bench.py:696-715, 728-736`）。これはレポート情報の選択であり、server 側の受理確認ではない。

## 適用条件と副作用

`--url` なしで起動する経路では、既存の Strata server が見つかればそれを使うため、この値で server を再起動・再設定しない。別のサービスが server 用ポートを使っている場合は起動を止め、別ポートを指定するよう stderr に出す（`terminal/tools/strata_bench.py:1129-1143`）。server をこの実行が起動した場合に限り、ベンチマーク終了時にそのプロセスを停止する（同 `:1181-1184`; 停止処理 `:847-854`）。

## 出力とエラー

値がない状態で `--gpu` を指定すると、引数 parser の必須値チェックにより通常の argparse usage error になる（parser 登録 `terminal/tools/strata_bench.py:1084-1095`）。値の形式・番号を quick-benchmark 自身が検証する処理は確認できない。起動した server が ready にならない場合、quick-benchmark はログ末尾 15 行を stderr に出し、終了コード `1` を返す（`terminal/tools/strata_bench.py:1141-1146`）。指定値固有の失敗時メッセージや終了コードは、server の実行結果に依存する。

## 根拠

- `terminal/tools/strata_bench.py:1079-1095` — CLI parser と `--gpu` の値・既定値。
- `terminal/tools/strata_bench.py:812-829, 1135-1146` — server 起動時の引数転送と起動失敗経路。
- `terminal/tools/strata_bench.py:696-715, 728-736, 1147-1155` — GPU 選択情報の優先順位とレポート用の利用。
- `terminal/serve/server.py:9322-9323` — server 側での `--gpu` 値の設定への反映。
- `terminal/serve/server_parts/engines.py:678-692` — server が設定値から GPU 番号を解釈する処理。
- `terminal/strata_control/gpu_roles.py:421-440` — 保存済み GPU roles と `gpu` 値の優先関係。
- `tools/bench.sh:6-10`、`tools/BENCH.bat:8-16` — wrapper が `strata_bench.py` に引数を渡す経路。
