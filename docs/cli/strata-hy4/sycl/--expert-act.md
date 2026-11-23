# `strata-hy4-sycl --expert-act`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（root） |
| オプション | `--expert-act` |
| 別名 | なし |
| 値 | 整数。usage は `0|1` と表示するが、parser は範囲検証をしない |

## 役割

エキスパート計算に使う activation の精度モードを切り替える。既定値の `1` は高精度モードを強制せず、GPU VRAM cache と peer GPU expert path では Q8 activation を選ぶ。`0` は高精度 activation を選び、CPU/RAM の expert pool にも反映される。CPU pool の `1` 時の初期値は CPU kernel と `STRATA_CPUEXP_ACT` によって決まる。`--cpu-hi` も高精度を強制する。

## 使い方

```sh
# 高精度モードを強制しない（既定値）。
strata-hy4-sycl --model SQ32.strata --engram Engram-Q8.strata --tokens ids.txt

# 高精度 activation に切り替えて入力トークンから生成する。
strata-hy4-sycl --model SQ32.strata --engram Engram-Q8.strata --tokens ids.txt --expert-act 0
```

## 値と既定値

- 省略時の値は `1`。
- `0` の場合、高精度 activation を選ぶ。`--cpu-hi` を併記した場合も高精度になる。
- `0` 以外は `1` と同じ分岐になり、高精度モードを強制しない。GPU VRAM/peer cache は Q8 activation を使う一方、CPU pool の activation 精度は初期化時の既定値や [`STRATA_CPUEXP_ACT`](../../../envvars/STRATA_CPUEXP_ACT.md) に従う。usage 表示は `0|1` だが、実装上は `0`/`1` に限定する validation がない。
- 値は C の `atoi` で整数化される。数値に変換できない文字列は `0` として扱われるため、高精度側になる。複数回指定時は引数走査で最後に代入された値が残る。
- 値を省略すると parser の `nxt()` が `ERR --expert-act needs a value` を stdout に出し、終了コード `2` で終了する。

## 実行時の動作

通常の推論経路では、値 `0` または `--cpu-hi` により高精度フラグを `setup_experts_unified` に渡す。同関数はそのフラグを反転して VRAM cache と peer expert cache の Q8 activation 設定に反映し、高精度が選ばれたときは CPU expert pool にも高精度 activation を設定する。`1` およびその他の非ゼロ値では GPU cache は Q8 activation を使うが、CPU pool にはこの引数から設定を上書きしないため、初期化時に決まる kernel 既定値と `STRATA_CPUEXP_ACT` が適用される。`--serve` 経路も `ServeOpts::hi_act` に同じ条件を渡し、サーバー側の expert pool 初期化で適用する。

パーサーは値を `atoi` で読み込み、別の範囲検証や警告を行わない。なお、通常推論では `Runner::expert_act` にも値を代入するが、確認した SYCL ソース内でこのメンバーの利用箇所は見つからなかった。実際の精度選択は上記の `hi_act || (expert_act == 0)` を通る経路で行われる。

## 適用条件と副作用

このオプションは `strata-hy4-sycl` の共通引数 parser にあり、通常推論と `--serve` の双方で読み取られる。`--cpu-hi` と併用した場合は OR 条件となるため、`--expert-act 1` を指定しても高精度設定が無効化されることはない。`0` は CPU/RAM および GPU/peer 上の expert activation 計算経路を高精度側に切り替える。`1` は GPU 側を Q8 にするが、CPU 側は [環境変数文書](../../../envvars/STRATA_CPUEXP_ACT.md) と CPU kernel の初期設定に委ねる。ファイルやネットワークへの追加副作用は、このオプション単独の処理には確認できなかった。

## 出力とエラー

`--expert-act` に値が続かない場合は stdout に不足値のメッセージを出し、終了コード `2` で終了する。値の形式・範囲を検証する専用エラーはない。その他の起動時エラーはモデルや expert pool の初期化処理から返るため、このオプション固有の失敗経路とは確認できなかった。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:104` — `expert_act` の既定値は `1`。
- `engine/src/hy4flash/sycl/sy_main.cpp:109-115` — 値不足時の stdout メッセージと終了コード `2`。
- `engine/src/hy4flash/sycl/sy_main.cpp:143` — `--cpu-hi` の設定。
- `engine/src/hy4flash/sycl/sy_main.cpp:160` — `--expert-act` の parser。`atoi` を使い、範囲検証をしない。
- `engine/src/hy4flash/sycl/sy_main.cpp:237-248` — serve 経路で `hi_act || (expert_act == 0)` を `ServeOpts` に渡す。
- `engine/src/hy4flash/sycl/sy_main.cpp:252-253` — usage が `--expert-act 0|1` と表示される。
- `engine/src/hy4flash/sycl/sy_main.cpp:292-304` — 通常推論で値を Runner に代入し、同じ高精度条件を expert setup に渡す。
- `engine/src/hy4flash/sycl/sy_graph.h:123-126,141-152,214-215` — expert setup の高精度フラグを GPU cache・peer cache・CPU pool に適用する。
- `engine/src/hy4flash/sycl/sy_vram_cache.h:903-914` — Q8 activation が有効なときの VRAM cache 計算分岐。
- `engine/src/hy4flash/sycl/sy_peer.h:609-610` — peer cache の Q8 / 非 Q8 計算分岐。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:3165-3169` — CPU expert pool の高精度 activation 状態を設定・参照する API 実装。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1857-1862` — CPU pool の kernel 別既定値と `STRATA_CPUEXP_ACT=hi|q8` による初期化時の上書き。
