# `HUGGING_FACE_HUB_TOKEN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Terminal の転送処理が Hugging Face と判定した HTTP(S) URL へのリクエストに、Bearer 認証ヘッダーを付ける token の候補の一つ。実装は `strata_control.transfer.hf_auth_headers` で、`HF_TOKEN` が空または未設定の場合にこの変数を読み、両方が使えなければ認証ヘッダーを付けない。対象には feed・署名の読み込みとファイル転送の HTTP リクエストが含まれる（`terminal/strata_control/transfer.py:239-251, 298-314, 405-418`）。

## 値と判定

Python の `env.get("HF_TOKEN") or env.get("HUGGING_FACE_HUB_TOKEN") or ""` で選択した後、選ばれた文字列に `.strip()` を適用する。文字列全体の形式検査や token の検証は行わない。選択は strip より先なので、空白だけの `HF_TOKEN` は空文字に strip された後で認証なしとなり、この変数への fallback は起きない（`terminal/strata_control/transfer.py:242-245`）。

| 条件 | unset | `HUGGING_FACE_HUB_TOKEN` 設定時 | 無効または認証なしになる例 |
|---|---|---|---|
| HTTP(S) URL が Hugging Face host と一致し、`HF_TOKEN` が未設定または空 | 選択結果は空。ヘッダーなし | 前後の空白を除いた文字列を `Bearer` 値として付与 | 未設定、`""`、空白だけならヘッダーなし |
| `HF_TOKEN` が非空 | この変数は選択されない | `HF_TOKEN` が優先される | `HF_TOKEN="hf_primary"` なら本変数の値は無視 |
| 非空だが空白だけの `HF_TOKEN` | strip 後に空になり、ヘッダーなし | 本変数へは fallback しない | `HF_TOKEN="   "` かつ本変数が `"hf_fallback"` でもヘッダーなし |
| URL が HTTP(S) 以外、または Hugging Face host でない | ― | 値があってもヘッダーなし | 例: `https://cdn-lfs.s3.amazonaws.com/...` |

token は `.strip()` で両端の空白を除くだけで、大文字小文字や内部文字列の妥当性は検査しない。Hugging Face host は `huggingface.co` / `hf.co` とそのサブドメイン、または `HF_ENDPOINT` の URL から得た host との完全一致で判定する。`HF_ENDPOINT` は前後空白を除き、抽出した host は小文字化される（`terminal/strata_control/transfer.py:220-236, 243-251`）。

## 有効になる条件

- 転送元が HTTP(S) で、host が `huggingface.co` / `hf.co` のドメインまたは `HF_ENDPOINT` の host と一致すること。異なる host へリダイレクトすると `Authorization` ヘッダーは削除される（`terminal/strata_control/transfer.py:220-236, 254-264`）。
- transfer のネットワーク経路を通ること。ローカルファイル・パスの読み込みには認証ヘッダーを作らない（`terminal/strata_control/transfer.py:303-321, 407-415`）。
- HTTP の場合は URL policy も適用され、loopback host または `STRATA_UPDATE_ALLOW_HTTP="1"` でなければ転送前に拒否される（`terminal/strata_control/transfer.py:166-175, 306-308, 410-415`）。
- `HF_TOKEN` が空でない場合はそちらが優先される（`terminal/strata_control/transfer.py:242-251`）。

値が有効でも、host が対象外なら送信されない。GPU backend、モデル状態、サーバーモード、ビルド macro による分岐はこの helper にない。

## 実行時の詳細

`hf_auth_headers` は feed 等の小さい HTTP 文書を読む `read_small` と、ファイルを取得する `_transfer` が各 HTTP リクエストを組み立てるときに呼ばれる。関数内 static cache はなく、呼び出しごとに `os.environ`（テスト等では任意の `environ` mapping）から値を取得する。したがって、転送中に環境を変更した場合も、その後に組み立てるリクエストで再評価される。ローカル経路ではこの helper を呼ばない（`terminal/strata_control/transfer.py:239-251, 298-314, 405-418`）。

## ログと測定値

この変数専用のログや値の出力はない。HTTP 応答が `HTTPError` になった場合、`read_small` と `_transfer` はステータスコードを含む `the update server answered {code} for {location}` の `TransferError` を作る。認証失敗を token 固有の理由として分類する処理はここにはない（`terminal/strata_control/transfer.py:322-331, 443-461`）。

`docs/DETAILS.md:211-217` は `uvx hf auth login` の説明内で「Strata はこの token を読まない・送らない」と記す。一方、この HEAD の transfer 実装は `HUGGING_FACE_HUB_TOKEN` を読み、条件を満たすリクエストに Bearer header を追加するため、この点は資料と現行ソースで不一致である。ここでは現在の挙動をソースで確認できる範囲に限定した。

## 根拠

- `terminal/strata_control/transfer.py:220-251` — Hugging Face host 判定、`HF_TOKEN` との優先順位、token の trim、Bearer header の作成。
- `terminal/strata_control/transfer.py:254-264` — 別 host への redirect 時に認証 header を削除。
- `terminal/strata_control/transfer.py:298-314, 405-418` — 小文書とファイル転送の HTTP リクエストへの適用。
- `terminal/strata_control/transfer.py:166-175, 322-331, 443-461` — HTTP policy と HTTP エラーの扱い。
- `docs/DETAILS.md:211-217` — 現行実装と異なる token 説明。
