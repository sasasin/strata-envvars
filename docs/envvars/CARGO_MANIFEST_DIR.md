# `CARGO_MANIFEST_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Strata Desktop の Rust コードが、実行ファイルの場所から packaged resource directory を特定できない場合に使う開発用 fallback のルートパスです。値は `env!("CARGO_MANIFEST_DIR")` でコンパイル時に文字列として埋め込まれます。実行中のプロセスが `CARGO_MANIFEST_DIR` を環境から読み取る処理ではなく、起動後に環境変数を変更しても埋め込み値は変わりません。

## 値と判定

| 状態 | Strata の扱い |
|---|---|
| Cargo がビルド時に設定 | `env!` がその文字列をコンパイル済みコードへ埋め込み、使用箇所で `PathBuf` にする。値自体の parse、正規化、空文字検査は行わない。 |
| ビルド時に未設定 | Rust の `env!` 展開が失敗し、該当する desktop crate はコンパイルできない。Strata コードに fallback 値はない。 |
| 空文字または不正なパス文字列 | この値を検査する Strata の処理はない。`PathBuf` への変換自体は行われ、その後の resource 探索やファイル存在確認に渡る。 |
| 実行時に unset / 空文字 / 値変更 | 実行時の再読取りはなく、影響しない。 |

CLI 引数や別の実行時環境変数との値の優先順位はありません。resource directory の選択では、実行ファイル位置を使う `packaged_resource_dir()` が先に試され、それが `None` の場合にだけ埋め込み値を使います。

## 有効になる条件

- `apps/desktop/src-tauri` の desktop アプリをビルドする際に評価される compile-time 環境変数です。GPU backend やモデル状態には依存しません。
- macOS / Windows 側の `resource_dir()` は、`app.path().resource_dir()` が取得でき、そこに `host/server/index.mjs` が存在すればその packaged resource directory を返します。それ以外は `CARGO_MANIFEST_DIR` の埋め込み値へ fallback します。この関数は `#[cfg(not(target_os = "linux"))]` です。
- Linux の supervisor は `packaged_resource_dir(current_exe)` が `None` の場合に埋め込み値を使います。self-test の resource 解決も packaged layout が見つからない場合に同じ値を使います。
- Cargo の通常のビルド環境では Cargo が manifest directory を表す値を提供しますが、Strata 側のコードが独自に値を決めたり、実行時に検証したりはしません。

## 実行時の詳細

非 Linux の通常起動では `start_host()` が `resource_dir()` の結果を `host_command()` に渡します。`host_command()` はその下から `host/server/index.mjs` を探し、見つからない場合は `the App Host entry is missing at ...`、UI の `dist` がない場合は `the built UI is missing at ...; run "npm --prefix host run build"` を返します。呼び出し元はこのエラーをログへ出して起動を失敗させます。

Linux では supervisor が packaged resource directory を探し、見つからなければ埋め込み値を `res` にします。host command の構築に失敗した場合はエラーを出して終了コード 1 を返します。self-test の fallback では選択されたルートを `resources-packaged` の失敗 detail に記録し、以降の host entry、UI dist、Node runtime の確認を行います。

値は Rust の `env!` 展開時に固定されます。Strata による runtime cache や、子プロセスへ `CARGO_MANIFEST_DIR` を転送・上書きする処理はありません。

## 根拠

- 候補一覧には名前がありますが、全参照は以下の 3 箇所で、いずれも `env!` マクロです（`docs/envvars/000_envvers.md:58`）。実行時 env API の参照はありません。
- 非 Linux の開発 fallback と platform 条件: `apps/desktop/src-tauri/src/main.rs:282-292`。呼び出し元は `main.rs:495-501`。
- packaged resource 探索: `apps/desktop/src-tauri/src/main.rs:590-605`。
- self-test の packaged 判定と fallback、診断記録: `apps/desktop/src-tauri/src/main.rs:668-704`。
- resource の存在確認とエラー文: `apps/desktop/src-tauri/src/main.rs:444-459`。
- Linux supervisor の packaged 優先・fallback、host 起動失敗時のログと終了: `apps/desktop/src-tauri/src/supervisor.rs:316-369`。

このため、`CARGO_MANIFEST_DIR` は候補一覧から除外する対象ではありませんが、通常の実行時環境変数としては扱えません。Strata が使用しているのは Cargo/Rust ビルド時の値です。
