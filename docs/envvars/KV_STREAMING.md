# `KV_STREAMING`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Docker entrypoint が旧イメージの設定名として存在を確認し、値が空でなければ警告します。この checkout の Strata エンジンが `KV_STREAMING` を読んで KV cache の形式や処理を変える実装は見つかりません。entrypoint はこの名前を `strata launch` の引数や `--set` に変換しません。Docker の旧設定案内でも、この名前は「警告を出して無視」とされています（`docker/entrypoint.sh:80-83`、`docs/DOCKER.md:265-275`）。

## 値と判定

entrypoint は `for` ループ内で `eval "v=\${$legacy:-}"` を実行し、`legacy` が `KV_STREAMING` の回にシェルの `${KV_STREAMING:-}` で値を得ます。その後 `[ -n "$v" ]` だけを判定します（`docker/entrypoint.sh:80-83`）。

| 状態 | entrypoint の扱い |
| --- | --- |
| 未設定 | 空として扱い、警告しない |
| 空文字 | 未設定と同じく警告しない |
| 空でない値 | 値の内容を parse せず、警告を出す |

`1` / `0`、数値、文字列の妥当性や範囲は検査しません。先頭文字や大文字小文字による判定もありません。空白だけの値も空でないため警告対象です。無効値として終了する経路や fallback はありません。

警告文は stderr に `[!] KV_STREAMING is from the older image and is ignored here. See docs/DOCKER.md ("From the older image").` と出ます（`docker/entrypoint.sh:37-39,80-83`）。この警告による終了はなく、entrypoint は後続の起動処理へ進みます。

## 有効になる条件

この確認は Docker イメージの entrypoint がサーバー起動経路を進む場合に行われます。イメージの既定 command は `run` です（`docker/Dockerfile:133-134`）。entrypoint は引数が `run` または `serve` 以外なら、`strata` は Strata 実行ファイルへ、それ以外は指定コマンドへ直ちに `exec` するため、その経路では旧名の警告処理を通りません（`docker/entrypoint.sh:53-56`）。

警告の判定に OS、backend、build macro、CLI オプション、モデル状態、他の環境変数は関与しません。エンジン側にこの変数名の参照はなく、CLI や `STRATA_SET` との優先順位もありません。Docker entrypoint は `KV_STREAMING` を明示的に子プロセスへ設定・除去しません。通常のシェル起動環境を引き継いで `strata launch` を実行しますが、この checkout でエンジンがその値を読むコードは確認できません。

## 実行時の詳細

entrypoint の警告ループは、Docker サーバー初期化の早い段階で実行されます。値はこのループで一度確認され、後から再読する処理はありません（`docker/entrypoint.sh:67-83`）。空でない値なら警告後も、エンジン確認や設定組み立てを続け、最終的に `strata launch --no-tui` を起動します（`docker/entrypoint.sh:136-160,169-226,253-285`）。この旧名の判定自体には CLI 設定、永続化、エラー終了はありません。

## 根拠

- `docker/entrypoint.sh:53-56` — 任意コマンドは旧名確認より前に `exec` される。
- `docker/entrypoint.sh:80-83` — 旧環境変数を動的に参照し、空でない場合だけ共通警告を出す。
- `docker/entrypoint.sh:169-226,253-285` — `strata launch` 用引数の組み立てと起動。`KV_STREAMING` を引数へ変換する処理はない。
- `docker/Dockerfile:133-134` — イメージの entrypoint と既定 command。
- `docs/DOCKER.md:265-275` — 旧イメージからの移行表で `KV_STREAMING` を警告付きで無視すると説明。
