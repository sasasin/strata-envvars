# `TMPDIR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`TMPDIR` は用途別の一時ファイル／作業ディレクトリの場所として参照される。Strata 全体で統一された値の形式や既定値はなく、serve の AMD engine 起動時、NVFP4 変換ツール、埋め込み Metal カーネル、ビルド・配布スクリプトで個別に扱いが異なる。

serve は起動時に親プロセスの環境を子 engine 用に複製し、設定の `env` に同名キーがあれば上書きする。AMD backend ではその後、空でない `TMPDIR` が書き込み可能か検査し、不可なら代替先へ差し替える。engine の起動ごとに環境を作るため、親プロセスの環境変更は次の `child_env` 呼び出しで反映されるが、起動済み子プロセスの環境は変わらない（`terminal/serve/server.py:4007-4028,4054-4062,4065-4095`; `terminal/serve/server.py:833-835`）。

## 値と判定

| 経路 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `serve` の子 engine 環境（共通） | `child_env` は親の `os.environ` を複製する。設定 `env` に `TMPDIR` があればその文字列で置換する。値自体は parse しない。 | 任意の値をそのまま渡す。 | 値の形式検証なし。 |
| `serve` の AMD guard | unset と空文字は `env.get(k)` が偽になり、書き込み検査も差し替えも行わない。 | 空でない値で、そこへ一時ファイルを作成できる場合は維持する。 | 空でない値で一時ファイル作成に失敗すると「書き込み不可」と判定し、代替先を探す。 |
| `terminal/tools/nvfp4_convert.py` | `os.environ.get("TMPDIR")` が `None` または `""` なら `tempfile.tempdir` に `--outfile` の親ディレクトリを設定する。 | 空でない文字列（例: `0`、空白のみを含む値も含む）は truthy として扱われ、Strata は `tempfile.tempdir` を設定しない。 | 値の形式・存在・書き込み可能性の検査なし。 |
| `HY4_EMBED_KERNELS` 有効な Metal engine | unset または空文字なら `/tmp` を使用する。 | 空でない値をディレクトリ名として使用する。 | 値の形式・存在・書き込み可能性の検査なし。 |
| packaging 等の shell スクリプト | `${TMPDIR:-/tmp}` は unset または空文字で `/tmp` を選ぶ。 | 空でない値を `mktemp` のテンプレート先頭に使う。 | スクリプト側で事前検証なし。作成失敗は `mktemp` または後続処理の失敗になる。 |

これらの経路に共通する `1` / `0`、大文字小文字、空白除去、数値境界の規則はない。AMD guard では `TMPDIR` だけでなく `TEMP` と `TMP` も同じ検査対象で、いずれかの空でない値が不可なら、見つかったすべての不可値を同じ代替ディレクトリに置き換える（`terminal/serve/server.py:4078-4094`）。

## 有効になる条件

- **serve / AMD:** `child_env` が AMD backend の設定で呼ばれた場合に限り `hip_env_guard` が走る。unset・空文字は検査されず、そのまま子 engine 環境に残る。空でない値が書き込み不可なら、まず `cfg.log` の親（なければ `cfg.cwd`、それもなければ `ROOT`）の `tmp`、次に `ROOT/tmp` を作成・検査し、書き込み可能な先があれば `TMPDIR` を差し替える。両方とも使えない場合は元の値を残す。CUDA、SYCL、CPU backend ではこの guard による判定・差し替えはない（`terminal/serve/server.py:4054-4062,4065-4095`; writable 検査は `terminal/serve/server_parts/engines.py:1083-1088`）。
- **NVFP4 変換:** `main()` が `--model` と `--outfile` を処理して出力先の親ディレクトリを作った後、環境変数を一度確認する。unset / 空文字のときだけ `tempfile.tempdir` を出力先親ディレクトリに設定する。`--dry-run` もこの判定後に converter を呼ぶ。Strata が `TMPDIR` の値から一時ファイルを直接作るわけではなく、変換処理へ既定ディレクトリを設定する（`terminal/tools/nvfp4_convert.py:88-112`）。`docs/NVFP4.md:36-41` は一時ファイルが出力 GGUF と同程度の空きディスクを要し、TMPDIR で別ディスクを選べる運用を記載している。
- **Metal engine:** `HY4_EMBED_KERNELS` 付きビルドで kernel パスが空かつ `STRATA_HY4_KERNELS` 自体が unset のときに埋め込みカーネル抽出が使われる。`STRATA_HY4_KERNELS` が空文字で設定されていても、コードは設定済みとして扱い、この TMPDIR 経路を使わない。`HY4_EMBED_KERNELS` がないビルドでは抽出関数は空文字を返し、TMPDIR は参照しない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1398-1433,1661-1671,1708-1712`; build 定義は `engine/src/hy4flash/metal/build_mac.sh:47`）。
- **配布・開発スクリプト:** 各スクリプトを実行したプロセスの環境で独立して評価する。serve や engine の CLI 引数による優先順位はない。

## 実行時の詳細

`serve` は `dict(os.environ)` を基に子環境を作り、設定 `env` のキーと値を文字列化して上書きする。AMD backend の場合、guard は `tempfile.TemporaryFile(dir=p)` で一時ファイル作成を試し、書き込み可能性を判定する。代替先を作成・検査できたときは各変数を置換する。どの代替先も使えなければ値は維持され、Strata は runtime が書き込み可能な一時フォルダーを必要とする旨を警告する。変更内容と警告は stderr に `strata serve: AMD: ` を付けて出す。engine はこの環境のスナップショットで起動する（`terminal/serve/server.py:4007-4028,4054-4095,833-835`; `terminal/serve/server_parts/engines.py:1083-1088`）。

NVFP4 変換では、unset / 空文字時に `tempfile.tempdir = str(out.parent)` を設定してから converter を呼ぶ。非空値なら Strata は `tempfile.tempdir` を変更しない。環境値を実行中に再読込するループや独自 cache はなく、判定は `main()` 内のこの一度である（`terminal/tools/nvfp4_convert.py:94-112`）。

埋め込み Metal カーネルでは、空でない TMPDIR の末尾に `/strata-hy4-kernels-<内容ハッシュ>/` を付ける。末尾が `/` でなければ区切りを一つ追加する。unset / 空文字なら `/tmp/` を基点にする。ディレクトリを mode `0700` で作成し、埋め込みファイルを書き出す。`mkdir` や `rename` の戻り値は確認しない。ファイルを開けない、または全量を書けない場合は stderr に `cannot write <path>` を出し空文字を返す。呼び出し側は抽出が空なら隣接する `hy4.metal` 等の通常探索へ進む（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1402-1432,1661-1671,1708-1712`）。

値を読む別の Strata 所有コードとして、Desktop app の Harness 環境フィルターは `TMPDIR` を許可リスト `KEEP` に含め、ホスト環境から子 Harness へ渡す。渡す値の内容を検証・変換せず、`extra` に同名キーがある場合はそちらが優先される（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`）。

ビルド・配布スクリプトは `tools/docker/build.sh:55-59`、`tools/docker/publish.sh:57-61`、`tools/packaging/build_cuda_linux.sh:62-64`、`tools/packaging/build_sycl_linux.sh:53-56`、`tools/packaging/build_cuda_linux_aarch64.sh:29-34`、`tools/packaging/install.sh:132-145`、`tools/packaging/mac/sign-and-notarize.sh:193-218`、`app/desktop/scripts/fetch-node.sh:74-80` で一時作業場所に利用する。これらは shell の `${TMPDIR:-/tmp}` を使い、macOS 署名スクリプトだけは末尾 `/` を一つ除いてから `mktemp` に渡す。署名スクリプトは作業ディレクトリの空き容量が不足すると `fail "free space" ... set TMPDIR to a bigger disk` として処理を止める（`tools/packaging/mac/sign-and-notarize.sh:211-219`）。

## ログと測定値

AMD serve guard が値を差し替えると stderr に `strata serve: AMD: TMPDIR=<値> is not writable: using <代替先>` を出す。`TMPDIR` など複数値が不可で代替先も見つからない場合は、`strata serve: AMD: TMPDIR, ... not writable (AMD's runtime needs a writable temporary folder)` の形式で出す。値が unset / 空文字、または書き込み可能なら、この guard から TMPDIR に関するログは出ない（`terminal/serve/server.py:4078-4095`）。

NVFP4 変換について `docs/NVFP4.md:36-41` は一時ファイル用のディスク要件と出力先 / TMPDIR の使い分けを記載するが、TMPDIR による性能測定値は記載されていない。対象コードにも TMPDIR による測定値はない。

## 根拠

- serve の環境複製・設定上書き・AMD guard 呼び出し: `terminal/serve/server.py:4007-4062`
- AMD の値検査・fallback・stderr 文言: `terminal/serve/server.py:4065-4095`; 一時ファイル検査: `terminal/serve/server_parts/engines.py:1083-1088`
- engine 子プロセスへの環境渡し: `terminal/serve/server.py:833-835`
- NVFP4 変換の判定と converter 呼び出し: `terminal/tools/nvfp4_convert.py:88-112`; 運用説明: `docs/NVFP4.md:36-41`
- Metal 埋め込みカーネルの条件・展開・失敗経路: `engine/src/hy4flash/metal/hy4_metal_main.cpp:1398-1433,1661-1671,1708-1712`; build macro: `engine/src/hy4flash/metal/build_mac.sh:47`
- Harness 子環境の許可と引き渡し: `app/host/server/agent/harness-runtime.mjs:20-36,75-83`
- shell の作業場所利用: `tools/docker/build.sh:55-59`; `tools/docker/publish.sh:57-61`; `tools/packaging/build_cuda_linux.sh:62-64`; `tools/packaging/build_sycl_linux.sh:53-56`; `tools/packaging/build_cuda_linux_aarch64.sh:29-34`; `tools/packaging/install.sh:132-145`; `tools/packaging/mac/sign-and-notarize.sh:193-219`; `app/desktop/scripts/fetch-node.sh:74-80`

`terminal/tools/vision/gguf_meta.h:139-155` にも TMPDIR の直接参照があるが、同ファイルは `gguf_meta_test.cpp` からのみ使われており、本番実装の根拠から除外した。候補一覧 `docs/envvars/000_envvers.md:2397` の名前は、上記の Strata 所有コードで実際の読み取り・環境転送が確認できる。
