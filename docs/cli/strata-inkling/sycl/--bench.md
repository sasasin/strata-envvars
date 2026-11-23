# `--bench`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--bench` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

SYCL 版 Inkling のモデルをロードして初期化した後、既定のプロンプト（token ID `1,2,3,4,5,6,7,8`）で greedy decode を実行し、prefill と decode のスループット、生成 token 数、D-Spark の受理率、VRAM 上の expert 数を標準出力に表示する。ベンチマーク実行にはモデルファイルと SYCL 実行環境が必要。

## 使い方

```sh
strata-inkling-sycl --model ./model.strata --bench
```

測定の生成長は `--gen`（既定値 32）、入力 token 列は `--prompt-tokens`（別名 `--prompt-ids`）で変更できる。通常は D-Spark を使い、`--no-dspark` を付けると通常 decode に切り替わる。

## 値と既定値

`--bench` は値を取らず、指定するとベンチマーク分岐を有効にする。未指定時はこの分岐を実行しない。複数回指定しても同じ真偽値を設定するだけで、追加の検証や別動作はない。parser は `--bench` 固有の validation を行わない。

## 実行時の動作

モデル指定が必要で、`InkSyModel::load` と `InkSyRunner::init` を通過した後に測定する。`run_greedy_decode` は slot 0 を reset し、prompt の prefill を計時してから最大 `n_gen` 個まで生成する。通常は speculative D-Spark decode を要求し、D-Spark の draft が得られない場合や context 上限に近い場合は通常 decode に戻る。`--no-dspark` があると通常 decode を使う。出力の `[BENCH]` 行には build、mode、prompt 長、prefill token/s、decode token 数・token/s、D-Spark 受理率、VRAM expert 数が含まれる。

`--gen` は測定の生成長を変え、`--prompt-tokens` / `--prompt-ids` は prompt を変える。CSV の空要素は読み飛ばされ、解析結果が空なら既定 prompt に戻る。`--parallel` は runner の slot 数初期化に使われるが、このベンチマーク関数は slot 0 のみを使う。`--par-sweep` は別の並列 sweep 分岐である。

## 適用条件と副作用

SYCL 版実行ファイルの parser にあるフラグで、モデルのロードと runner の初期化後にデバイス上で推論を行うため、GPU 計算資源とモデル用メモリを使用する。ベンチマーク分岐自体はファイル出力を行わず、測定値を stdout に出す。モデルのロードまたは runner 初期化に失敗すると、それぞれ `[ERROR]` / `runner init:` を stderr に出して終了コード 1 で終了する。

注意点として、測定関数 `run_greedy_decode` は失敗時に `false` を返すが、呼び出し側は戻り値を検査せず `[BENCH]` 行を出す。そのため forward 処理が失敗しても、この分岐自身が失敗終了を伝えるとは限らず、初期化値を使った測定値が表示される可能性がある。

## 出力とエラー

成功時の測定結果は stdout の `[BENCH] ...` 行に出力される。モデルの指定がない場合は stderr に Usage を出して終了コード 1。モデルロード失敗は `[ERROR] <理由>`、runner 初期化失敗は `[ERROR] runner init: <理由>` を stderr に出して終了コード 1。測定中の `forward_batch` 失敗は helper 内で `false` を返すが、その戻り値を呼び出し側が無視するため、失敗を示す明示的なエラー出力や終了コードはこの経路からは確認できない。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-145` — SYCL CLI の既定値と parser。`--bench` は値なしで `do_bench=true` にし、`--gen`、prompt、parallel、`--no-dspark` も同じ parser で扱う。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-204` — モデル必須条件、モデル load、runner 初期化と失敗時の stderr・終了コード。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:31-99` — slot 0 の reset、prefill/decode 計時、D-Spark の利用条件、forward 失敗時の戻り値。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:198-207` — runner slot 数初期化と prompt CSV の空時 fallback。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:257-265` — `--bench` の実行、`run_greedy_decode` 戻り値の未確認、`[BENCH]` 出力項目。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:267-285` — `--par-sweep` が `--bench` と別の処理であること。
