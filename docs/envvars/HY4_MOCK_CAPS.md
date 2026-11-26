# `HY4_MOCK_CAPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

これは `terminal/tools/hy4_mock_engine.py` が mock エンジンの機能応答を切り替えるための環境変数である。同スクリプトの説明では serve / Control / app のプロトコル試験用 stand-in とされている。`--info` の能力応答に drafter と images を載せ、serve が起動引数を選ぶ経路を試験できる。`strata-hy4` 本体が読む設定ではなく、実エンジンの機能を有効化しない（`terminal/tools/hy4_mock_engine.py:1-7,53-62`; テストでの設定例: `terminal/serve/test_hy4_serve_e2e.py:122-127`）。

## 値と判定

`caps_of(env)` は `env.get("HY4_MOCK_CAPS") or ""` を文字列化して空白で分割し、`=` を含むトークンだけを最初の `=` で二分して辞書化する。キーは大文字小文字を区別し、同じキーが複数ある場合は後の値が残る。値の型・全体形式・許容範囲の検証はない（`terminal/tools/hy4_mock_engine.py:53-55`）。

| 条件 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `--info` の drafter 能力 | `drafter=none` | `drafter=dfly2` を出力する値 | `drafter=none`、`drafter=DFLY2` など。serve が `dfly2` と完全一致で判定する |
| `--info` の画像能力 | `images=0` | `images=1` を出力する値 | `images=0`、`images=true`、`images=01` など。serve が `1` と完全一致で判定する |
| mock の serve 起動 | `images` は無効 | `images=1` のとき起動時 `INFO` に `images=1` を出力し、`image=...` キーを受理 | `images` が `1` 以外なら `INFO` は `images=0`、画像キーは `ERR unsupported key image` |

トークンの例は `drafter=dfly2 images=1`。`0`、`1`、`true` などの値自体は一般的な真偽値としては解釈されず、上表のキーごとの完全一致にだけ使われる。`x=1=2` は `x` の値が `1=2` になる。`x` のように `=` がないトークンは無視される（`terminal/tools/hy4_mock_engine.py:53-55,61-62,75-77,123-126`）。

## 有効になる条件

- `HY4_MOCK_CAPS` を読むのは mock エンジンだけである。E2E テストは `clean_env(...)` にこの変数を含めて serve プロセスを起動し、mock 子プロセスへ継承させる（`terminal/serve/test_hy4_serve_e2e.py:122-127`）。
- serve が drafter 能力を probe するのは、`--draft` が既に引数に無く、設定上 drafter が必要な場合である。`--info` が `drafter=dfly2` と返した場合だけ `--draft dfly2` を追加する。そうでなければ既定の告知 `[strata] Hy4-Flash: this engine has no drafter (DFly2) yet, so it starts without it` を出す（`terminal/serve/hy4_kind.py:54-59,99-101,143-150`）。
- serve が画像能力を probe するのは `--vision` が起動引数にある場合である。`images` が文字列 `1` でなければ `--vision` とその値を引数から除き、既定では `[strata] Hy4-Flash: this engine does not read images yet, so it starts without the image reader` を出す（`terminal/serve/hy4_kind.py:143-155`）。
- mock の通常起動では、`images=1` のときだけ `image` リクエストキーを認める。それ以外では最初の未対応キーについて `ERR unsupported key <key>` を stdout に返して、そのリクエストを処理しない（`terminal/tools/hy4_mock_engine.py:75-77,113-126`）。

## 実行時の詳細

mock の `--info` 起動は `caps_of(os.environ)` を呼び、`arch=hy4flash ... drafter=<値> images=<値>` を stdout に出力して終了する。通常の mock serve 起動も `caps_of(os.environ)` を呼ぶが、起動 `INFO` 行の `images` は `images == "1"` の場合だけ `1`、それ以外は `0` とする。起動時の `drafter` 表示はこの環境変数ではなく、CLI の `--draft dfly2` の有無で決まる（`terminal/tools/hy4_mock_engine.py:58-77`）。

serve 側の probe は実行ファイルと `--native` / `--model` のモデル引数があり、実行ファイルがファイルとして存在するとき、現在の `os.environ` を複製した環境で mock の `--info` を起動する。結果は実行ファイルのパス・更新時刻・サイズとモデルパスをキーに `_PROBES` へキャッシュするため、同じ serve プロセス内で環境変数だけを変更しても probe 済み能力は再取得されない。probe は指定時間内に完了しない場合や起動・終了に失敗した場合 `None` となり、serve は drafter / images の能力がないものとして扱う（`terminal/serve/hy4_kind.py:70-96,143-155`）。

## ログと測定値

mock の `--info` は能力行を stdout に出す。通常起動では `INFO` 行の `images` が `images=1` または `images=0`、`drafter` が `dfly2` または `off` になる。serve は capability 不足時に `NO_DRAFTER_NOTE` / `NO_IMAGES_NOTE` の原文を標準出力へ出し（有効条件を満たす場合）、mock が非対応の画像キーを受け取ると `ERR unsupported key image` を stdout に返す（`terminal/tools/hy4_mock_engine.py:60-62,75-78,123-126`; `terminal/serve/hy4_kind.py:48-50,149-155`）。測定値に関する記述は該当しない。

## 根拠

- `terminal/tools/hy4_mock_engine.py:1-7,53-77,113-126`
- `terminal/serve/hy4_kind.py:54-59,62-96,99-101,143-155`
- `terminal/serve/test_hy4_serve_e2e.py:122-127`
