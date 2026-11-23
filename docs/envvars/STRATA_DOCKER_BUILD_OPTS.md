# `STRATA_DOCKER_BUILD_OPTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`tools/docker/build.sh` が `docker build` を実行するとき、環境変数の内容を追加のコマンドライン引数として挿入する。スクリプト自身はオプションを解析・検証せず、値を真偽値や設定値として使わない。たとえば `--network host` のような Docker build オプションを渡す用途としてコメントに例示されている（`tools/docker/build.sh:20,130-134`）。

`tools/docker/publish.sh` はこの名前をコメントに記すだけで、値は読まない。ビルド可能な flavor ごとに `build.sh` を子プロセスとして呼ぶため、環境から export されていれば、その子プロセスで同じ値が利用される（`tools/docker/publish.sh:27,63-82`）。

## 値と判定

build script における式は `${STRATA_DOCKER_BUILD_OPTS:-}` で、unset と空文字のどちらも空に置き換わる。非空の値は引用符なしで展開されるため、シェルの単語分割と pathname expansion を受け、できた各語が `docker build` の引数になる。シェルは展開後の値に含まれる引用符を引用構文として再解釈しない。値全体の parse、型・空白・大文字小文字・数値の検証、Strata 独自の上限・境界処理はない（`tools/docker/build.sh:22,130-134`）。

| 条件 | unset | 値の扱い（例） | Strata 側で無効と判定する値 |
|---|---|---|---|
| `build.sh` が `docker build` に進む場合 | オプション引数を追加しない | 空文字も追加なし。`--network host` は2引数、`--network=host` は1引数として渡る。`0`、`1`、`true`、`false` も真偽値扱いせず、各々その文字列の引数として渡す | なし。Strata は引数として渡すだけで、Docker CLI に受理されるかは判定しない |

値に空白があれば通常は単語分割され、glob パターンがあれば現在の作業ディレクトリ（この箇所では `repo`）に対して展開され得る。分割や glob 展開を避けたい場合のエスケープ方法を Strata は提供していない。Docker が引数をどう解釈するか、無効な Docker オプションが何を意味するかは本書の対象外。

## 有効になる条件

- `tools/docker/build.sh` が引数検証と build context の準備を通過し、`--ctx-only` で早期終了していないこと。`--ctx-only` では Docker build 呼び出し自体がない（`tools/docker/build.sh:42-48,55-59,124-134`）。
- 値を使うには環境変数としてプロセスに渡されている必要がある。`publish.sh` 経由では、export された環境値が `build.sh` に継承される。`publish.sh` 自身は読取り・変換・設定をしない（`tools/docker/publish.sh:27,82`）。
- スクリプト内に OS、CUDA/HIP/SYCL flavor、ビルド macro、モデル状態、または別環境変数によるこの値の分岐はない。Docker が利用でき、build 呼び出しまで進む経路でのみ引数として渡される（`tools/docker/build.sh:130-134`）。
- CLI の `--no-cache` は別途 `$nocache` として渡され、コマンド上ではこの環境変数の引数より前に置かれる。Strata は両者の競合解決をしておらず、重複オプションの優先順位は Docker CLI 側の扱いとなる（`tools/docker/build.sh:40,130-134`）。
- `publish.sh --push` はイメージの push を制御する別の CLI 条件であり、この値の読み取りには影響しない（`tools/docker/publish.sh:41,82,89-96`）。

## 実行時の詳細

値は `build.sh` の `docker build` コマンド行を実行する時点でシェル展開される。関数内 static 値やプロセス内 cache はなく、同じスクリプト中での繰り返し読取りもない。build script はこの値を書き換えず、値の内容を別の環境変数や build arg に変換もしない（`tools/docker/build.sh:130-134`）。

直接 `build.sh` を呼ぶ場合も `publish.sh` から呼ぶ場合も、実際の Docker 呼び出しより前に引数検証、context の組み立て、設定概要の表示を行う。`publish.sh` は package のある flavor について順次 `build.sh` を起動し、環境変数を明示的な引数にはせず、プロセス環境を継承させる（`tools/docker/build.sh:24-59,65-68,124-134`; `tools/docker/publish.sh:64-82`）。実行中に親環境の値を変えても、既に起動済みの子プロセスへ反映される処理はない。

## ログと測定値

対象変数専用のログ、値の表示、警告はない。build script は Docker 呼び出し前に context・flavor・base・engine・tag を表示し、Docker build 後に `docker image inspect` の結果を表示してから `Not pushed anywhere. Size on disk: ... bytes.` を出力する（`tools/docker/build.sh:126-136`）。`set -e` のため `docker build` が非ゼロ終了すると inspect とサイズ表示へ進まず、inspect が非ゼロ終了した場合もサイズ表示へ進まない。いずれも script は失敗終了する。自動作成 context は終了 trap で削除されるが、指定された `--ctx` の context はこの cleanup の対象外（`tools/docker/build.sh:22,55-59,130-136`）。失敗時のエラー内容や終了の詳細は Docker コマンド側の出力・終了値であり、Strata はこの変数について独自の診断を追加しない。

## 根拠

- `tools/docker/build.sh:20,130-134` — 変数の説明コメントと唯一の実読取り・引数展開。
- `tools/docker/build.sh:22,40-48,55-59,124-136` — shell の失敗設定、CLI 条件、早期終了、ログと build 後の処理。
- `tools/docker/publish.sh:27,63-82` — コメントのみの参照と `build.sh` 子プロセス呼出し。
- `docs/DOCKER.md:372-385,418-435` — Docker build / publish の利用経路の説明との照合。環境変数の値の意味を裏付ける用途には使っていない。
