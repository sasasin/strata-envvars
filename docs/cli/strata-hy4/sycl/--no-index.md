# `--no-index`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（通常実行、または `--serve`） |
| オプション | `--no-index` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

HY4 SYCL Runner の sparse attention で使う IndexPool の更新・候補選択を無効にします。通常実行と engine line protocol のサーバーモードのどちらにも渡されます。IndexPool を使わない場合、sparse attention は候補リストを使う `MLA_LIST` ではなく `MLA_CAUSAL` で処理されます。SW-A/window attention のモードはこのフラグでは変更されません。

## 使い方

```sh
# 通常の token-file 推論で IndexPool を無効にする
strata-hy4-sycl --model SQ32.strata --tokens ids.txt --gen 32 --no-index

# engine line protocol サーバーで IndexPool を無効にする
strata-hy4-sycl --serve --native SQ32.strata --no-index
```

実際のファイル名や位置は利用環境に合わせてください。通常実行ではモデル指定が必要で、`--load-only` を付けない場合は token file も読み込まれます。

## 値と既定値

値を取りません。parser はフラグの出現時に `no_index = true` とし、既定値は `false` です。引数なしで複数回指定しても同じ真偽値を設定します。値の検証や数値範囲の検査はありません。直後に値らしい別引数を置くと、それはこのフラグの値ではなく別の引数として解析され、認識されない引数ならエラーになります。

## 実行時の動作

- 通常実行では `no_index` を `Runner::index_on` に変換します。サーバーモードでも `ServeOpts` に渡した後、同じ設定を Runner に反映します（`engine/src/hy4flash/sycl/sy_main.cpp:99,176,238-248,288-289`、`engine/src/hy4flash/sycl/sy_serve.h:28-40,262-265`）。
- SYCL の attention 処理では、sparse layer かつ `index_on` が真のときだけ `idx_update` を呼び、条件を満たす場合に `idx_select` を行います。このフラグを付けるとその処理を通らず、`use_list` は偽のままです。attention mode は sparse layer で `MLA_CAUSAL` になります。一方、SW-A layer は引き続き `MLA_WINDOW` です（`engine/src/hy4flash/sycl/sy_graph.h:992-1007,1014-1022`）。command graph 経路でも `use_list` を無効にして sparse attention を `MLA_CAUSAL` にします（同 `:1246-1258`）。
- IndexPool 関連の device buffer は Runner 初期化時に確保されます。このフラグが無効にするのは上記の更新・選択経路であり、これらの確保自体を止める条件は確認できません（`engine/src/hy4flash/sycl/sy_graph.h:556-576`）。したがって「index 関連メモリを一切確保しない」指定ではありません。
- `--index-topk` の既定値は 2048 で、通常は index list を使い始める位置の判定に使われますが、`--no-index` が有効な間は `index_on` が偽なのでこの選択経路に入りません。ただし Runner は `index_topk` を使って `keys` buffer のサイズを決めるため、値を変更した場合の確保サイズへの影響は残ります（`engine/src/hy4flash/sycl/sy_main.cpp:104,175,288-289`、`engine/src/hy4flash/sycl/sy_graph.h:575,1001,1250-1253`）。

## 適用条件と副作用

通常実行と `--serve` の両方で有効です。無効化の対象は sparse attention の IndexPool 経路であり、SW-A/window attention やモデルロード自体を無効にはしません。ソース上で数値範囲検証、警告、ファイル書き込みなど、このフラグ固有の処理は見つかりませんでした。IndexPool buffer は初期化時に確保されるため、無効化だけでそれらの割当てが省かれるとは限りません。性能や出力品質への定量的な影響は測定していません。

## 出力とエラー

`--no-index` 自体に専用の出力・エラー経路はありません。parser は値を要求しません。認識されない引数は stderr に `unknown arg <引数>` を出し、終了コード 2 で返ります（`engine/src/hy4flash/sycl/sy_main.cpp:108-115,190-196`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:99,104,174-176` — フラグの状態と既定値、parser 定義。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248,250-254,283-295` — server／通常実行の分岐、Runner 設定への伝達、および初期化失敗時の処理。
- `engine/src/hy4flash/sycl/sy_serve.h:28-40,262-269` — サーバー設定への保持と Runner への適用。
- `engine/src/hy4flash/sycl/sy_graph.h:556-576,992-1028,1246-1258` — IndexPool buffer 確保、更新・選択の条件、attention mode と command graph の設定。
- `docs/cli/README.md:1452-1483` — `strata-hy4-sycl` のコマンド階層と `--no-index` の索引リンク。これは文書配置の照合に使用し、挙動の根拠にはしていません。
