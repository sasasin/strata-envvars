# `strata-inkling --cpu`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP root） |
| オプション | `--cpu` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

実行 backend を CPU に固定する。GPU 対応ビルドでも CPU backend を選びたい場合に使う。対象は索引に記載された CUDA/HIP 版の `strata-inkling` であり、Metal 版と SYCL 版は別 parser である。

## 使い方

```sh
strata-inkling --native ./model.strata --cpu
strata-inkling --selfcheck --native ./model.strata --cpu
```

通常の生成ではモデル指定が必要。selfcheck では同じフラグで CPU backend を使って検査する。

## 値と既定値

値は不要。parser は `--cpu` を見つけると `cfg.force_cpu = true` にするだけで、数値や文字列の検証はない。指定しない場合 `force_cpu` は `ServeConfig` の既定値 `false` で、ビルド構成に応じた GPU backend の選択へ進む。フラグを繰り返しても真を再設定するだけで、動作は変わらない。値を続けて書く構文はなく、余分な引数は次の parser 反復で未知オプションとして扱われる。

## 実行時の動作

`--cpu` は `force_cpu` を設定し、その値が通常生成、serve、selfcheck、bench、KLD 評価、参照 logits 出力それぞれの backend factory 呼び出しに渡る。factory は `force_cpu` が真なら GPU backend 分岐を通らず `make_cpu_backend()` を返す。CPU backend は常にビルドされる設計である。したがって `--gpu` など GPU 用の指定が同じ起動引数にあっても、backend 選択は CPU に固定される。

このオプション自体はバックエンドを選択するだけで、出力先やモデルファイルを書き換える処理はない。CPU のスレッド数を設定するオプションではない。特に `--cpu-threads` は `BackendOpts` 上で CUDA Graph の mapped-memory CPU expert pool を有効化する設定とされており、`--cpu` によって選ばれる CPU backend とは用途が異なる。

## 適用条件と副作用

CUDA/HIP root parser のフラグであり、Metal と SYCL の Inkling CLI には同じ `--cpu` 分岐がない。ビルドに GPU backend が含まれていなくても factory は CPU backend を選べる。通常生成ではモデルを開いて CPU backend を初期化し、serve では選択した backend を使って serve loop に入る。計算を CPU backend に行わせるため、GPU を使う実行経路からは切り替わるが、性能差や対応モデルの範囲はこのフラグのコードだけからは断定できない。

`--cpu` による専用の警告や標準出力はない。モデル引数がない通常生成は `--native ... is required` を stderr に出して終了コード 2。モデルの open または backend 初期化に失敗すると stderr（serve 時はプロトコルエラー）へ失敗内容を出し、終了コード 1 となる。selfcheck もモデル open、backend init、selfcheck の各失敗で stderr に FAIL を出して 1、成功時は選択した backend 名を表示する。

## 根拠

- `engine/src/ink_serve.h:436` — `ServeConfig::force_cpu` の既定値 `false`。
- `engine/src/ink_main.cpp:379-384,476-477` — 引数走査と `--cpu` の値なし parser 分岐。
- `engine/src/ink_main.cpp:101-127,130-145,254-280,324-332,540-572,575-579` — selfcheck、bench、KLD 評価、参照 logits 出力、serve、通常生成の backend 選択箇所。
- `engine/src/ink_backend.h:131-167` — CPU backend は常に構築対象であり、`force_cpu` が真なら CPU factory を返す分岐。
- `engine/src/ink_backend.h:26-28` — `--cpu-threads` 相当の `cpu_threads` と通常の `threads` の backend 設定上の説明。
- `engine/src/ink_cpu_backend.cpp:1409-1411` — CPU backend factory。
- `engine/src/ink_main.cpp:488-502,551-568` — help の利用例、未知引数の終了コード、およびモデル必須・open/init エラー経路。
- `engine/src/ink_main.cpp:546-549,564-568` — 選択された backend が検査・評価・生成経路へ渡される箇所。
- `docs/cli/000_cli_tools.md:12` と `docs/cli/README.md:1509-1517` — ツール ID、CUDA/HIP parser の所在、および `root/--cpu.md` への索引リンク。索引リンクと実 parser のオプション名は一致する。
