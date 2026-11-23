# `STRATA_TEST_REAL_NVIDIA_SMI`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は `terminal/conftest.py` の pytest 共通セットアップが、POSIX のテスト実行環境に失敗する `nvidia-smi` スタブを入れるか決めるテスト用フラグです。Strata の通常実行時の GPU 検出や NVIDIA driver 設定を切り替える読み取り箇所は見つかりませんでした。`tools/check` は `terminal/tests`、`terminal/serve`、`terminal/tools` の pytest を `terminal` を作業ディレクトリとして起動します（`tools/check:286-323,427-432`）。

## 値と判定

`terminal/conftest.py` のモジュール読み込み時に `os.environ.get(...)` の戻り値を Python の真偽値として判定します。文字列の parse や値の比較はありません。`os.name != "nt"` が先に評価されるため、Windows では変数を読みません（`terminal/conftest.py:71`）。

| 条件 | unset | 有効になる値（スタブ注入を止める） | 無効になる値（スタブを注入） |
|---|---|---|---|
| `os.name != "nt"` | 無効 | 空でない任意の文字列。例: `1`、`true`、`0`、`false`、空白だけ | unset、空文字 `""` |
| `os.name == "nt"` | 変数を評価しない | 該当なし（値にかかわらずこの分岐は動かない） | 該当なし |

したがって `0` や `false` も空でないためスタブ注入を止めます。大小文字、前後の空白、数値としての妥当性は検査されません。CLI 引数や別の設定値との優先順位はありません。

## 有効になる条件

- スタブ注入を止める効果は、`os.name != "nt"` の pytest セッションで変数が空でない場合に限られます。Windows ではこのコードによる効果はありません（`terminal/conftest.py:71`）。
- 未設定または空文字の場合、POSIX のセットアップが作るスタブが既存 `PATH` より先に置かれます。テストが後で独自の `PATH` や `nvidia-smi` の reader を差し替える経路は、このフラグ自体によるものではありません（`terminal/conftest.py:64-77`）。
- CUDA/HIP/SYCL の build、サーバーモード、モデル状態による分岐はこの読み取り箇所にはありません。

## 実行時の詳細

pytest が `terminal/conftest.py` を読み込むときに一度評価されます。unset または空文字で POSIX の場合、共通セットアップは `_home` 配下に `no-nvidia-smi/nvidia-smi` を作成します。そのファイルはシェルスクリプトで、実行すると `exit 1` を返し、実行権限を付けたうえで、そのディレクトリを現在のプロセスの `PATH` の先頭に追加します。既存 `PATH` は後ろに連結されます（`terminal/conftest.py:46,64-77`）。ソースコメントは、この設定が子プロセスにも使われ、実機の NVIDIA card があるテストホストと GitHub runner の差を抑える意図だと説明しています（`terminal/conftest.py:64-70`）。

非空値ではスタブ用ディレクトリ／ファイルを作成せず、この箇所は `PATH` を変更しません。環境変数を pytest 起動後に変更しても、このセットアップの判定は再評価されません。変数自体によるログ出力、終了、警告はありません。スタブを選んだ場合に `nvidia-smi` を実行した呼び出し元が見る結果はスタブの終了コード `1` です（`terminal/conftest.py:74-77`）。

## 根拠

- `terminal/conftest.py:64-77` — コメントにあるテスト用の意図、OS 条件、真偽値判定、スタブ作成、実行権限、`PATH` の変更。
- `tools/check:286-323,427-432` — pytest の起動処理と `terminal` 配下の対象。
- `docs/DETAILS.md:1140` — `nvidia-smi` に触れる記述は GPU 番号の例であり、このテスト用フラグの説明ではありません。
