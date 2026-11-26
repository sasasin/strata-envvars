# `STRATA_METAL_KPROF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal エンジンの window 実行で、指定 token 数の head 付き cached window が 20 回目に達したとき、カーネル class ごとの GPU 時間を測って stderr に出す診断用フックです。通常の window 実行を設定する変数ではなく、CLI 引数や生成設定による優先順位もありません。読み取りと起動判定は `Window::run`、測定と出力は `Window::kprof` が行います（`engine/metal/src/engine/window.cpp:1489-1492,1545-1555,1856-1898`）。

## 値と判定

`Window::run` の cache hit 分岐内で `std::getenv` が非 null なら `std::atoi` に渡し、そうでなければ `0` にします。この `static const int` は初めて cache hit 分岐に入ったときに評価され、その後はプロセス内で再読込されません（`engine/metal/src/engine/window.cpp:1530-1532,1545-1550`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Metal `Window::run` の cached-window 分岐 | `kt=0`。通常の window サイズは 1 以上なので一致しない | `2`、`+2`、` 2x` は `atoi` の結果が 2 となり、`Tn=2` で起動条件を満たし得る | 空文字、`abc`、`0`、`0anything` は 0。`-2` は -2。いずれも有効な `Tn` と一致しない |

`atoi` は先頭の空白と符号、続く十進数字を読み、数字の後ろは検査しません。全体の数値妥当性、大文字小文字、範囲を別途検査するコードはありません。数値変換で数字を読めない場合は 0 です。`Tn` は `Window::run` 冒頭で `1..MAXT`（head 付きならさらに `max_t_` 以下）に制限されます（`engine/metal/src/engine/window.cpp:1489-1492`）。

## 有効になる条件

- Metal エンジンの `Window::run` が呼ばれること。これは Metal 実装内のフックで、他 backend についてこのコードによる読み取りはありません。
- `STRATA_METAL_KPROF` の変換結果と window の token 数 `Tn` が一致し、`head` が true であること（`engine/metal/src/engine/window.cpp:1548-1550`）。
- 対象の window 形状がすでに `wcache_` にあり、cache hit 側に入ること。cache miss では計測判定箇所に到達しません（`engine/metal/src/engine/window.cpp:1530-1532,1545-1550,1560-1568`）。
- 一致した head 付き cache hit の通算 20 回目に `stream_` が false であること。`seen` は一致するたびに増え、20 回目に streaming 中なら `kprof` は呼ばれず、その後は 20 と再一致しないため実行されません（`engine/metal/src/engine/window.cpp:1548-1550`）。

条件を満たさない場合、fallback や理由ログはありません。別の CLI オプションや環境変数による上書きは、この判定箇所にはありません。

## 実行時の詳細

値と `seen` は関数内 `static` で保持されます。環境変数の変更は最初の cache hit 分岐で値が初期化された後には反映されません。`seen` は同じプロセスの `Window::run` 呼び出し間で共有され、対象 token 数と `head` が一致した cache hit のみで増えます（`engine/metal/src/engine/window.cpp:1545-1550`）。

通常の cached window を `run_ds(c)` で実行した後に判定されます。条件成立時、`kprof` は dispatch を pipeline 名などで class 分けし、window 全体と各 class の dispatch 群を `run_graph` でそれぞれ 7 回実行し、中央値を使います。これは診断計測の追加 GPU 実行であり、CLI の生成設定を変える処理ではありません（`engine/metal/src/engine/window.cpp:1545-1550,1856-1898`）。

## ログと測定値

stderr に次の形式で window 全体と class ごとの行を出します。文言は `engine/metal/src/engine/window.cpp:1896-1898` の実装文字列です。

```text
strata metal kprof: window T%d, %zu dispatches, GPU %.3f ms; classes alone (serialized) sum %.3f ms:
strata metal kprof: %8.3f ms %5.1f%%  %s
```

コードにこの機能の標準的な性能値や機種別測定値は記載されていません。条件を満たさない場合、このフックからのログは出ません。

## 根拠

- `engine/metal/src/engine/window.cpp:1489-1492` — window サイズの範囲検査。
- `engine/metal/src/engine/window.cpp:1530-1558` — cache hit/miss、実行後の値判定と呼び出し。
- `engine/metal/src/engine/window.cpp:1856-1898` — class 分類、計測回数・中央値、stderr 出力。
