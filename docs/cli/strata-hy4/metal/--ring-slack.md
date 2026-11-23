# `--ring-slack`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--ring-slack` |
| 別名 | なし |
| 値 | 整数。追加する SWA KV リングスロット数 |

## 役割

`--serve` の会話再利用で、以前の会話 KV を共通 prefix まで巻き戻して再利用する際に残しておく SWA（sliding-window attention）リングの余白を指定します。リングの余白が大きいほど、末尾まで KV が書き込まれた後に、より長い speculative tail を含む状態から prefix を再利用できる範囲が広がります。その分リングバッファは大きくなります。コマンド例は、モデルファイルを指定してサーバーモードを起動する形です。

## 使い方

```sh
strata-hy4-metal --model ./model.strata --serve --session-reuse 1 --ring-slack 8192
```

## 値と既定値

- 引数は `atoi` で整数に変換されます。parser に形式・上限の検証はありません。数値変換後に 0 以上なら指定値を採用し、負数なら明示指定がなかった場合と同じ扱いになります。
- 省略時は `--session-reuse` が有効なら `8192`、無効なら `0` です。非負の明示値は `--session-reuse` の状態にかかわらずこの既定値を上書きします。
- 同じオプションを複数回指定した場合、引数ループで値を代入し直すため最後の指定が残ります。
- `0` は余白なしです。負数はエラーにはならず、上記の既定値へフォールバックします。

## 実行時の動作

`--ring-slack` は serve 用の `ServeOpts` に設定され、`hy4_serve_main` から `Runner::ring_slack` に渡ります。Runner は SWA リング長を `512 + Tc + ring_slack` 以上の 16 の倍数に切り上げます。したがって、この値は KV バッファ確保量にも影響します。

会話スロットの選択時には、実際の余白 `r.ring - 512`（リング長の 16 スロット丸めを含む）が prefix 再利用判定に使われます。共通 prefix の末尾より先に書き込まれた token 数も考慮し、`fwd + 64 - L > slack` ならその prefix からの再開をやめて位置 0 から処理します。複数スロットの場合は、再利用可能な共通 prefix が `--conversation-min-tokens` の床（prompt が短い場合は prompt 長の半分）以上あるスロットを選びます。

この挙動が働くのは `--serve --session-reuse 1` の会話再利用経路です。画像を含むリクエストも KV 再利用を抑止します。`--session-reuse` が無効の場合、serve は `no_reuse` としてスロット再利用を抑止しますが、明示した正の `--ring-slack` は Runner のリング確保量には反映されます。通常の単発実行ではこの CLI 値は Runner に設定されません。単発実行の `--ab` は `gen + 64` を別途設定する経路です。

## 適用条件と副作用

このオプションは Metal 版 `strata-hy4-metal` の parser にあり、serve の実行設定に渡されます。余白を増やすと各 SWA 層で使うリング KV の確保量が増えます。ソースではリング長を 16 スロット単位に切り上げ、各 SWA 層の KV セットサイズをリング長に比例させています。メモリ量の具体値はモデルの層構成などに依存します。

`--serve` 起動時の `INFO` プロトコル行には採用された `ring_slack` 値が出力されます。値固有のエラーや警告を出す分岐は確認できませんでした。引数を消費する箇所に値の検証がないため、境界値や極端に大きな値に対する安全な実用上限は、このソース調査からは確認できません。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1496` — serve / session reuse の初期値と、リング余白引数の未指定 sentinel `-1`。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1591-1594` — `--ring-slack` が値を `atoi` で読み取る parser 定義。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1649` — serve 分岐と、明示された非負値または `session_reuse` に応じた `8192` / `0` の既定値。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:24-37,219-232` — `ServeOpts` の値と Runner への転送。`engine/src/hy4flash/metal/hy4_metal_serve.h:302-304` は起動時 `INFO` 行への出力。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:379-389,614-616` — SWA リング長の計算と KV セット確保。`engine/src/hy4flash/metal/hy4_metal_main.cpp:379-389` は各 SWA 層のリング比例のサイズ計算。
- `engine/src/hy4flash/metal/hy4_metal_slots.h:8-17,35-58` — prefix の再開位置とリング余白による制約、複数スロット選択時の再利用下限。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:375-388` — 画像要求または session reuse 無効時に再利用を抑止する条件。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1708-1715,1734` — 単発 Runner の生成と `--ab` 時に別途 `gen + 64` を設定する処理。
