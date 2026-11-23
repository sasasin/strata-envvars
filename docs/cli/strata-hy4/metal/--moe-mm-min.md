# `strata-hy4-metal --moe-mm-min`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Hy4-Flash Metal runner） |
| オプション | `--moe-mm-min` |
| 別名 | なし |
| 値 | 整数。MoE の MPP grouped GEMM を使い始める token 数のしきい値 |

## 役割

Metal runner が MoE の routed expert 計算に MPP grouped GEMM 経路を使い始める、チャンク内 token 数の下限を指定します。MPP カーネルが利用でき、現在のチャンクがしきい値以上である場合に適用されます。モデルロードや通常の dense GEMM のしきい値を指定するオプションではありません。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --gen 64 --moe-mm-min 64
```

モデルと入力 token を指定して生成する例です。値は整数として読み取られます。

## 値と既定値

- 省略時は `64` です。parser の初期値 `moe_mm_min_arg` が `Runner::moe_mm_min` に渡されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491`, `1546`, `1752`）。
- parser は `atoi` で整数化しますが、このオプション固有の範囲検査やエラー処理はありません（同 `1546`）。したがって、正の整数を指定してください。非数値文字列を含む値や負数をどう扱うかについて、CLI 独自の validation は確認できません。
- `--moe-mm-min` の値がチャンクの token 数 `T` 以上に達したことを条件に MPP MoE 経路へ分岐します（同 `1182`）。

## 実行時の動作

parser の値は `Runner::moe_mm_min` に設定されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1546`, `1752`）。MoE 処理では、`moe2` が有効で `T <= 8` のときは先に `moe2` 経路を選ぶため、このしきい値はその分岐を切り替えません。そうでなく、MPP が利用可能で `T >= moe_mm_min` なら MPP grouped GEMM の計画・実行へ進みます。それ以外は `pair_max` に応じた pair 経路または sorted 経路へ進みます（同 `1174-1182`, `1226-1239`）。

MPP 経路では `--no-moe-bucket` が無効で、`--moe-tm` が 0、`--moe-tn` が 64 の場合に bucketed MPP 計画を使います。それ以外は tile 設定に基づく MPP 計画になります。これらはしきい値そのものを変更せず、しきい値を超えた後の MPP 経路の選択に作用します（同 `1184-1185`, `1214-1224`）。

## 適用条件と副作用

- MPP の利用可否は `--no-mpp` などにより MPP のコンパイルを試みるか、実行時のカーネルコンパイルが成功したかで決まります。MPP が無効または利用不可なら `mpp_ok` が false となり、このしきい値による MPP 経路への切替は起きません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:530-555,1729`）。
- `--mpp-min` は `lin()` 内の dense GEMM 選択に使われる別のしきい値です。MoE 専用の本オプションとは別に設定できます（同 `332`, `487`, `1751-1752`）。
- MPP が利用可能な場合、Runner は `moe_h2` と `moe_y` の作業バッファ容量を `min(T, moe_mm_min)` に基づいて確保します（同 `601-603`）。負数を含む値は範囲検査されず、バッファ容量計算に影響するため指定しないでください。
- `forward_chunk` の non-barrier 実行可否にも `min(mpp_min, moe_mm_min)` が参照されます。本オプションは MoE 経路選択以外にこの実行制御にも影響します（同 `1291-1296`）。

## 出力とエラー

本オプションの値に対する専用の警告・エラー出力は確認できません。MPP カーネルをコンパイルできない場合は stderr に利用不可の理由を出して通常カーネルへフォールバックし、MoE の MPP 条件も成立しなくなります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:533-555`, `1182`）。未知の引数は stdout と stderr にエラーを出して終了コード 2 になりますが、本オプション自体は parser に登録されています（同 `1546`, `1604-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1546` — 既定値、値の整数変換、オプション登録。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1751-1752` — CLI 値を Runner に設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:530-558` — MPP カーネルのコンパイル試行と利用可否、失敗時のフォールバック。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:601-603` — MoE 作業バッファの容量決定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1174-1239` — `moe2`、MPP grouped GEMM、pair/sorted 経路の条件分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1291-1296` — `mpp_min` と本オプションが non-barrier 実行可否に与える条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1609` — 未知の引数の出力と終了コード。
