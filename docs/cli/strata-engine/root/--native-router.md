# `strata` の `--native-router`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。

## 概要

`--native-router` は、実験的な CUDA router 実装を有効にする値なしのフラグです。通常の engine parser では `--native-router` を指定すると有効になり、省略時は無効です。parser には無効化用の対になるフラグはありません。

```sh
strata --native-router --pack DIR --tokens "1,2,3"
```

`--pack` と `--tokens` は engine の基本呼び出し例です。実際には利用する実行モードに合わせて引数を指定してください。このオプションだけではモデルや GPU の指定は行いません。

## 適用条件と動作

通常の MoE routing では、router 重みから BF16 投影を行って expert logits を作り、全 expert 上の routing を実行します。`--native-router` が有効で、expert 数が 512、`k`（選択数）が 10 の場合に限り、融合 CUDA top-10 kernel に切り替わります。条件外では通常の `router_top10` が使われます。このフラグを指定しただけで、モデルの expert 数や top-k 設定は変更されません。

native kernel は logits を softmax して上位 10 expert を選び、同値なら expert ID の小さい方を先に選択します。選択した重みは選択集合内で再正規化されます。router の logits と出力 ID・重みは CUDA device buffer として渡されます。

複数 token の verify window は、この native router が有効な 512/10 条件ではまとめて処理する経路を避け、token ごとの `moe_route` に分岐します。したがって `--native-router` はその経路のバッチ化条件にも影響します。

## 相互作用と副作用

- `--native SHARD1` は native 経路一式を有効にする preset で、その一部として `native_router` も有効にします。`--native-router` 単独では他の `--native-*` フラグを有効にしません。`--native` の処理は PLE shard の要件など別の検証を持ちます。
- 有効状態は engine 起動時に kernel 側のプロセス共有フラグへ設定され、routing 呼び出し時に参照されます。session config fingerprint にも `native_router` の値が記録されます。
- このフラグ自体がファイルを書き換えたり、モデルをダウンロードしたりする処理はソース上で確認できません。推論時には routing kernel を切り替えるため、選択結果と出力計算経路に影響します。

## 検証と失敗

フラグは値を受け取らないため、`--native-router VALUE` のような値の範囲検証はありません。引数 parser はフラグを bool に設定するだけです。native kernel 呼び出しは stream、バッファのアラインメント・範囲・重なりを検査し、不正なら例外を送出します。CUDA kernel launch のエラーも例外になります。通常の routing 呼び出し側はその例外を `router: <理由>` のエラー文字列にし、routing を失敗として返します。条件外の model shape は native kernel の validation failure ではなく、通常 router へ分岐します。

## 根拠

- `src/program/generate.cpp:466,808-810,854,2498` — 既定値 `false`、基本呼び出し形式、help の説明、値なしフラグの parser 定義。
- `src/program/generate.cpp:3263-3267,3936-3939,9450-9458` — `--native` preset が router を有効化する処理、kernel への設定、session config fingerprint への記録。
- `src/core/layer.cpp:405-423,440-453` — router 投影後の 512 experts・top-10 条件分岐、例外の変換、native router 時に複数 token の batch 分岐を避ける条件。
- `src/kernels/cuda/native_router.cu:33,45-97,208-235` — 初期無効状態、CUDA top-10 の選択・同値処理・重み再正規化、buffer 検査と launch error の送出。
- `CMakeLists.txt:390-403,530-538` — CUDA kernel source としての組み込み、および CUDA build 時の compile option 設定。

調査範囲は記載した checkout のソースです。Release artifact の同一 revision での `--help` 実行や、CUDA 実機での動作確認は行っていません。
