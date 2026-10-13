# `STRATA_ROCM_INDEX`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

AMD HIP 用 ROCm Python wheels のインデックス URL を指定します。Linux の `setup.py` では、適合するシステム ROCm を使えないときに TheRock wheels を取得する URL を上書きします。Windows では、開発用 HIP エンジンを作る `tools/hip/build_windows.bat` が pip の `--index-url` に渡します。この変数は実行エンジンでは読まれません。

## 値と判定

| 経路 | 未設定または空文字 | 空でない値 |
|---|---|---|
| Linux `setup.py` | GPU architecture ごとの `ROCM_INDEXES` URL | 文字列をそのまま URL として使用。trim、URL 検証、末尾 `/` の正規化はしない |
| Windows `tools/hip/build_windows.bat` | `https://nightly.repo.amd.com/rocm/whl-next/` を設定 | `%STRATA_ROCM_INDEX%` を pip の `--index-url` に渡す |

Linux では Python の `os.environ.get(...) or ...` 判定なので、空文字は未設定と同じです。空白だけの文字列は truthy な値としてそのまま使われます。Windows バッチの `if not defined` は空の変数にも既定 URL を設定します。いずれも値を真偽値や数値として parse しません。

Linux の既定 URL は `gfx1100`–`gfx1102` が `gfx110X-dgpu`、`gfx1200`–`gfx1201` が `gfx120X-all`、`gfx1030`–`gfx1031` が `gfx103X-all`、`gfx1151` が `gfx1151` です。`gfx1103` は `STRATA_EXPERIMENTAL_GFX1103=1` のときだけ architecture 候補に加わり、その既定 URL は `gfx110X-all` です。

## 有効になる条件

- Linux の `setup.py` では、選択した GPU architecture 用の HIP engine をソースから再構築するときに `build_engine_hip()` から `rocm_root()` が呼ばれます。適合する system ROCm が見つかるとそちらを返すため、この環境変数は使われません。engine と vision が既に最新なら、`build_engine_hip()` が先に戻るため参照されません。
- TheRock wheels を使うとき、各 architecture の index URL は重複を除いて集約されます。異なる family の複数カードは通常エラーになりますが、同じ `STRATA_ROCM_INDEX` を設定すると URL 集合上は1つになり、そのチェックには該当しません。選ばれた index の末尾パス要素が family 名として扱われ、version pin とインストール済み library の family 選択にも使われます。custom URL の末尾要素が既知の family 名と一致しない場合は、family 固有 pin に一致しないため `ROCM_VERSION_DEFAULT` が優先版になります。
- Linux では `STRATA_ROCM_VERSION` が空でない値に設定されていると、その正確な version を使い、index の version listing を取得しません。未設定なら `<index>/rocm/` を取得して希望 version の有無を調べます。
- Windows では `tools/hip/build_windows.bat` の開発ビルドだけが対象です。バッチは `.rocm-win/strata-rocm.txt` に記録した version と extras が現在の要求と一致すると pip install を省略します。この stamp 比較に index URL は含まれないため、同じ version と extras のまま URL だけ変えても再インストールは起きません。

## 実行時の詳細

Linux の `rocm_index(arch)` は呼び出しごとに環境を読み、override が truthy なら architecture に関係なく同じ文字列を返します。通常は GPU family ごとの既定 URL を返します。`rocm_root()` は index 群を1つにまとめた後、`.venv` の `.strata-rocm.json` に保存された index と version、およびインストール済み SDK を確認します。stamp が現在の index と選択 version に一致し、family の pin も一致すれば listing と pip install を省略します。そうでなければ `rocm_wanted()` が index の `<index>/rocm/` を最大30秒で読みます。取得できない場合は推奨 version を保持して先へ進み、pip 側のエラーになります。推奨 version が listing にないときは同じ 7.x line、次に同じ major の最新 version を選び、警告します。該当 major がない場合も警告して推奨版を残します。パッケージ取得・導入が失敗すると setup の処理は失敗します。

Windows バッチは環境変数を `setlocal` 内で使い、pip の `--index-url` として渡します。要求 stamp と異なる場合だけ ROCm wheels を導入し、pip または `rocm-sdk init` の失敗時は終了コード 1 でバッチを終了します。pip 自体や TheRock index の動作は Strata の挙動として扱いません。

## 文書との照合

`docs/AMD_HIP.md` は Linux の TheRock index がカード family ごとにあること、および `STRATA_ROCM_VERSION` / `STRATA_ROCM_INDEX` が上書きに使えることを説明しています。`setup.py` の実装では、custom index が全 architecture に共通で適用される点、既存 stamp による導入省略、システム ROCm 使用時の未参照も条件として加わります。Windows の default index と install 条件は `tools/hip/build_windows.bat` にあります。

## 根拠

- `setup.py:1820-1828` — Linux 用 architecture 別の既定 index。
- `setup.py:1863-1865` — override 読み取りと空文字時の fallback。
- `setup.py:1884-1920` — version listing、選択規則、失敗時 fallback と警告。
- `setup.py:2543-2581` — system ROCm 判定、index 集約、stamp、pip install。
- `setup.py:2632-2655` — engine 再利用時の早期 return と ROCm 選択の呼び出し。
- `tools/hip/build_windows.bat:13-23,38-46` — Windows の既定値、stamp 比較と pip 引数。
- `docs/AMD_HIP.md:31-38,118-122` — AMD セットアップ経路と Windows ビルド資料。
