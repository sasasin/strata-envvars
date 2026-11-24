# `ALL_PROXY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`ALL_PROXY` は `terminal/setup.py` の `proxy_hint()` が、ダウンロード失敗時に案内文を選ぶために読みます。`HTTPS_PROXY`、`https_proxy`、`all_proxy` と同じ設定有無の確認対象です。いずれかに空でない値があれば「proxy が設定されている」と案内し、そうでなければ `HTTPS_PROXY` の設定例を案内します（`terminal/setup.py:236-241`）。

このコードが行うのは環境変数の確認と失敗案内の選択です。`ALL_PROXY` の値を parse したり、この値を Strata の別プロセスへ渡したりする処理は確認できません。Strata の通信がこの値でどのように proxy を使うかは、この読み取り箇所からは説明できません。

## 値と判定

`os.environ.get()` の戻り値を真偽値として判定します。値の形式や内容は検証しません（`terminal/setup.py:238-241`）。

| 条件 | unset | 有効になる値（例） | 有効にならない値（例） |
|---|---|---|---|
| setup が失敗案内を組み立てるとき | `ALL_PROXY` 単独では proxy 設定ありと判定しない | 空でない文字列。例: `http://host:port`、`1`、`false`、空白 | 空文字 `""`。ただし他の3名のいずれかが空でなければ proxy 設定ありになる |

ここでの「有効」は proxy 通信を有効化する意味ではなく、「proxy が設定されている」という案内分岐に入る意味です。`0`、`false`、不正な URL らしい値も空でなければ同じ分岐です。大文字小文字の比較や数値変換はありません。名前は大文字 `ALL_PROXY` と小文字 `all_proxy` の両方を個別に参照します。

## 有効になる条件

- `terminal/setup.py` のダウンロード処理で、ネットワーク到達失敗または `OSError` / `HTTPException` などの接続失敗案内が組み立てられること。通常の成功経路ではこの確認はありません（`terminal/setup.py:1123-1128`, `3573-3581`）。
- `ALL_PROXY` 以外の `HTTPS_PROXY`、`https_proxy`、`all_proxy` が空でない場合も同じ案内分岐です（`terminal/setup.py:238-241`）。
- setup の CLI 引数、OS、GPU backend、build macro による `proxy_hint()` 内の条件分岐はありません。ここで確認する値の優先順位もなく、4名のいずれか1つでも空でない値があれば該当します（`terminal/setup.py:236-241`）。

## 実行時の詳細

`proxy_hint()` は値をモジュール初期化時に保存せず、呼び出されるたびに4つの名前を `os.environ.get()` で確認します。呼び出しは `net_fail()` と、ダウンロード中の HTTP / OS 接続例外の案内生成箇所です（`terminal/setup.py:236-241`, `1123-1128`, `3573-3581`）。したがって、setup プロセスの環境が変わった後に関数が呼ばれれば、その時点の値が判定されます。

該当経路では `fail()` が案内を表示し、`--output jsonl` 使用時は `error` イベントにも `hint` と `exit_code: 1` を含めて、終了コード 1 で setup を停止します（`terminal/setup.py:1049-1056`）。`ALL_PROXY` の文字列自体はその案内やイベントに出力されません。

## ログと測定値

proxy 設定ありと判定した場合の案内は、通常の接続失敗経路では `a proxy is set in this terminal (HTTPS_PROXY): check that it is the right one and that it is running` です。`net_fail()` 経由では先頭が大文字になり `A proxy ...` となります。4名すべてが未設定または空なら `behind a company or school proxy, set HTTPS_PROXY (for example HTTPS_PROXY=http://host:port) in this terminal first` を案内します（`terminal/setup.py:236-241`, `1123-1128`, `3573-3581`）。

これは失敗時の案内であり、`ALL_PROXY` による接続成功・失敗の変化を示す Strata の測定値はありません。

## 根拠

- `terminal/setup.py:236-241` — 4つの proxy 変数の設定有無判定と案内文。
- `terminal/setup.py:1123-1128` — `net_fail()` からの読み取り、および失敗処理。
- `terminal/setup.py:3573-3581` — ダウンロード失敗経路からの直接の案内呼び出し。
- `terminal/setup.py:1049-1056` — `fail()` の表示、JSONL error イベント、終了コード。
