# `STRATA_BUILD_COMMIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。Strata が直接読む箇所を対象とし、外部ライブラリの動作は対象外です。

## 役割

端末配布アーカイブを作成するとき、そのアーカイブの元になった Strata の完全な commit SHA を供給します。`packaging/package_terminal.py` は `STRATA_BUILD_COMMIT` を `STRATA_COMMIT` より後順位の候補として読み、値が40桁の16進 SHA として有効なら小文字化してアーカイブ内の `COMMIT` ファイルに書きます。この値は通常の Strata engine の実行時設定ではありません。

主な供給経路は Docker build です。両 Dockerfile は build argument `STRATA_COMMIT` を環境変数 `STRATA_BUILD_COMMIT` に設定してからパッケージ作成スクリプトを実行します。`docker/build.sh` はホスト側の `STRATA_BUILD_COMMIT` または git HEAD を選び、Docker build argument `STRATA_COMMIT` として渡します。

## 値と判定

Python の `build_commit()` は候補ごとに truthiness を確認し、`.strip()` 後の文字列全体が `[0-9a-fA-F]{40}` に一致するか検査します。一致した値は前後空白を除去して小文字化します。数値変換や SHA の存在確認はしません。

| `STRATA_BUILD_COMMIT` の状態 | `build_commit()` の処理 |
|---|---|
| 未設定、空文字 | 候補として採用せず、後続の Git fallback へ進む |
| 前後空白付きの40桁16進文字列 | 空白を除去し小文字化して採用 |
| 40桁の大文字・小文字混在16進文字列 | 小文字化して採用 |
| 40桁でない、16進以外を含む、または空白だけ | 無効として次の fallback へ進む |

優先順位は `--commit` CLI 引数、`STRATA_COMMIT`、`STRATA_BUILD_COMMIT`、ソースツリーでの `git rev-parse HEAD` です。上位候補が有効なら下位候補は見ません。たとえば有効な `STRATA_COMMIT` は `STRATA_BUILD_COMMIT` より優先され、無効な `STRATA_COMMIT` は `STRATA_BUILD_COMMIT` の判定へ進みます。すべての候補が無効で Git も有効な40桁SHAを返さない場合、通常の配布ビルドは停止します。`--skip-deps` のレイアウト確認では停止せず、警告を出して `COMMIT` ファイルなしのアーカイブを作ります。

## 有効になる条件

- `packaging/package_terminal.py` が実行され、`--commit` と `STRATA_COMMIT` が有効な SHA を与えず、この環境変数が有効な40桁 SHA を与える場合に候補として採用されます。
- Docker 経由では Dockerfile の `ARG STRATA_COMMIT` が `ENV STRATA_BUILD_COMMIT=${STRATA_COMMIT}` に渡されます。トップレベル `Dockerfile` と `docker/Dockerfile` の両方にこの宣言があります。
- `docker/build.sh` 経由では、ホストの `STRATA_BUILD_COMMIT` が空でなければそれを使い、空または未設定ならリポジトリの HEAD を使います。その後、値に小文字 `0-9a-f` 以外が含まれる場合は空にして build argument に渡します。この shell 側の確認は40桁長を検査しません。最終的な40桁検査は Python 側で行われます。
- ビルド用コンテキストに `.git` がなく、CLI 引数や `STRATA_COMMIT` / `STRATA_BUILD_COMMIT` の有効値もない場合は Git fallback も使えず、通常ビルドは失敗します。Strata の Docker 文書はソースビルドで `.git` をコピーしないこと、および `STRATA_COMMIT` build argument の指定を説明しています。

OS、CUDA/HIP/SYCL backend、GPU、モデル状態、サーバーモードには依存しません。Strata の engine コードがこの名前を環境変数として読む箇所は見つかりません。

## 実行時の詳細

`build_commit()` は `package_terminal.py` の main 処理から呼ばれ、プロセス環境をその呼び出し時に参照します。値は `static` cache されませんが、この処理はパッケージ作成時の一回の呼び出しです。読み取った SHA はアーカイブのルートに `COMMIT` として保存され、後のベンチマーク記録で配布物の commit を示す情報になります。生成後の Strata 実行時に `STRATA_BUILD_COMMIT` を再読する処理ではありません。

有効値が得られない場合、`--skip-deps` なしでは `SystemExit` により次の文言で停止します。この文言は `STRATA_BUILD_COMMIT` を明示していませんが、候補判定後にも SHA が得られなかった場合の経路です。

> the commit of these sources is unknown (no .git here, no --commit, no STRATA_COMMIT): the archive would carry no COMMIT file, and every `strata bench run` on it would be nonconforming

`--skip-deps` を指定した場合は同じ説明を `warning: ` 付きで標準出力に出し、`COMMIT` を書かずに続行します。成功時の SHA 自体について専用ログはなく、アーカイブの `COMMIT` ファイルに現れます。

## 根拠

- `packaging/package_terminal.py:320-331`: 候補順、環境変数の読み取り、空白除去、40桁16進文字列の判定、小文字化、Git fallback。
- `packaging/package_terminal.py:347-349,357-368`: `--commit` の定義、優先順位を含む `build_commit()` 呼び出し、未知 commit 時の停止または `--skip-deps` 警告。
- `packaging/package_terminal.py:411-415`: 有効な commit をアーカイブ staging root の `COMMIT` に書く処理。
- `Dockerfile:71-76`、`docker/Dockerfile:34-37`: Docker build argument から環境変数への設定とパッケージャー起動。
- `docker/build.sh:59-61,105-109`: ホスト環境変数または git HEAD の選択、値の文字種検査、Docker build argument の受け渡し。
- `docs/DOCKER.md:303-307`: `.git` が build に含まれず、`STRATA_COMMIT` argument を渡すソースビルドの説明。
- `docs/BENCHMARK_PROTOCOL.md:326-329`: リリースアーカイブ内の `COMMIT` ファイルを commit 情報として扱う説明。
