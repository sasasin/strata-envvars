# `--det`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP） |
| オプション | `--det` |
| 別名 | なし |
| 値 | 必須。`atoi` で整数変換し、0 は無効、0 以外は有効として扱う |

## 役割

オフライン実行の iHC mix で、決定論的な部分和・reduction 経路を選ぶ。既定で有効であり、`--det 0` を指定すると別の mix kernel 経路へ切り替わる。これは生成サンプリング全体を決定論的にする指定ではなく、Runner 内の iHC mix の実装選択である。

## 使い方

モデル・入力 token ファイルと GPU 実行環境が用意された状態で実行する。

```sh
# 既定の決定論的 iHC mix を明示する
strata-hy4 --model model.strata --tokens prompt.ids --gen 1 --det 1

# 決定論的 iHC mix を無効にする
strata-hy4 --model model.strata --tokens prompt.ids --gen 1 --det 0
```

## 値と既定値

- `--det` の値は省略できない。引数 parser は `atoi(value) != 0` を保存するため、数値として 0 の値は無効、0 以外の数値は有効になる。既定値は `true`。
- `atoi` による変換後の値を個別に検証していないため、数値に変換できない文字列も 0 として扱われる。複数回指定した場合は、後の指定が前の値を上書きする。
- オプション値が欠けると `ERR --det needs a value` を stdout に出して終了コード 2 で終了する。

## 実行時の動作

オフライン経路では `Runner` 初期化後に `r.det_mix = det_flag || draft == "dfly2"` と設定する。したがって通常は `--det 0` で無効になるが、`--draft dfly2` を同時指定すると `--det 0` でも有効に戻る。`--draft` の既定値は `auto` で、この式では `dfly2` と同一扱いにならない。

`det_mix` が有効な場合、iHC mix は `k_hc_mix_part_d`（バッチ幅が16以上なら `_batch` 版）と決定論的 finish/reduce kernel を使う。無効の場合は accumulator を確保・ゼロ初期化し、別の partial / finish kernel を使う。ソースコメントは有効経路を「float atomics を使わない決定論的 iHC mix」と説明している。

`--serve` 経路では `--det` の値は `ServeOpts` に渡されず、serve 用 Runner の `det_mix` へ代入されない。Runner メンバーの初期値は `true` であり、さらに speculative drafter が初期化できた場合も `true` に設定される。このため serve 中に `--det 0` でこの挙動を無効にはできない。

## 適用条件と副作用

- この option は `engine/src/hy4flash/run/hy4_main.hip.cpp` の `strata-hy4` parser に登録されている。索引上の同名 option はこの CUDA/HIP ルートコマンドの文書であり、SYCL 側の `--detcheck` / `--detnotap` とは別である。
- 選択された経路は iHC mix kernel と一時 GPU buffer の確保方法を変える。性能差や再現性の程度はこのソース調査では測定していない。
- `--det` 自体に数値範囲 validation はない。`atoi` の変換仕様を超える入力形式の詳細や overflow 時の結果は、この CLI ソースだけからは保証できない。

## 出力とエラー

値が欠けた場合の stdout と終了コードは上記のとおり。未知の引数は stderr に `unknown arg <引数>` を出し、終了コード 2 で返る。`--det` に不正な数値文字列を渡したときの専用エラー表示はなく、変換結果の 0 として処理される。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:372` — `det_flag` の既定値が `true`。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383` — 引数走査と、値欠落時に stdout へエラーを出し終了コード 2 とする処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:429` — `--det` の登録と `atoi(value) != 0` の変換。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505` — 未知引数の stderr 出力と終了コード 2。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-580` — serve 分岐で `ServeOpts` を作るが `det_flag` は渡さない。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:692-703` — オフライン Runner への `det_mix` 設定と初期化。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1959-1974` — `det_mix` の既定値、決定論的経路と代替経路の kernel 呼び出し。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1976-1987` — iHC pre-mix でも同じ flag によって kernel 経路を切り替える処理。
- `engine/src/hy4flash/run/hy4_serve.hip.h:43-67,307-317,320-336` — `ServeOpts` に該当 field がないこと、serve Runner の生成、および speculative drafter 有効時の `det_mix = true`。
- `engine/src/hy4flash/run/hy4_spec.hip.h:94-95` — speculative decoder が schedule-independent な iHC mix を明示的に有効化する処理。

調査は指定 commit の parser・呼び出し経路・kernel 分岐のソース確認に限定した。実行、ビルド、GPU 性能測定は行っていない。
