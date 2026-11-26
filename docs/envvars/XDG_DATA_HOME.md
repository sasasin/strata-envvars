# `XDG_DATA_HOME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata はこの変数を複数のプロセスで読み、ユーザー単位のコンポーネント領域、Linux/macOS desktop のデータ領域、Linux window のフォント探索先、Terminal installer の配置先を決める。用途ごとに空文字や相対パスの扱いが異なる。

- Terminal の Python と App Host の JavaScript は、通常 `<XDG_DATA_HOME>/strata/components` をコンポーネント領域にする。ここには engine/control などのコンポーネント、更新状態、App Host の設定・shell prefs・install 領域が置かれる。`STRATA_COMPONENTS_DIR` が指定されればこちらが優先する（`terminal/strata_control/engine_component.py:179-193`, `app/host/server/control-runtime.mjs:26-31,88-99`, `app/host/server/shell-prefs.mjs:20-21`, `app/host/server/native-control.mjs:146,186-187`）。
- Linux/macOS の desktop shell は `<XDG_DATA_HOME>/strata` をデータ領域として使い、ログ、runtime、shell 設定などをそこに置く。`STRATA_DESKTOP_DATA_DIR` が設定されていればそちらが優先する（`app/desktop/src-tauri/src/desktoplog.rs:31-62`, `app/desktop/src-tauri/src/shell.rs:33-35`, `app/desktop/src-tauri/src/desktoplog.rs:123-132,320-339`）。
- Linux の window process は XDG データ領域の `fonts` も COLRv1 フォント探索対象に加える（`app/desktop/src-tauri/src/fontguard.rs:36-57`, 呼出元 `app/desktop/src-tauri/src/main.rs:1298-1314`）。
- `tools/packaging/install.sh` は Terminal を `<XDG_DATA_HOME>/strata/terminal/<version>` に展開する。`STRATA_DATA_DIR` があればそちらが優先する（`tools/packaging/install.sh:20-27,150,179-180`）。

環境変数自体が選択するのは配置パスであり、GPU backend、モデル選択、生成内容はこの変数の読み取り箇所では変更されない。

## 値と判定

同じ名前でも読み取り箇所により規則が異なる。

| 経路・条件 | unset | 設定時に採用される値 | 無効・fallback となる値 |
|---|---|---|---|
| Desktop Rust `desktoplog`、Windows 以外（Linux/macOS） | `HOME/.local/share/strata`。HOME もなければ OS の temp dir 下の `strata` | `STRATA_DESKTOP_DATA_DIR` が未設定なら、絶対パスだけを採用し末尾に `/strata`。空文字・相対パスは採用しない | `XDG_DATA_HOME` の空文字・相対パスは HOME fallback。`STRATA_DESKTOP_DATA_DIR` 自体は `var_os` の設定有無で優先し、空文字や相対値もそのまま PathBuf として使う |
| Desktop Rust `desktoplog`、Windows | XDG を読まず、`LOCALAPPDATA/Strata`、次に `USERPROFILE/AppData/Local/Strata`、最後に temp dir | 該当なし | XDG はこの build 経路で参照されない |
| Linux window の fontguard | 非空の HOME があれば `HOME/.local/share/fonts` を追加。HOME がなければこの既定フォルダーは追加しない | `std::env::var` が String にできる非空値をそのまま PathBuf にし `/fonts` を追加。相対パスも受理 | unset、空文字、Unicode String にできない値は HOME fallback。文字列の絶対性・正規化・存在は値判定時に検査しない |
| Terminal Python `engine_component.components_dir` および `strata_cli.handover.components_dir`、Windows 以外 | `Path.home()/.local/share/strata/components` | 空でない値をそのまま `Path` にして `/strata/components` を追加。相対値も受理 | unset または空文字なら HOME fallback |
| App Host JavaScript `componentsDirectory`、Windows 以外 | `homedir()/.local/share/strata/components` | truthy な値を `path.join` で `/strata/components` と結合。空文字は値として採用しない | unset または空文字なら homedir fallback |
| `tools/packaging/install.sh` | `HOME/.local/share/strata` | `STRATA_DATA_DIR` が空でなければ優先。それ以外は空でない XDG 値の末尾に `/strata` | unset または空文字は `HOME/.local/share/strata` へ fallback。パスの妥当性・絶対性は検査しない |

ここでの parse は数値・真偽値変換ではなく文字列からパスを組み立てる処理である。大小文字、空白（trim しない）、`0` や `false` に特別な意味はない。Python/JS/shell は空文字を fallback とし、Rust fontguard も空文字を unset と同様に扱う。一方 desktop Rust の `desktoplog` は XDG の空値を絶対パス判定で落とす。全ての規則の根拠は上表に挙げた各実装箇所。

## 有効になる条件

- Python/JavaScript のコンポーネント領域では Windows 分岐は `LOCALAPPDATA`（またはユーザーホーム下の既定値）を使い、XDG を参照しない（`terminal/strata_control/engine_component.py:185-189`, `app/host/server/control-runtime.mjs:28-30`）。
- `STRATA_COMPONENTS_DIR` が空でない場合、Python と App Host の component path はそれを優先する。`strata update` の `--components-dir` 引数を渡した場合も、CLI 側で明示パスを使い helper の既定値を通らない（`terminal/strata_control/engine_component.py:179-189`, `terminal/strata_cli/update_cmd.py:47-50,318-324`）。
- App Host は起動時に `componentsDirectory()` を呼び、Control 子プロセスへ解決済みパスを `STRATA_COMPONENTS_DIR` として渡す。このため子 Control は同じ component root を使う（`app/host/server/index.mjs:167-171,230`, `app/host/server/control-runtime.mjs:88-99`）。
- Python の `discovery.components_dir` は `engine_component.components_dir` を呼び、同じ既定パスを install directory の親としても使う（`terminal/strata_control/discovery.py:47-59`）。ただし `STRATA_INSTALL_DIR` または `STRATA_DATA_DIR` がある場合、install 探索の明示候補が別途優先される（`terminal/strata_control/discovery.py:174-195,212-220`）。
- Terminal 起動時の handover は component path の `control/active.json` に新しい完全な Control がある場合だけ移譲する。開発 checkout では通常移譲を無効にし、`STRATA_HANDOVER` / `STRATA_NO_HANDOVER` の guard でも抑止される。XDG は探索 root を決めるが、それだけで移譲は起きない（`terminal/strata.py:35-48`, `terminal/strata_cli/handover.py:34-42,70-74,126-153`）。
- Linux の fontguard は Linux window process でだけ呼ばれる。既存の `FONTCONFIG_FILE`、`STRATA_FONT_CONFIG=off`、既存 COLRv1 font の有無などで設定生成を迂回でき、XDG の値だけではフォント設定変更を保証しない（`app/desktop/src-tauri/src/main.rs:1298-1314`, `app/desktop/src-tauri/src/fontguard.rs:141-157`）。
- Desktop Rust では `STRATA_DESKTOP_DATA_DIR` が XDG より先に選ばれる（`app/desktop/src-tauri/src/desktoplog.rs:31-58`）。
- Installer shell は Linux x86_64/ARM64 と macOS Apple silicon の対象判定を通った後に配置先を使い、`STRATA_DATA_DIR` が XDG より優先される（`tools/packaging/install.sh:24-27,59-67`）。

## 実行時の詳細

Python の `engine_component.components_dir` は、明示 `environ` が渡されなければ呼出し時の `os.environ` を読み、呼出しごとにパスを計算する。`resolve`、`status`、update state 読み取りなどから既定 root として利用される（`terminal/strata_control/engine_component.py:179-193,216-259,1209-1217,1340-1354`）。Terminal entry point は起動直後、重い import の前に `maybe_hand_over` を呼び、その中で component root を求める（`terminal/strata.py:35-48`, `terminal/strata_cli/handover.py:5,34-42,126-139`）。handover の子プロセス環境は元環境を複製するため XDG も引き継がれる（`terminal/strata_cli/handover.py:117-120,148-158`）。

App Host の `componentsDirectory` は呼出し時に `env`（既定は `process.env`）から読み、キャッシュは関数内にない。呼出し元ではその root を engine/control、cloudflared、shell prefs、settings、install root の探索・作成に使う（`app/host/server/control-runtime.mjs:27-31,37-43,88-99,114`; `app/host/server/index.mjs:167-171,230,1002`; `app/host/server/shell-prefs.mjs:20-21`; `app/host/server/native-control.mjs:146,185-187`）。

Desktop Rust の `data_dir()` は呼出しごとに `STRATA_DESKTOP_DATA_DIR` または platform path を計算する。Linux/macOS ではこれが logs、runtime、shell-prefs の配置に使われ、起動ログや診断ログの保存先も変わる（`app/desktop/src-tauri/src/desktoplog.rs:31-62,123-132,320-339`, `app/desktop/src-tauri/src/shell.rs:33-35`）。Linux window process は起動時に `font_dirs` を呼び、そこで得た directories を浅い走査に使う。対象 font が見つかり、fontconfig の設定生成にも成功した場合に限り、同じ window process の `FONTCONFIG_FILE` を設定する。window が起動した後の環境変更を再評価するループはない（`app/desktop/src-tauri/src/main.rs:1298-1314`, `app/desktop/src-tauri/src/fontguard.rs:36-57,60-89,117-157`）。

Installer shell は `DATA_DIR` をスクリプト開始時に一度設定し、versioned Terminal directory と `current` symlink をその下に作る（`tools/packaging/install.sh:22-27,150,179-180`）。

これらの読み取りは値を静的 cache に保持する実装ではない。ただしプロセス起動後に親プロセス側の環境変数を変えても既に起動した子プロセスの環境は遡って変わらず、fontguard と installer はそれぞれの処理開始時点の環境に基づいて動作する。

## ログと測定値

XDG の値を表示する専用ログ、警告、終了経路は見つからない。値が変わる主な観測結果は対象ディレクトリ・ファイルの場所である。Terminal の component root が違えば更新状態や engine/control の探索先が変わり、該当先に engine がないと `EngineMissing` の理由にその root が含まれる（`terminal/strata_control/engine_component.py:1211-1217`）。Desktop のログは選択された data dir 下に作られ、診断ログ収集も同領域の runtime/server logs を参照する（`app/desktop/src-tauri/src/desktoplog.rs:61-62,123-132,320-339`）。

Fontguard は XDG 値の理由ログを出さず、COLRv1 font が見つからないか設定ファイル生成が失敗すれば `None` を返して `FONTCONFIG_FILE` を設定しない（`app/desktop/src-tauri/src/fontguard.rs:117-157`, 呼出元 `app/desktop/src-tauri/src/main.rs:1310-1314`）。この変数に関する測定値は資料にない。

## 根拠

- Python の component root、既定値、呼出用途: `terminal/strata_control/engine_component.py:179-193,216-259,1209-1217,1340-1354`; handover: `terminal/strata_cli/handover.py:34-42,70-74,117-158`, `terminal/strata.py:35-48`。
- App Host の component root と子 Control への受け渡し: `app/host/server/control-runtime.mjs:26-31,37-43,88-99`; 利用先: `app/host/server/index.mjs:167-171,230,1002`, `app/host/server/shell-prefs.mjs:20-21`, `app/host/server/native-control.mjs:146,185-187`。
- Python install 探索の優先候補: `terminal/strata_control/discovery.py:47-59,174-220`。
- Desktop data path: `app/desktop/src-tauri/src/desktoplog.rs:31-62`; ログ・診断の利用: `app/desktop/src-tauri/src/desktoplog.rs:123-132,320-339`; shell prefs: `app/desktop/src-tauri/src/shell.rs:33-35`。
- Linux font search: `app/desktop/src-tauri/src/fontguard.rs:36-57,60-89,117-157`; Linux window process: `app/desktop/src-tauri/src/main.rs:1298-1314`。
- Installer の優先順位と配置先: `tools/packaging/install.sh:20-27,59-67,150,179-180`。
- `docs/INSTALL.md:136` と `docs/TERMINAL_LAUNCH.md:210` の XDG 配置案内をコードと照合した。候補名の全参照も確認し、テスト用の環境設定、文書・コメント、子プロセス用に値を明示設定する箇所を、利用者の環境から読み取る実装とは区別した。Strata の実行時コードで利用者環境の XDG 値を読む箇所は上記の列挙箇所。
