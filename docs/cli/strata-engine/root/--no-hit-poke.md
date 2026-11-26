# `strata` `--no-hit-poke`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（通常の generate / serve エンジン引数。Qwen3.6 専用 parser は別スコープ） |
| オプション | `--no-hit-poke` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

常駐 expert cache の GPU hit path で、hit 計算を enqueue した直後に行うイベント query を抑止する A/B 用フラグです。hit path 自体を無効にはしません。未指定時は `no_hit_poke` が `false` のため query が有効で、指定時にだけ抑止されます（`engine/src/program/generate.cpp:944-947,4210`、SYCL parser は `engine/sycl/src/program/generate.cpp:610-613,2174`）。

## 使い方

```sh
# 常駐 expert cache を使う実行で、hit path の早期イベント query を止める
strata MODEL --expert-cache 64 --no-hit-poke
```

`MODEL` は通常のモデル引数です。このフラグだけでは hit path は有効にならず、コード上は `--expert-cache` が正数で、かつ CPU pool を無効化していない場合に hit path のバッファを準備します（`engine/src/program/generate.cpp:903,10380-10424`）。

## 値と既定値

値は不要です。parser は引数文字列が `--no-hit-poke` と一致したとき `o.no_hit_poke = true` とし、値の変換・範囲検証は行いません（`engine/src/program/generate.cpp:4210`、`engine/sycl/src/program/generate.cpp:2174`）。既定値は `false` で、複数回指定しても同じ真偽値への代入です（`engine/src/program/generate.cpp:947`、`engine/sycl/src/program/generate.cpp:613`）。

## 実行時の動作

CUDA/HIP 側では、hit が1件以上ある layer で GPU hit 計算を enqueue し、完了イベントを記録した後、通常は `cudaEventQuery` を1回呼びます。`--no-hit-poke` があると `drive.d.hit_poke = false` になり、この早期 query だけが省かれます（`engine/src/program/generate.cpp:10418-10424`、`engine/src/core/expert_source.cpp:6030-6031,6066-6071`）。コメントでは、この query を CPU pool の処理中に GPU hit を開始させる A/B 操作として説明しています（同 `expert_source.cpp:6068-6070`）。

このフラグは後段の combine を省略しません。hit 結果を加算する前の完了確認 query と hit-ready / hit-late の計数は残ります（`engine/src/core/expert_source.cpp:6074-6084`）。SYCL 側でも同じ真偽値が設定され、hit enqueue 後の `dpct::sycl_event_query` を条件付きで呼びます（`engine/sycl/src/program/generate.cpp:5872-5878`、`engine/sycl/src/core/expert_source.cpp:2927-2934`）。SYCL の完了確認と combine は別途続きます（同 `expert_source.cpp:2937-2949`）。

## 適用条件と副作用

- 実際の差が生じるのは、expert cache が正数かつ CPU pool が有効で hit path が初期化され、layer に少なくとも1件の hit がある場合です。条件外では `hit_poke` の値が使われる query 経路に入りません（`engine/src/program/generate.cpp:10380-10424`、`engine/src/core/expert_source.cpp:6030-6031`。SYCL は `engine/sycl/src/program/generate.cpp:5822-5878`、`engine/sycl/src/core/expert_source.cpp:2875-2876`）。
- 同じ hit path の GPU buffer allocation や完了イベント生成の失敗は、このフラグで回避されません。CUDA/HIP と SYCL の初期化は allocation 失敗時にエラーを stderr に出し `return 1`、イベント生成失敗時も同様に `return 1` します（`engine/src/program/generate.cpp:10389-10421`、`engine/sycl/src/program/generate.cpp:5831-5875`）。
- ソース上、このオプションが変更するのは上記の早期イベント query の条件です。実行時間や性能への効果はこの調査では測定していません。

## 出力とエラー

このフラグ専用の validation message や警告はありません。hit path を初期化する経路で共用バッファの確保に失敗すると `strata generate: the R4 hit path could not allocate its device buffers`、イベント生成に失敗すると `strata generate: the hit path could not create its probe event` を stderr に出して `return 1` します（`engine/src/program/generate.cpp:10389-10421`、SYCL は `engine/sycl/src/program/generate.cpp:5831-5875`）。これらはフラグ固有の失敗ではありません。

## 根拠

- CLI 索引では `strata-engine` の root 引数 scope（`docs/cli/README.md:1036-1040`）に本オプションのリンクがあります（同 `README.md:1148`）。ツール索引では通常 parser を `engine/src/program/generate.cpp`、Qwen3.6 parser を別 scope としています（`docs/cli/000_cli_tools.md:10`）。
- CUDA/HIP parser、既定値、help 記載: `engine/src/program/generate.cpp:944-947,1411-1413,4210`。
- CUDA/HIP hit path の条件、フラグの転送、失敗経路: `engine/src/program/generate.cpp:10380-10427`。
- CUDA hit での enqueue、早期 query、後段の完了 query と加算: `engine/src/core/expert_source.cpp:6029-6084`。
- SYCL parser、既定値、help 記載と hit path: `engine/sycl/src/program/generate.cpp:610-613,968-970,2174,5822-5881`。
- SYCL hit での条件付き早期 query と後段の処理: `engine/sycl/src/core/expert_source.cpp:2875-2876,2927-2949`。
- 同一 revision の現行 parser と使用箇所を確認しました。CLI help はソース内の補助記述として照合し、別途バイナリの help は実行していません。
