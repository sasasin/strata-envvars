# `FAKE_SD_FAIL`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`serve/fixtures/fake_sd_cli.py` がテスト用の代替 `sd-cli` として起動された場合に、意図的に失敗させるフック。Strata エンジンや通常の `sd-cli` の設定ではなく、画像生成 API の失敗処理を検証するテスト用である。

## 値と判定

| 環境変数の状態 | fixture の判定 | 結果 |
| --- | --- | --- |
| 未設定 | `os.environ.get(...)` が `None` | 失敗しない |
| 空文字 | `""`（偽） | 失敗しない |
| 空でない文字列（`"1"`、`"0"` を含む） | 真 | 診断行を出して終了コード `1` で終了 |

数値変換や文字列全体の比較は行わない。ファイル先頭の説明にある `FAKE_SD_FAIL=1` は利用例であり、実装上は値が空でないことだけを見ている。

## 有効になる条件

- `serve/fixtures/fake_sd_cli.py` が実行されることが条件。本番の `sd-cli` や Strata の C++ エンジンにはこの名前の読み取り箇所はない。
- `serve/test_images.py` は `fake_args` で画像生成コマンドを fixture に差し替え、`test_bad_request_and_failure` 内で `FAKE_SD_FAIL` を設定して HTTP エラー経路を検証する。
- `serve/images.py` は子プロセスの環境として `image_env(...)` を渡す。同関数はデフォルトで現在の `os.environ` を複製するため、テストで設定した値は fixture プロセスへ渡る。

## 実行時の詳細

fixture は引数記録用の `FAKE_SD_ARGS`、待機用の `FAKE_SD_SLEEP` を処理した後、`[INFO ] loading tensors completed, taking 0.10s` を標準出力へ出す。続いて `FAKE_SD_FAIL` が真なら `[ERROR] ggml_vulkan: ErrorDeviceLost` を出し、PNG を書かずに `1` を返す。

画像生成側は子プロセスの非ゼロ終了を失敗として扱い、ログ末尾を含む `ImageJobFailed` を送出する。HTTP ハンドラーはこれを HTTP 500 と `image_generation_failed` エラーに変換する。テストでは応答に `ErrorDeviceLost` が含まれ、失敗数が1増え、busy 状態と FIFO lock が解除されることを確認する。

環境変数は fixture の起動ごとに評価され、値を静的キャッシュしない。画像ジョブごとに `image_env` が環境を作り直す。通常のOS環境変更が既存プロセスへ自動反映されるという意味ではなく、Strata のソースで確認できるのはこの環境辞書の生成と子プロセスへの引き渡しまでである。

## 文書との照合

`docs/DETAILS.md` の「Images (vision)」節はモデル入力の画像エンコーダーを説明しており、この画像生成 API テスト用 fixture や `FAKE_SD_FAIL` には触れていない。該当する環境変数の仕様説明はソース中の fixture とテストに限られる。

## 根拠

- `serve/fixtures/fake_sd_cli.py:1-4,35-42` — fixture の用途説明、環境変数の truthiness 判定、標準出力、終了コード。
- `serve/test_images.py:23-30,233-241,298-305` — テスト用実行ファイルへの差し替えと、環境変数を設定した失敗経路の検査。
- `serve/images.py:131-149,220-237,265-276` — 現在の環境の複製、子プロセスへの設定、非ゼロ終了時の失敗処理。
- `serve/server.py:5717-5723` — `ImageJobFailed` を HTTP 500 の `image_generation_failed` 応答へ変換。
- `docs/DETAILS.md:1571-1600` — 照合した画像関連節。対象は画像入力・vision encoder。
