# `LAYER_SPLIT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

この checkout の Strata 本体は `LAYER_SPLIT` を layer 分割の設定として読みません。Docker イメージの `docker/entrypoint.sh` が、旧イメージ由来の設定名の一つとして値の有無だけを確認します。非空なら旧設定として無視した旨を警告します。

## 値と判定

entrypoint は `for legacy in ... LAYER_SPLIT ...` で候補名を順に設定し、`eval "v=\${$legacy:-}"` でその名前の環境変数を展開します。その後 `[ -n "$v" ]` を判定します。文字列の parse、数値変換、許容値検証はありません。

| 環境値 | 結果 |
| --- | --- |
| 未設定 | 空として扱い、警告しない |
| 空文字 | 空として扱い、警告しない |
| 空でない値（`auto`、数値、任意の文字列を含む） | `[!] LAYER_SPLIT is from the older image and is ignored here. See docs/DOCKER.md ("From the older image").` を stderr に出す |

非空かどうか以外に値による違いはなく、この変数に対応する既定の layer 分割値もありません。`LAYER_SPLIT` を CLI 引数や `STRATA_SET` に変換するコードはありません。Docker 文書は、engine 設定には `STRATA_SET` を使うよう案内していますが、旧 `LAYER_SPLIT` の値との対応や優先順位は定めていません。

## 有効になる条件

この確認は Docker entrypoint の通常起動経路で行われます。引数なし、`run`、`serve` の場合は entrypoint が起動処理を続け、旧変数を警告対象にします。一方、それ以外のコマンドが引数に指定されると、entrypoint は冒頭でそのコマンドを `exec` するため、旧変数チェックを通りません。

OS や GPU backend による分岐はこの確認箇所にはありません。少なくとも調査対象 commit の Strata ソースには、`LAYER_SPLIT` をエンジンの layer 分割値として読み取る箇所は見つかりませんでした。

## 実行時の詳細

entrypoint 起動時に shell が環境値を一度展開します。値が空でなければ `warn` 関数経由で stderr に旧設定の警告を出します。この判定は終了や起動拒否を行わず、その後の entrypoint 処理を続けます。値を設定し直したり CLI 引数へ転送したりはしません。entrypoint が後で `strata launch` に渡す引数の構築にも `LAYER_SPLIT` は含まれません。

この名前の別の参照として、`strata_control/amd_four_card.py` の `LAYER_SPLIT` は `"13,26,39"` という Python 定数で、設定 dict の `layer_split` キーへ書かれます。これは環境変数の読み取りではありません。ベンチマーク記録中の `LAYER_SPLIT=auto` も記録テキストであり、本番コードの読み取り根拠にはなりません。

## 根拠

- `docker/entrypoint.sh:53-56` — `run` / `serve` 以外の引数では旧変数チェックより先にコマンドを `exec`。
- `docker/entrypoint.sh:37-39,80-83` — `warn` は `[!]` を付けて stderr に出力し、非空の旧変数を警告する。
- `docker/entrypoint.sh:190-225` — 起動引数の構築箇所。`STRATA_SET` は `--set` に展開されるが `LAYER_SPLIT` の転送処理はない。
- `strata_control/amd_four_card.py:25,74-75` — 同名の Python 定数を `layer_split` 設定値として使う箇所。環境変数読み取りではない。
- `docs/DOCKER.md:270-275` — Docker 文書でも旧 `LAYER_SPLIT` は警告付きで無視すると説明。
