# `--native-router`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--native-router` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

MoE のルーティングで、通常の top-k カーネルに代えて実験的な native router カーネルを使うスイッチです。CUDA 系では expert 数が 512、top-k が 10 のときに有効になり、SYCL 実装では expert 数 512 または 256、top-k が 10 のときに専用経路へ入ります。それ以外の形状では通常の router に進みます。

## 使い方

```sh
# トークン ID を指定して推論し、対応する MoE ルーティングで native router を有効にする
strata generate --pack pack/full --tokens "1,2,3" --native-router
```

## 値と既定値

- 値や別名はなく、指定すると `native_router = true` になります。省略時は `false` です（CUDA parser: `engine/src/program/generate.cpp:804,3924`、SYCL parser: `engine/sycl/src/program/generate.cpp:488,1963`）。
- 引数値の変換や値域 validation はありません。重複して指定しても同じ真偽値を再設定します。
- `--native <SHARD1>` の全 native preset でもこのフラグが有効になります（`engine/src/program/generate.cpp:5160-5164`、`engine/sycl/src/program/generate.cpp:2592-2596`）。

## 実行時の動作

CUDA 系と SYCL の engine parser は、それぞれこの設定を router カーネルの global enable 状態へ渡します（`engine/src/program/generate.cpp:6118-6121`、`engine/sycl/src/program/generate.cpp:3233-3236`）。MoE router は expert logits を計算した後、enable 状態と形状を確認します。CUDA 系は `n_expert == 512 && k == 10` の場合に native top-10 を呼び、それ以外は汎用 `router_top10` を使います（`engine/src/core/layer.cpp:417-423`）。SYCL は `n_expert == 512 || n_expert == 256` かつ `k == 10` の場合に native multi-expert 関数を呼び、その他は汎用関数を使います（`engine/sycl/src/core/layer.cpp:411-417`）。

CUDA native kernel は 512 logits 全体を softmax 正規化し、上位 10 expert を選び、選択した重みを再正規化します。同率時は小さい expert index を先に選びます（`engine/src/kernels/cuda/native_router.cu:56-98`）。kernel entry は非 null stream、4-byte alignment、重ならない入出力 span を検査し、launch error を例外にします（`engine/src/kernels/cuda/native_router.cu:219-226`）。

## 適用条件と副作用

- このスイッチだけではルーティング結果を変えません。対象の MoE 層が上記 backend ごとの expert 数と top-k 条件に一致した場合に限り、専用カーネルを選びます。形状が合わない場合は汎用経路へ戻ります。
- native kernel 呼び出しが例外を投げると router 処理は `false` を返し、エラー文字列に layer の router 名と例外内容を設定します。通常 router へフォールバックはしません（CUDA 系: `engine/src/core/layer.cpp:420-423`、SYCL: `engine/sycl/src/core/layer.cpp:414-417`）。
- router 設定はセッションのグラフ捕捉前に設定されます。kernel header は既存 graph が選択済み kernel を保持すると記しています（`engine/src/program/generate.cpp:6118-6121`、`engine/include/strata/kernels/native_router.hpp:5-8`）。
- ソース上、このフラグ自体によるファイル生成、ネットワークアクセス、追加の同期・メモリ確保は確認できません。CUDA kernel の実際の性能差は調査していません。

## 出力とエラー

parser はこのフラグについて専用の警告やエラーを出しません。値を伴わせても値として消費せず、別の引数として処理されます。認識されない引数は `unknown argument` を stderr に出し usage を表示して code 2 で終了します（`engine/src/program/generate.cpp:4268-4273`）。native router の検証または kernel launch が失敗した場合は例外内容が layer のエラー文字列に格納され、MoE route は失敗を返します（`engine/src/core/layer.cpp:420-423`）。この route failure を最終的に表示する箇所と終了コードは、今回確認した範囲では特定できていません。

## 根拠

- parser の既定値・登録・help 表記: `engine/src/program/generate.cpp:804,1256,3924`、`engine/sycl/src/program/generate.cpp:488,844,1963`。
- `--native` による一括有効化、kernel 有効状態の設定: `engine/src/program/generate.cpp:5160-5164,6118-6121`、`engine/sycl/src/program/generate.cpp:2592-2596,3233-3236`。
- backend ごとの形状条件と失敗伝播: `engine/src/core/layer.cpp:417-423`、`engine/sycl/src/core/layer.cpp:411-417`。
- CUDA top-10 の選択・重み計算と引数検査: `engine/src/kernels/cuda/native_router.cu:56-98,219-226`。
- parser と使用箇所は CUDA 系と SYCL 系を確認しました。安全な同一 revision の CLI 実行可能ファイルによる `--help` 確認、および GPU 実行は行っていません。
