# `CONFIG`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは clean（`## main...origin/main`）。

## 役割

`CONFIG` は旧 Docker イメージから引き継がれた環境変数名として、Strata の Docker entrypoint が設定有無を確認します。現行イメージの設定には使わず、値が空でなければ旧名は無視されるという警告を stderr に出します。エンジンや通常の Strata CLI が `CONFIG` の値を読む実装は見つかりませんでした。

## 値と判定

entrypoint は `for legacy in ... CONFIG` のループで名前を変数 `legacy` に入れ、`eval "v=\${$legacy:-}"` で間接参照します。シェルの `${name:-}` による判定なので、未設定と空文字はいずれも空として扱われます。空でない値は文字列の内容を検証せず、何が設定されていても警告だけを出します。

| `CONFIG` の状態 | entrypoint の動作 |
|---|---|
| 未設定 | 警告なし |
| 空文字 | 警告なし |
| 空でない任意の文字列 | `[!] CONFIG is from the older image and is ignored here. See docs/DOCKER.md ("From the older image").` を stderr に出す |

数値変換、許容範囲、無効値時の fallback はありません。変数の値による分岐もありません。

## 有効になる条件

- Docker の通常起動で entrypoint が `run` / `serve` として続行するときに確認されます。entrypoint は最初の引数が `run` または `serve` 以外なら、警告処理に到達する前にコマンドを `exec` します。
- `CONFIG` が空でないことが警告の条件です。OS、GPU backend、build macro、モデル状態による条件はありません。
- `CONFIG` の値は `strata launch` の引数に追加されず、設定として適用されません。Docker 文書も旧イメージの `CONFIG` を「ignored with a warning」と案内しています。

## 実行時の詳細

通常起動時、entrypoint はディレクトリ準備やコンテナメモリなどの警告を処理した後、旧変数一覧を走査します。`CONFIG` に値があれば `warn` 関数が `[!] ` を付けて stderr に出力します。その後の処理はこの値に依存せず続き、起動時の `strata launch` 引数にも含めません。警告時に終了したり、値を別名へ転送したりする処理はありません。entrypoint を介さない通常の CLI 起動ではこの警告経路はありません。

なお、`--config` / `--from-config` は CLI 引数として別途存在しますが、環境変数 `CONFIG` とは異なる入力です。

## 根拠

- `docker/entrypoint.sh:53-55`: `run` / `serve` 以外のコマンドは旧変数警告ループより前に `exec` されます。
- `docker/entrypoint.sh:37-39,67-83`: `warn` は stderr に出力し、旧変数名を間接参照して空でない場合だけ無視警告を出します。
- `docker/entrypoint.sh:169-171,190-225,253-283`: 通常起動の `strata launch` 引数を組み立てる箇所に `CONFIG` は含まれず、処理は起動へ進みます。
- `docs/DOCKER.md:265-275`: 旧イメージの `CONFIG` を警告付きで無視すると説明しています。
- `strata_cli/cli.py:47,73,91`: `--config` / `--from-config` は CLI 引数であり、環境変数 `CONFIG` の読み取りではありません。
