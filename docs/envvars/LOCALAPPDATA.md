# `LOCALAPPDATA`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。Strata が値を明示的に参照する処理だけを記載する。Windows 自身や外部ライブラリによる扱いは対象外。

## 役割

Windows では、Strata Terminal/Control のユーザー単位データ、コンポーネント、状態、デスクトップログなどの既定位置を決めるために参照されます。主な既定ルートは `%LOCALAPPDATA%\Strata` です。アプリや Control は `STRATA_COMPONENTS_DIR`、`STRATA_DESKTOP_DATA_DIR`、`STRATA_DATA_DIR` などの個別指定を優先する経路があります。

## 値と判定

`LOCALAPPDATA` 自体は Strata 共通の形式検査や正規化を受けません。各読み取り箇所が空文字をどう扱うか、パスを絶対パスに制限するかは異なります。

| 使用箇所 | 空文字・未設定時 | 設定値の扱い |
|---|---|---|
| Python の状態・コンポーネント既定値 | 空文字または未設定なら `Path.home()/AppData/Local` | `Strata` などのサブフォルダーを付ける。値をそのまま `Path` に渡す |
| Node の Host パス | 空文字または未設定なら `USERPROFILE`（なければ Node の home）下の `AppData\\Local` | Windows の `\\` 区切りでサブフォルダーを追加 |
| Rust デスクトップデータ | 空文字または未設定なら `USERPROFILE\\AppData\\Local`、それもなければ temp dir | `var_os` で取得し、絶対パスの場合だけ採用。相対パスは fallback |
| SYCL prefill cache | `HOME` が設定されていればそちらを使うため参照しない。`HOME` もない場合、未設定ならキャッシュパスなし | `STRATA_CACHE_DIR` が空または未設定の場合に限り、値へ `/strata/i8-crossover.txt` を連結 |
| PowerShell Terminal installer | `STRATA_DATA_DIR` も空ならエラー終了 | 空でない `STRATA_DATA_DIR` があればそちらを優先。なければ値に `\\Strata` を連結 |
| Windows セットアップバッチ | Python の既知フォルダー検索で値を使う | `%LOCALAPPDATA%\\Programs\\Python\\Python{313,312,311,310}\\python.exe` を順に調べる |

Python/Node の主要パス関数では値が空文字かどうかだけを確認し、存在確認や絶対パス検査はしていません。Rust ログ保存経路だけは絶対パスを条件とします。PowerShell では空文字は未設定と同様に扱われます。

## 有効になる条件

- Python の `state_base()` と `components_dir()` は Windows 分岐でのみこの変数を使います。`STRATA_COMPONENTS_DIR` が truthy ならコンポーネント位置にはそちらを使います。状態位置には `STRATA_STATE_DIR` ではなく `STRATA_TUNE_DIR` / `STRATA_TIMESKIP_DIR` のような用途別 override が呼び出し側で使われることがあります。
- Host の `stateRoot()` と `componentsDirectory()` も `platform === 'win32'` の場合に参照します。コンポーネント位置は `STRATA_COMPONENTS_DIR` を優先し、状態の tuning/time-skip 位置はそれぞれ `STRATA_TUNE_DIR` / `STRATA_TIMESKIP_DIR` があれば上書きします。
- Rust デスクトップは Windows ビルドでのみ `LOCALAPPDATA` を調べます。さらに `STRATA_DESKTOP_DATA_DIR` が OS 環境に存在すれば、空文字であっても `var_os` の値が先に採用され、`LOCALAPPDATA` の既定処理へ進みません。
- SYCL の crossover cache では `STRATA_CACHE_DIR` が非空ならそれが優先され、次に `HOME` が設定されていれば `$HOME/.cache/strata` を使います。`LOCALAPPDATA` はその両方が使えないときの代替候補です。
- `strata_control.private_files` は `LOCALAPPDATA` が truthy なら Windows 以外でもユーザーデータ root として候補に加えます。実際の修復処理 `repair_known_roots()` 自体は Windows 以外では何もしません。

## 実行時の詳細

Python の `state_base()` は `LOCALAPPDATA/Strata` を返し、その下に runtime、tuning、time-skip、プロセス状態などが作られます。コンポーネント位置は `LOCALAPPDATA/Strata/components` で、同じ基準から隣接する `install` と `app-settings.json` の位置も導かれます。関数は呼び出し時に環境 mapping を参照し、値をプロセス起動時に固定するキャッシュはありません。

Node Host は同じ基準でユーザー状態・components の位置を組み立てます。Windows のブラウザー探索では値を候補ルートに加え、Chrome/Edge/Chromium の実行ファイルを探します。Cloudflared 探索では `LOCALAPPDATA/Microsoft/WinGet/Links` を追加候補にします。Terminal の cloudflared 探索も同じ WinGet Links パスを候補にします。Agent bridge はこのルートをファイル追跡の除外対象に加え、Agent の子プロセス環境を作る処理は `LOCALAPPDATA` を許可環境変数として残します。

Windows デスクトップの Rust `data_dir()` は、ログと runtime の場所に `LOCALAPPDATA/Strata`（絶対パスの場合）を使用します。fallback は順に `USERPROFILE/AppData/Local/Strata`、一時ディレクトリ下の `Strata` です。明示的な `STRATA_DESKTOP_DATA_DIR` がある場合はこの解決より優先されます。

PowerShell の Terminal installer は `STRATA_DATA_DIR` がなく、かつ `LOCALAPPDATA` も空なら、`STRATA_DATA_DIR` を設定するよう案内して終了します。続行時は選ばれたデータディレクトリの下に `terminal/<version>` を作り、配布物をそこへ展開します。`START-HERE.bat` は PATH や `py` launcher で Python が見つからない場合に限り、`LOCALAPPDATA` 下のバージョン別 Python を探します。

デスクトップアプリの NSIS installer は `$LOCALAPPDATA\Programs\Strata` をアプリ本体の既定インストール先に使います。旧バージョンのインストール移行先の判定や、アンインストール時にデータフォルダーを削除する対象の組み立ても `$LOCALAPPDATA` を参照します。アンインストールの確認画面と削除条件は同ファイル内に実装されています。

SYCL prefill は INT8/FP16 の crossover 測定値キャッシュを `i8-crossover.txt` に読み書きします。キャッシュファイルが開けない場合は read miss になり、書き込み側もディレクトリ作成・ファイル更新に失敗した場合は cache を利用できません。`LOCALAPPDATA` はファイル名の組み立てに使うだけで、Windows に限定した分岐ではありません。

## 根拠

- Python の状態ルートとその利用: `strata_control/paths.py:13-21`, `strata_control/runtime.py:101-111`, `strata_cli/cli.py:1483,1650`, `strata_control/procs.py:194`。
- Python の components と隣接位置: `strata_control/engine_component.py:176-190`, `strata_control/discovery.py:44-56`。
- Node Host の状態・components 位置: `apps/host/server/platform-paths.mjs:16-32`, `apps/host/server/control-runtime.mjs:26-31`。
- Browser/Cloudflared 探索と Agent: `apps/host/server/agent/browser-probe.mjs:9-18`, `apps/host/server/cloudflared-find.mjs:57-68`, `strata_cli/launch/access.py:74-94`, `apps/host/server/agent/agent-bridge.mjs:130-135`, `apps/host/server/agent/harness-runtime.mjs:20-33`。
- Rust のデータ・ログ位置: `apps/desktop/src-tauri/src/desktoplog.rs:31-59,320-340`。
- SYCL crossover cache: `sycl/src/prefill/prefill.cpp:858-885`。
- Windows installer と初回セットアップ: `packaging/install.ps1:45-68`, `START-HERE.bat:57-65`。
- デスクトップ NSIS installer の配置・移行・アンインストール: `apps/desktop/src-tauri/nsis/installer.nsi:559,690-740,983-987,1043-1046`。
- ユーザーデータ root と Windows 修復: `strata_control/private_files.py:415-430,506-545`。
