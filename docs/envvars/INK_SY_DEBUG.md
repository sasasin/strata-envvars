# `INK_SY_DEBUG`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling-2 の Intel Arc SYCL runner がバッチサイズ 1 の処理を行うとき、埋め込み・attention・MoE の中間 float バッファをホスト側で集計し、統計を stderr に出す診断用フックである。モデルの計算や出力値を選ぶ設定ではない。値が有効でも `M != 1` なら診断は行わない。実装は `InkSyRunner::forward_batch` 内にある（`engine/src/inkling2/sycl/ink_sy_runner.h:421-426,472-486,583-593,728-732`）。

この runner は SYCL backend のビルドに含まれる。SYCL backend は `STRATA_ENABLE_SYCL` が有効な場合に別 backend として構成され、CUDA/HIP とは同時に有効化できない（`engine/CMakeLists.txt:23-32`）。Inkling-2 の CMake component は `STRATA_BUILD_INKLING` と `STRATA_BUILD_INKLING2` がともに有効な場合に追加される（`engine/CMakeLists.txt:917-922`）。

## 値と判定

`std::getenv` で設定有無を調べ、値の先頭 1 byte が文字 `'1'` かを比較する。文字列全体の parse や数値変換はしない。さらに `M == 1` が必要である（`engine/src/inkling2/sycl/ink_sy_runner.h:472`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `InkSyRunner::forward_batch`、`M == 1` | 無効 | `1`, `1anything`, `10`（先頭 byte が `'1'`） | 空文字、`0`, `0anything`, `-1`, `true`, `True`, ` 1`, `anything` |
| 同関数、`M != 1` | 無効 | なし | 設定値にかかわらず無効 |

大文字小文字や空白を正規化せず、先頭 byte だけを比較するため `true` は有効にならず、先頭に空白がある ` 1` も無効である。負数や数値としての妥当性は検査しない。未設定と空文字はいずれも条件式が偽になる。別の既定値、CLI 引数、設定ファイル、他の環境変数との優先順位はない（同 `:472`）。

## 有効になる条件

- `engine/src/inkling2/sycl/ink_sy_runner.h` が組み込まれた SYCL backend の実行経路であること。CUDA/HIP 実装からこの環境変数を読む箇所はない（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:15-16`; リポジトリ内の完全一致検索では読込は同 `ink_sy_runner.h:472` のみ）。
- 当該 `forward_batch` 呼び出しの `M` が 1 であること。SYCL backend adapter は入力を `runner_.max_batch` 以下のチャンクに分けて各チャンクのサイズ `M` を渡すため、元のバッチが大きくても末尾チャンクが 1 件なら、その呼び出しでは条件を満たし得る（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:129-138,167-170`）。
- `INK_SY_DEBUG` が設定され、その値の先頭 byte が `'1'` であること（`engine/src/inkling2/sycl/ink_sy_runner.h:472`）。

CLI オプション、サーバーモード、モデル状態、GPU 世代、追加の build macro による値の上書きは、この判定にはない。SYCL backend 自体を構成しないビルドでは、この runner の診断コードも実行経路に入らない（`engine/CMakeLists.txt:23-32`; `engine/src/inkling2/CMakeLists.txt:206-208`）。

## 実行時の詳細

環境変数はプロセス起動時や `InkSyRunner` 初期化時ではなく、`forward_batch` の呼び出しごとに `dbg` を初期化するとき読み取られる。環境値は `getenv` で2回参照されるが、判定結果 `dbg` はその呼び出し中のローカル `const bool` であり、各診断箇所で再評価されない。次の呼び出しでは再読込されるため、その間にプロセス環境が変更されれば次回の判定に反映される（`engine/src/inkling2/sycl/ink_sy_runner.h:472-474`）。

`dbg_buf` は `dbg` が偽なら直ちに戻る。有効時は指定されたデバイスバッファをホストへ転送し、`wait()` で待ってから値を集計する（同 `:473-484`）。埋め込み出力、visit 0 の Q/K/V・sinks・attention 出力と出力射影、各 visit の MoE hidden と current state が対象である（同 `:486,583-593,728-732`）。この経路は観測用の転送・同期・集計・ログを追加するが、そこからモデルバッファへ書き戻す処理はなく、診断値による分岐もない。

## ログと測定値

診断が有効な場合、各バッファについて次の形式の1行を stderr に出す。`tag` は `embed`、`v0_q` など呼出箇所で指定された名前、または `v<visit>_ip<layer>_moeh` / `v<visit>_ip<layer>_cur` である。`n` は集計要素数、`nan` と `inf` は非有限値の数、`min` / `max` は有限値の範囲、`l2` は有限値についての二乗和平方根である。有限値が一つもない場合、`min` / `max` は初期値の `1e30` / `-1e30` のまま出力される（`engine/src/inkling2/sycl/ink_sy_runner.h:478-484,486,583-593,728-732`）。

```text
  [DBG %s] n=%d nan=%d inf=%d min=%.4g max=%.4g l2=%.4g
```

未設定・無効値、または `M != 1` ではこの診断行は出ない。Strata の資料にこの変数による性能測定値は見当たらず、ここでは測定値を記載しない。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_runner.h:421-426,472-486,583-593,728-732` — `forward_batch` の値判定、診断バッファ転送・集計・出力、および全診断箇所。
- `engine/src/inkling2/sycl/ink_sycl_backend.cpp:129-138,167-175` — backend adapter から runner へのバッチ分割と呼出し。
- `engine/CMakeLists.txt:23-32,917-922`; `engine/src/inkling2/CMakeLists.txt:206-208` — SYCL backend と Inkling-2 component の構成条件。
