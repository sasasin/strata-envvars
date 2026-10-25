# `STRATA_DSV41_NO_SMOKE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

`setup.py` で DeepSeek-V4.1 の ISTA-DAS 系 GGUF セットを準備した後に行う、固定質問による 16 token の起動・応答 smoke test を省略します。セットアップのダウンロードや pack 作成、pack 内の必須ファイル検査は省略しません。

## 値と判定

値は `os.environ.get("STRATA_DSV41_NO_SMOKE") == "1"` で比較されます。文字列全体が ASCII の `1` と一致する場合だけスキップします。数値変換や trim、大文字小文字変換はありません。

| 環境変数の状態 | smoke test |
|---|---|
| 未設定 | 実行 |
| 空文字 | 実行 |
| `1` | スキップ |
| `0`、`true`、` 1`、`1 `、その他の値 | 実行 |

## 有効になる条件

- 対象は `setup.py` の `install_dsv41()` が扱う DeepSeek-V4.1 セットアップです。通常モデルのセットアップ経路にはこの判定がありません。
- モデルの `recipe` が `ista` の場合にだけ pack 検査と smoke test 分岐へ進みます。現在の `IST-DAS-1.75bpw`、`IST-DAS-2.00bpw`、`IST-DAS-2.25bpw` が該当します。`UD-Q8_K_XL` は `recipe: "ud"` なのでこの環境変数による smoke test の分岐には入りません。
- `STRATA_DSV41_NO_SMOKE=1` でも、pack 作成後の `strata-dsv41 --pack-info --pack ...` による検査は実行されます。検査が失敗すれば、その時点でセットアップは失敗します。

## 実行時の詳細

変数は `install_dsv41()` の step 6「preparing the model for Strata」で、ISTA-DAS セットの pack 検査に成功した後に評価されます。モジュール初期化時のキャッシュではなく、セットアップ処理中に `os.environ.get()` を呼びます。プロセス起動後に環境を変えた場合の再評価機会はこの分岐に到達した時点です。子プロセスに値を渡して判定させる実装ではありません。

値が厳密に `1` なら、`warn()` 経由で標準出力に `  [!]  the 16-word test run was skipped (STRATA_DSV41_NO_SMOKE=1)` を出し、smoke test を呼ばず step 7 の開始スクリプト作成へ進みます。値がそれ以外なら、固定質問「What is the capital of France?」で engine を実行します。通常は 16 token を生成し、応答に `Paris` を含むかなどの文字列検査に通る必要があります。テストが失敗すると `fail()` でセットアップを停止します。

このスイッチは smoke test を通過したことを保証する検査の代わりにはなりません。スキップ時も pack の必須ファイル存在検査は残りますが、実際に engine がモデルを読み込んで回答できるかは確認されません。

## 根拠

- `setup.py:748-775` — ISTA-DAS の3モデルは `recipe: "ista"`、Unsloth `UD-Q8_K_XL` は `recipe: "ud"`。
- `setup.py:7912-7920` — `dsv41_pack_info()` が `--pack-info` を実行し、終了コード・`MISSING`・`all present` を検査。
- `setup.py:7923-7936` — smoke helper が `tools/dsv41/smoke.py` を呼び、失敗を結果として返す。
- `setup.py:8081-8118` — step 6 のpack検査、環境変数の完全一致判定、警告または smoke test の分岐。
- `setup.py:808-823` — `warn()` は `say()` 経由で標準出力に `[!]` を表示。
- `tools/dsv41/smoke.py:1-7, 23, 43-58, 67-100` — 固定質問、既定16 token、応答テキストの妥当性検査、終了コード。
- `docs/DEEPSEEK41.md:52` — smoke test の手順説明。環境変数によるスキップの記述はないため、この調査では現行コードを根拠とした。
