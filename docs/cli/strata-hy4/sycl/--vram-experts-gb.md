# `--vram-experts-gb`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--vram-experts-gb` |
| 別名 | なし |
| 値 | 数値を1つ取る。実装は `double` に変換し、非負値を VRAM 予算として扱う。単位換算は 1 GiB = 1,073,741,824 bytes。 |

## 役割

Hy4-Flash の Section 4 expert のうち、rank 順で選ばれるものを VRAM キャッシュへ置くための予算を指定する。残りの expert は RAM、さらに RAM 予算を超えた分は cold SSD tier に振り分けられる。単一プロンプト実行と `--serve` の両方で同じ配置処理に渡される（`engine/src/hy4flash/sycl/sy_main.cpp:103,140,226-248,298-307`、`engine/src/hy4flash/sycl/sy_serve.h:280-285`、`engine/src/hy4flash/sycl/sy_graph.h:118-123,155-200`）。

## 使い方

```sh
# SYCL エンジンでモデルを起動し、expert 用 VRAM 予算を 8 GiB に指定
strata-hy4-sycl --native model.strata --vram-experts-gb 8

# engine line protocol の serve 起動でも同じ配置予算を指定
strata-hy4-sycl --serve --native model.strata --vram-experts-gb 8
```

`--native` は parser 上で `--model` と同じモデル引数です（`engine/src/hy4flash/sycl/sy_main.cpp:130`）。

## 値と既定値

値は `atof` で `double` に変換され、構文や数値範囲を検査する専用 validation はありません。数値に変換できない文字列は `atof` の変換結果（通常 0）として扱われます。オプションを複数回指定すると、引数走査中に同じ変数へ代入されるため最後の指定が残ります。値を省略した場合は `nxt()` が `ERR --vram-experts-gb needs a value` を stdout に出し、終了コード 2 で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:103,109-115,140`）。

初期値は `-1.0` です。負値は直接 VRAM 予算にせず、後述する環境変数または自動算出へ進みます。`0` は明示的なゼロ予算となり、主 GPU の expert cache は無効になります。正数は `値 × 1,073,741,824` bytes に変換されます（`engine/src/hy4flash/sycl/sy_graph.h:127-141`）。

## 実行時の動作

引数値が 0 以上なら `HY4S_VRAM_EXPERTS_GB` より優先して使います。引数が負値または未指定なら、環境変数が存在する場合はその値を `atof` で読み、正値だけを予算にします。環境変数が存在しない場合は主 GPU の global memory の 94% を上限候補にし、すでに割り当て済みの device memory と呼び出し側の予約分を差し引きます。残りが 256 MiB を超えなければ予算は 0 です（`engine/src/hy4flash/sycl/sy_graph.h:127-141`）。環境変数の説明は [`HY4S_VRAM_EXPERTS_GB`](../../../envvars/HY4S_VRAM_EXPERTS_GB.md) を参照してください。

算出予算は `SyVramExpertCache::init` に渡されます。最大 expert body サイズを 4 KiB 境界に丸めた slot が 41 個分に満たない予算、または slot サイズ 0 の場合、キャッシュを有効化せず正常に戻ります。それ以上でも workspace 分を引いた残額から格納 slot 数を決め、rank 順に expert body を device memory へ読み込みます。割り当て可能な device memory が要求数に届かない場合は、確保できた slab 分で続行します（`engine/src/hy4flash/sycl/sy_vram_cache.h:691-750,776-798`）。

`--gpus` / `--devices` で peer GPU が指定されている場合、正の CLI 引数値は各 peer にも同じ値の予算として個別に渡されます。そのため複数 GPU 全体の合計上限ではありません。CLI 引数が 0 または負値なら peer GPU は各デバイスの global memory の 90% から workspace と 256 MiB を差し引く自動予算を使います。この peer 側の分岐は環境変数ではなく CLI 引数を見ており、たとえば CLI 引数が負値で `HY4S_VRAM_EXPERTS_GB` が正値でも、主 GPU と peer GPU では異なる予算決定経路になります（`engine/src/hy4flash/sycl/sy_graph.h:144-152`、`engine/src/hy4flash/sycl/sy_peer.h:182-186,231-255`）。

キャッシュに載った expert は VRAM に置かれ、残りは rank 順に RAM 予算へ入り、RAM を超えた expert は cold SSD 側へ割り当てられます。起動後の配置数・容量は `[experts] unified pool` の stderr ログに表示されます。キャッシュが有効な場合は `[vram-cache]` に slot 数・slab 数・device bytes も出力されます（`engine/src/hy4flash/sycl/sy_graph.h:173-200,229-235`、`engine/src/hy4flash/sycl/sy_vram_cache.h:795-798`）。

## 適用条件と副作用

このオプションは `strata-hy4-sycl` の parser にある設定です。単一実行はモデルと runner の初期化後、expert pool の構築に使います。`--serve` 経路も trunk/KV/DFly2 を割り当てた後に同じ helper を呼びます。したがって自動予算は、実行モードごとの呼び出し時点で既に使用中の GPU memory を差し引きます（`engine/src/hy4flash/sycl/sy_main.cpp:298-307`、`engine/src/hy4flash/sycl/sy_serve.h:280-285`）。

主 GPU キャッシュを増やすほど、その分の expert を RAM / cold SSD へ配置せず device memory に保持します。値が小さく cache slot 条件を満たさない場合は VRAM expert cache を使わず、expert は後段の配置対象になります。GPU 数、モデルの expert body サイズ、残りの device memory により実際の slot 数は指定値と一致しないことがあります（`engine/src/hy4flash/sycl/sy_vram_cache.h:723-750`）。

## 出力とエラー

この値自体に対する範囲エラーや警告は実装されていません。expert cache / pool の構築に失敗した場合、通常実行では `experts: <詳細>` を stderr に出して終了コード 1、`--serve` では `ERR experts: <詳細>` を protocol 出力して終了コード 1 になります（`engine/src/hy4flash/sycl/sy_main.cpp:304-307`、`engine/src/hy4flash/sycl/sy_serve.h:283-285`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:103,109-115,140`: 既定値、引数の値取得・変換、値省略時の出力と終了。
- `engine/src/hy4flash/sycl/sy_main.cpp:226-248,298-307`: `--serve` への値引き渡し、単一実行で helper を呼ぶ箇所と失敗処理。
- `engine/src/hy4flash/sycl/sy_serve.h:280-285`: serve 側での expert pool 構築と失敗出力。
- `engine/src/hy4flash/sycl/sy_graph.h:127-152,155-200,229-235`: CLI・環境変数・自動値の優先順位、peer GPU への予算、RAM / cold SSD への振り分け、配置ログ。
- `engine/src/hy4flash/sycl/sy_vram_cache.h:691-798`: cache の閾値、slot / slab 確保、expert 読み込みと cache ログ。
- `engine/src/hy4flash/sycl/sy_peer.h:182-186,231-255`: peer GPU の自動予算と明示予算の適用。
