# `--no-hit-poke`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、トップレベル） |
| オプション | `--no-hit-poke` |
| 別名 | なし |
| 値 | なし。フラグを指定すると有効 |

## 役割

expert cache の GPU hit 計算を起動した直後に CUDA driver を一度呼び出す「poke」を行わない A/B 用フラグです。既定では poke が有効で、このフラグを付けると無効になります。hit 計算の起動や CPU 側の miss 計算を無効化するオプションではありません。([`src/program/generate.cpp:593-596`](../../../../../../Niko1221/Strata/src/program/generate.cpp))

## 使い方

モデルを指定して推論エンジンを起動する例です。`MODEL.gguf` は実際のモデルファイルに置き換えてください。

```sh
strata --model MODEL.gguf --expert-cache 1 --no-hit-poke
```

`--expert-cache 1` は hit 経路を有効にするための例です。`--no-hit-poke` 自体は単独でも parser に受理されますが、hit 経路が動作しない実行では効果がありません。エンジンの実際の配布形態・パスは環境によって異なります（[CLI 入口の記録](../../000_cli_tools.md)）。

## 値と既定値

値を取らない真偽フラグです。`Options` の `no_hit_poke` は初期値 `false` で、parser が `--no-hit-poke` を見つけると `true` にします。数値などの値検証はありません。([`src/program/generate.cpp:593-596`](../../../../../../Niko1221/Strata/src/program/generate.cpp)、[`src/program/generate.cpp:2748`](../../../../../../Niko1221/Strata/src/program/generate.cpp))

## 実行時の動作

hit 経路の初期化条件は、`o.expert_cache > 0` かつ `!o.no_pool` です。この経路では device buffer と完了 probe 用 CUDA event を準備し、`drive.d.hit_poke = !o.no_hit_poke` と設定します。したがって `--expert-cache` が正の値でなく CPU pool を止める `--no-pool` も指定されている場合、このフラグは hit 経路に反映されません。([`src/program/generate.cpp:6829-6839`](../../../../../../Niko1221/Strata/src/program/generate.cpp)、[`src/program/generate.cpp:6867-6876`](../../../../../../Niko1221/Strata/src/program/generate.cpp))

hit 経路では、GPU hit 対象の選定・必要な cache fill・量子化・kernel enqueue を行い、完了 event を stream に記録します。既定設定ではその直後に `cudaEventQuery` を呼び、GPU 作業の開始を促します。このオプションを指定すると、この一回の query だけを省略し、作業開始が次の driver 呼び出しまで遅れる可能性があります。([`src/core/expert_source.cpp:5219-5229`](../../../../../../Niko1221/Strata/src/core/expert_source.cpp)、[`src/core/expert_source.cpp:5271-5305`](../../../../../../Niko1221/Strata/src/core/expert_source.cpp))

CPU pool が miss 側の計算を終えた後、`Combine` 段階では完了状態の計測 query が引き続き実行されます。従って「driver query をすべて無効にする」設定ではありません。hit 結果は miss 結果へ加算され、その後の層処理へ渡されます。([`src/core/session.cpp:730-750`](../../../../../../Niko1221/Strata/src/core/session.cpp)、[`src/core/expert_source.cpp:5309-5319`](../../../../../../Niko1221/Strata/src/core/expert_source.cpp))

## 適用条件と副作用

- このフラグは GPU expert hit の重複実行・cache の選定規則を変えず、enqueue 後の driver 呼び出しタイミングだけを変えます。完了状態が CPU pool の復帰時点で観測されるかは実行環境に依存します。
- `--no-pool` を併用すると hit 経路の初期化条件から外れます。([`src/program/generate.cpp:6838-6839`](../../../../../../Niko1221/Strata/src/program/generate.cpp))
- `--expert-cache` が有効な実行では、終了時に `R4 overlap` として pool 復帰時に hit work が完了していた layer 数を出力します。集計されるのは `Combine` 時の event query 結果です。([`src/program/generate.cpp:16969-16974`](../../../../../../Niko1221/Strata/src/program/generate.cpp)、[`src/core/expert_source.cpp:5312-5317`](../../../../../../Niko1221/Strata/src/core/expert_source.cpp))
- 初期化時に hit 用 device buffer を確保できない場合は stderr に `the R4 hit path could not allocate its device buffers` を出して `1` を返します。probe event を作成できない場合も stderr にエラーを出して `1` を返します。これらは hit 経路の初期化失敗であり、フラグ固有の validation error ではありません。([`src/program/generate.cpp:6838-6850`](../../../../../../Niko1221/Strata/src/program/generate.cpp)、[`src/program/generate.cpp:6867-6870`](../../../../../../Niko1221/Strata/src/program/generate.cpp))

## 根拠

- parser の既定値とフラグ受理: `src/program/generate.cpp:593-596, 2748`
- help の説明: `src/program/generate.cpp:994-996`
- hit 経路の条件・設定: `src/program/generate.cpp:6829-6876`
- hit の enqueue、任意 poke、Combine 時の計測: `src/core/expert_source.cpp:5214-5320`
- CPU pool と GPU hit の呼び出し順: `src/core/session.cpp:730-750`
- overlap の集計出力: `src/program/generate.cpp:16969-16974`

調査は上記 commit の checkout 内ソースに限定しました。該当 revision のビルド済み CLI は実行しておらず、別ビルド・GPU・driver ごとの実測差は確認していません。
