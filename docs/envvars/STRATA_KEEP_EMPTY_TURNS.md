# `STRATA_KEEP_EMPTY_TURNS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

`terminal/serve/frontend.py` の `ChatTemplate.render()` が、モデルへ渡すメッセージ履歴から空の assistant メッセージを取り除くかを切り替える。`STRATA_KEEP_EMPTY_TURNS` が文字列 `"1"` のとき、この除去を行わず、従来どおりそれらもテンプレートへ渡す。値はモデルの出力や選択を直接指定するものではなく、テンプレートへ渡す履歴を変える（`terminal/serve/frontend.py:71-87`）。

## 値と判定

Python の `os.environ.get("STRATA_KEEP_EMPTY_TURNS") == "1"` で毎回文字列全体を比較する。数値変換、空白除去、大文字小文字変換はしない。未設定 (`None`)、空文字、`"0"`、`"true"`、`"01"`、`"1anything"` など `"1"` 以外はすべて除去側の動作になる。`"1"` のみ除去を抑止する（`terminal/serve/frontend.py:75-78`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
| --- | --- | --- | --- |
| `ChatTemplate.render()` | 空の assistant 履歴を除去 | `1` | 空文字、`0`、`true`、`01`、`1anything` など `1` 以外 |

ここで「空」と判定されるのは、メッセージが辞書で role が `assistant`、テキスト部分を連結した内容の `.strip()` が空、画像を含まず、`tool_calls` が truthy でない場合。テキスト部分は文字列ならそのまま、リストなら `type` が `text`、`input_text` または未指定の辞書要素の `text` を連結する。画像の有無は `image_url`、`input_image`、`image` の各 type を調べる（`terminal/serve/frontend.py:168-175`, `235-236`）。メッセージ列の最後の要素は、空であっても常に残る。`"1"` はそれ以外の位置にある対象メッセージも残す（`terminal/serve/frontend.py:75-78`）。

## 有効になる条件

- Strata の Python サーバーが `ChatTemplate` を用いてプロンプトを描画する経路で参照される。サーバーはテンプレートを `ChatTemplate` として構築し（`terminal/serve/server.py:8974-8979`）、`Service.render_prompt()` から `self.template.render()` を呼び出す（`terminal/serve/server.py:5173-5190`）。
- CUDA/HIP/SYCL、OS、モデル種類、build macro、CLI 引数、別の環境変数による追加条件や優先順位は、この判定にはない。該当する empty assistant メッセージが履歴になければ、値によるメッセージ除去の差は生じない（`terminal/serve/frontend.py:75-87`）。
- `"1"` 以外の場合でも、最後のメッセージ、空でないテキストを持つ assistant メッセージ、画像を含む assistant メッセージ、truthy な `tool_calls` を持つ assistant メッセージは、この条件では除去されない（`terminal/serve/frontend.py:75-78`）。

## 実行時の詳細

`ChatTemplate.render()` が呼ばれるたびに `os.environ.get()` を評価し、該当する途中の空 assistant メッセージを除いた新しいリストをテンプレートに渡す。読み取った値を保持するキャッシュはないため、プロセス実行中に環境値が変更されれば次の描画呼び出しから判定に反映される（`terminal/serve/frontend.py:71-87`）。サーバーでは描画結果が `encode_prompt()` に渡され、トークン化される（`terminal/serve/server.py:5196-5209`）。

他の環境変数・CLI 引数・設定ファイルとの上書き関係は実装されていない。`ChatTemplate` の能力検出も `render()` を呼ぶが、その空 assistant の probe メッセージには `tool_calls` があるため、本変数の除去条件には該当しない（`terminal/serve/frontend.py:89-115`）。

## ログと測定値

この分岐に伴うログ、警告、終了・失敗経路は実装されていない。プロンプト履歴の内容が変わり得るが、この環境変数についての性能測定値は確認できない。

## 根拠

- `terminal/serve/frontend.py:71-87` — 値の読み取り、履歴フィルター、テンプレート描画。
- `terminal/serve/frontend.py:89-115` — 起動時の能力検出と描画 probe。
- `terminal/serve/frontend.py:168-175`, `235-236` — テキスト・画像の判定。
- `terminal/serve/server.py:5173-5209`, `8974-8979` — サーバーの描画・トークン化経路と `ChatTemplate` の構築。
