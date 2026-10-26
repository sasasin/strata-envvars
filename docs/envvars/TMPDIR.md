# `TMPDIR`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Strata のサーバーは `TMPDIR` を含む親プロセス環境をエンジン子プロセスに引き継ぎます。HIP backend の場合だけ、値が設定されている一時ディレクトリが書き込み可能かを起動前に調べ、書けなければ代替先を探します。Linux 配布・インストール・macOS 署名スクリプトも一時作業ディレクトリの場所として参照します。

## 値と判定

| 経路 | 未設定・空文字 | 設定値 |
|---|---|---|
| `serve/server.py` の `child_env` / HIP guard | 未設定は変更しない。空文字も guard の検査対象にしない | `TEMP` と `TMP` と同様に、値をパスとして扱い、guard が書き込み可能性を調べる |
| `packaging/*.sh` の `mktemp` | `${TMPDIR:-/tmp}` により `/tmp` を使う | 指定値を一時ディレクトリの親として使う。値が存在しない・書けない場合の独自 fallback はなく、`mktemp` の失敗になる |
| `packaging/mac/sign-and-notarize.sh` | `${TMPDIR:-/tmp}` により `/tmp` を使う | 指定値を使う前に末尾の `/` を1個取り除く。その後 `mktemp` が失敗するとエラー終了する |

環境変数の値を数値や真偽値には変換しません。サーバーの guard は環境マップの `TMPDIR` が truthy（Python で空文字以外）かを見ます。空白の trim、パスの絶対化、展開などは guard 側で行いません。`Path` と一時ファイル API に渡されたパスとして検査されます。

## 有効になる条件

- `child_env(cfg)` はまず `dict(os.environ)` を作り、続いて設定プロファイルの `cfg["env"]` を適用するため、プロファイルに `TMPDIR` があれば親プロセスの値を上書きします。
- `hip_env_guard` は `cfg["backend"] == "hip"` のときだけ `child_env` から呼ばれます。CUDA、CPU 等の経路では `TMPDIR` をこの guard で検査・修正しません。
- HIP guard は `TEMP`、`TMP`、`TMPDIR` のうち、設定値があり、かつその値で一時ファイルを作れないものを不良値として扱います。3変数すべてが未設定または空ならこの確認はありません。
- 不良値があれば、ログの親ディレクトリの `tmp`、次にサーバーの `ROOT/tmp` を作成して書き込み可能性を試します。見つかった場合、不良だった変数すべてを同じ代替ディレクトリに設定します。候補が使えなければ元の値を残し、警告だけを出します。
- HIP guard はエンジンの起動ごとに組み立てる子環境に対して実行されます。親プロセスの環境そのものを書き換えず、起動後に `TMPDIR` を変更しても既に作成した子の環境には反映されません。

## 実行時の詳細

`_dir_writable(p)` は `tempfile.TemporaryFile(dir=p)` を開けるかで検査し、`OSError` を失敗として扱います。guard が値を置き換えた場合は stderr に `strata serve: AMD: TMPDIR=<元の値> is not writable: using <代替先>` の形式で出します。代替先が見つからない場合は `strata serve: AMD: TMPDIR not writable (AMD's runtime needs a writable temporary folder)` 相当の行を出します。不良値が複数ある場合、最後の警告に変数名をカンマ区切りで列挙します。

サーバーでは単一エンジン経路・レプリカ経路のどちらも `child_env` の結果を `StrataEngine` に渡します。レプリカ経路では各レプリカの設定で個別に作成されます。HIP 用 guard は値の補正をするだけで、エンジン起動の成否を直接判定しません。

配布スクリプトでは `packaging/install.sh` がインストール用ファイル、`build_cuda_linux.sh` と `build_sycl_linux.sh` がパッケージ用ステージング領域を、macOS の `sign-and-notarize.sh` が署名・公証作業領域を `TMPDIR` 配下に作ります。後者は不足空き容量を検出した場合に `TMPDIR` を大きなディスクへ向けるようエラーを表示します。`apps/desktop/scripts/fetch-node.sh` も同じ `/tmp` fallback の形式で Node.js 用作業ディレクトリを作成します。

## 根拠

- `serve/server.py:3499-3537` — 親環境の複製、設定環境の上書き、HIP 時の guard、子環境の返却。
- `serve/server.py:3540-3578` — 一時ディレクトリの書き込み確認、代替先、stderr 警告。
- `serve/server.py:7980-7985,8347-8352` — レプリカと通常起動から `child_env` をエンジンへ渡す箇所。
- `packaging/install.sh:77-80`, `packaging/build_cuda_linux.sh:48-50`, `packaging/build_sycl_linux.sh:48-51` — `/tmp` fallback 付きの作業領域。
- `packaging/mac/sign-and-notarize.sh:185-204` — 末尾スラッシュ処理、署名作業領域、容量不足の案内。
- `apps/desktop/scripts/fetch-node.sh:75` — Node.js 作業領域。

`docs/DETAILS.md` と関連設計資料には、`TMPDIR` 固有の説明や測定値を確認できませんでした。サーバー内の HIP guard の根拠は現行コードであり、コメントに記載された HIP runtime の問題を独立に測定したものではありません。
