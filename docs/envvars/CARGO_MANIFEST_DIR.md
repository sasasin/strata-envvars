# `CARGO_MANIFEST_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Strata Desktop の Rust ソースで `env!("CARGO_MANIFEST_DIR")` によりビルド時に埋め込まれた manifest directory を、パッケージ済みリソースが見つからないときの開発用リソース起点として使う。実行中のプロセスからこの環境変数を読み直す設定ではない。参照は `app/desktop/src-tauri/src/main.rs` の非 Linux 向け `resource_dir`、全対象 OS の `--self-test`、および Linux supervisor にある（`app/desktop/src-tauri/src/main.rs:323-332, 731-755`; `app/desktop/src-tauri/src/supervisor.rs:503-507`）。Cargo package の manifest は `app/desktop/src-tauri/Cargo.toml`（`app/desktop/src-tauri/Cargo.toml:1-5`）。

`resource_dir` は Tauri の resource directory に `host/server/index.mjs` があればそれを返し、そうでなければ埋め込み値を返す。Linux supervisor と self-test は、実行ファイルの位置からパッケージ済み resources を特定できなかった場合に同じ埋め込み値へ fallback する（`app/desktop/src-tauri/src/main.rs:323-332, 653-668, 738-755`; `app/desktop/src-tauri/src/supervisor.rs:503-507`）。

## 値と判定

この値は Rust の `env!` マクロ引数としてコンパイル時に展開され、実行時に文字列を parse したり値域を検証したりしない。したがって unset / 空文字 / `0` / `1` / `true` などを実行時設定値として判定する分岐はない。マクロ展開後は `PathBuf::from(...)` に渡され、通常起動ではリソース探索と App Host 起動に使われる。値の形式を検査したり、別の環境変数・CLI 値と優先順位を付けたりする処理は確認できない（`app/desktop/src-tauri/src/main.rs:331-332, 749-755`; `app/desktop/src-tauri/src/supervisor.rs:505-507`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Rust コンパイル時の `env!` 展開 | 実行時の unset 判定はない。マクロに値を渡せないビルド環境ではコンパイルに必要な値を解決できない | 文字列として展開された値を `PathBuf` に渡す。実行時の候補選択には、その場所に期待するファイルがあるかという別判定がある | 値自体の文字列検証はない。ディレクトリが期待レイアウトでない場合、パスは fallback 候補として使われた後、ファイル存在確認や Node 探索で失敗し得る |

## 有効になる条件

- 対象コードは `app/desktop/src-tauri` の Desktop アプリである。`resource_dir` 経路は `#[cfg(not(target_os = "linux"))]` で、Linux では使用しない（`app/desktop/src-tauri/src/main.rs:323-324, 554-557`）。Linux の通常起動は `supervisor::run`、Linux self-test は `run_self_test` を使う（`app/desktop/src-tauri/src/main.rs:924-945`; `app/desktop/src-tauri/src/supervisor.rs:478-507`）。
- 実行ファイル位置から `packaged_resource_dir` が `host/server/index.mjs` を含む resources directory を見つけた場合、その値が優先され、この変数由来の fallback は使われない（`app/desktop/src-tauri/src/main.rs:653-668, 740-755`; `app/desktop/src-tauri/src/supervisor.rs:503-507`）。非 Linux の通常起動でも、Tauri の resource directory に同ファイルがあれば manifest directory は選ばれない（`app/desktop/src-tauri/src/main.rs:323-332`）。
- Linux では `--help`、`--save-logs`、`--quit`、既存 session への join で `supervisor::run` が先に戻る場合、このリソース選択箇所には到達しない（`app/desktop/src-tauri/src/supervisor.rs:478-501`）。
- CLI からの値上書き、他の環境変数との相互作用、実行中の環境変更を読む条件はない。

## 実行時の詳細

`env!` がコンパイル時に埋め込んだ値は、該当経路が実行されたとき `PathBuf` に変換される。環境変数を起動時・初回呼び出し時・リクエストごとに再読する実装や cache はなく、起動後の環境変更では埋め込み値は変わらない（`app/desktop/src-tauri/src/main.rs:331-332, 749-755`; `app/desktop/src-tauri/src/supervisor.rs:505-507`）。

通常起動では選ばれた resource root から `host/server/index.mjs`（root 直下に無ければ `../host` 側）と `dist`、Node runtime を探し、見つかれば App Host 用コマンドを構成する（`app/desktop/src-tauri/src/main.rs:365-379, 501-545`; Linux supervisor は `app/desktop/src-tauri/src/supervisor.rs:503-532`）。Linux で App Host 構成に失敗すると `say` で理由を出して exit code 1。非 Linux の Tauri setup では起動エラーを `desktoplog::startup_failed` に渡す（`app/desktop/src-tauri/src/supervisor.rs:516-521`; `app/desktop/src-tauri/src/main.rs:985-990`）。self-test は packaged resources が無いとき埋め込みパスを開発 root として記録し、その下の host/UI/Node 等を検査する。結果を JSON と stdout に出し、全 step 成功なら 0、失敗なら 1 を返す（`app/desktop/src-tauri/src/main.rs:738-783, 872-898`）。

## ログと測定値

この変数自体を理由にしたログや測定値はない。Linux self-test で packaged layout が見つからないと `resources-packaged` step の detail に `not a packaged layout; using development root <path>` を記録する。App Host の entry が無い場合は `the App Host entry is missing at <path>`、UI が無い場合は `the built UI is missing at <path>; run "npm --prefix host run build"` を返す（`app/desktop/src-tauri/src/main.rs:743-755, 509-518`）。Linux 通常起動で `host_command` が失敗すれば理由をログに出して 1 を返し、self-test は JSON report を出して失敗時に 1 を返す（`app/desktop/src-tauri/src/supervisor.rs:516-521`; `app/desktop/src-tauri/src/main.rs:872-898`）。

## 根拠

- `app/desktop/src-tauri/src/main.rs:323-332` — 非 Linux の resource directory 選択と manifest directory fallback。
- `app/desktop/src-tauri/src/main.rs:653-668, 738-755` — packaged resource 探索と self-test の fallback。
- `app/desktop/src-tauri/src/main.rs:365-379, 501-545` — 選択後の Node / App Host の探索と起動コマンド構成。
- `app/desktop/src-tauri/src/main.rs:872-898` — self-test report と終了コード。
- `app/desktop/src-tauri/src/supervisor.rs:478-521` — Linux supervisor の経路、fallback 後の起動失敗処理。
- `app/desktop/src-tauri/Cargo.toml:1-5` — Desktop Rust package の manifest。
