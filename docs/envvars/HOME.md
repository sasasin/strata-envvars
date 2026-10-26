# `HOME`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Strata が明示的に参照する `HOME` は、Linux/macOS 用の Terminal インストーラーでインストール先の既定値を作る用途と、ホストサーバーで tuning / Time-skip の状態ディレクトリを作る用途です。エンジンの実行設定ではありません。

## 値と判定

この変数の値自体は数値や真偽値として parse されず、パスの一部として使われます。挙動は実行経路ごとに異なります。

| 経路 | `HOME` の扱い |
|---|---|
| `packaging/install.sh` の `DATA_DIR` | `STRATA_DATA_DIR` が未設定または空なら、`XDG_DATA_HOME` が未設定または空の場合に `$HOME/.local/share/strata` を既定値にする。`STRATA_DATA_DIR` または `XDG_DATA_HOME` が空でない場合は `HOME` を展開しない。 |
| `packaging/install.sh` の `BIN_DIR` | `STRATA_BIN_DIR` が未設定または空なら `$HOME/.local/bin` を使う。設定値が空でなければ `HOME` を展開しない。 |
| ホストサーバーの POSIX `stateRoot()` | `XDG_STATE_HOME` が truthy ならそれを使い、そうでなければ `HOME` が truthy のとき `$HOME/.local/state`、未設定または空のとき `.local/state` を基底にし、末尾に `/strata` を付ける。 |
| ホストサーバーの Windows `stateRoot()` | 明示的な `HOME` は参照しない。`LOCALAPPDATA`、次に `USERPROFILE`、最後に `homedir()` を使う。 |

## 有効になる条件

- インストーラーでの効果は `packaging/install.sh` を実行するときだけです。`DATA_DIR` と `BIN_DIR` はスクリプト冒頭で一度設定されます。`set -u` が有効なので、既定値の展開で必要になった `HOME` が未設定なら、後段のカスタムエラー処理に入る前にシェルの未設定変数エラーで停止します。空文字として設定されている場合は未設定エラーにはならず、既定パスは `/.local/share/strata` または `/.local/bin` になります（ただし前述の上書き変数が有効なら `HOME` は参照されません）。
- ホストサーバーでは POSIX 上の `stateRoot()` が `HOME` を読むときだけ効果があります。`XDG_STATE_HOME` が空でない場合は `HOME` を使いません。`STRATA_TUNE_DIR` は tuning ディレクトリを、`STRATA_TIMESKIP_DIR` は Time-skip ディレクトリを個別に上書きします。
- `stateRoot()` は `process.env` を既定引数として呼び出し時に評価します。`index.mjs` は `tuningDir(env)` を tuning 状態に使い、`timeskip.mjs` は `timeSkipDir(env)` を使います。値の変更を監視する処理や、子プロセスへ `HOME` を書き換えて渡す処理は確認できません。

## 実行時の詳細

インストーラーは `DATA_DIR/terminal/<version>` に Terminal を展開し、`DATA_DIR/terminal/current` と `BIN_DIR/strata` をリンクします。`PATH` に `BIN_DIR` が含まれていなければ、出力に絶対パスの起動方法と PATH への追加案内を表示します。通常の導入先は `HOME`、または上書き変数によって決まります。

ホストサーバーの POSIX 状態ルートは `XDG_STATE_HOME/strata`、または `HOME/.local/state/strata` です。`HOME` も空であれば相対パス `.local/state/strata` になります。そこから tuning と Time-skip 用の各ディレクトリを作ります。Windows ではこの POSIX 分岐を通らないため、`HOME` は状態ルートを決めません。

## 根拠

- `packaging/install.sh:22-27,92-95,119-127` — `HOME` を参照する既定インストール先、展開・リンク先、および実行案内。
- `apps/host/server/platform-paths.mjs:16-32` — POSIX / Windows の `stateRoot()` と tuning / Time-skip パスの上書き処理。
- `apps/host/server/index.mjs:18,820` — ホストサーバーが tuning 用 `stateDir` を `tuningDir(env)` から得る箇所。
- `apps/host/server/timeskip.mjs:23,27` — Time-skip が `timeSkipDir(env)` を使う箇所。
- `docs/INSTALL.md:131-133` と `docs/TERMINAL_LAUNCH.md:205` は状態・コンポーネントの保存場所を説明していますが、ここで調べたインストーラーの `HOME` 優先順位やホスト側 `stateRoot()` の fallback を詳述していません。上記の挙動はソースコードに基づきます。
