# `LOCALAPPDATA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`LOCALAPPDATA` は Strata の Windows 向けコードで、ユーザー別データや状態の保存場所、Windows のアプリ・connector・browser の候補パスを組み立てるために参照される。また、Terminal インストーラーは既定のデータ格納場所を決める。単一の共通 parser はなく、未設定・空文字・相対パスの扱いは各利用箇所で異なる。

## 値と判定

| 利用箇所 | 未設定・空文字 | 値の変換・制限 |
| --- | --- | --- |
| Windows の Node/Python 状態・component パス | 未設定または空文字なら `USERPROFILE`（Node）または `Path.home()`（Python）の `AppData/Local` に fallback | 文字列をそのままパスの先頭に使う。正規化・絶対パス検証なし。Node は `LOCALAPPDATA || ...`、Python は `environ.get(...) or ...`。 |
| Windows デスクトップログ等 | 未設定、空文字、相対パスなら `USERPROFILE/AppData/Local` に fallback。`USERPROFILE` もなければ temp | `var_os` で OS 文字列として読み、`PathBuf` 化後に絶対パスだけ採用。 |
| SYCL prefill crossover cache | 未設定なら `HOME` も未設定の場合に限り値を使う。空文字でも `getenv` は設定ありとみなし、`/strata/i8-crossover.txt` を組み立てる | `STRATA_CACHE_DIR` が非空ならそちら、そうでなければ `HOME` が設定されていれば `$HOME/.cache/strata` が優先。LOCALAPPDATA は `HOME` が未設定のときだけ `/strata` の基底となる。 |
| cloudflared / browser 候補検索 | 空文字・未設定は候補を追加しない | Windows でのみ値をディレクトリとして連結。パス検証は候補検索側ではしない。 |
| `tools/packaging/install.ps1` | `STRATA_DATA_DIR` も未設定または空なら停止し、エラーを表示 | `STRATA_DATA_DIR` が truthy なら優先。そうでなければ `LOCALAPPDATA/Strata` をデータ先にする。 |
| Desktop NSIS installer | NSIS の `$LOCALAPPDATA` path variable を使う | current-user install は `Programs/Strata` に置き、旧 install の移行元・uninstall 時の Strata data 削除対象にも使う。uninstall の Strata data 削除は値が空でない場合だけ実行する。 |
| その他の Windows 読み取り | 値の有無で読み取り対象への追加・パス検証を行う | `private_files.py` は truthy の値だけ使う。updater は `var_os` で取得した値をパス比較関数に渡す。 |

環境変数値そのものの数値変換や真偽文字列の解釈はありません。`LOCALAPPDATA=0`、`true`、`false`、空白だけの値も、truthy 判定で弾かれない箇所では文字列パスとして扱われます。絶対パスを検査するのは desktop shell が採用する値であり、updater では `LOCALAPPDATA` 自体ではなく、比較対象のインストール先を検査します。大文字小文字を無視するのは agent の環境変数名 allowlist だけで、Windows パス比較の規則をここで統一するものではありません。根拠: `app/host/server/platform-paths.mjs:17-23`、`terminal/strata_control/paths.py:13-21`、`app/desktop/src-tauri/src/desktoplog.rs:31-47`、`engine/sycl/src/prefill/prefill.cpp:958-965`、`tools/packaging/install.ps1:114-115`、`terminal/strata_control/private_files.py:418-432`、`app/desktop/src-tauri/src/updater.rs:82-108`。

## 有効になる条件

- Node/Python の状態保存先は Windows 分岐で使われる。Node は `<LOCALAPPDATA>\\Strata`、Python は `<LOCALAPPDATA>/Strata` を状態基底にする。Node 側の `STRATA_TUNE_DIR` / `STRATA_TIMESKIP_DIR`、Python 側の `STRATA_RUNTIME_DIR` など用途別 override があれば、該当する保存先はそちらが優先される。component 置き場では `STRATA_COMPONENTS_DIR` が `LOCALAPPDATA` より優先される。Linux/macOS のこれらの分岐は `XDG_STATE_HOME` / `XDG_DATA_HOME` を使う。根拠: `app/host/server/platform-paths.mjs:17-32`、`app/host/server/control-runtime.mjs:26-30`、`terminal/strata_control/paths.py:13-21`、`terminal/strata_control/engine_component.py:179-189`。
- Python の `strata_control.discovery.components_dir()` と Terminal の `strata_cli.handover.components_dir()` も Windows で同じ component 既定値を使う。ここでは `STRATA_COMPONENTS_DIR` が truthy ならそちらが優先される。根拠: `terminal/strata_control/discovery.py:47-59`、`terminal/strata_cli/handover.py:34-42`。
- デスクトップ shell は Windows build の `platform_data_dir()` で値を使い、`STRATA_DESKTOP_DATA_DIR` が設定されていれば `data_dir()` が先にそれを返す。data dir はログ、runtime、shell preferences 等の基底になる。LOCALAPPDATA が相対パスなら採用されず、USERPROFILE、最後に temp へ fallback する。根拠: `app/desktop/src-tauri/src/desktoplog.rs:31-62`、`:122-132`、`:320-335`、`app/desktop/src-tauri/src/shell.rs:34`。
- Windows の Terminal インストーラーは、Windows x64 と release feed の検査を通過した後にこの値を使う。`STRATA_DATA_DIR` が truthy ならそちらが優先され、両方 truthy でなければ明示的なエラーで終了する。根拠: `tools/packaging/install.ps1:100-115`。
- Desktop の NSIS installer は `$LOCALAPPDATA` path variable を current-user install の既定先 `<LOCALAPPDATA>\Programs\Strata` に使い、旧 `<LOCALAPPDATA>\Strata` からの移行を呼び出す。uninstall の fresh-start 処理では `$LOCALAPPDATA` が空でないときだけ `<LOCALAPPDATA>\Strata` を再帰削除し、保存済み install path が `<LOCALAPPDATA>\Strata` と一致する場合は再利用しない。これは NSIS installer 内の path variable 使用で、Rust/Python の環境取得 API とは別の経路。根拠: `app/desktop/src-tauri/nsis/installer.nsi:558-560,740,981-988,1040-1047`。
- SYCL の int8/FP16 crossover 選択でのみ、キャッシュ用パスの最後の fallback として参照される。`STRATA_PREFILL_MMQ=auto` で該当する expert group の crossover が必要になり `i8_calibrate()` が初回実行される経路で、queue・format ごとのメモリ内 cache に未登録の場合にファイル cache を読み、なければ測定・書き込みを試みる。`STRATA_CACHE_DIR` が非空、または `HOME` が設定済みなら `LOCALAPPDATA` は使われない。根拠: `engine/sycl/src/prefill/prefill.cpp:958-965`、`:1006-1018`、`:4862-4877`。
- cloudflared 探索では Windows で値が truthy の場合だけ `%LOCALAPPDATA%/Microsoft/WinGet/Links/cloudflared.exe` を候補に追加する。Python 側の同等の候補追加も Windows かつ値が truthy の場合だけ。候補が実行可能でバージョン条件を満たすかは後続処理で判定される。根拠: `app/host/server/cloudflared-find.mjs:43-70,95-110`、`terminal/strata_cli/launch/access.py:122-146`。
- browser probe は Windows で `LOCALAPPDATA` が truthy のとき Chrome、Edge、Chromium の検索 root に加える。ファイルが存在する場合だけ `findBrowser()` がその候補を返す。根拠: `app/host/server/agent/browser-probe.mjs:9-18,34-45`。
- Windows のファイル所有権・修復処理では `private_files.py` が truthy の値をユーザーデータ root に追加する。既知 root は `<LOCALAPPDATA>/Strata` が存在する場合に走査対象になる。`repair_known_roots()` 自体は Windows 以外では直ちに空の結果を返す。根拠: `terminal/strata_control/private_files.py:418-442,509-540`、呼び出し元 `terminal/strata_cli/cli.py:2175-2188`。
- デスクトップ updater は Windows の installer 起動時に値を受け取り、実行中 install 先が `<LOCALAPPDATA>/Strata` そのものなら NSIS の `/D=` 指定を拒否する。`LOCALAPPDATA` が未設定ならこの特定の比較は行われない。根拠: `app/desktop/src-tauri/src/updater.rs:82-117,312-337`。
- agent Harness の起動時には `agentEnvironment()` が環境を allowlist で絞り、`LOCALAPPDATA` を含む許可名を値ごと子プロセス環境にコピーする。これは変数値による Strata 内分岐ではなく、外部コマンド環境への転送。agent の file tracker では値を除外 root に含める。根拠: `app/host/server/agent/harness-runtime.mjs:20-36,75-83`、`app/host/server/agent/agent-bridge.mjs:181-190`。

## 実行時の詳細

- Node/Python のパス関数は既定引数として実プロセス環境を受け取り、呼び出し時に値からパスを組み立てる。値を環境変数として static cache するコードは確認できない。Node の `stateRoot()` は Windows で `Strata` を基底にし、tuning、Time-skip、温度 probe 等の配置に利用される。Python の `state_base()` は runtime / tuning / time-skip / process records の基底に使われる。根拠: `app/host/server/platform-paths.mjs:17-32`、`app/host/server/temperature-telemetry.mjs:100-108`、`terminal/strata_control/paths.py:13-21`、`terminal/strata_control/runtime.py:128-145`、`terminal/strata_control/procs.py:192-200`。
- component の既定パスは desktop host と Control、Terminal が共有し、engine component / Control install / app settings などの親フォルダーを決める。`STRATA_COMPONENTS_DIR` が指定されると通常の LOCALAPPDATA 由来の既定先を置き換える。根拠: `app/host/server/control-runtime.mjs:26-30,37-43`、`terminal/strata_control/engine_component.py:179-193`、`terminal/strata_control/discovery.py:47-59`。
- SYCL cache の環境変数は `i8_cache_file()` が呼ばれるたびに評価される。キー一致のファイルが読めれば crossover を再利用し、読めない・一致しない場合は測定後に書き込みを試す。書き込み先を開けないときは `mkdir` を一度試し、再度失敗しても return し、LOCALAPPDATA 固有の警告や終了はない。根拠: `engine/sycl/src/prefill/prefill.cpp:958-1002,1015-1018,1126-1129`。
- `START-HERE.bat` は `py -3`、次に PATH 上の `python` を試した後、`LOCALAPPDATA\Programs\Python\Python313` から `Python310` までの `python.exe` を候補として調べる。LOCALAPPDATA の値を変更する処理ではなく、起動時の候補探索。根拠: `START-HERE.bat:68-76`。

## ログと測定値

LOCALAPPDATA の採用・fallback だけを知らせるログは確認できない。Terminal setup installer では `STRATA_DATA_DIR` と `LOCALAPPDATA` の両方が無効な場合、`Windows did not say where your user folder is...` を出して終了する（`tools/packaging/install.ps1:114`）。SYCL crossover cache が使われた場合は stderr に `strata: int8 experts: crossover ... from the cache ...`、測定された場合は `strata: int8 experts, measured here ...` が出る。これらは crossover の cache hit / 測定を示し、LOCALAPPDATA の値自体は表示しない（`engine/sycl/src/prefill/prefill.cpp:1015-1018,1126-1128`）。性能測定値は新たに取得していない。

## 根拠

- Windows のパス既定値: `app/host/server/platform-paths.mjs:17-32`、`terminal/strata_control/paths.py:13-21`、`terminal/strata_control/engine_component.py:179-189`、`terminal/strata_cli/handover.py:34-42`。
- Desktop shell の data/log path: `app/desktop/src-tauri/src/desktoplog.rs:31-62,122-132,320-335`。
- SYCL cache fallback: `engine/sycl/src/prefill/prefill.cpp:958-1002,1015-1018,1126-1129,4862-4877`。
- Windows installer / Python discovery: `tools/packaging/install.ps1:100-115`、`START-HERE.bat:68-76`。
- Desktop installer: `app/desktop/src-tauri/nsis/installer.nsi:558-560,740,981-988,1040-1047`。
- Candidate search, file roots and child environment: `app/host/server/cloudflared-find.mjs:43-70`、`app/host/server/agent/browser-probe.mjs:9-45`、`terminal/strata_cli/launch/access.py:122-146`、`terminal/strata_control/private_files.py:418-442,509-540`、`app/host/server/agent/harness-runtime.mjs:20-36,75-83`、`app/host/server/agent/agent-bridge.mjs:181-190`。
- Updater install-target guard: `app/desktop/src-tauri/src/updater.rs:82-117,312-337`。
