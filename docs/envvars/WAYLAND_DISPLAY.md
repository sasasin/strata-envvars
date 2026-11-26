# `WAYLAND_DISPLAY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata はこの変数を、グラフィカルなデスクトップセッションの判定と desktop app の診断情報収集に使う。setup と serve では `DISPLAY` と合わせて「画面セッションがあるか」を判定し、条件を満たした場合に VRAM reserve の推奨を表示する。値によって reserve や engine の設定を自動変更するものではない（`terminal/setup.py:9021-9024`、`terminal/strata_control/setup_config.py:417-419`、`terminal/serve/server_parts/http_api.py:119-122,125-142`）。

desktop app では、クラッシュ報告または `--save-logs` の診断ファイルに環境変数の値を記録する対象名の一つである（`app/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320`）。

## 値と判定

| 読み取り経路 | unset / 空文字 | 判定される値 | 無効になる値 |
|---|---|---|---|
| setup の `linux_desktop()` | 未設定または空文字は偽 | Linux (`sys.platform.startswith("linux")`) で、`WAYLAND_DISPLAY` または `DISPLAY` のどちらかが空でない文字列なら真 | Linux 以外では常に偽。`WAYLAND_DISPLAY` が未設定・空でも、`DISPLAY` が非空なら真 |
| serve の `linux_desktop()` | 未設定または空文字は偽 | `os.name != "nt"` かつ `sys.platform != "darwin"` で、`WAYLAND_DISPLAY` または `DISPLAY` が非空なら真 | Windows / Darwin では偽。Wayland 値が未設定・空でも `DISPLAY` が非空なら真 |
| desktop app の診断 `graphics_environment()` | 未設定なら記録しない。空文字は設定値として `WAYLAND_DISPLAY=` と記録 | Unicode 文字列として取得できれば値をそのまま記録 | `std::env::var` が値を取得できない場合（未設定または Unicode 文字列でない場合）は項目を省く |

Python 側は `env.get("WAYLAND_DISPLAY")` の戻り値を `or` と `bool` に渡すだけで、文字列の parse、空白除去、大文字小文字変換はしない。したがって `"0"`、`"false"`、`"wayland-0"`、空白だけの文字列はいずれも非空なので真、`""` は偽となる。数値境界の概念はない。`DISPLAY` も同じ判定に使われる（`terminal/setup.py:9021-9024`、`terminal/serve/server_parts/http_api.py:119-122`）。

## 有効になる条件

- setup の reserve 推奨では、Linux であることに加えて `hip` backend であり、`--vram-reserve-mib` が指定されていないことが必要。さらに `multi` でなく、先行する小容量 GPU 用案内の条件（単体 GPU で `0 < vram_gb < 7.5`）に当てはまらないことが必要。条件成立時に推奨文を表示するだけで、設定は変更しない（`terminal/setup.py:8769,9021-9033`、`terminal/strata_control/setup_config.py:410-419`）。
- serve の起動後の VRAM note では、通常の単一 engine 経路（replica group も layer split もない）、backend が `hip`、モデル読み込み後の `vram_free_mib` が整数かつ 2048 未満であることが必要。reserve は engine 引数 `--vram-reserve-mib` の値を整数変換し、引数なしなら 700 MiB とする。整数変換に失敗した場合も 700 MiB に戻る。reserve が 3072 MiB 以上なら note を出さない（`terminal/serve/server_parts/http_api.py:116,125-142`、`terminal/serve/server.py:9472-9483`）。
- `WAYLAND_DISPLAY` 単独では両経路を有効にしない。上記 OS 条件と `DISPLAY` との OR 判定を通過した後、backend・GPU 状態・CLI 引数などの条件も必要である。
- desktop app の診断記録は上述の VRAM/backend 条件と無関係で、`graphics_environment()` が呼ばれた時点で値を読み直す（`app/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320`）。

## 実行時の詳細

setup の `linux_desktop()` は `env` 引数を省略すると `os.environ` を参照する。`setup_config` がそれを呼ぶのは GPU 設定の案内を組み立てる場面で、`hip` かつユーザー指定の reserve がない場合に限られる（`terminal/setup.py:9021-9024`、`terminal/strata_control/setup_config.py:410-419`）。

serve も `linux_desktop()` の既定引数でプロセス環境を読み、engine 起動後に判定する。replica / split 経路では呼ばれず、通常経路では条件に合う場合だけ note を標準出力へ出す。結果を cache するコードはなく、setup と serve の呼び出しごとに判定する（`terminal/serve/server_parts/http_api.py:119-122`、`terminal/serve/server.py:9472-9483`）。

desktop app の `graphics_environment()` は名前一覧 `NAMES` をループし、`std::env::var(n)` で各値を取得する。クラッシュ報告の生成時、および `--save-logs` の保存時に呼ばれ、結果は `Graphics session:` の下に記録される。各呼び出し時に環境を読み、値を加工・転送して別プロセスの環境に設定する処理はこの箇所にはない（`app/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320`、`app/desktop/src-tauri/src/supervisor.rs:465-475,484-493`）。

## ログと測定値

- setup が上記条件を満たすと、`desktop_reserve_note()` の2行を `say("  " + line)` で表示する。文面は `If this AMD card also drives your desktop and the desktop or apps crash once the model is loaded, keep more VRAM free: ./setup.sh --vram-reserve-mib 3072` と、reserve に関する補足（`terminal/setup.py:9027-9033`、`terminal/strata_control/setup_config.py:417-419`）。
- serve では条件成立時に `[strata] note: ...` から始まる推奨を `print(..., flush=True)` で標準出力へ出す。VRAM 空き量、`--vram-reserve-mib 3072` の提案、expert cache に使える量の差を含む（`terminal/serve/server_parts/http_api.py:138-142`、`terminal/serve/server.py:9480-9483`）。
- desktop app のクラッシュ報告と保存ログは、取得できた場合に `  WAYLAND_DISPLAY=<値>` の行を `Graphics session:` 節へ含める。これは環境値の記録であり、Strata による値の警告や検証結果ではない（`app/desktop/src-tauri/src/desktoplog.rs:186-194,254-259,310-320`）。
- この変数による性能測定値は該当しない。

## 根拠

- `terminal/setup.py:9021-9033`
- `terminal/strata_control/setup_config.py:178-190,410-423`
- `terminal/serve/server_parts/http_api.py:116-142`
- `terminal/serve/server.py:9472-9483`
- `app/desktop/src-tauri/src/desktoplog.rs:186-194,241-259,310-320`
- `app/desktop/src-tauri/src/supervisor.rs:465-475,484-493`
