# `STRATA_ROCM_VERSION`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査日の Strata 作業ツリーは `main...origin/main` で、未コミット変更はありません。外部ライブラリや GPU driver 自身が読む同名変数は対象外です。

## 役割

HIP エンジンをソースから用意するときに使う ROCm のバージョンを指定する、セットアップ／ビルド時の変数です。Strata の実行エンジンが起動時に読む変数ではありません。

Linux の `setup.py` は、まず利用可能な system ROCm を選びます。その経路ではこの変数は使われません。system ROCm が条件を満たさない場合に TheRock の Python wheel を選び、この変数が空でないと wheel の exact version として使います。Windows の `tools/hip/build_windows.bat` は別実装で、既定値 `10.2.0a20260930` を設定して Python wheel の導入とパッケージ作成へ渡します。根拠: `setup.py:3657-3664,4690-4728`; `tools/hip/build_windows.bat:13-28,41-51,113-115`。

## 値と判定

| 経路 | 未設定・空文字 | 非空値 | 既定値・制約 |
|---|---|---|---|
| Linux `setup.py` の TheRock wheel 経路 | `os.environ.get(...) or None` により unset と空文字は同じ扱い。arch family ごとの pin、なければ `7.10.0a20251120` を希望値にし、index の一覧を取得して同じ minor line、次いで同じ major の最新 wheel を選ぶ | trim、形式検査、範囲検査をせず、文字列を exact version として使う。index の一覧検索や自動 pin 選択を行わない | family pin は `gfx103X-all=7.13.0a20260515`, `gfx110X-all=7.10.0a20251121`, `gfx1151=7.14.0a20260608`。その他は `7.10.0a20251120`。invalid／存在しない版は pip の失敗経路へ進む |
| Windows `tools/hip/build_windows.bat` | `if not defined` により unset または空の変数には `10.2.0a20260930` を設定 | 非空値をそのまま `rocm[extras]==<値>` と `package_windows.py --rocm-version <値>` に渡す | batch 内でバージョン形式・範囲は検証しない。pip install が失敗すると batch は exit code 1 で終了する |

Linux では CLI に同等のバージョン引数はありません。`--backend hip` は HIP 経路を選びますが、ROCm バージョンはこの環境変数で指定します。なお同じ `setup.py` 実行でも `ROCM_PATH`（未設定なら `/opt/rocm`）に `hipcc`、hipBLAS、必要な開発ファイルがあり、ROCm version が 7.0 以上（ヘッダーが読めない場合も開発ファイルが揃えば可）なら system install が採用され、`STRATA_ROCM_VERSION` は無視されます。根拠: `setup.py:4690-4710,9207-9210`。

## 有効になる条件

- Linux の setup で AMD/HIP engine の build が必要になり、`rocm_root()` が TheRock wheel 経路に進む場合に使われます。既存 engine がソース／arch 条件を満たす場合は build を省略します。HIP image reader の GPU build で ROCm を再解決する場合にも呼ばれます。根拠: `setup.py:4784-4809,4876-4900,5032-5037,7772-7799`。
- Linux で複数の GPU family の index が必要な場合、system ROCm が使えなければ wheel 選択前に `fail()` で止まります。異なる family の wheel index は混ぜられません。根拠: `setup.py:4707-4711`。
- `--backend hip` の Windows setup は `setup.py` 内では ready-made engine を使い、`--build` も Windows では失敗します。Windows 向けソース build は同梱の `tools/hip/build_windows.bat` が担当し、そこで独自の既定値を使います。根拠: `setup.py:7779-7785`; `tools/hip/build_windows.bat:1-11,24-28`。
- Windows batch では `.rocm-win/strata-rocm.txt` の記録が希望 version と arch extras に一致すると pip install を省略します。`STRATA_ROCM_KEEP=1` なら stamp が違っても pip install を省略します。その場合、変数の値は package の `--rocm-version` に渡りますが、既存 venv の ROCm をその値に更新しません。根拠: `tools/hip/build_windows.bat:41-51,113-115`。

## 実行時の詳細

`setup.py` はモジュール読み込み時に `ROCM_VERSION_OVERRIDE` を一度だけ設定します。後から同一プロセスの環境を書き換えても、この定数は再評価されません。TheRock index と対応版の自動選択は override がない場合だけ実行し、ネットワーク取得に失敗した場合は希望版を保ちます。gfx1151 で ROCm 7.11 未満を指定した場合は、Strix Halo と新しい kernel の組み合わせに関する warning を追加します。根拠: `setup.py:3657-3664,3737-3773`。

Linux wheel 経路では `.strata-rocm.json` の index/version stamp と venv 内 SDK の有無を見て再利用します。通常の family pin が既に入っていれば lookup を省略しますが、override が非空ならこの pin cache 条件を通らず、override を再評価します。それでも stamp の version/index が選択値と同じなら pip install は省略されます。異なる場合は `rocm[libraries,devel]==<version>` を pip に渡し、同じ version で index だけ違う場合は先に `rocm==<version>` を `--force-reinstall --no-deps` で入れ直します。選択した SDK の compiler が見つからない場合は `fail()` で setup を停止します。根拠: `setup.py:4712-4743`。

`rocm_pick()` が index にない preferred version を代替できない場合は warning を作ります。override 指定時はこの index fallback を通らないため、無効／未提供の文字列を Strata 自身が補正することはありません。pip の非ゼロ終了は `run()` が `command failed (exit N): <command>` を表示し、`fail()` が `Setup stopped...` を表示して exit 1 にします。Windows batch の pip、`rocm-sdk init`、build、package コマンドも失敗時に `exit /b 1` します。根拠: `setup.py:3741-3751,3754-3773,4722-4733,900-909,959-978`; `tools/hip/build_windows.bat:47-51,72-85,95-115`。

`docs/AMD_HIP.md` は `STRATA_ROCM_VERSION` を ROCm wheel の override と説明しています。ソース上では Linux の system ROCm が条件を満たせばこの指定は使われず、Windows batch には別の既定値があります。したがって適用範囲は上記の実装条件に従います。参照: `docs/AMD_HIP.md:112-116`。

## 根拠

- 全参照検索: `setup.py:3657,3662-3663,3749,3751,3757-3760,4715-4719`; `tools/hip/build_windows.bat:18,27,44,48-49,115`。ほかの一致箇所は `setup.py` 内のコメント／warning 文および `docs/AMD_HIP.md` の説明です。
- 変数はビルド・セットアップ用途です。実行エンジンやサーバーが実行時に読み取る箇所は見つかりませんでした。
