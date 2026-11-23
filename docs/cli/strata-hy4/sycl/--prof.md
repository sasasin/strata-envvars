# `strata-hy4-sycl --prof`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL 実装） |
| オプション | `--prof` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

通常の（`--serve` を付けない）SYCL 推論で、prefill と decode の処理時間を Engram、attention、MLP/MoE などの層単位に集計して `stderr` に出します。計測時には各層処理の前後で SYCL キューを待機させるため、処理区間を分けた時間を確認できますが、通常実行と同じ実行条件の性能値にはなりません。

## 使い方

```sh
# 入力 token ID を処理し、prefill の層別時間を stderr に出す
strata-hy4-sycl --model SQ32.strata --engram Engram-Q8.strata --tokens ids.txt --prof

# 生成も実行し、prefill と decode の層別時間を stderr に出す
strata-hy4-sycl --model SQ32.strata --engram Engram-Q8.strata --tokens ids.txt --gen 32 --prof
```

モデルと token 入力の指定方法は `sy_main.cpp` の usage 表示に示されています。`--prof` 自体には引数を付けません。

## 値と既定値

`--prof` は値を取らない真偽フラグです。未指定時は `false`、指定すると `true` になります。繰り返し指定しても同じ真偽値を設定するだけです。オプション直後に値を置く構文はありません。値の範囲検証はありません。

## 実行時の動作

parser は `--prof` を見つけると `prof` を有効にし、通常推論用 `Runner` の `r.prof` に渡します（`engine/src/hy4flash/sycl/sy_main.cpp:177,283-291`）。`Runner::forward_chunk` はグラフ実行の条件から `prof` 有効時を除外し、各層で `wait()` を挟んで Engram、attention、MLP/MoE の経過時間を累積します（`engine/src/hy4flash/sycl/sy_graph.h:1382-1423`）。したがって、計測対象のチャンクが最大8 tokenでグラフ経路を使える場合でも、`--prof` により eager 経路になります。

prefill 完了後に `[prof prefill]` 行を `stderr` へ出力します。通常の decode 経路では decode 完了後にも `[prof decode]` 行を出します。行には Engram、sliding-window attention、sparse attention、最初の層の MLP、残りの層の MoE、CPU experts の累積秒数が含まれます（`engine/src/hy4flash/sycl/sy_main.cpp:369-373,577-580`; `engine/src/hy4flash/sycl/sy_graph.h:1426-1432`）。投機的 `dfly2` decode の分岐は `prof_report("decode")` を呼ばず、そちらの decode 集計行は出しません（`engine/src/hy4flash/sycl/sy_main.cpp:379-409`）。

## 適用条件と副作用

- SYCL の通常推論経路に適用されます。`--serve` が指定されていても parser は `--prof` を受理しますが、serve 分岐が構築する `ServeOpts` には `prof` を設定せず、その後 `hy4s_serve_main` に渡します（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`）。この分岐では `--prof` は作用しません。
- 計測中は層ごとにキューを待機するため、実行順序・同期回数・実行時間に影響します。ソースは同期の実装を示しますが、その影響量は定めていません。
- `--prof2` は別の区間別タイムライン計測フラグです。両方を同時に指定できますが、いずれも小さいチャンクの graph 経路を無効にします（`engine/src/hy4flash/sycl/sy_main.cpp:177-178`; `engine/src/hy4flash/sycl/sy_graph.h:1387-1391`）。

## 出力とエラー

このフラグ固有の validation error はありません。`--prof` の後ろに値を置くと、その値は別引数として扱われ、未認識引数として `stderr` に `unknown arg <値>` を出して終了コード 2 になります（`engine/src/hy4flash/sycl/sy_main.cpp:190-197`）。

計測結果は標準エラー出力です。通常推論では prefill 集計行が出ます。通常の decode 経路では decode 集計行も出ますが、投機的 `dfly2` decode 分岐からはこのレポート関数が呼ばれません（`engine/src/hy4flash/sycl/sy_graph.h:1428-1432`; `engine/src/hy4flash/sycl/sy_main.cpp:369-373,379-409,577-580`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:99,177` — `prof` の初期値と `--prof` の引数解析。
- `engine/src/hy4flash/sycl/sy_main.cpp:283-291` — 通常推論の `Runner` への設定。
- `engine/src/hy4flash/sycl/sy_graph.h:1382-1423` — graph 経路の除外、層処理前後の待機と時間加算。
- `engine/src/hy4flash/sycl/sy_graph.h:1426-1432` — 集計項目および `stderr` へのレポート。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248` — serve 分岐と `ServeOpts` の組み立て。`prof` は渡されない。
- `engine/src/hy4flash/sycl/sy_main.cpp:369-373,577-580` — prefill/decode 後のレポート呼び出し。

この文書は指定 revision のソースを根拠としています。CLI バイナリの `--help` は実行していません。
