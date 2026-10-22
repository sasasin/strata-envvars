# `STRATA_HOME`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

host サーバーの per-user データ用ルートディレクトリを指定します。ここに `data/state.json` などの状態データを置き、書き込み可能な候補として選ばれれば `models/` も作ります。engine インストーラーなど、host 内の複数機能がこのルートを基準にパスを作ります。

Windows の `strata` CLI では別の用途として、ユーザー所有ファイルの権限修復で「ユーザーデータのルート」の一つに数えます。

## 値と判定

| 状態 | host サーバー (`apps/host/server/store.mjs`) | Windows CLI の権限修復 (`strata_control/private_files.py`) |
|---|---|---|
| 未設定 | `~/.strata`、次に `<cwd>/.strata` を候補にする | この変数由来のルートは追加しない |
| 空文字 | falsy として候補から除外。未設定と同じ | falsy として無視 |
| 空でない値 | 文字列をそのまま先頭候補として使う。相対パスも拒否・絶対化されず、プロセスの cwd 基準で扱われる | `Path(value)` をルート候補に加える。`user_roots()` では `resolve()` で正規化し、`known_roots()` では存在確認に使う |

文字列の trim、展開、値形式の検証はありません。例えば空白だけの値も非空文字列として扱われます。host は候補ごとに `models/` と `data/` を再帰作成し、両方の作成に成功した最初の候補を採用します。失敗は捕捉して次候補へ進み、全候補で失敗した場合は `No writable data directory found — set STRATA_HOME to a writable path` を投げます。

## 有効になる条件

- host サーバーの `store.mjs` がロードされるときに評価されます。ES module の初期化で `HOME` が決まるため、ロード後に `process.env.STRATA_HOME` を変更しても選択済みの `HOME` や `DATA_DIR` は移りません。
- `STRATA_HOME` のディレクトリ作成に成功したときだけ採用されます。失敗時は `homedir()/.strata`、続いて `process.cwd()/.strata` に fallback します。環境変数が設定されていても、その場所が使えなければ fallback します。
- `STRATA_MODELS_DIR` が設定されていれば、モデル用ディレクトリの選択はそちらを優先する別設定です。`STRATA_HOME` は引き続き `data/` など host のデータ基点です。モデル用の環境変数がない場合でも、モデル保存先の希望場所はプラットフォーム別の Documents で、そこを使えない場合などに `STRATA_HOME/models` が fallback になります。
- Windows CLI の修復処理では、`STRATA_HOME` は `APPDATA` などと並ぶ候補の一つです。`known_roots()` は存在するルートのみを返します。権限修復そのものは Windows でのみ動きます。

## 実行時の詳細

host は採用したルートから `DATA_DIR = HOME/data`、状態ファイル `data/state.json` を作ります。状態ファイルがない、または読み込み・JSON parse に失敗した場合は初期状態を使います。保存時は同じ状態ファイルへ書き、書き込みエラーは `[strata] could not persist state:` として stderr に出します。

他の host 処理もこのルートを使います。engine installer は `HOME/engine` をインストール先にし、Cloudflare connector は `HOME/engine/cloudflare`、artifacts の preview は `HOME/previews` を使います。API でユーザー指定パスの先頭 `~` を展開するときも `store.HOME` に置き換えます。ディスク空き・合計容量の helper は既定で `HOME` を調べますが、呼び出し元は別パスを渡せます。

Windows CLI 側では `user_roots()` が `STRATA_HOME` を含む既知のユーザーデータ環境変数を列挙し、`is_users_own()` が対象パスがそのルート内かを判定します。`repair_known_roots()` はそのルート群を走査し、権限エラーがある項目を修復しようとします。CLI は起動時のアクセスエラー再試行や `repair-access` コマンドからこの関数を呼びます。未設定時に `~/.strata` を走査するのは Python CLI 側の `known_roots()` が独自に追加する既定ルートであり、Node host の fallback 選択とは別実装です。

## 根拠

- 候補順、空値の除外、ディレクトリ作成、fallback、全失敗時の例外: `apps/host/server/store.mjs:14-30`。
- `data/state.json` と読み書きの fallback / ログ: `apps/host/server/store.mjs:31-32,50-60,131-147`。
- モデル用ディレクトリとの関係: `apps/host/server/store.mjs:61-87`、`apps/host/server/model-directory-default.mjs:7-20`。
- engine / connector / preview / `~` 展開: `apps/host/server/engine-install.mjs:13-18`、`apps/host/server/index.mjs:918,1041-1044,1735-1738`。
- ルート列挙と対象判定、Windows 修復: `strata_control/private_files.py:415-439,506-570`。CLI からの呼び出し: `strata_cli/cli.py:2075-2091,2094-2103,2106-2114`。
- `apps/host/docs/README-historical.md:96-102` は過去の `~/.strata` と fallback の説明です。現行動作は上記コードを根拠にしました。`docs/DETAILS.md` にはこの環境変数の実装説明や測定値は見当たらず、性能・正確性の主張は記載していません。
