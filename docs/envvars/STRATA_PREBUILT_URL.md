# `STRATA_PREBUILT_URL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

セットアップが CUDA エンジン、または Windows の HIP エンジンの既成 zip を探す URL 基底（末尾の `/` は任意）またはローカルフォルダーを指定する。通常の `terminal/setup.py` 経路では `--prebuilt` の既定値として使われ、明示した `--prebuilt` が優先する。指定した基底に既成エンジンがないときは、バージョン別 URL や標準の latest URL へは切り替えず、更新 feed を試すか、呼び出し元のセットアップがソースビルドへ進む。対応 GPU 用のエンジンがすでにインストール済みなら URL を参照しない場合がある。`terminal/setup.py:273-284, 6193-6202, 6295-6318`。

## 値と判定

この変数の値は文字列として取得され、boolean・数値・URL の形式検証はない。通常経路の `argparse` は `os.environ.get("STRATA_PREBUILT_URL", PREBUILT_URL)` をデフォルトにするため、未設定時は `https://github.com/Niko1221/Strata/releases/latest/download/`、設定値が空文字なら空文字のままになる。`--prebuilt VALUE` を指定すると、通常経路ではその値が環境変数由来の既定値に優先する。`terminal/setup.py:278, 11550-11551`。

| 条件 | unset | 有効になる値の例 | 無効・特別扱いになる値の例 |
|---|---|---|---|
| 通常の CUDA / Windows HIP セットアップまたは更新 | `PREBUILT_URL` を使用 | `https://host/path/`、`https://host/path`、既存のローカルフォルダー | 空文字は既成 zip の取得をスキップ。存在しないローカルパスは `not found: ...` で失敗。形式・大文字小文字・空白の検査はない |
| CUDA 12 エンジンへの自動切替 | `PREBUILT_URL` を使用 | 環境変数の文字列を同じ基底として使用 | 空文字は既成エンジン取得をスキップし、CUDA 12 をローカルビルド |

`prebuilt_bases()` は末尾に `/` または `\\` がなければ `/` を追加する。基底が `PREBUILT_URL` と同じ場合だけ、ソースのバージョンが読めればそのバージョンのリリース URL を先に試し、失敗時に latest を試す。`source_version()` が `"0"` の場合は latest のみ。環境変数または `--prebuilt` で異なる基底を指定した場合、その基底だけを URL 候補とし、HEAD 失敗時には呼び出し側が更新 feed を試す。`terminal/setup.py:6193-6202, 8059-8067, 6331-6350`。

`STRATA_PREBUILT_URL` の読み取り時に空文字を無効値として置き換える処理はない。ただし取得関数の `if not url_base` で空文字は `None` 相当の「既成エンジンなし」として扱われる。通常 CUDA セットアップではローカルビルドへ進み、Windows HIP では既成 AMD エンジンが得られず `no ready-made AMD engine for this Strata version` で終了する。`terminal/setup.py:5430-5432, 6327-6329, 9606-9625`。

## 有効になる条件

- 通常の `--prebuilt` 既定値経由では、`terminal/setup.py` の引数解析を通り、エンジン取得関数へ進むセットアップまたは更新で参照される。`--build` 指定時は新規セットアップの既成エンジン取得を行わず、ソースビルドする。`--update --build` は再ビルドする。`terminal/setup.py:11535, 9606-9625, 6452-6458`。
- セットアップで互換性のある既成エンジンがすでに存在する場合はそれを返すため、指定 URL からダウンロードしない。更新でも、既成エンジンが必要バージョン以上なら更新関数は URL を使わず戻る。`terminal/setup.py:6303-6318, 6515-6516`。
- 通常セットアップの CUDA 取得は `--build` と HIP の Linux 経路では行わず、Windows HIP 取得は Windows の HIP 分岐だけで使う。CUDA 取得の結果が `None` ならソースビルドへ進む。`terminal/setup.py:9606-9625`。
- Pascal / Volta GPU を検出して CUDA 12 エンジンへ移す経路は `use_cuda12()` が環境変数を直接読み直す。この経路では CLI の `--prebuilt` 値ではなく環境変数値（未設定なら `PREBUILT_URL`）が使われる。`terminal/setup.py:9192-9200, 9209-9229`。
- Mac のモデル別セットアップ、shape engine、`CONTROL` / コンポーネント経路は通常の `get_prebuilt(a.prebuilt, ...)` に到達しないため、この変数による既成エンジン URL 指定の対象外。`terminal/setup.py:9600-9604, 11628-11638, 9492-9508`。
- 適合する既成エンジンがないと URL が HTTP(S) なら asset に HEAD を送り、候補切れ後に feed を試す。ローカルパスまたは `file://` は `download()` でコピーする。ローカルファイルが存在しなければ `not found: ...` を出して失敗する。`terminal/setup.py:3513-3544, 6331-6352`。

## 実行時の詳細

通常経路の値は `main()` が `parse_args()` を呼ぶ時点で `--prebuilt` のデフォルトとして読み込まれ、取得処理では `a.prebuilt` として渡される。引数解析後にプロセス環境を変えても、この値は更新されない。一方、CUDA 12 への自動切替経路は `use_cuda12()` の呼び出し時に `os.environ.get()` を直接評価するため、引数解析時の `a.prebuilt` と別の読み取り箇所である。環境変数をキャッシュする共通 helper や永続設定への保存はない。`terminal/setup.py:9209-9222, 11550, 11606`。

この変数を使って子プロセス用の環境を個別設定するコードはない。通常の環境継承を使う `subprocess` 呼び出しでは親の環境に値が残っていれば継承されるが、調査した Strata のエンジン取得経路はその継承値をエンジン設定として扱わず、Python 側で取得先を決める。`terminal/setup.py:1131-1151, 5192-5204, 6295-6301`。

既定の URL 基底では、通常セットアップはソースのバージョンに対応する配布先を先に調べ、失敗した場合に latest を試す。独自の基底ではその URL のみを試す。取得できない場合は更新 feed へフォールバックし、それも得られなければ CUDA の新規セットアップは「コンパイルする」と警告してビルドへ進む。更新時は既存エンジンを保持してセットアップを続ける経路がある。`terminal/setup.py:6193-6202, 6335-6350, 6452-6458, 6537-6549`。

## ログと測定値

CUDA エンジンの取得では `Downloading the ready-made Strata engine ...`、Windows HIP では `Downloading the ready-made Strata engine for AMD GPUs (with the ROCm libraries it uses) ...` を出す。標準 URL のソースバージョン別候補が HTTP 404 の場合はその候補について何も表示せず latest へ進み、それ以外の失敗では `The ready-made engine for v... could not be reached (...): trying the latest release` を出す。独自 URL の最終候補が失敗し feed にもエンジンがない場合は、CUDA 経路で `no ready-made engine at ... (...): compiling instead`、HIP 経路で `no ready-made AMD engine at ... (...)` を警告する。更新処理で取得できない場合は `could not update the engine: starting the installed ...` として既存エンジンを使う。`terminal/setup.py:6184-6190, 5439-5450, 6335-6350, 6543-6549`。

## 根拠

- 変数の全参照（コメント2か所、実読み取り2か所）と通常既定値: `terminal/setup.py:273-284, 9221-9222, 11550-11551`。
- URL 正規化・候補順: `terminal/setup.py:6193-6202, 8059-8067`。
- CUDA / HIP 取得、既存エンジンの再利用、フォールバック: `terminal/setup.py:5414-5455, 6295-6357, 9606-9625`。
- 更新時の条件と失敗時の扱い: `terminal/setup.py:6452-6549`。
- URL / ローカルファイルのダウンロード挙動: `terminal/setup.py:3513-3544`。
- CUDA 12 自動切替: `terminal/setup.py:9192-9229`。
