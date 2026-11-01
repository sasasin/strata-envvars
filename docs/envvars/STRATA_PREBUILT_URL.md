# `STRATA_PREBUILT_URL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外です。

## 役割

セットアップが取得する ready-made Strata エンジン ZIP の配布元フォルダーを指定します。値はエンジンの実行時設定ではなく、Strata の `setup.py` がエンジンを取得・更新するときに使います。既定の配布元は `https://github.com/Niko1221/Strata/releases/latest/download/` です。既定値のままなら、まずこの checkout のバージョンの release を試し、見つからないとき latest release に進みます。既定値と異なる URL / パスを指定すると、その一箇所だけを使います（`setup.py:225-235,5275-5284`）。

候補名の参照をリポジトリ全体で検索すると、コメント2箇所と環境から値を読む箇所2箇所が `setup.py` にあります。他に同名の読み取りや共通 env helper への動的な引き渡しは見つかりませんでした（`setup.py:227,5277,7635,9167`）。

## 値と判定

文字列の parse、正規化、範囲検査はありません。パス末尾に `/` または `\` がなければ `prebuilt_bases()` が `/` を付けます。大文字小文字や値の内容の妥当性は、URL / ローカルパスとして処理できるかで決まります（`setup.py:5275-5284`）。

| 入力 | Strata の扱い |
| --- | --- |
| 未設定 | `os.environ.get(..., PREBUILT_URL)` が既定 URL を返します。通常セットアップと更新では `--prebuilt` の既定値になります。既存モデルを CUDA 12 に移す専用経路でも同じ既定 URL になります。 |
| 空文字 | 通常は CLI 既定値として空文字のまま保持されます。`get_prebuilt()` / Windows HIP の `get_prebuilt_hip()` は空値なら `None` を返し、ready-made engine を探しません。CUDA 12 への移行では空文字が `url_base` として渡り、ready-made engine を探さずローカルビルドに進みます（`setup.py:4594-4612,5364-5397,7606-7614,9167`）。 |
| `--prebuilt DIR` または同名環境変数のローカルパス | アセット名を連結したパスをコピー元として扱います。ファイルがなければ `not found: ...` で失敗します。`file://` パスもコピー元になります（`setup.py:3008-3022,5400-5419`）。 |
| HTTP(S) の URL フォルダー | アセット名を連結して HEAD で確認し、取得可能ならダウンロードします。末尾スラッシュは補われます（`setup.py:5396-5419`）。 |
| その他の非空文字列 | Strata は URL 構文として事前検証せず、HTTP(S) 以外ならローカルパスとしてコピーを試します。パスが存在しなければ `fail()` 経由で終了します。 |

通常の `argparse` 定義では `--prebuilt` の明示値が環境変数由来の default を上書きします。明示 `--prebuilt ""` も空値として扱われます（`setup.py:9167-9168`）。ただし後述の CUDA 12 移行経路は parser の `a.prebuilt` を使わず、環境変数を直接読みます。

## 有効になる条件

- **通常の NVIDIA セットアップ**: `engine_step()` が `--build` でなく、HIP でもない場合に `get_prebuilt(a.prebuilt, ...)` へ渡します。アーキテクチャ不一致、必要な vision encoder の欠如、古すぎるエンジンなどでは ready-made engine を使わずビルドに移る経路があります（`setup.py:7772-7798,5364-5385,5433-5453`）。
- **CUDA 12 の選択**: `--cuda 12` を含むセットアップでは通常 `a.prebuilt` が使用されます。別経路として、CUDA 13 の既存モデルを起動するとき、追加 GPU に CUDA 13 非対応の Pascal / Volta（compute capability が `CUDA13_MIN_ARCH` 未満）が含まれると `ensure_engine_for()` がモデルを CUDA 12 エンジンへ移します。この移行は `os.environ.get("STRATA_PREBUILT_URL", PREBUILT_URL)` を直接使い、同じ起動の `--prebuilt` 引数は参照しません（`setup.py:7575-7585,7623-7644`）。
- **Windows HIP**: `engine_step()` は `get_prebuilt_hip(a.prebuilt, gpu)` に渡します。**Linux HIP** は既製エンジンをこの変数から取得せず `build_engine_hip()` に進みます（`setup.py:7779-7798`）。
- **更新**: `--update` は `update_installed_engine(a.prebuilt)` を呼びます。エンジンが既に必要なバージョン以上なら URL の取得処理は行われません。更新対象で取得・更新が失敗した場合は、既存エンジンを維持して起動する経路があります（`setup.py:7023-7038,5519-5528,5571-5607`）。
- **対象外経路**: Mac の `CONTROL` エンジンコンポーネント経路は `engine_step()` を迂回し、`--backend sycl` は SYCL セットアップへ早期 return します。これらでは本変数による ready-made engine URL 選択をしません（`setup.py:7772-7777,9220-9225`）。

取得済み ready-made engine が `BUILD.json` にあり、実行ファイルも存在し、要求 GPU の arch を満たし、バージョンが `MIN_ENGINE` 以上なら、指定 URL を見に行かずその既存エンジンを返します。したがって、値を設定しただけでインストール済みエンジンが置き換わるわけではありません（`setup.py:5371-5386`）。

## 実行時の詳細

通常経路では `setup.py` の引数 parser 構築時に環境変数を `--prebuilt` の default として読み、そのプロセス内で引数値をエンジン選択・更新処理へ渡します。起動後の環境変更を再読込する cache はありません。CUDA 12 移行経路だけは移行処理時に環境変数を直接読みます（`setup.py:7635-7636,9167-9168`）。

`get_prebuilt()` は値が空なら `None` を返します。非空値ではエンジンの ZIP 名を付け、HTTP(S) なら HEAD を試します。既定 URL では checkout の版の release を先に探し、失敗時に latest を試します。その checkout 版も latest も HTTP で得られない場合、CUDA 13 では update feed から取れるか試し、取れなければ警告して `None` を返し、通常セットアップはローカルビルドへ進みます。CUDA 12 でも `get_cuda12_engine()` が `None` の場合にビルドします（`setup.py:5275-5284,5396-5417,7606-7614`）。

ダウンロード ZIP は展開前に release API の size / SHA-256 と照合します。ローカルフォルダーまたは GitHub release 以外のミラーなど、照合する公開 digest が得られない場合は警告して続行します。サイズまたは SHA-256 が不一致ならダウンロードを削除して拒否し、初回セットアップでは失敗を報告します。更新では既存エンジンを保持します（`setup.py:5194-5213,5229-5255,5258-5272,5418-5424`）。

観測できる結果には `Downloading the ready-made Strata engine ...`、`no ready-made engine at ...`、ローカルビルドへの案内、SHA-256 の未検証警告があります。存在しないローカルパスは `not found: ...`、HTTP ダウンロードが最後まで到達不能なら `cannot reach ...` を `fail()` が出して `SystemExit(1)` で終了します。更新経路では取得例外を捕捉し、`could not update the engine` / `could not update the AMD engine` 等の警告を出して既存エンジンで続けます（`setup.py:887-907,3015-3022,3050-3059,5418-5424,5542-5548,5593-5607`）。

## 根拠

- 候補名のコメント、既定 URL、既定版→latest の選択: `setup.py:225-235,5275-5284,6813-6821`
- 環境変数の読み取り、CLI default、CLI による上書き、早期 return: `setup.py:7633-7636,9167-9168,9212-9225`
- NVIDIA / CUDA 12 / HIP の利用経路: `setup.py:4594-4629,5364-5453,7575-7644,7772-7804`
- update の適用条件と既存エンジン維持: `setup.py:5519-5607,7023-7057`
- ローカルコピー、ダウンロード、digest 確認と失敗経路: `setup.py:3008-3022,5194-5272,5396-5424`
- CUDA 12 のモデル単位の選択と移行条件の設計資料: `docs/OLDER_GPUS.md:62-94`
