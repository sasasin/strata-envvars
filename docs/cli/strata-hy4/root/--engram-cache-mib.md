# `strata-hy4 --engram-cache-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP runner） |
| オプション | `--engram-cache-mib` |
| 別名 | なし |
| 値 | MiB を表す値。`atof` で変換した結果が 0 以上なら受理される |

## 役割

Engram shard を使う CUDA/HIP runner のホスト側行 LRU キャッシュ容量を MiB で指定します。値はプロセス環境変数 `HY4_ENGRAM_CACHE_MIB` に設定され、Engram の初期化時にキャッシュ行数へ換算されます。また、モデル読み込み時にホスト RAM の安全予算を自動計算する経路でも Engram cache 分の予約量として使われます。

## 使い方

```sh
# Engram shard を使うオフライン実行で、キャッシュ予算を 256 MiB に指定する
strata-hy4 --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --gen 128 --engram-cache-mib 256
```

## 値と既定値

- 値は文字列として読み、`atof` の結果が `0.0` 以上なら `HY4_ENGRAM_CACHE_MIB` に設定します。小数も受け取り、上限値の検証はありません。`atof` のため厳密な数値書式検証ではなく、数値に変換できない文字列は通常 0 として扱われます。負数は設定を行わず、すでに環境変数があればその値を残します（`engine/src/hy4flash/run/hy4_main.hip.cpp:467-470`）。
- 引数自体がない場合、共通の値取得処理が stdout に `ERR --engram-cache-mib needs a value` を出して終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`）。
- オプションを複数回指定した場合、0 以上と判定された最後の値が環境変数を上書きします。負数は上書きしません。POSIX では `setenv(..., 1)`、Windows では `_putenv_s` でプロセス環境に設定します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410`）。
- オプションを省略した場合は既存の `HY4_ENGRAM_CACHE_MIB` があれば利用します。環境変数もない場合、Engram の実キャッシュは既定 6,000,000 行を基準とし、RAM 上限が 20 GiB 以下なら 128 MiB 相当、40 GiB 以下なら 256 MiB 相当、72 GiB 以下なら 512 MiB 相当に縮小されます（`engine/src/hy4flash/run/hy4_engram.h:18-21`、`engine/src/hy4flash/run/hy4_graph.hip.h:1661-1673`）。

## 実行時の動作

Engram shard のパスが空でない場合、runner 初期化で `HY4_ENGRAM_CACHE_MIB` を読み、`MiB × 1,048,576 ÷ 116` を `size_t` に変換して LRU 行数を決めます。容量 0 は `EngramIO` の LRU を作らない指定です（`engine/src/hy4flash/run/hy4_graph.hip.h:1660-1676`、`engine/src/hy4flash/run/hy4_engram.cpp:492-504`、`engine/src/hy4flash/run/hy4_engram.h:89-92`）。指定した値が使われると stderr に `[engram] cache budget ...` の行数ログを出します。これは row data 100 byte に加えて管理領域を見込む換算です（`engine/src/hy4flash/run/hy4_engram.h:18`、`engine/src/hy4flash/run/hy4_graph.hip.h:1663-1666`）。

モデル読み込み時の RAM 自動予算では、`HY4_RAM_BUDGET_GB`、次に `STRATA_HY4_RAM_GB` が設定されていればその値を予算として使い、この分岐では Engram cache 量を加味しません。どちらもなければ `HY4_ENGRAM_CACHE_MIB / 1024` を予約量から差し引きます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:809-828`）。この計算は Engram shard を runner に渡す前に行われるため、Engram を無効にしている場合でもこの自動 RAM 予算の式には環境変数値が使われます。RAM 予算の自動計算がホスト側 expert 需要を超過と判定すると、CPU + SSD cold-expert streaming へ切り替わる場合があります（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-848`）。

## 適用条件と副作用

- 実キャッシュへの適用は、Engram shard を指定して runner の初期化まで進んだ場合です。`--no-engram` はオフライン実行では空の shard path を、serve では同様に空 path を渡します。`--load-only` はモデル読み込み後、Runner 初期化前に終了するため、実キャッシュは初期化されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:493,659-665,703-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:315-317`）。
- オプションは CUDA/HIP 用 `strata-hy4` の parser にあるものです。Metal runner は同名引数を「not used by the Metal runner」と stderr に出す別実装であり、SYCL runner は値を読み捨てます。指定文書の scope には含めません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603`、`engine/src/hy4flash/sycl/sy_main.cpp:142`）。
- 設定値自体はプロセス環境に書き込まれます。ファイルへの書き込みやネットワーク通信をこのオプションが直接行う処理は確認できません。オフライン実行で Engram shard の読込など初期化に失敗すると `init: <error>` を stderr に出し、終了コード 1 になります。serve では `ERR init: <error>` をプロトコル出力（stdout）へ出し、終了コード 1 で戻ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:703-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:73-81,315-317`）。

## 出力とエラー

- オプションの引数が欠けると stdout にエラーを出し、終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`）。
- 負数など `atof(value) >= 0.0` が偽になる値を渡しても、このオプション自身はエラーを出さず、環境変数を変更しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:467-470`）。
- Engram が有効で明示値または環境値が読まれたとき、キャッシュ予算と行数を stderr に表示します。Engram の初期化が失敗した場合、オフラインは stderr の `init:` エラー、serve は stdout の `ERR init:` プロトコル出力になります（`engine/src/hy4flash/run/hy4_graph.hip.h:1663-1666`、`engine/src/hy4flash/run/hy4_main.hip.cpp:703-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:73-81,315-317`）。

## 根拠

- parser、値変換、環境変数への設定: `engine/src/hy4flash/run/hy4_main.hip.cpp:467-470`。
- 値取得時の引数不足エラー: `engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`。
- 環境変数の設定方法: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410`。
- Engram LRU の行数換算、RAM 上限による fallback、キャッシュ初期化: `engine/src/hy4flash/run/hy4_graph.hip.h:1660-1676`。
- LRU 行数 0 の意味と実際の配列確保: `engine/src/hy4flash/run/hy4_engram.h:89-92`、`engine/src/hy4flash/run/hy4_engram.cpp:492-504`。
- ホスト RAM の自動予算と expert streaming 切替: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:809-848`。
- オフライン/serve での Engram 無効化と init エラー出力: `engine/src/hy4flash/run/hy4_main.hip.cpp:493,703-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:73-81,315-317`。

調査範囲は指定 commit に含まれる Strata 所有ソースです。CLI 実行や `--help` は行っていません。`atof` の文字列変換の細部は C runtime に依存するため、ソースから確認できる比較条件と変換関数までを記載しました。
