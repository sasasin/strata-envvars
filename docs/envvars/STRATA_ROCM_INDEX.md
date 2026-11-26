# `STRATA_ROCM_INDEX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

AMD GPU 向け setup が TheRock の ROCm wheel を取得するときに使う package index URL を指定する。Linux の `terminal/setup.py` では既定の GPU family 別 index を置き換え、Windows の `terminal/tools/hip/build_windows.bat` では既定 index URL を `pip --index-url` に渡す。Strata の実行エンジンが起動時に読む設定ではなく、セットアップ時の依存取得先を変える変数である。Linux は利用可能な system ROCm が見つかれば wheel 取得をせず、この変数も評価しない（`terminal/setup.py:4508-4509`, `5550-5579`）。

## 値と判定

| 経路 | 未設定 | 設定時に使われる値 | 空文字・無効値 |
|---|---|---|---|
| Linux `terminal/setup.py` | `ROCM_INDEXES[arch]` の GPU family 別 URL | `os.environ.get("STRATA_ROCM_INDEX")` が truthy ならその文字列をそのまま使う。例: `https://mirror.example/simple/` | 空文字は未設定と同じ既定 URL。`strip`、URL 形式検証、scheme 検証、大小文字変換はしないため、`not-a-url` や空白だけの文字列も truthy な値として選ばれる。`0` / `false` も文字列として index に使う。 |
| Windows `build_windows.bat` | `https://nightly.repo.amd.com/rocm/whl-next/` を設定 | batch 内で既定値を設定した後の `%STRATA_ROCM_INDEX%` を pip に渡す | `if not defined` に該当する場合は既定値を設定する。形式検証や正規化はない。 |

Linux の選択式は `os.environ.get(...) or ROCM_INDEXES[arch]` であり、値を parse しない。Linux の family ごとの既定 URL は gfx1100/1101/1102、gfx1200/1201、gfx1030/1031/1032、gfx1151、gfx1150、gfx1103 ごとに `terminal/setup.py:4431-4441` に定義されている。Windows は文字列を `pip install --index-url` に渡すだけである（`terminal/tools/hip/build_windows.bat:28-30, 49-53`）。

## 有効になる条件

- Linux では `--backend hip` 等の HIP セットアップで `rocm_root(archs)` が wheel 経路まで進むこと。`ROCM_PATH`（未設定なら `/opt/rocm`）の system ROCm が hipcc・hipBLAS と開発ファイルを備え、バージョンが 7.0 以上ならそこで返り、index は使わない。古い ROCm または開発ファイル不足なら警告して wheel 経路へ進む（`terminal/setup.py:5550-5573`）。
- Linux の対象 GPU architecture に対応する wheel があること。`gfx906` 等の `ROCM_INDEXES` にない architecture は index を選ぶ前に失敗する（`terminal/setup.py:5574-5578`）。
- Linux で複数 architecture を使う場合、既定では family ごとの index が異なる構成は失敗する。`STRATA_ROCM_INDEX` を一つ指定すると全 architecture に同じ index が返るため、この異なる index の検査を通過する。ただし、指定先に必要な wheel があることまでは Strata は事前保証しない（`terminal/setup.py:5579-5583`）。
- Linux の `STRATA_ROCM_VERSION` が空でない場合はその値が wheel version として優先され、index の一覧取得による version 選択をしない。未指定なら選ばれた index の family 名を使って family pin または既定 version を選び、index の一覧を読めた場合は候補 version を選び直す（`terminal/setup.py:4447-4452, 4529-4565`）。
- Linux は stamp の index と version が一致し、SDK と pin 条件も満たすと wheel の一覧取得・再インストールを省略する。index が変われば stamp と一致しなくなりインストール経路に進む（`terminal/setup.py:5584-5600`）。
- Windows batch installer では version と arch extras から作る stamp が一致し、`STRATA_ROCM_KEEP=1` でない場合に pip を実行する。stamp 自体には index が含まれないため、version と extras が一致すれば index だけを変更しても pip install は実行されない。`STRATA_ROCM_KEEP=1` は stamp の不一致時もインストールを抑止する（`terminal/tools/hip/build_windows.bat:43-53`）。

## 実行時の詳細

Linux の読み取りは `rocm_index(arch)` の呼び出しごとで、関数内 `static` や import 時の cache はない。`rocm_root` は利用可能な system ROCm を先に調べ、wheel 経路で architecture ごとに `rocm_index` を呼ぶ。選ばれた index は ROCm version listing の URL、pip の `--index-url`、stamp の `index`、インストール済み library family の選択に使われる。末尾 path component は family 名にも使われるため、カスタム URL の末尾名が family pin や installed library の絞り込みに影響する（`terminal/setup.py:4508-4509, 4512-4514, 5550-5600, 5606-5615`）。

通常の setup プロセスでは index 読み取り後に対話的な環境変更を受け付ける処理はない。関数が再度呼ばれれば環境から読み直すが、インストール済み stamp が一致する場合は再取得しない。`rocm_root` は HIP engine build と HIP image reader の準備から呼ばれる（`terminal/setup.py:5681, 5754-5765, 5934-5939`）。

Windows batch は `STRATA_ROCM_INDEX` が未定義なら nightly URL を設定し、wheel install が必要なときにその値を pip に渡す。pip の終了コードが非 0 なら batch は `exit /b 1` で終了する（`terminal/tools/hip/build_windows.bat:28-30, 43-53`）。Linux では pip 実行が失敗すると `run` が `command failed (exit N): <command>` を表示して setup を exit code 1 で停止する（`terminal/setup.py:1131-1157, 5594-5600`）。不正な URL の Strata 独自検証や事前拒否は見つからず、実際の取得成否は pip 実行時に表面化する。

## ログと測定値

Linux が wheel を入れるときは stdout に `Installing ROCm <version> for AMD GPUs into .venv (AMD's TheRock wheels, ~10 GB, no sudo) ...` を表示し、実行コマンドも `  > ` で表示する。index の変更だけを示す専用ログはない（`terminal/setup.py:5594-5600, 1131-1157`）。指定 index の一覧に希望 version がない場合、同じ version line / major から選べたときは `ROCm <preferred> is not on this index any more: using <got>, the newest of the same <line|major> (set STRATA_ROCM_VERSION to choose another)`、同じ major の version がないときは `ROCm <preferred> is not on this index and nothing of its major version is: <first> to <last> are (set STRATA_ROCM_VERSION to one of them)` を `  [!]` 付きで表示する。一覧取得に失敗した場合は希望 version を保ち、この選択理由 warning は発生しない（`terminal/setup.py:4529-4565, 5590-5593, 1044-1047`）。system ROCm が古い、または HIP 開発ファイルが不足すると、wheel fallback の理由も `  [!]` 付きで表示する（`terminal/setup.py:5567-5572, 1044-1047`）。Windows は install 時に `Installing ROCm ...` を表示し、pip の失敗時は batch を終了する（`terminal/tools/hip/build_windows.bat:49-52`）。この変数自体の性能測定値は該当しない。

## 根拠

- Linux の index 定義と値の選択: `terminal/setup.py:4431-4441, 4508-4509`
- index を利用する system ROCm / wheel 分岐、multi-GPU 条件、stamp と pip install: `terminal/setup.py:5550-5600`
- URL からの version listing、`STRATA_ROCM_VERSION` の優先順位: `terminal/setup.py:4529-4565`
- Linux の呼び出し元と失敗表示: `terminal/setup.py:5681, 5754-5765, 5934-5939, 1044-1057, 1131-1157`
- Windows の既定値、stamp 条件、pip への転送と終了: `terminal/tools/hip/build_windows.bat:28-30, 43-53`
