# `MIGRATE_ONLY`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata 同梱の CUDA→SYCL 移行スクリプト `sycl/tools/migrate.sh` が作る compilation database の入力ファイル一覧を、通常の自動検出から明示リストへ切り替えます。Strata の通常実行や SYCL ビルド時に読む環境変数ではなく、移行ツール用です。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定、または空文字 | `MIGRATE_ONLY` 分岐に入らず、`src` 以下から `.cu` と CUDA 関連ヘッダーを include する `.cpp` を検索した結果を使う |
| 空白だけ | Python では空文字列でないため分岐に入り、`.split()` の結果である空リストを使う。database は 0 translation units になる |
| その他の非空文字列 | Python の `str.split()` で空白区切りにした各トークンをファイル名として使う |

区切りは任意の連続する空白で、先頭・末尾の空白や空トークンは捨てられます。引用符やエスケープを解釈するシェル形式の parser、値の妥当性検査、ファイル存在確認はありません。ファイル名に空白が含まれる場合、この指定方法では1つの名前として渡せません。大文字小文字は環境変数名として区別されます。

明示リストを使う場合も、`src/prefill/moe_mmq.cu`、`src/prefill/ggml_cuda_host.cu`、`src/kernels/native_expert_parity.cpp` は後段で常に除外されます。残りは set 化して重複を除き、ソートして compilation database に入ります。

## 有効になる条件

`sycl/tools/migrate.sh` を実行し、その中の Python 処理が実行される場合に限ります。値の真偽は Python の `os.environ.get()` によるため、unset と空文字は既定の自動検出、空白だけを含む値を含む非空文字列は明示リスト扱いです。OS や GPU backend による分岐はこの箇所にはありません。

## 実行時の詳細

スクリプトは repo を作業ディレクトリにした後、Python でファイル一覧を決め、各ファイル向けの compiler arguments を compilation database に書き出します。`MIGRATE_ONLY` が非空なら自動検出結果を置き換え、リストにないファイルは database と dpct の入力に含まれません。その後 `dpct -p "$db_dir"` が database を使って移行します。変数はスクリプト内で再読されず、Strata の実行ファイルや SYCL ビルドへ引き継いで機能を変える処理も確認できません。

database 作成後の主な出力は `<out>/migrate.log` で、スクリプトは dpct の出力末尾40行を表示し、dpct の終了コードと `<out>` 内のファイル数も表示します。これらの出力は通常の移行処理によるもので、`MIGRATE_ONLY` 専用の警告やエラー文はありません。

## 文書との照合

`docs/INTEL.md` は移行手順として、通常の `migrate.sh` が compilation database を作って dpct を実行することを説明しています（同文書では86 translation unitsと記載）。環境変数による絞り込みの説明はありません。現行コードでは、未設定・空文字の場合に自動検出し、非空の場合に指定リストへ置き換えます。`sycl/CMakeLists.txt` は生成済みの移行コピーを SYCL build が利用する仕組みを説明していますが、`MIGRATE_ONLY` 自体を読みません。

## 根拠

- `sycl/tools/migrate.sh:1-13`: スクリプトの用途、引数、repo への移動。
- `sycl/tools/migrate.sh:17-37`: 自動検出、環境値判定と `.split()`、除外・重複排除・順序、database 作成。
- `sycl/tools/migrate.sh:39-49`: dpct の実行とログ・終了コード・出力ファイル数。
- `docs/INTEL.md:166-173`: SYCL migration の手順と通常時の translation unit 数の説明。
- `sycl/CMakeLists.txt:3-7,87-104`: SYCL build が移行済みコピーと元ソースを解決する方法。
