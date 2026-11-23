# `STRATA_BUILD_COMMIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Terminal 配布アーカイブを作るとき、そのソースの commit SHA をビルド環境から渡すための packaging 用入力です。engine の実行時動作や推論設定は変えません。`tools/packaging/package_terminal.py` は最終的に選んだ SHA をアーカイブ内の `COMMIT` ファイルに書き、Strata の benchmark がソース revision を記録できるようにします（`tools/packaging/package_terminal.py:422-438, 465-471, 514-516`）。

Docker 経路では `tools/docker/build.sh` がこの変数を読み、Dockerfile の `STRATA_COMMIT` build arg に渡します。Dockerfile はその build arg を `STRATA_BUILD_COMMIT` として Terminal の packaging コマンドへ渡します（`tools/docker/build.sh:61-63, 130-134`; `tools/docker/Dockerfile:34-37`; `tools/docker/Dockerfile.src:109-116`）。

## 値と判定

| 読み取り経路 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `package_terminal.py` を直接実行 | `os.environ.get` は `None` または `""`。どちらも候補として採用せず、次の候補へ進む | 前後の空白を除いた **40 桁**の ASCII 16 進文字列。大文字・小文字を受け付け、採用時は小文字に正規化する（例: `a`×40、`A`×40、前後に空白を付けたもの） | 空白だけ、空文字、39 桁または 41 桁、`0`、`true`、`0anything`、16 進文字以外を含む文字列。値全体を正規表現で検査し、部分一致では採用しない |
| `tools/docker/build.sh` を経由 | シェルの `${STRATA_BUILD_COMMIT:-...}` により unset と空文字はいずれも `git -C "$repo" rev-parse HEAD` の結果へ置き換える | 置換後に小文字 `0-9a-f` だけからなる文字列。ここでは長さを検査しない。通常は git が返す 40 桁 SHA | 大文字、空白、その他の文字を含む値は `commit` を空にする。長さだけが不正な小文字 hex はこの段階では残るが、後段の packaging 検証には通らない |

直接実行時、候補の優先順位は CLI `--commit`、`STRATA_COMMIT`、`STRATA_BUILD_COMMIT`、ソースツリーの `git rev-parse HEAD` です。各候補は空でなく、trim 後に 40 桁 hex の場合だけ採用されます。したがって、上位候補が unset・空・無効なら次へ進み、CLI 引数または `STRATA_COMMIT` が有効なら `STRATA_BUILD_COMMIT` は使われません（`tools/packaging/package_terminal.py:422-433, 449-451`）。

## 有効になる条件

- Terminal アーカイブの packaging を実行する経路で使われます。engine の C++/CUDA/HIP/SYCL 実行時設定として読む箇所はありません。
- 直接 packaging では `--commit` または `STRATA_COMMIT` が有効な値なら、そちらがこの変数より優先されます。両方が無効または未設定のときに限り、本変数が候補になります（`tools/packaging/package_terminal.py:422-433, 465`）。
- Docker 用 `tools/docker/build.sh` は本変数を先に読み、値を `STRATA_COMMIT` build arg として渡します。Dockerfile 内では `ARG STRATA_COMMIT` から `ENV STRATA_BUILD_COMMIT=${STRATA_COMMIT}` を設定します。このため packaging の実行時には同じ commit 値が `STRATA_COMMIT` 候補としても存在し、同値の本変数より先に選ばれます（`tools/docker/build.sh:61-63, 130-134`; `tools/docker/Dockerfile:34-37`; `tools/docker/Dockerfile.src:110-116`）。
- `tools/docker/build.sh` 経由で本変数が unset または空なら、checkout の HEAD を代用します。git の参照に失敗した場合や、その後の有効な commit 値が得られない場合、Terminal packaging は git fallback も試します（`tools/docker/build.sh:61-63`; `tools/packaging/package_terminal.py:426-433`）。
- Docker build の値が最終的に 40 桁 hex として採用できない場合、通常の配布アーカイブ作成（`--skip-deps` なし）は停止します。`--skip-deps` の場合は警告を出して処理を続けますが、`COMMIT` ファイルは作られません（`tools/packaging/package_terminal.py:465-471, 514-516`）。

## 実行時の詳細

`tools/docker/build.sh` は context 作成時にシェル変数 `commit` を一度設定します。ここで本変数が非空ならその値を使い、unset/空なら git HEAD を読みます。小文字 hex 以外を含む場合は値を空にしてから Docker build arg を組み立てます。build arg は後続の `docker build` に渡され、Terminal stage で `package_terminal.py` が実行されます（`tools/docker/build.sh:55-63, 130-134`; `tools/docker/Dockerfile:33-40`）。

直接 packaging の場合は `main()` が `build_commit(args.commit)` を呼び、その呼び出しで `os.environ.get("STRATA_BUILD_COMMIT")` を評価します。関数内 static cache やリクエストごとの再評価はありません。通常のコード経路ではこの選択は一度の packaging 実行時に行われます（`tools/packaging/package_terminal.py:422-438, 441-465`）。

有効な値が得られると、staging directory に `COMMIT` を一行で作成し、その directory が配布アーカイブへ収録されます（`tools/packaging/package_terminal.py:514-516, 547-548`）。この環境変数自体を読む Strata のサーバー／CLI 実行経路は見つかりませんでした。

## ログと測定値

有効値を採用したときの commit 専用ログはありません。採用できる値がなく `commit is None` になると、実装は `the commit of these sources is unknown (no .git here, no --commit, no STRATA_COMMIT): the archive would carry no COMMIT file, and every `strata bench run` on it would be nonconforming` を作ります。`--skip-deps` なしではこの文言で `SystemExit` し、指定時は `warning: ` を先頭に付けて stdout へ出します（`tools/packaging/package_terminal.py:465-471`）。

## 根拠

- `tools/docker/build.sh:61-63, 130-134` — 環境変数のシェル展開、文字種検査、Docker build arg への受け渡し。
- `tools/packaging/package_terminal.py:422-438, 449-451, 465-471, 514-516` — 値の検証と優先順位、fallback、失敗時の扱い、`COMMIT` ファイル作成。
- `tools/docker/Dockerfile:33-40` — Docker build arg から環境変数を設定し、Terminal packaging を実行。
- `tools/docker/Dockerfile.src:109-116` — ソースビルド経路での build arg と環境変数の設定。
