# `STRATA_ROCM_VERSION`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Linux の setup が AMD HIP engine 用 TheRock ROCm wheel を `.venv` に入れる経路で、選択する ROCm `rocm` package のバージョンを固定する。空でない値ならインデックスの一覧を引いて候補を選ぶ処理を通らず、その文字列を一つの指定バージョンとして使う。適切な system ROCm が見つかった場合は wheel を選ばないため、この変数はその system ROCm を切り替えない。通常の Windows セットアップは ready-made HIP engine を使い、この変数は `terminal/tools/hip/build_windows.bat` で Windows 用 engine をビルドする経路に使われる（`terminal/setup.py:4424-4452, 4546-4565, 5550-5599`; `terminal/setup.py:16-19`; `terminal/tools/hip/build_windows.bat:2-5, 28-30, 37-53`）。

## 値と判定

| 経路 | 未設定 | 有効になる値 | 空文字・無効値 |
|---|---|---|---|
| Linux `terminal/setup.py` の TheRock wheel 経路 | family 別 pin（未登録 family は `7.10.0a20251120`）を優先し、index の一覧を使って代替版を選ぶ | 空でない文字列をそのまま指定版として使用。例: `7.12.0a20260311` | 空文字は `or None` により未設定と同じ。値の形式・大文字小文字・前後空白・バージョン妥当性をここでは検証・正規化しない。たとえば `bad`, `7.12`, ` 7.12.0 ` も override として渡される |
| Windows `terminal/tools/hip/build_windows.bat` | `10.2.0a20260930` を設定 | 変数の値をそのまま `rocm[extras]==<値>` に使う | `if not defined` のため未定義または空なら既定値を設定。形式検証はなく、pip の指定にそのまま渡す |

Linux の読み取りは `os.environ.get("STRATA_ROCM_VERSION") or None`。したがって `unset` と `""` は同じ扱いで、`"0"` や空白だけの値は truthy な override になる。文字列を数値化したり、値の一部だけを比較したりはしない（`terminal/setup.py:4451-4452, 4546-4560`）。Linux の override がない場合、`gfx103X-all` は `7.13.0a20260515`、`gfx110X-all` は `7.10.0a20251121`、`gfx1151` は `7.14.0a20260608`、それ以外は `7.10.0a20251120` が選択候補となる（`terminal/setup.py:4447-4450, 4551-4560`）。

## 有効になる条件

- Linux では HIP engine をソースからビルドするとき、または HIP 画像 reader をビルドするときに `rocm_root()` が wheel 経路を選ぶこと。engine が既に有効でソース変更もなく再ビルドしない起動では、ROCm の再選択は呼ばれない（`terminal/setup.py:5669-5682, 5750-5765`）。
- `rocm_root()` は先に `ROCM_PATH`（未設定なら `/opt/rocm`）などから system ROCm を探索する。`hipcc` と hipBLAS library があり、ROCm version が不明または 7.0 以上で、HIP development files が欠けていなければ system ROCm を返すため、この場合 `STRATA_ROCM_VERSION` は wheel の選択に使われない。古いまたは development files 不足の system ROCm は警告後に wheel 経路へ進む（`terminal/setup.py:5550-5573`）。
- wheel の取得先 index は `STRATA_ROCM_INDEX` があればその値、なければ GPU architecture 別の index で決まり、`STRATA_ROCM_VERSION` は index を変更しない。version override が index に存在するかは事前検査されず、pip install に渡される（`terminal/setup.py:4508-4509, 4546-4560, 5594-5599`）。
- wheel 経路では対象 architecture に対応する index が必要。index が複数 family にまたがる GPU 構成は、override があっても wheel install 前に system ROCm 7 を要求して終了する。`gfx906` は wheel index がないため source setup では扱えず、同様に終了する（`terminal/setup.py:5574-5583`）。
- Windows の通常の app setup は ready-made HIP engine を使う。Windows のソースビルド補助 `build_windows.bat` では、`STRATA_HIP_ARCHS` に基づく device extras とともに pip に渡し、`STRATA_ROCM_KEEP=1` なら stamp が一致しない場合でも pip install をスキップする（`terminal/setup.py:16-19`; `terminal/tools/hip/build_windows.bat:37-53`）。

## 実行時の詳細

Linux の値は `terminal/setup.py` のモジュール読み込み時に一度定数へ取り込まれ、プロセス中の環境変更は再読込されない。`rocm_wanted()` は override が truthy なら index の一覧を取得せず、その値を返す。未設定なら family pin を使い、index の `<index>/rocm/` を timeout 30 秒で取得して候補を調べる。取得失敗時は空の一覧として pin を維持し、pip に後続の解決を任せる。pin が一覧にない場合は同じ major.minor の最新、次に同じ major の最新を選び警告し、どちらもなければ pin のまま警告する（`terminal/setup.py:4523-4560`）。

wheel をインストールする場合、選択値は `rocm[libraries,devel]==<値>` に埋め込まれ、成功後に `.strata-rocm.json` へ index と version が記録される。既存 stamp と同じ index/version の wheel があると再インストールを避けるが、truthy な override があると pin の stamp を再利用する条件から外れ、override の値で再選択・比較する（`terminal/setup.py:5584-5600`）。形式不正など pip が受け付けない値の場合、setup の `run()` はコマンドの非 0 終了を `command failed (exit …): <コマンド名>` として報告し、setup を終了コード 1 で止める（`terminal/setup.py:5594-5600, 1131-1156`）。

Windows のビルド script は値と extras を stamp の `WANT` と照合し、必要なら exact version 指定で pip install してから `rocm-sdk init` を実行する。失敗時は `|| exit /b 1` で停止し、値は package 作成ツールへ `--rocm-version` としても渡され、生成する NOTICE と metadata に記録される（`terminal/tools/hip/build_windows.bat:43-53, 123-125`; `terminal/tools/hip/package_windows.py:84-88, 185-194`）。

## ログと測定値

Linux で index の pin が見つからず代替版を使う場合、`warn()` 経由で `ROCm <pin> is not on this index any more: using <版>, the newest of the same <line|major> (set STRATA_ROCM_VERSION to choose another)` を出す。major の代替もない場合は `ROCm <pin> is not on this index and nothing of its major version is: <最小> to <最大> are (set STRATA_ROCM_VERSION to one of them)` を出す。truthy な override ではこれらの index 選択警告は出ない。ただし `gfx1151` で version を `rocm_vkey()` が認識できない場合は ROCm 9.0 相当として比較され、7.11 未満向け警告の条件から外れる。認識できる 7.11 未満なら Strix Halo の警告が付く（`terminal/setup.py:4517-4520, 4529-4543, 4546-4565`; `terminal/setup.py:1044-1046`）。

この変数に結び付いた測定値は該当しない。

## 根拠

- `terminal/setup.py:4442-4453, 4546-4565` — Linux の既定値、module-level 読み取り、override と index lookup の分岐。
- `terminal/setup.py:5550-5605` — system ROCm の優先、wheel 経路の条件、stamp、install と失敗経路。
- `terminal/setup.py:5669-5682, 5750-5765` — HIP engine / HIP 画像 reader の build 経路から `rocm_root()` を呼ぶ条件。
- `terminal/tools/hip/build_windows.bat:13-30, 37-53, 123-125` — Windows ビルド補助での既定値、stamp、pip 引数、下流への引き渡し。
- `terminal/tools/hip/package_windows.py:84-88, 185-194` — 引き渡された値の package NOTICE / metadata への記録。
- `terminal/setup.py:16-19, 6477-6492` — 通常セットアップの Windows ready-made engine 経路。
