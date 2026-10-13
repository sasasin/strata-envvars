# `STRATA_KEEP_EMPTY_TURNS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

サーバーのチャットテンプレートへ渡すメッセージ列について、途中にある空の assistant メッセージを残すかどうかを切り替えます。既定では該当する途中のメッセージをテンプレート描画前に除きます。`STRATA_KEEP_EMPTY_TURNS=1` を設定すると、従来どおりそのまま描画します。これは `serve/frontend.py` の `ChatTemplate.render()` にある Python サーバー側の処理です。

## 値と判定

| 環境変数の値 | 動作 |
|---|---|
| 未設定 | 空の assistant メッセージを除く |
| 空文字 | 空の assistant メッセージを除く |
| 正確に `1` | すべてのメッセージを残す |
| その他（例: `0`, `true`, `01`, `1 `） | 空の assistant メッセージを除く |

値は `os.environ.get(...) == "1"` で文字列全体を比較します。数値変換や前後空白の除去、大文字小文字を無視する処理はありません。

「空の assistant メッセージ」として除かれるのは、最後のメッセージではなく、次の条件をすべて満たすメッセージです。

- メッセージが辞書で、`role` が文字列 `assistant`。
- `_text_of(content).strip()` が空。文字列の content のほか、`text` / `input_text` 型のテキスト部分を判定します。
- `image_url` / `input_image` / `image` 型の画像部分を含まない。
- `tool_calls` が偽値。空でない tool call 群を持つメッセージは除きません。

したがって空白だけの本文も空とみなされます。画像または tool calls を持つ assistant メッセージは、本文テキストが空でも残ります。

## 有効になる条件

この設定が使われるのは `serve/frontend.py` の `ChatTemplate.render()` を通るテンプレート描画です。エンジンの環境変数やネイティブ推論カーネルを直接切り替える設定ではありません。コードは API dialect や OS ごとの別判定を設けていません。チャットテンプレートの能力検出も同じ `render()` を呼ぶため、サーバー起動時のプローブ描画にも適用されます。

## 実行時の詳細

`ChatTemplate.render()` は呼び出しごとに `os.environ.get("STRATA_KEEP_EMPTY_TURNS")` を評価し、条件を満たしたメッセージを除いた新しいリストを `self.template.render(...)` に渡します。モジュール起動時に値をキャッシュする実装ではありません。したがってプロセス内で環境値が変更されれば、以降の render 呼び出しの判定にも反映されます。

アプリケーションのサービス処理は `Service.render_prompt()` から `self.template.render()` を呼び、通常の描画に加え、reasoning effort の扱いによっては同じ要求内で複数回描画します。環境変数は各描画時に評価されます。除外はテンプレートへ渡すリストに対するもので、元のメッセージ辞書や会話履歴を書き換える処理はここにはありません。

`docs/TROUBLESHOOTING.md` は、空の返信がチャット履歴から見えなくなった場合の回避策として、サーバー環境に `STRATA_KEEP_EMPTY_TURNS=1` を設定すると以前の描画に戻ると説明しています。`docs/DETAILS.md` も同項目を TROUBLESHOOTING への参照として挙げています。性能値や推論結果への影響を示す測定値は確認できません。

## 根拠

- `serve/frontend.py:57-66` — `ChatTemplate.render()` の環境変数比較、フィルタ条件、描画への引き渡し。
- `serve/frontend.py:121-127,130-161` — テキスト部分と画像部分の判定。
- `serve/frontend.py:68-74,84-113` — template capability probe が同じ `render()` を使う。
- `serve/server.py:3401-3417` — サービスの prompt 描画経路と複数回描画するケース。
- `serve/server.py:6276-6280` — 起動時に `ChatTemplate` をサービスへ渡す箇所。
- `docs/TROUBLESHOOTING.md:89-91`, `docs/DETAILS.md:278-279` — 空の assistant turn が履歴で消える場合と設定による復元についての案内。
