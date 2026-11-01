# `STRATA_COMMIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`packaging/package_terminal.py` がターミナル配布アーカイブの元 commit SHA を特定するときに読む値です。成功時は SHA をアーカイブ直下の `COMMIT` ファイルに書き込みます。エンジン実行時の設定や推論動作を変える読み取りはありません。

## 値と判定

`build_commit()` は `--commit`、`STRATA_COMMIT`、`STRATA_BUILD_COMMIT` の順に候補を調べ、最初に有効な候補を採用します。有効値は前後の空白を除いた 40 桁の ASCII 16 進文字列で、大文字・小文字を受け付け、返す値を小文字にします。部分一致や短縮 SHA は受け付けません。

| `STRATA_COMMIT` の状態 | 判定と次の処理 |
|---|---|
| 未設定または空文字 | 候補として採用せず、`STRATA_BUILD_COMMIT` を調べる |
| 40 桁の 16 進文字列（前後に空白があってもよい） | trim して小文字化した値を採用。ただし有効な `--commit` があればそちらが優先 |
| その他（例: 短縮 SHA、40 桁でない値、内部に空白がある値） | 無効候補として飛ばし、`STRATA_BUILD_COMMIT`、さらに Git checkout の `HEAD` を調べる |

`--commit` が明示されていても形式が無効なら、エラーにはせず次候補へ進みます。環境変数の値を採用できず Git からも SHA を取得できない場合は commit 不明になります。

## 有効になる条件

この値は `packaging/package_terminal.py` の実行時だけ参照されます。OS、GPU backend、モデル状態による分岐はありません。通常の Strata engine / server / CLI 実行コードでは `STRATA_COMMIT` を読み取る箇所は見つかりませんでした。

Docker のターミナル build では Dockerfile が build arg `STRATA_COMMIT` を環境変数 `STRATA_BUILD_COMMIT` に移し、パッケージャーがその変数を fallback として読みます（`Dockerfile:71-76`, `docker/Dockerfile:34-38`）。一方、パッケージャーを直接起動する場合は `STRATA_COMMIT` を直接指定できます。

## 実行時の詳細

アーカイブ作成の `main()` が引数を解析した後、`build_commit(args.commit)` を呼びます。環境値はその呼び出し時に読み、static cache はありません。`STRATA_COMMIT` が有効なら、その値を `COMMIT` に1行で書き込みます。これにより配布先に `.git` がなくても `strata bench run` が install の commit を記録できます。benchmark 側は `.git` がない場合 `COMMIT` ファイルを読み、SHA が不明なら run を nonconforming と判定します。

候補をどれも解決できないとき、通常の配布ビルド（`--skip-deps` なし）は `the commit of these sources is unknown ...` の理由で `SystemExit` し、終了コード 1 になります。`--skip-deps` のレイアウト確認では同じ理由を `warning: ...` として標準出力に出し、続行しますが、アーカイブに `COMMIT` は作られません。Docker の source build 説明も、commit を渡さない場合 Terminal stage が停止すると記載しています。

## 根拠

- `packaging/package_terminal.py:320-331` — 候補順、形式検査、trim / 小文字化、Git HEAD fallback。
- `packaging/package_terminal.py:339-369` — CLI `--commit`、`build_commit()` 呼び出し、commit 不明時の warning / 終了。
- `packaging/package_terminal.py:411-414` — 有効な SHA をアーカイブの `COMMIT` に書き込む処理。
- `Dockerfile:71-76`, `docker/Dockerfile:34-38`, `docker/build.sh:59-61,105-109` — Docker build arg から `STRATA_BUILD_COMMIT` を渡す経路。
- `strata_cli/bench_facts.py:389-399`, `strata_cli/bench_standard.py:825-826` — benchmark 側で `.git` または `COMMIT` を読み、SHA 不明を nonconforming とする処理。
- `docs/DOCKER.md:303-307`, `docs/BENCHMARK_PROTOCOL.md:326-329` — Docker build と配布アーカイブの commit 記録に関する説明。
