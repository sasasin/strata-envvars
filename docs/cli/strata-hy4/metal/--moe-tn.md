# `--moe-tn`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--moe-tn` |
| 別名 | なし |
| 値 | 整数。MPP MoE grouped GEMM の N tile 幅として使用 |

## 役割

Metal 版 HY4 の MoE prefill を MPP grouped GEMM で処理するとき、N 方向の tile 幅（TN）を指定する。既定値は `64`。値を変えると汎用タイル経路で使うカーネル名と MoE の plan 設定が変わる。MPP が利用できない、またはその token 数で MPP MoE 経路に入らない場合、この値は実行経路に反映されない。

## 使い方

```sh
# Metal 版でモデルを読み込み、MoE の TN を 32 に指定する
strata-hy4-metal --model /path/to/model.gguf --moe-tn 32
```

## 値と既定値

- 値は `atoi` で整数に変換される。省略時は `64`。
- parser に範囲検証や値の補正はない。複数回指定した場合は引数走査で後に現れた値が残る。
- MPP MoE のカーネル定義には TN=`32` と `64` の組み合わせがある。ソースにはその他の TN の組み合わせは登録されていない。従って `32` または `64` 以外を安全な値として扱える根拠は確認できない。

## 実行時の動作

parser は値を `moe_tn_arg` に格納し、Runner に渡す。MPP が有効で、token 数 `T` が `moe_mm_min` 以上の場合に MoE MPP 経路が候補になる。既定の `moe_mm_min` は 64 で、`T <= 8` の MoE2 経路はこの分岐より先に選ばれる。MPP コンパイルが失敗したときは MPP 無しで初期化され、MoE は fallback 経路へ進むため `--moe-tn` は適用されない。

MoE MPP 経路では、`--no-moe-bucket` がなく、`--moe-tm` が省略時のまま（0）、かつ TN が 64 の場合に bucket 方式を使う。この条件を外れると汎用方式になり、既定 TM（`T <= 2560` なら 32、それより大きければ 64）または正の `--moe-tm` 値と TN からカーネル名を組み立てて dispatch する。Metal ソースが登録する汎用 MoE kernel は TN 32/64 と TM 16/32/64 の限定された組み合わせである。したがって TN=32 は bucket 条件を外して汎用方式へ切り替える。既定設定では `T <= 8` は先行する MoE2 経路を使うが、`--no-moe2` 等でその経路を無効にした場合は異なる。MPP と `T >= moe_mm_min` の条件を満たさない通常経路では TN は参照されない。

## 適用条件と副作用

- MPP MoE が実際に選ばれる条件は、MPP kernel の初期化成功、`T >= moe_mm_min`、および先行する MoE2 経路が選ばれないこと。既定では `T <= 8` は MoE2 が処理する。`--no-mpp`、`--moe-mm-min`、`--no-moe2` など関連指定がこの適用可否に関わる。
- `--moe-tn 64` は、既定の bucket 設定（TM 自動、bucket 有効）なら bucket 経路の選択条件を満たす。TN を変えるか、`--moe-tm` または `--no-moe-bucket` を指定すると汎用経路になる。
- TN は `1536 / TN` の整数除算にも使われるため、0 は除算の問題を起こす。ゼロやテンプレート未登録の値に対する専用 validation はなく、正しい kernel が見つからない場合などの具体的な Metal runtime の失敗表示・終了コードはこの範囲のソースから特定できない。未登録値を指定しないこと。
- MPP kernel のコンパイル失敗時、stderr に MPP 不使用の診断が出て通常 kernel へ fallback する。これはオプション値自体の警告ではない。

## 出力とエラー

`--moe-tn` 固有の成功メッセージや validation error は実装されていない。MPP compile fallback の stderr 診断は `hy4_metal_main.cpp:543-555` にある。汎用経路では組み立てた kernel 名を `cx.pipeline` 経由で取得して dispatch に登録するが、未登録の名前に対する下位 Metal API のエラー文や終了状態は Strata 側の該当箇所から確認できない。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491-1492,1537-1539` — 既定値、`atoi` による parser、隣接する `--moe-tm` / `--no-moe-bucket` の parser。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1738-1745` — TN と関連値を Runner に設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:522-555` — MPP compile 試行と fallback。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1167-1184,1213-1238` — 小 batch MoE2、MPP・bucket 条件、TN を含む汎用経路選択、および非 MPP fallback。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:425-439` — kernel pipeline の取得と dispatch 登録。
- `engine/src/hy4flash/metal/hy4_mppmoe.metal:445-451` — MPP MoE の明示的な template kernel 登録（TN 32/64、TM 16/32/64）。
