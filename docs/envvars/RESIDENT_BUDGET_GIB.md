# `RESIDENT_BUDGET_GIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。作業開始時の Strata checkout は `main...origin/main` で、未コミット変更はありません。

## 役割

現行 Strata のエンジン設定としては読み取られていません。Strata の Docker entrypoint が旧イメージ由来の設定名として検査し、値が空でなければ「旧イメージの変数で、ここでは無視する」という警告を stderr に出します。Docker の移行案内も `RESIDENT_BUDGET_GIB` を警告付きで無視する旧名として掲載しています（`docker/entrypoint.sh:80-83`, `docs/DOCKER.md:265-275`）。

## 値と判定

entrypoint は `legacy` に列挙した名前を `eval "v=\${$legacy:-}"` で間接参照し、`[ -n "$v" ]` で判定します（`docker/entrypoint.sh:80-82`）。値の文字列や数値としての parse、範囲検査はありません。

| 状態 | entrypoint の動作 |
| --- | --- |
| 未設定 | 空値として扱い、警告しない |
| 空文字 | 空値として扱い、警告しない |
| 空でない値（`0` を含む任意の文字列） | stderr に旧イメージ由来で無視する旨を警告する |

値に応じた既定値、fallback、clamp、CLI 引数との優先順位は実装されていません。この変数をエンジンの `strata launch` 引数や `STRATA_SET` に変換する処理もありません。

## 有効になる条件

この検査はコンテナ entrypoint の通常起動経路で行われます。引数なし、または先頭引数が `run` / `serve` の場合は警告ループへ進みます。一方、先頭引数がそれ以外なら entrypoint は先に指定コマンドを `exec` するため、この検査は実行されません（`docker/entrypoint.sh:53-56,80-83`）。

OS、GPU backend、build macro、モデル状態によってこの警告の判定は変わりません。少なくとも現行 checkout では、エンジンや CLI がこの名前を別途参照する箇所は確認できませんでした。`docs/envvars/000_envvers.md` の候補掲載は旧設定名としての entrypoint 検査に対応しています。

## 実行時の詳細

警告文は `[!] RESIDENT_BUDGET_GIB is from the older image and is ignored here. See docs/DOCKER.md ("From the older image").` です。`warn` は `[!] ` を付けて stderr に出力します。警告ループは `die` や終了処理を呼ばず、その後もコンテナの起動処理へ進みます（`docker/entrypoint.sh:37-39,80-83`）。

この確認は起動時の entrypoint 実行中に行われ、結果を cache する実装はありません。Docker 起動後にプロセス環境を変えた場合の再評価もありません。通常経路ではこの値を削除・書換えする処理は見つからず、後続コマンドへ環境が継承される可能性はありますが、Strata のソース内でこの名前を読む追加箇所は確認できませんでした。そのため、エンジン側の効果については断定しません。

## 根拠

- `docker/entrypoint.sh:1-7` — Strata コンテナの entrypoint と起動形態。
- `docker/entrypoint.sh:37-39` — 標準出力・標準エラーの通知関数。
- `docker/entrypoint.sh:53-56` — 通常起動以外のコマンドが警告検査より先に `exec` される分岐。
- `docker/entrypoint.sh:80-83` — 旧名の間接読み取り、非空判定、警告。
- `docs/DOCKER.md:265-275` — 旧イメージからの移行表。`RESIDENT_BUDGET_GIB` は「ignored with a warning」と記載。
