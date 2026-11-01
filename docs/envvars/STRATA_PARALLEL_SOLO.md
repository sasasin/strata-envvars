# `STRATA_PARALLEL_SOLO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

サーバーの batch slot で decode 中のリクエストが単独になったとき、slot に留めず通常の solo generation 経路へ戻す動作を止めます。solo 経路へ戻る際は slot を `BSTOP` し、engine が slot の session state を引き継いで通常の生成を続けます。サーバーが batch slot を使わない構成ではこの変数を読みません。リクエスト開始時から solo 経路にいる場合の動作も変えません。

## 値と判定

Python の `os.environ.get("STRATA_PARALLEL_SOLO") == "0"` という文字列の完全一致です。数値変換、trim、大文字小文字変換はありません。

| 環境値 | slot から solo へ戻る分岐への影響 |
|---|---|
| 未設定 | 無効化しない（他の条件を満たせば戻る） |
| `0` | 無効化する。slot に留まる |
| 空文字 | 無効化しない |
| `00`, `0 `, `false`, `False`, `1` など | 無効化しない。完全一致するのは `0` だけ |

既定値は実質的に有効（solo へ戻る動作を許す）です。無効な文字列として拒否する値や警告・fallback はありません。

## 有効になる条件

この環境変数が影響するには、サーバーが batch slot 経路を使い（`StrataEngine.generate()` が `self.batch` を見て `generate_batched()` に入る）、slot 内で生成中である必要があります。さらに、slot から solo へ戻る判定時に次の条件をすべて満たす必要があります。

- 入力が embeddings ではない。
- このリクエストが既に solo に戻った回数が 2 回未満。
- 残り生成上限 `left` が 32 token 以上。
- engine の `INFO` にある `slot_cache` が truthy。
- `STRATA_PARALLEL_SOLO` が文字列 `0` ではない。
- slot 状態ロック内で使用中 slot がちょうど 1 つ、待ちリクエストが 0 件。

engine は `--batch` が有効なとき `slot_cache` を `--prompt-cache > 0` に応じて `1` または `0` として `INFO` に出します。したがって `--prompt-cache 0` ではこの復帰動作は起きません。環境変数が `0` でも batch slot 内の生成そのものや、slot 内で有効にした MTP draft の設定を無効化する処理はありません。

## 実行時の詳細

値はサーバー起動時に定数へ cache されず、batch slot の `BT` token ごとに `_may_go_solo()` が呼ばれた際に `os.environ.get()` で読み直されます。従って、サーバープロセス内で環境を変更すれば、その後の判定に反映されます。slot 条件の確認後、復帰可能と判定するとサーバーは `BSTOP <slot>` を送ります。engine の `BDONE` が `cancel` で返り、リクエストが未完了かつキャンセル/EOS でなければ、server は残りを solo path で続けます。環境値が `0` の場合 `_may_go_solo()` は false を返すため、その切り替えの `BSTOP` は送られず、slot 側で続行します。

環境変数自体についてのログ、警告、終了・失敗経路は実装にありません。slot から solo に戻る際には内部の `btrace("back to the solo path")` が呼ばれますが、観測可能な出力になるかは `btrace` の診断設定に依存します。

## 根拠

- `serve/server.py:1873-1884`: solo 復帰回数・残り token の閾値、embeddings と `slot_cache` の条件、環境値の完全一致判定、単独 slot と待ち件数の条件。
- `serve/server.py:1913-1932, 2148-2176`: batch 経路の状態管理と、各 `BT` token 後の判定および `BSTOP` 送信。
- `serve/server.py:2177-2203`: `BDONE cancel` 後、条件を満たす場合に solo path に戻して生成を続ける処理。
- `serve/server.py:2327-2336`: `self.batch` がある場合だけ `generate_batched()` を呼ぶ。
- `serve/server.py:1102-1105, 1167-1173`: engine の `INFO` 行の受信・保存と batch slot 数の取得。
- `src/program/generate.cpp:852, 3227, 12284-12286`: `--prompt-cache` の既定値 6、CLI 値の非負変換、および batch 時に `prompt_cache > 0` から `slot_cache` を出力する処理。
- `docs/BATCHING.md:159-170`: slot 内生成、単独になった slot の solo 復帰、`--prompt-cache 0` とこの環境変数の説明。挙動の根拠は上記の実装。
