# `INKLING_MOCK_CAPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

この変数は、本番の `strata-inkling` engine ではなく、テスト／QA 用の `terminal/tools/inkling_mock_engine.py` が模擬する capability を指定する。`caps_of()` が値を辞書にし、`--info` の capability 表示と、serve 中の `images` capability による `image` 入力キーの受け入れを変える。実際の推論機能を有効にする設定ではない（`terminal/tools/inkling_mock_engine.py:1-5,55-56,64-68,117-120,220-223`）。

この mock 専用スクリプト内で環境から値を読む実装が確認できるため、環境変数候補として文書化する。Strata の本番 engine がこの名前を読むコードは見つからなかった。`docs/DETAILS.md` にもこの mock 用変数の説明はない。

## 値と判定

`os.environ.get("INKLING_MOCK_CAPS") or ...` で値を得て、偽値（未設定または空文字）なら既定の `drafter=dspark images=1 parallel=64` を使う。文字列を空白で分割し、`=` を含む各 token を最初の `=` で二分して辞書にする。値の型変換や妥当性検証、許可キーの検査はない。重複キーは後の token が辞書値を上書きする。キー・値の比較は大文字小文字を区別する（`terminal/tools/inkling_mock_engine.py:55-56`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `--info` 表示 | `drafter=dspark images=1 parallel=64` 相当 | `drafter=... images=... parallel=...` の token が表示値を置き換える。任意の文字列を値にできる | `=` を含まない token は無視。個々のキーを省略すると表示では既定値に戻る |
| `--serve` の `GEN` 入力 | `images=1` なので `image` キーを受け入れる | `images=1` の完全一致だけが `image` キーを許可する | `images=0`、`images=true`、`images=01`、`images=1x`、`Images=1` などは許可しない |

空文字 `INKLING_MOCK_CAPS=""` は unset と同じ既定値になる。一方、空白だけの文字列は truthy のため既定値に戻らず、分割後は空辞書になる。この場合 `--info` 表示は各キーの表示 fallback を使うが、serve の `INFO` 行では `images=0` となる。たとえば `images=` は空の値を設定するため `images=1` と一致せず、`images=1 extra` は `images=1` を有効にするが `extra` は無視される。`images=1=more` は値が `1=more` となるため有効ではない。整数への変換や数値境界はない（`terminal/tools/inkling_mock_engine.py:55-56,65-68,119-120,220`）。

## 有効になる条件

- この名前を読むのは Python mock engine のみ。実際の `strata-inkling` engine や他の backend／OS に対する設定ではない（`terminal/tools/inkling_mock_engine.py:1-5,55-56`）。
- `--info` では `drafter`、`images`、`parallel` の値が文字列として出力される。`--serve` 時にこれらのうち分岐に使われるのは `images` の完全一致 `1` だけで、`drafter` と `parallel` は `--info` 表示にしか使われない。serve の `INFO` 行に出る drafter は `--draft` 引数から別に決まる（`terminal/tools/inkling_mock_engine.py:64-68,117-120`）。
- `--serve` の通常 `GEN` プロトコルでは、`images` が `1` 以外のとき `image=...` キーは不正キーとなり、最初の不正キーについて `ERR unsupported key image` を stdout に出してその入力を処理しない。`images=1` でも、受信した image 数と `IMAGE_PAD_ID` の個数が一致しなければ `ERR image: ... files for ... image placeholders` を出して処理しない（`terminal/tools/inkling_mock_engine.py:205-227`）。
- `IMAGE_PAD_ID` は別変数 `INKLING_MOCK_PAD_ID`（未設定または空なら `200054`）でプロセス起動時に設定される。画像 placeholder 数の条件に影響するが、`INKLING_MOCK_CAPS` の画像許可判定を上書きしない（`terminal/tools/inkling_mock_engine.py:23,224-227`）。
- 値の違いが scripted token 列や本物の画像処理を有効にする根拠はない。画像は mock の入力検査と token 数計算に使われ、生成列は別途指定された script から出る（`terminal/tools/inkling_mock_engine.py:77-80,224-256`）。

## 実行時の詳細

引数 `--version` の場合は capability を読み取らず終了する。`--info` の場合は `caps_of(os.environ)` を呼び、値を表示して終了する。通常起動では引数・script・record を処理した後、`caps_of(os.environ)` を一度呼んで `caps` に保持し、起動時の `INFO` 表示と後続の `GEN` 検査に使う（`terminal/tools/inkling_mock_engine.py:59-69,70-82,117-120,163-165,205-223`）。したがって実行中にプロセス環境を変更しても再読込する箇所はなく、現在の `caps` には反映されない。CLI の `--vision` や `--draft` は `INKLING_MOCK_CAPS` の値を上書きしない。

テスト用 server の E2E harness はこのスクリプトを `strata-inkling` 名の wrapper から起動する（`terminal/serve/test_inkling_serve_e2e.py:147-165`）。この harness の存在は mock の利用範囲を示すもので、本番 engine の動作根拠ではない。

## ログと測定値

変数値自体について警告やエラーを出す処理はない。`--info` は `arch=... drafter=... images=... image_pad=... parallel=...` 形式を stdout に出す（`terminal/tools/inkling_mock_engine.py:64-68`）。serve 起動時の `INFO` 行は `images=1` または `images=0` を出す（`terminal/tools/inkling_mock_engine.py:117-120`）。画像キーが capability で拒否された場合は `ERR unsupported key image`、placeholder 数が合わない場合は `ERR image: {画像数} files for {placeholder数} image placeholders` を stdout に出す（`terminal/tools/inkling_mock_engine.py:220-227`）。性能測定値は該当しない。

## 根拠

- `terminal/tools/inkling_mock_engine.py:1-5` — mock engine の用途。
- `terminal/tools/inkling_mock_engine.py:55-56,64-68,70-82` — 環境値の読み取り、既定値、`--info` と通常起動での評価。
- `terminal/tools/inkling_mock_engine.py:117-120,205-227` — serve 表示、画像 capability 判定と失敗経路。
- `terminal/tools/inkling_mock_engine.py:23,224-256` — placeholder ID と mock の処理結果。
- `terminal/serve/test_inkling_serve_e2e.py:147-165` — E2E harness からの mock 起動例。
