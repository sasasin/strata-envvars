# `setup.py --prebuilt`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（`terminal/setup.py`） |
| オプション | `--prebuilt` |
| 別名 | なし |
| 値 | 既製エンジン ZIP の置き場所を表す URL またはローカルフォルダー。値の型・形式を parser では検証しない |

## 役割

CUDA など通常のエンジン取得経路で使う既製エンジンの配布元を指定する。標準のセットアップでは環境変数 `STRATA_PREBUILT_URL`（未設定時は Strata の GitHub Releases URL）が既定値になり、必要なプラットフォーム用 ZIP を取得して `engine/`（CUDA 12 用は `engine-cuda12/`）へ展開する。既存エンジンの更新にも値が渡される。

## 使い方

```sh
# ローカルに置いた既製エンジン ZIP のあるフォルダーを使ってセットアップする
./setup.sh --prebuilt /mnt/strata-engine-dist/

# 自分のリリース配布フォルダーを使って Windows のセットアップを行う
START-HERE.bat --prebuilt "https://example.invalid/releases/download/v1.2.3/"
```

値にはアーカイブそのものではなく、アーカイブを含むフォルダーを指定する。実際に探すファイル名は OS/backend と CUDA toolkit により変わる。

## 値と既定値

- parser は `--prebuilt` の次の引数を文字列として受け取り、`choices` や独自 validation を設定していない。指定しない場合は `STRATA_PREBUILT_URL` の値、それも未設定なら `https://github.com/Niko1221/Strata/releases/latest/download/` が使われる（`terminal/setup.py:11550-11551`, `terminal/setup.py:273-284`）。
- 明示した `--prebuilt` は環境変数より優先される。値の末尾が `/` または `\` でなければ、実行時に `/` を補ってからアセット名を連結する（`terminal/setup.py:6193-6202`）。
- 同じオプションを複数回指定した場合の独自処理はない。`argparse` の通常の引数処理に任される。
- 空文字列など不正な場所も parser では拒否されない。空値は取得関数で既製エンジンなしとして扱われ、ローカルの対象ファイルが存在しない場合は `download()` が `not found` を報告して setup を停止する（`terminal/setup.py:6327-6329`, `terminal/setup.py:3537-3544`）。

## 実行時の動作

1. 通常の非 HIP Windows 経路・Linux では、`--build` がなければ `get_prebuilt(a.prebuilt, ...)` に値を渡す。`--build` はこの既製エンジン取得を飛ばし、ローカルビルドへ進む（`terminal/setup.py:9597-9625`）。
2. Windows の AMD HIP 経路は `get_prebuilt_hip(a.prebuilt, ...)` を使う。HIP エンジンの取得に失敗すると、この経路は案内メッセージを出して終了する。ここでは `--build` の有無にかかわらず既製 HIP エンジン取得が呼ばれる（`terminal/setup.py:9606-9612`）。
3. 既定 URL の場合は、checkout のバージョンに対応する release URL を先に試し、見つからなければ `latest` に進む。カスタム URL／ローカルフォルダーを明示した場合はその場所だけを使う（`terminal/setup.py:6193-6202`）。URL はアセット名との結合に使われ、リモートでは存在確認の HEAD 要求後にダウンロードする。ローカルの値では HEAD 要求を行わず、同じアセット名を末尾に加えたファイルをコピーする（`terminal/setup.py:6331-6352`, `terminal/setup.py:5433-5451`, `terminal/setup.py:3513-3544`）。
4. 通常の ZIP 名は Windows が `strata-windows-x64.zip`、それ以外が `strata-linux-x64.zip`。CUDA 12 用は末尾が `-cuda12.zip` の別アセットであり、Windows HIP は `strata-windows-x64-hip.zip` を使う（`terminal/setup.py:284`, `terminal/setup.py:293`, `terminal/setup.py:5059`, `terminal/setup.py:6300-6302`, `terminal/setup.py:5433`）。
5. 展開前に GitHub Releases API が公表するサイズと SHA-256 を確認する。GitHub の release URL でないローカルフォルダーや一般のミラーには照合先 digest がなく、警告を出してインストールを続ける。アーカイブの取得・検証後は `engine/` または `engine-cuda12/` に展開し、置き換え前のエンジンは一世代 `.previous` に退避する（`terminal/setup.py:6068-6094`, `terminal/setup.py:6103-6164`, `terminal/setup.py:6215-6240`, `terminal/setup.py:6387-6398`）。
6. `--update` では `update_installed_engine(a.prebuilt, ...)` に渡され、古いエンジンを更新する。更新に失敗した場合は警告して既存エンジンを起動可能な状態に保つ。`--update --build` は取得の代わりに再ビルドする（`terminal/setup.py:8497-8510`, `terminal/setup.py:6452-6551`）。

## 適用条件と副作用

- `--check`、`--inspect`、`--prepare-pack` などエンジン取得に進まないモードでは、この値は実際の既製エンジン取得に使われない。形状別エンジンやアプリ内 `CONTROL` モードも `engine_step()` の別経路を通る（`terminal/setup.py:11624-11627`, `terminal/setup.py:9597-9604`, `terminal/setup.py:9399-9403`）。
- CUDA の既製エンジンがすでに適合している場合は再利用され、指定先を見に行かない。GPU アーキテクチャや engine の最低バージョンが合わない場合は警告してローカルビルドへ進む（`terminal/setup.py:6303-6318`, `terminal/setup.py:6366-6386`）。
- リモート URL ではネットワークアクセスが発生する。アーカイブは Strata の engine ディレクトリーにコピー／展開され、ダウンロード済み ZIP は展開後に削除される。悪いサイズ・ハッシュと判定された ZIP も削除される（`terminal/setup.py:6333-6357`, `terminal/setup.py:6150-6163`, `terminal/setup.py:6387-6389`）。
- `STRATA_SKIP_SHA256=1` が別途設定されていると SHA-256 検証を省略して警告する。GitHub が digest を返さない場合も拒否せず未検証のまま続行する（`terminal/setup.py:6138-6147`）。
- `use_cuda12()` の自動移行経路は `a.prebuilt` ではなく `STRATA_PREBUILT_URL` または組み込み既定値を直接 `get_cuda12_engine()` に渡す。その経路では CLI の明示値が反映されない（`terminal/setup.py:9209-9229`）。

## 出力とエラー

- 取得開始時に `Downloading the ready-made Strata engine ...` を表示する。GitHub API から digest を得られない場合や、ローカル／ミラー配布の場合は未検証の警告を表示して続行する（`terminal/setup.py:6351`, `terminal/setup.py:6142-6147`）。
- ZIP のサイズまたは SHA-256 が GitHub 公開値と違う場合はアーカイブを削除する。初回導入では `fail()` がエラーを出して終了コード 1 で停止し、更新時は既存エンジンを維持する（`terminal/setup.py:6150-6163`, `terminal/setup.py:6167-6181`）。
- リモート URL が見つからない場合は feed のエンジン取得も試み、取得できなければ警告して初回セットアップではビルドへ進む。既存エンジン更新では失敗を警告し、現在の engine を使い続ける（`terminal/setup.py:6333-6350`, `terminal/setup.py:6537-6550`）。Windows HIP ではエンジンを取得できない場合に `fail()` で停止する（`terminal/setup.py:9606-9612`）。
- 壊れた ZIP は展開時に `zipfile.BadZipFile` となり、該当アーカイブを削除して例外を上位へ伝える（`terminal/setup.py:6358-6365`）。

## 根拠

- `terminal/setup.py:11550-11551` — parser の値・既定値。
- `terminal/setup.py:273-284`, `terminal/setup.py:293`, `terminal/setup.py:5059` — 組み込み URL と取得対象アセット。
- `terminal/setup.py:6193-6202`, `terminal/setup.py:6054-6065` — URL の正規化、既定 URL と明示指定の探索順、ローカル値の分類。
- `terminal/setup.py:6295-6398`, `terminal/setup.py:5414-5491` — CUDA 系および Windows HIP の取得・検証・展開。
- `terminal/setup.py:9597-9631`, `terminal/setup.py:8497-8510`, `terminal/setup.py:6452-6551` — setup と更新からの呼び出し、`--build` との関係。
- `terminal/setup.py:6103-6181`, `terminal/setup.py:6215-6240` — digest 検証・失敗処理・旧エンジン退避。
- `terminal/setup.py:9209-9229` — CUDA 12 自動移行時は CLI 値を直接参照しない経路。
