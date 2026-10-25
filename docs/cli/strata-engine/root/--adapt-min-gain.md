# `--adapt-min-gain`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（`src/program/generate.cpp` の generate parser） |
| オプション | `--adapt-min-gain` |
| 別名 | なし |
| 値 | 数値 `F`。`float` に変換されるが、範囲検証はない |

## 役割

適応型 VRAM expert tier が、VRAM 外の候補 expert を resident expert と入れ替えるために要求する routing 使用数の差を指定します。候補の decayed routing count が、追い出し候補の count にこの値を加えた値以上なら交換対象になります。既定値は `1.5` です（`src/program/generate.cpp:695-698,1072-1073`）。

## 使い方

```sh
strata generate --pack /path/to/pack --tokens "1,2,3" --serve --resident-cpu-experts --adapt-min-gain 3.0
```

この例は generate parser の構文例です。`--tokens` は非 serve 実行では必須ですが、`--serve` ではリクエストから token を受け取るため省略可能です。実際に適応が動くには tier が有効であることも必要です（`src/program/generate.cpp:808-812,2423-2442,3168-3177`）。

## 値と既定値

- 省略時は `1.5f` です（`src/program/generate.cpp:695-698`）。
- parser は `std::atof` で読み、`float` にキャストします。数値の範囲、有限性、変換成功を検証しません（`src/program/generate.cpp:2626-2629`）。したがって、不正な数値文字列は通常 `atof` の変換結果 `0` になります。負数や `nan` / `inf` も parser では拒否されません。
- 同じオプションを複数回指定した場合、引数走査中に `o.adapt_min_gain` が順に上書きされるため最後の値が残ります（`src/program/generate.cpp:2416-2421,2628`）。
- 値を省略すると `next()` が stderr に `<option> needs a value` を出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

serve の blocking tier と asynchronous tier の交換候補判定では、各層について VRAM 外の expert のうち decayed count が `2.0` 以上のものを候補にし、resident expert を count の小さい順に照合します。候補 count が resident count + `F` より小さければ、その層の以降の候補判定を打ち切ります。交換数はさらに `--adapt-swaps` で制限されます（`src/program/generate.cpp:10308-10328,10577-10592`）。

この値は `--adapt-every` の適応間隔や `--adapt-decay` が作る count と組み合わさります。tier が無効（`--adapt-every <= 0` または `--adapt-swaps <= 0`）なら適応処理自体が動きません。`--adapt-async 1` も `--serve` と resident RAM / resident experts / expert arena などの条件を満たさない場合は無効化され blocking tier に戻ります（`src/program/generate.cpp:8066-8088`）。

**ソース上の経路差があります。** 変数 `o.adapt_min_gain` を使うのは serve の blocking 判定と async 判定です（`src/program/generate.cpp:10322-10324,10586-10589`）。一方、非 serve の generate 経路は parser が値を受理するものの、交換判定に定数 `1.5f` を使っています（`src/program/generate.cpp:16310-16318`）。この経路では指定値を変えても閾値は変化しません。

## 適用条件と副作用

適応 tier が交換を選ぶと、expert を GPU cache と RAM 側の resident source / arena 間で入れ替え、residency table を更新します。非 serve 経路については、選んだ expert の GPU cache への refill、追い出した expert の prefetch、コピー完了までの pending 管理が実装されています（`src/program/generate.cpp:16325-16377`）。serve の blocking tier は `--serve` 側の adaptive refill 処理を使い、async tier は helper thread 等の非同期処理を使います（`src/program/generate.cpp:10302-10330,10463-10549`）。

このオプション自体はファイルを指定・生成せず、ネットワーク処理も定義しません。適応による配置変更で GPU と CPU が異なる expert を担当するため、出力が実行ごとに変わり得る旨が batching 文書に記載されています（`docs/BATCHING.md:371-382`）。

## 出力とエラー

未知の引数は stderr に `unknown argument: ...` と usage を出し、終了コード `2` になります（`src/program/generate.cpp:2787-2792`）。このオプションの数値自体には validation error がなく、構文上の不正値を拒否する経路は確認できません。

適応 refill が失敗した場合、実行経路に応じて stderr に `strata generate: an adaptive refill failed...` を出し、処理を失敗として返します（`src/program/generate.cpp:16323-16327,16347-16357`）。コピー成否や GPU 実行時の具体的な終了コードはこのオプション固有には定まっていません。

## 根拠

- parser と既定値・usage: `src/program/generate.cpp:695-698,1072-1073,2626-2629`
- 欠落値・未知引数の処理: `src/program/generate.cpp:2418-2420,2787-2792`
- serve blocking tier の閾値判定: `src/program/generate.cpp:10302-10328`
- serve async tier の閾値判定: `src/program/generate.cpp:10577-10592`
- 非 serve 経路での固定閾値: `src/program/generate.cpp:16310-16318`
- 非 serve 経路の refill・コピー・prefetch: `src/program/generate.cpp:16325-16377`
- 適応 tier と batching の動作説明: `docs/BATCHING.md:371-382`
