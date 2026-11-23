# `strata-hy4-sycl --ram-experts-gb`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL） |
| オプション | `--ram-experts-gb` |
| 別名 | なし |
| 値 | 数値文字列。`atof` で `double` に変換され、正の値は RAM expert 予算の GB として扱われる |

## 役割

モデルの expert を GPU VRAM、ホスト RAM、cold SSD の各 tier に配置する際、ホスト RAM 側の予算を指定します。モデルの Section 3 rank 順に、VRAM/peer GPU に割り当てられなかった expert を予算内で RAM に置き、残りを cold SSD 側にします。単発推論と `--serve` の両方で同じ配置処理に渡されます（`engine/src/hy4flash/sycl/sy_main.cpp:140-141,226-248,298-307`、`engine/src/hy4flash/sycl/sy_serve.h:280-285`、`engine/src/hy4flash/sycl/sy_graph.h:118-123,155-200`）。

## 使い方

```sh
# 単発実行で RAM expert の予算を 20 GB に指定
strata-hy4-sycl --model model.strata --tokens ids.txt --ram-experts-gb 20

# server モードでも同じ予算を指定
strata-hy4-sycl --serve --native model.strata --ram-experts-gb 20
```

## 値と既定値

値を 1 個取ります。parser は値を `atof` で変換し、既定値は `-1.0` です（`engine/src/hy4flash/sycl/sy_main.cpp:103,109-115,140-141`）。明示値が `> 0` の場合、`値 * 1e9` byte を RAM 予算として使います。したがってこの実装での `GB` は 10 億 byte 単位です（`engine/src/hy4flash/sycl/sy_graph.h:162-170`）。

値の範囲検査や変換エラー検査はありません。`atof` が 0 を返す文字列（例: 数値として解釈できない文字列）や `0`、負数は正の予算として扱われず、下記の環境変数または自動予算へ進みます。重複指定は引数ループで後から代入された値が残ります（`engine/src/hy4flash/sycl/sy_main.cpp:105-115,140-141`）。値を省略すると `nxt()` が stdout に `ERR --ram-experts-gb needs a value` を出し、終了コード 2 で終了します（同 `:109-115`）。

## 実行時の動作

正の CLI 値があればそれを優先します。CLI 値が正でない場合、`HY4S_RAM_BUDGET_GB` が設定されていればその値を `atof` で変換して `1e9` 倍します。この環境変数値にも正値チェックはありません。環境変数が未設定なら、システム RAM 予算から `host_overhead_bytes + 8.5 GB`（OS、SYCL runtime、KV、bounce ring、Engram 用としている量）を差し引き、負にならない残余を使います（`engine/src/hy4flash/sycl/sy_graph.h:162-170`）。このため `--ram-experts-gb 0` は RAM tier を 0 に固定する指定ではなく、環境変数または自動予算にフォールバックします。

配置は expert の rank 順に行い、各 expert の body サイズを 4096 byte 単位に切り上げて予算に加算します。VRAM cache にある expert と peer GPU にある expert は RAM 予算を消費しません。RAM 予算に収まらなくなった地点から後続 expert は cold SSD 側になります（`engine/src/hy4flash/sycl/sy_graph.h:173-200`）。その後 `CpuExperts` を初期化し、cold expert があれば cold tier を設定します（同 `:204-227`）。

単発実行では parse した値を `setup_experts_unified` に渡し（`engine/src/hy4flash/sycl/sy_main.cpp:298-307`）、server モードでも `ServeOpts` 経由で同じ helper に渡します（`engine/src/hy4flash/sycl/sy_main.cpp:226-248`、`engine/src/hy4flash/sycl/sy_serve.h:36-37,280-285`）。

## 適用条件と副作用

この文書の対象は SYCL 版 `strata-hy4-sycl` です。CUDA/HIP と Metal の同名オプションについては対象外です。RAM 予算を小さくすると RAM tier に載る expert が減り、残りは cold SSD tier に割り当てられます。cold expert がある場合、非 Windows ではモデルファイルの page cache を破棄する試行を行い、cold サイズが 12 GB 未満かつ `STRATA_CPUEXP_COLD_IO` が未設定なら同変数を `buffered` に設定してから cold tier を構成します（`engine/src/hy4flash/sycl/sy_graph.h:204-227`）。配置結果は標準エラーに `[experts] unified pool ... RAM ... cold SSD ...` として出力されます（同 `:229-234`）。

## 出力とエラー

parser の値不足は stdout にエラーを出して終了コード 2 になります（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。配置 helper が失敗すると単発実行は stderr に `experts: <理由>` を出し、終了コード 1 で終了します（同 `:304-307`）。server モードでは protocol 出力に `ERR experts: <理由>` を出して終了コード 1 です（`engine/src/hy4flash/sycl/sy_serve.h:283-285`）。成功時の tier 別 expert 数と RAM 使用量・cold SSD 量は stderr に出力されます（`engine/src/hy4flash/sycl/sy_graph.h:229-234`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:103,109-115,140-141` — 既定値、値の取得・変換、値不足時の失敗。
- `engine/src/hy4flash/sycl/sy_main.cpp:226-248,298-307` — server と単発実行から配置 helper への値の受け渡し、単発実行の失敗経路。
- `engine/src/hy4flash/sycl/sy_serve.h:36-37,280-285` — server option の保持と helper の呼び出し・失敗経路。
- `engine/src/hy4flash/sycl/sy_graph.h:118-123,155-200` — RAM 予算の優先順位・自動算出と VRAM/RAM/cold SSD への配置。
- `engine/src/hy4flash/sycl/sy_graph.h:204-234` — cold tier に関する処理、副作用、配置結果の出力。
