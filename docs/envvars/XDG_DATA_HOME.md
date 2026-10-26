# `XDG_DATA_HOME`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Strata の一部の実行経路で、ユーザー単位のデータ置き場の基底ディレクトリを決めます。主な適用先は、Linux/macOS のデスクトップアプリが使うログ・runtime、Control と CLI が共有する engine/control component、Terminal インストーラーの配置先です。Strata 全体で共通の設定ではなく、各実装で空値の扱いや優先順位が異なります。

## 値と判定

| 経路 | `XDG_DATA_HOME` が未設定または空 | 空でない値 | 優先する設定 |
|---|---|---|---|
| `strata_control.engine_component.components_dir()` と `strata_cli.handover.components_dir()` | `Path.home()/.local/share` を使い、`strata/components` を付加 | 値をそのまま基底パスにし、`strata/components` を付加 | 空でない `STRATA_COMPONENTS_DIR` が優先。`strata update` では `--components-dir` も優先 |
| Host の `componentsDirectory()` | `homedir()/.local/share` を使い、`strata/components` を付加 | 値をそのまま使い、`strata/components` を付加 | 空でない `STRATA_COMPONENTS_DIR` が優先 |
| デスクトップ shell の Rust `platform_data_dir()`（Windows 以外） | `$HOME/.local/share`。`HOME` も未設定なら `temp_dir()` | 絶対パスなら採用。相対パスまたは空文字は採用せず、上記 fallback | `STRATA_DESKTOP_DATA_DIR` が設定されていれば `data_dir()` はそれを直接返す |
| `packaging/install.sh` | `${HOME}/.local/share/strata` | 値をそのまま使い、`strata` を付加 | 空でない `STRATA_DATA_DIR` が優先 |

Python と JavaScript の component-dir 実装は絶対パス検査をしません。非空の相対値も相対パスとして使います。Python の `or` と JavaScript の `||`、および shell の `${VAR:-fallback}` は空文字を fallback として扱います。Rust は `var_os` で設定有無を確認しますが、その後 `is_absolute()` を通る値だけを採用するため、空文字も fallback になります。大文字小文字の比較や数値変換はありません。

## 有効になる条件

- Python の component path は、既定では `strata_control.engine_component.components_dir()` が必要になる Control/CLI の処理に適用されます。たとえば `strata update` は `--components-dir` がなければこの関数を使い、`STRATA_COMPONENTS_DIR` がなければ `XDG_DATA_HOME` を参照します。Control の `discovery` も同じ関数へ委譲します。
- Terminal の起動時 handover は `strata.py` の早い段階で `strata_cli.handover.maybe_hand_over()` を呼びます。そこで `STRATA_COMPONENTS_DIR` または標準の per-user path から `control/active.json` を探します。XDG のパスに有効な新しい Control がなければ、XDG 値だけで handover は起きません。
- Host の `componentsDirectory()` は Windows では `LOCALAPPDATA` 側の分岐を使い、`XDG_DATA_HOME` を読みません。非 Windows で計算した component path は engine の導入や Control の選択などに渡されます。Control 子プロセスの環境には計算済みの `STRATA_COMPONENTS_DIR` が設定されるため、その子プロセスでは XDG 値よりそちらが優先されます。
- Rust の `platform_data_dir()` は `cfg(not(windows))` です。`data_dir()` は `STRATA_DESKTOP_DATA_DIR` が存在すれば XDG 分岐より先にそれを返します。起動ログ、crash log、`--save-logs` が参照するログ/runtime path にデータディレクトリが使われます。
- `packaging/install.sh` は Linux/macOS 向けの Terminal インストールスクリプトです。`STRATA_DATA_DIR` が空でなく設定されている場合は XDG 値を見ません。

## 実行時の詳細

Python は `components_dir()` の呼び出し時に渡された mapping（通常は `os.environ`）を読みます。判定結果を module-level cache には保存しません。Host の JavaScript 実装も `componentsDirectory()` の呼び出しごとに `env`（既定は `process.env`）を参照します。Rust の `data_dir()` も呼び出しごとに環境を参照し、`OnceLock` 等で XDG 値を cache していません。これらは呼び出し前に同一プロセスの環境が変更されれば、その後の呼び出しで新しい値を使います。

Shell installer は起動時に `DATA_DIR` を一度設定します。その実行中に環境が変わっても再評価されません。設定先は `$DATA_DIR/terminal/$version` で、同じ領域の `terminal/current` symlink を更新します。

## 根拠

- Python component path、`STRATA_COMPONENTS_DIR` の優先、空値 fallback: `strata_control/engine_component.py:176-186`。同じ規則を用いる handover 側: `strata_cli/handover.py:34-42,70-74,126-134`。起動時呼び出し: `strata.py:32-36`。
- update CLI の明示 path と既定 component path: `strata_cli/update_cmd.py:174-195`。component path を install/settings path に使う discovery helper: `strata_control/discovery.py:44-56`。
- Host の platform 分岐と component-dir 既定値: `apps/host/server/control-runtime.mjs:26-31`。Control 子プロセスへの computed `STRATA_COMPONENTS_DIR` の設定: 同 `:77-89`。Host 側の利用例: `apps/host/server/index.mjs:132-136,178-192`。
- デスクトップ shell の環境優先、絶対パス判定、fallback、ログと runtime への適用: `apps/desktop/src-tauri/src/desktoplog.rs:31-62,123-130,281-289,310-340`。
- インストーラーの優先順位と出力先: `packaging/install.sh:20-27,92-104,120-123`。
